"""LAB=<deps> NVIM=<nvim> python -m unittest discover -s tests -v.

LAB must contain vim-lsp and deoplete.nvim. Requires pynvim in this Python.
Uses an isolated Neovim, real Deoplete worker and vim-lsp, and a stdio LSP peer.
"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest

import pynvim


ROOT = Path(__file__).resolve().parents[1]
LAB = Path(os.environ.get('LAB', '/nonexistent'))
NVIM = os.environ.get('NVIM', 'nvim')


def vim_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def edit(start, end, text, line=0):
    return {'range': {'start': {'line': line, 'character': start},
                      'end': {'line': line, 'character': end}}, 'newText': text}


@unittest.skipUnless((LAB / 'vim-lsp').is_dir() and
                     (LAB / 'deoplete.nvim').is_dir() and shutil.which(NVIM),
                     'set LAB (vim-lsp and deoplete.nvim) and NVIM to run acceptance tests')
class CompletionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='deoplete-accept-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.log = self.directory / 'requests.jsonl'
        self.nvim = None
        self.addCleanup(self.close_editor)

    def start(self, items, lines, resolved=None, action='insert'):
        self.close_editor()
        self.log.unlink(missing_ok=True)
        scenario = self.directory / 'scenario.json'
        scenario.write_text(json.dumps({'items': items, 'resolved': resolved or {}}))
        init = self.directory / 'init.vim'
        command = [sys.executable, str(ROOT / 'tests/fixtures/completion_server.py'),
                   str(scenario), str(self.log)]
        init.write_text('\n'.join([
            'set nocompatible noswapfile encoding=utf-8',
            'let &runtimepath = $VIMRUNTIME . ' + vim_string(
                ',' + str(LAB / 'deoplete.nvim') + ',' + str(LAB / 'vim-lsp') + ',' + str(ROOT)),
            'let g:python3_host_prog = ' + vim_string(sys.executable),
            'let g:loaded_python_provider = 0',
            'let g:loaded_ruby_provider = 0',
            'let g:loaded_perl_provider = 0',
            'let g:loaded_node_provider = 0',
            'call remote#host#RegisterPlugin("python3", ' +
                vim_string(LAB / 'deoplete.nvim/rplugin/python3/deoplete') +
                ', [{"sync": v:false, "name": "_deoplete_init", "type": "function", "opts": {}}])',
            "call deoplete#custom#option('sources', {'_': ['lsp']})",
            "call deoplete#custom#option('min_pattern_length', 1)",
            "call deoplete#custom#option('auto_complete_delay', 0)",
            'let g:deoplete#enable_at_startup = 1',
            'let g:lsp_completion_documentation_enabled = 0',
            'let g:lsp_completion_action = ' + vim_string(action),
            'runtime plugin/lsp.vim',
            "call lsp#register_server({'name': 'test', 'cmd': {s -> " +
                json.dumps(command) + "}, 'allowlist': ['json']})",
            'let g:test_accepted = 0',
            'autocmd User lsp_complete_done let g:test_accepted += 1',
            'filetype plugin on',
        ]) + '\n')
        env = dict(os.environ, HOME=str(self.directory))
        for kind in ['CONFIG', 'DATA', 'STATE', 'CACHE']:
            env[f'XDG_{kind}_HOME'] = str(self.directory / kind.lower())
        self.nvim = pynvim.attach('child', argv=['env', *[f'{key}={env[key]}' for key in
            ['HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME']],
            NVIM, '--embed', '--headless', '-u', str(init), '-i', 'NONE', '-n'])
        self.nvim.command('edit ' + str(self.directory / 'test.json'))
        self.nvim.current.buffer[:] = lines
        self.wait(lambda: self.nvim.call('lsp#get_server_status', 'test') == 'running', 'server startup')
        self.wait(lambda: self.nvim.vars.get('deoplete#_initialized', False), 'Deoplete startup')

    def close_editor(self):
        if self.nvim is None:
            return
        try:
            self.nvim.command('qa!')
        except (EOFError, OSError):
            pass
        self.nvim.close()
        self.nvim = None

    def wait(self, predicate, description):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.02)
        self.fail(f'{description}; buffer={list(self.nvim.current.buffer)!r}; '
                  f'popup={self.nvim.call("complete_info")!r}; '
                  f'messages={self.nvim.command_output("messages")}')

    def type(self, keys, expected_input):
        self.nvim.input(keys)
        self.wait(lambda: self.nvim.call('deoplete#util#get_input', 'TextChangedI') == expected_input,
                  'typed input')
        # An old popup can remain visible while Deoplete processes TextChangedP.
        # Wait for the worker result before inspecting or accepting that popup.
        self.wait(lambda: self.nvim.vars.get('deoplete#_context', {}).get('input') == expected_input,
                  'Deoplete result for ' + repr(expected_input))

    def popup(self, label):
        return self.wait(lambda: [item for item in self.nvim.call('complete_info')['items']
                                 if item.get('abbr', '').rstrip('~') == label] if
                         self.nvim.call('pumvisible') else [], 'popup for ' + label)[0]

    def requests(self, method):
        return [message for message in map(json.loads, self.log.read_text().splitlines())
                if message.get('method') == method]

    def accept(self, item, expected):
        candidate = self.popup(item['label'])
        managed = self.nvim.call('lsp#omni#get_managed_user_data_from_completed_item', candidate)
        self.assertEqual(managed['completion_item'], item)
        info = self.nvim.call('complete_info')
        index = next(i for i, value in enumerate(info['items']) if value == candidate)
        self.assertEqual(info['selected'], -1, 'test expects no preselected candidate')
        previous = self.nvim.vars['test_accepted']
        self.nvim.input('\x0e' * (index + 1) + '\x19')  # Ctrl-N, Ctrl-Y; remain in Insert mode.
        self.wait(lambda: self.nvim.vars['test_accepted'] > previous, 'vim-lsp acceptance handler')
        self.assertEqual(list(self.nvim.current.buffer), expected)
        self.assertEqual(self.nvim.eval('mode(1)')[0], 'i')
        self.assertIn(item, [request['params'] for request in self.requests('completionItem/resolve')])

    def test_json_quote_and_prefix_growth(self):
        for prefix in ['', 'm', 'ma', 'mat']:
            with self.subTest(prefix=prefix):
                item = {'label': 'matchDepTypes', 'textEdit': edit(2, 3, '"matchDepTypes"')}
                self.start([item], ['  '])
                self.type('A"', '  "')
                self.popup(item['label'])
                initial_requests = len(self.requests('textDocument/completion'))
                for length, character in enumerate(prefix, 1):
                    self.type(character, '  "' + prefix[:length])
                    self.popup(item['label'])
                self.assertEqual(len(self.requests('textDocument/completion')), initial_requests)
                self.accept(item, ['  "matchDepTypes"'])

    def test_punctuation_replacement(self):
        item = {'label': 'rgb', 'textEdit': edit(0, 2, 'rgb')}
        self.start([item], ['#'])
        self.type('Ar', '#r')
        self.accept(item, ['rgb'])

    def test_snippet_text_edit(self):
        item = {'label': 'rgb', 'insertTextFormat': 2,
                'textEdit': edit(0, 2, 'rgb(${1:red}, ${2:green})$0')}
        self.start([item], ['#'])
        self.type('Ar', '#r')
        self.accept(item, ['rgb(red, green)'])
        self.assertEqual(self.nvim.current.window.cursor, (1, 4))

    def test_insert_replace_edit(self):
        for action, expected in [('insert', 'printSuffix'), ('replace', 'print')]:
            with self.subTest(action=action):
                item = {'label': 'print', 'textEdit': {
                    'insert': edit(0, 3, '')['range'],
                    'replace': edit(0, 9, '')['range'], 'newText': 'print'}}
                self.start([item], ['prSuffix'], action=action)
                self.nvim.current.window.cursor = (1, 2)
                self.type('ii', 'pri')
                self.accept(item, [expected])

    def test_multibyte_before_completion(self):
        item = {'label': 'matchDepTypes', 'textEdit': edit(2, 4, '"matchDepTypes"')}
        self.start([item], ['é "'])
        self.type('Am', 'é "m')
        self.accept(item, ['é "matchDepTypes"'])

    def test_metadata_and_resolved_additional_edit(self):
        item = {'label': 'print', 'kind': 3, 'sortText': '001', 'filterText': 'print',
                'data': {'opaque': ['keep', 42]}, 'textEdit': edit(0, 3, 'print', line=1)}
        extra = edit(0, 0, 'import printer\n')
        self.start([item], ['', 'pr'], resolved={'additionalTextEdits': [extra]})
        self.nvim.current.window.cursor = (2, 1)
        self.type('Ai', 'pri')
        self.accept(item, ['import printer', '', 'print'])

    def test_cached_json_snippet_and_additional_edit(self):
        item = {'label': 'matchDepTypes', 'insertTextFormat': 2,
                'textEdit': edit(2, 3, '"matchDepTypes": [${1:"dependencies"}]$0', line=1),
                'additionalTextEdits': [edit(0, 0, '// schema\n')]}
        self.start([item], ['', '  '])
        self.nvim.current.window.cursor = (2, 1)
        self.type('A"', '  "')
        self.popup(item['label'])
        initial_requests = len(self.requests('textDocument/completion'))
        for length, character in enumerate('mat', 1):
            self.type(character, '  "' + 'mat'[:length])
            self.popup(item['label'])
        self.assertEqual(len(self.requests('textDocument/completion')), initial_requests)
        self.accept(item, ['// schema', '', '  "matchDepTypes": ["dependencies"]'])

    def test_mixed_replacement_starts(self):
        items = [{'label': 'red', 'textEdit': edit(0, 2, 'red')},
                 {'label': 'rgb', 'textEdit': edit(1, 2, 'rgb')}]
        for item, expected in zip(items, ['red', '#rgb']):
            with self.subTest(label=item['label']):
                self.start(items, ['#'])
                self.type('Ar', '#r')
                self.accept(item, [expected])

    def test_insert_text_snippet(self):
        item = {'label': 'print', 'insertTextFormat': 2,
                'insertText': 'print(${1:value})$0'}
        self.start([item], ['pr'])
        self.type('Ai', 'pri')
        self.accept(item, ['print(value)'])

    def test_ordinary_insert_text(self):
        item = {'label': 'print', 'insertText': 'print'}
        self.start([item], ['pr'])
        self.type('Ai', 'pri')
        self.accept(item, ['print'])


if __name__ == '__main__':
    unittest.main()
