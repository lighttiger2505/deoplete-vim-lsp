"""Optional Vim cold-start regression; see tests/README.md for the command.

LAB also needs nvim-yarp and vim-hug-neovim-rpc. Vim needs +python3 and local
socket access for its RPC adapter. The terminal uses Python's standard PTY API.
"""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

try:
    import pty
except ImportError:
    pty = None

from test_completion_integration import LAB, ROOT, edit, vim_string as q

VIM_BIN = os.environ.get('VIM_BIN', 'vim')


@unittest.skipUnless(pty and shutil.which(VIM_BIN) and all((LAB / name).is_dir() for name in
                     ['vim-lsp', 'deoplete.nvim', 'nvim-yarp', 'vim-hug-neovim-rpc']),
                     'Vim acceptance needs LAB with vim-lsp, Deoplete and its Vim RPC adapters')
class VimCompletionIntegrationTests(unittest.TestCase):
    def test_cold_start_and_accepted_json_prefix(self):
        # Nothing is seeded: the source must initialize via real Vim RPC.
        temp = tempfile.TemporaryDirectory(prefix='deoplete-vim-accept-')
        self.addCleanup(temp.cleanup)
        items = [{'label': 'matchDepTypes', 'textEdit': edit(2, 3, '"matchDepTypes"')}]
        lines, keys, typed = ['  '], 'A"', '  "'
        expected, growth, action = ['  "matchDepTypes"'], 'mat', 'insert'
        directory = Path(temp.name)
        (directory / 'scenario.json').write_text(json.dumps({'items': items}))
        (directory / 'test.json').write_text('\n'.join(lines) + '\n')
        state_path = directory / 'state.json'
        command = [sys.executable, str(ROOT / 'tests/fixtures/completion_server.py'),
                   str(directory / 'scenario.json'), str(directory / 'requests.jsonl')]
        paths = [LAB / 'deoplete.nvim', LAB / 'vim-lsp', LAB / 'nvim-yarp',
                 LAB / 'vim-hug-neovim-rpc', ROOT]
        init = '\n'.join([
            'set nocompatible noswapfile encoding=utf-8',
            "let &runtimepath = $VIMRUNTIME . " + q(',' + ','.join(map(str, paths))),
            'let g:python3_host_prog = ' + q(sys.executable),
            "call deoplete#custom#option('sources', {'_': ['lsp']})",
            "call deoplete#custom#option('min_pattern_length', 1)",
            "call deoplete#custom#option('auto_complete_delay', 0)",
            'let g:deoplete#enable_at_startup = 1',
            'let g:lsp_completion_documentation_enabled = 0',
            'let g:lsp_completion_action = ' + q(action),
            'runtime plugin/lsp.vim',
            "call lsp#register_server({'name': 'test', 'cmd': {s -> " + json.dumps(command) +
                "}, 'allowlist': ['json']})",
            'let g:test_accepted = 0',
            'autocmd User lsp_complete_done let g:test_accepted += 1',
            'function! Snapshot(timer) abort',
            "let state = {'lines': getline(1, '$'), 'mode': mode(1), 'popup': complete_info(), "
            "'accepted': g:test_accepted, 'messages': execute('messages'), "
            "'context': get(g:, 'deoplete#_context', {}), "
            "'running': lsp#get_server_status('test'), 'ready': get(g:, 'deoplete#_initialized', 0)}",
            "call writefile([json_encode(state)], " + q(state_path) + ')',
            'endfunction',
            'autocmd VimEnter * call timer_start(20, function("Snapshot"), {"repeat": -1})',
            'filetype plugin on',
        ]) + '\n'
        (directory / 'init.vim').write_text(init)
        master, slave = pty.openpty()
        env = dict(os.environ, TERM='xterm', HOME=str(directory))
        for kind in ['CONFIG', 'DATA', 'STATE', 'CACHE']:
            env[f'XDG_{kind}_HOME'] = str(directory / kind.lower())
        proc = subprocess.Popen([VIM_BIN, '-Nu', str(directory / 'init.vim'),
                                 '-i', 'NONE', '-n', str(directory / 'test.json')],
                                stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        state = {}

        def wait(predicate):
            nonlocal state
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.02)[0]:
                    os.read(master, 65536)
                try:
                    state = json.loads(state_path.read_text())
                except (OSError, ValueError):
                    continue
                if predicate(state):
                    return state
            self.fail(repr(state))
        try:
            wait(lambda s: s['running'] == 'running' and s['ready'])
            os.write(master, keys.encode())
            wait(lambda s: s['context'].get('input') == typed and s['popup']['pum_visible'])
            for character in growth:
                typed += character
                os.write(master, character.encode())
                wait(lambda s: s['context'].get('input') == typed and s['popup']['pum_visible'])
            old = state['accepted']
            os.write(master, b'\x0e\x19')
            wait(lambda s: s['accepted'] > old)
            self.assertEqual(state['lines'], expected)
            self.assertTrue(state['mode'].startswith('i'), state)
        finally:
            os.write(master, b'\x1b:qa!\r')
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            os.close(master)
