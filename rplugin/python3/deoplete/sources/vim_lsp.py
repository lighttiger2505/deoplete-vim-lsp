import time
import logging

from deoplete.source.base import Base
from deoplete.util import load_external_module

load_external_module(__file__, 'sources')

from vim_lsp import complete_util


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

get_handler = logging.FileHandler('/home/lighttiger2505/deoplete-vim-lsp.log')
logger.addHandler(get_handler)


class Source(Base):
    def __init__(self, vim):
        Base.__init__(self, vim)

        # Override deoplete prop
        self.name = 'lsp'
        self.mark = '[lsp]'
        self.rank = 500
        self.input_pattern = r'[^\w\s]$'
        self.events = ['BufEnter']
        # Work chache
        self.ls_cache = None
        self.ls_requests = complete_util.LanguageServerRequests(vim)
        self.buf_changed = False
        # Remove vim variables
        self.vim.vars['deoplete#source#vim_lsp#_results'] = []
        self.vim.vars['deoplete#source#vim_lsp#_context'] = {}
        self.vim.vars['deoplete#source#vim_lsp#_requested'] = False

    def on_event(self, context):
        if context['event'] == 'BufEnter':
            self.buf_changed = True

    def gather_candidates(self, context):
        if self.buf_changed:
            self.reflesh_whitelisted_servers()
        if self.ls_cache is None:
            self.ls_cache = complete_util.LanguageServerCache(self.ls_requests)

        for server_name in self.ls_cache.server_names():
            logger.info(server_name)
            if not self.ls_cache.has_completion_provider(server_name):
                continue
            if self._is_auto_complete():
                return self.async_completion(server_name, context)
            return self.sync_completion(server_name, context)

        return []

    def complete_requested(self):
        return self.vim.vars['deoplete#source#vim_lsp#_requested']

    def response_context(self):
        return self.vim.vars['deoplete#source#vim_lsp#_context']

    def response_candidates(self):
        return self.vim.vars['deoplete#source#vim_lsp#_context']

    def sync_completion(self, server_name, context):
        self.vim.vars['deoplete#source#vim_lsp#_requested'] = False
        context['is_async'] = False
        self.ls_requests.get_completion(server_name, context)

        cnt = 0
        while cnt < 10:
            cnt += 1
            if self.vim.vars['deoplete#source#vim_lsp#_requested']:
                if complete_util.match_context(
                        context,
                        self.vim.vars['deoplete#source#vim_lsp#_context']
                ):
                    context['is_async'] = False
                    return complete_util.parse_candidates(
                        self.vim.vars['deoplete#source#vim_lsp#_results'],
                        self.vim.vars['deoplete#sources#vim_lsp#show_info'],
                    )
            time.sleep(0.01)
        return []

    def async_completion(self, server_name, context):
        # Async
        if context['is_async']:
            if self.vim.vars['deoplete#source#vim_lsp#_requested']:
                if complete_util.match_context(
                        context,
                        self.vim.vars['deoplete#source#vim_lsp#_context']
                ):
                    context['is_async'] = False
                    return complete_util.parse_candidates(
                        self.vim.vars['deoplete#source#vim_lsp#_results'],
                        self.vim.vars['deoplete#sources#vim_lsp#show_info'],
                    )

                # old position completion
                self.vim.vars['deoplete#source#vim_lsp#_requested'] = False
                context['is_async'] = True
                self.ls_requests.get_completion(server_name, context)

            # dissmiss completion
            return []

        # request language server
        self.vim.vars['deoplete#source#vim_lsp#_requested'] = False
        context['is_async'] = True
        self.ls_requests.get_completion(server_name, context)
        return []


    def _is_auto_complete(self):
        return self.vim.call(
            'deoplete#custom#_get_option',
            'auto_complete',
        )
