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
        self.clears = 0
        self.auto_complete = True
        self.reply = None

    def call(self, name, *args):
        if name == 'lsp#get_allowed_servers':
            return ['test']
        if name == 'lsp#get_server_status':
            return 'running'
        if name == 'lsp#get_server_capabilities':
            return {'completionProvider': {'triggerCharacters': self.triggers}}
        if name in ('deoplete_vim_lsp#clear', 'deoplete_vim_lsp#request'):
            self.clears += 1
            self.vars.update({'deoplete#source#vim_lsp#_items': [],
                              'deoplete#source#vim_lsp#_done': False,
                              'deoplete#source#vim_lsp#_incomplete': False})
        if name == 'deoplete_vim_lsp#request':
            self.requests.append(args)
            if self.reply:
                self.vars.update(self.reply)
        if name == 'deoplete#custom#_get_option':
            return {'auto_complete': self.auto_complete, 'auto_complete_popup': 'auto'}[args[0]]
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

    def respond(self, incomplete=False):
        self.vim.vars['deoplete#source#vim_lsp#_items'] = [{'word': 'matchDepTypes"'}]
        self.vim.vars['deoplete#source#vim_lsp#_done'] = True
        self.vim.vars['deoplete#source#vim_lsp#_incomplete'] = incomplete

    def test_complete_quote_response_survives_prefix_without_request(self):
        self.source.gather_candidates(context('  "'))
        self.respond()
        for text in ['  "', '  "m', '  "ma', '  "match']:
            self.assertEqual(self.source.gather_candidates(context(text)), [{'word': 'matchDepTypes"'}])
        self.assertEqual(self.vim.requests, [('test', 3)])

    def test_incomplete_response_refreshes_only_on_changed_input(self):
        self.source.gather_candidates(context('fmt.'))
        self.respond(True)
        self.assertTrue(self.source.gather_candidates(context('fmt.')))
        self.assertEqual(self.source.gather_candidates(context('fmt.P')), [])
        self.assertEqual(len(self.vim.requests), 2)
        self.respond(True)
        self.assertEqual(self.source.gather_candidates(context('fmt.Pr')), [])
        self.assertEqual(len(self.vim.requests), 3)

    def test_changed_anchor_line_and_backspace_invalidate(self):
        self.source.requested_context = context('  "ma')
        for text in ['other "match', '  "m', '  "max;other', '  "mb']:
            self.assertFalse(self.source.match_context(context(text)), text)
        self.assertFalse(self.source.match_context(context('  "match', 2)))
        self.assertTrue(self.source.match_context(context('  "match')))

    def test_new_negotiated_trigger_refreshes(self):
        self.source.gather_candidates(context('fmt'))
        self.respond()
        self.assertEqual(self.source.gather_candidates(context('fmt.')), [])
        self.assertEqual(len(self.vim.requests), 2)

    def test_buffer_entry_clears_items_and_invalidates_pending_request(self):
        for completed in [False, True]:
            with self.subTest(completed=completed):
                self.source.clean_state()
                self.vim.requests.clear()
                self.source.gather_candidates(context('pri'))
                if completed:
                    self.respond()
                clears = self.vim.clears
                self.source.on_event({'event': 'BufEnter'})
                self.assertEqual(self.vim.clears, clears + 1)
                self.assertEqual(self.source.gather_candidates(context('pri', bufnr=2)), [])
                self.assertEqual(len(self.vim.requests), 2)

    def test_restarted_source_disowns_pending_request(self):
        self.source.gather_candidates(context('pri'))
        clears = self.vim.clears
        module.Source(self.vim)
        self.assertEqual(self.vim.clears, clears + 1)

    def test_buffer_identity_prevents_reuse_without_event(self):
        self.source.gather_candidates(context('pri'))
        self.respond()
        self.assertEqual(self.source.gather_candidates(context('pri', bufnr=2)), [])
        self.assertEqual(len(self.vim.requests), 2)

    def test_changed_pending_context_sends_new_request(self):
        for new_context in [context('other'), context('pr'), context('pri', line=2)]:
            with self.subTest(context=new_context):
                self.source.clean_state()
                self.vim.requests.clear()
                self.source.gather_candidates(context('pri'))
                self.assertEqual(self.source.gather_candidates(new_context), [])
                self.assertEqual(len(self.vim.requests), 2)

    def test_failed_request_retries_when_typing_resumes(self):
        self.source.gather_candidates(context('pri'))
        self.respond(incomplete=True)
        self.vim.vars['deoplete#source#vim_lsp#_items'] = []
        self.assertEqual(self.source.gather_candidates(context('pri')), [])
        self.assertEqual(len(self.vim.requests), 1)
        self.assertEqual(self.source.gather_candidates(context('prin')), [])
        self.assertEqual(len(self.vim.requests), 2)

    def test_each_request_is_one_editor_call(self):
        self.source.gather_candidates(context('pri'))
        clears = self.vim.clears
        self.source.gather_candidates(context('other'))
        self.assertEqual(self.vim.clears, clears + 1)

    def test_failed_request_after_pending_growth_retries_immediately(self):
        self.source.gather_candidates(context('pri'))
        self.assertEqual(self.source.gather_candidates(context('prin')), [])
        self.assertEqual(len(self.vim.requests), 1)
        self.respond(incomplete=True)
        self.vim.vars['deoplete#source#vim_lsp#_items'] = []
        self.assertEqual(self.source.gather_candidates(context('prin')), [])
        self.assertEqual(len(self.vim.requests), 2)
        self.respond()
        self.assertTrue(self.source.gather_candidates(context('prin')))

    def test_clean_state_forgets_the_request(self):
        self.source.gather_candidates(context('pri'))
        self.respond(incomplete=True)
        self.source.clean_state()
        self.assertIsNone(self.source.requested_context)
        for name in ['items', 'done', 'incomplete']:
            self.assertFalse(self.vim.vars['deoplete#source#vim_lsp#_' + name])

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

    def test_manual_completion_waits_for_reply_then_times_out(self):
        self.vim.auto_complete = False
        self.vim.reply = {'deoplete#source#vim_lsp#_done': True,
                          'deoplete#source#vim_lsp#_items': [{'word': 'print'}]}
        ctx = context('pri')
        self.assertEqual(self.source.gather_candidates(ctx), [{'word': 'print'}])
        self.assertFalse(ctx['is_async'])
        self.vim.reply = None
        self.assertEqual(self.source.gather_candidates(context('pri')), [])
        self.assertEqual(len(self.vim.requests), 2)

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
