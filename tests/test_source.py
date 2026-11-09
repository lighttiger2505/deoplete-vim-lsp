"""Run with PYTHONPATH=<deoplete.nvim>/rplugin/python3 python3 -m unittest discover -s tests."""
import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace
import unittest

from deoplete.child import Child

spec = importlib.util.spec_from_file_location(
    'vim_lsp', Path(__file__).parents[1] / 'rplugin/python3/deoplete/sources/vim_lsp.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Vim:
    def __init__(self):
        self.vars = {'deoplete#sources#vim_lsp#log': ''}
        self.requests = []
        self.triggers = ['"', ':', '[', '.']

    def call(self, name, *args):
        if name == 'lsp#get_allowed_servers':
            return ['test']
        if name == 'lsp#get_server_status':
            return 'running'
        if name == 'lsp#get_server_capabilities':
            return {'completionProvider': {'triggerCharacters': self.triggers}}
        if name == 'deoplete_vim_lsp#request':
            self.requests.append(args)
        if name == 'deoplete#custom#_get_option':
            return {'auto_complete': True, 'auto_complete_popup': 'auto'}[args[0]]
        if name == 'getbufvar':
            return 0


def context(text, line=1, bufnr=1, changedtick=1):
    return {'input': text, 'position': [0, line, len(text)+1, 0],
            'complete_position': re.search(r'\w*$|$', text).start(),
            'bufnr': bufnr, 'changedtick': changedtick,
            'filetypes': ['json'], 'event': 'TextChangedI'}


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.vim = Vim()
        self.source = module.Source(self.vim)
        self.source.min_pattern_length = 1

    def respond(self):
        self.vim.vars['deoplete#source#vim_lsp#_items'] = [{'word': 'matchDepTypes"'}]
        self.vim.vars['deoplete#source#vim_lsp#_done'] = True

    def test_new_negotiated_trigger_refreshes(self):
        self.source.gather_candidates(context('fmt'))
        self.respond()
        self.assertEqual(self.source.gather_candidates(context('fmt.')), [])
        self.assertEqual(len(self.vim.requests), 2)

    def test_real_deoplete_minimum_and_trigger_gate(self):
        child = SimpleNamespace(_vim=self.vim)
        for minimum in [1, 2]:
            self.source.min_pattern_length = minimum
            for text, prefix, expected in [('  "', '', False), ('  "m', 'm', minimum > 1),
                                           ('  "ma', 'ma', False), ('  ;', '', True), ('  ', '', True)]:
                ctx = dict(context(text), complete_str=prefix)
                self.assertEqual(Child._is_skip(child, ctx, self.source), expected, (minimum, text))

    def test_buffer_entry_refetches_server_capabilities(self):
        self.assertRegex('fmt.', self.source.get_input_pattern('go'))
        self.vim.triggers = ['"']
        self.assertRegex('fmt.', self.source.get_input_pattern('go'))
        self.source.on_event({'event': 'BufEnter'})
        self.assertNotRegex('fmt.', self.source.get_input_pattern('go'))

    def test_input_pattern_reuses_the_server_list(self):
        calls = []
        call = self.vim.call
        self.vim.call = lambda name, *args: calls.append(name) or call(name, *args)
        for _ in range(3):
            self.source.get_input_pattern('go')
        self.source.gather_candidates(context('pri'))
        self.assertEqual(calls.count('lsp#get_allowed_servers'), 1)
        self.assertEqual(calls.count('lsp#get_server_capabilities'), 1)

    def test_unadvertised_dot_and_pattern_override(self):
        self.vim.triggers = ['"', '[']
        self.assertNotRegex('fmt.', self.source.get_input_pattern('go'))
        self.source.input_pattern = r'!$'
        self.assertEqual(self.source.get_input_pattern('go'), r'!$')
        self.source.input_patterns = {'go': r'\?$'}
        self.assertEqual(self.source.get_input_pattern('go'), r'\?$')


if __name__ == '__main__':
    unittest.main()
