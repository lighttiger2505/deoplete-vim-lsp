import re
import time

from deoplete.source.base import Base


LSP_KINDS = [
    'Text',
    'Method',
    'Function',
    'Constructor',
    'Field',
    'Variable',
    'Class',
    'Interface',
    'Module',
    'Property',
    'Unit',
    'Value',
    'Enum',
    'Keyword',
    'Snippet',
    'Color',
    'File',
    'Reference',
    'Folder',
    'EnumMember',
    'Constant',
    'Struct',
    'Event',
    'Operator',
    'TypeParameter',
]


class Source(Base):
    def __init__(self, vim):
        Base.__init__(self, vim)

        self.name = 'lsp'
        self.mark = '[lsp]'
        self.rank = 500
        self.input_pattern = r'[^\w\s]$'
        self.events = ['BufEnter']
        self.vars = {}
        self.vim.vars['deoplete#source#vim_lsp#_results'] = []
        self.vim.vars['deoplete#source#vim_lsp#_context'] = {}
        self.vim.vars['deoplete#source#vim_lsp#_requested'] = False

        self.server_names = None
        self.server_capabilities = {}
        self.server_infos = {}
        self.buf_changed = False


    def on_event(self, context):
        if context['event'] == 'BufEnter':
            self.buf_changed = True

    def gather_candidates(self, context):
        if not self.server_names or self.buf_changed:
            self.server_names = self.vim.call('lsp#get_whitelisted_servers')
            self.buf_changed = False

        for server_name in self.server_names:
            if server_name not in self.server_capabilities:
                self.server_capabilities[server_name] = self.vim.call(
                    'lsp#get_server_capabilities', server_name)
            if not self.server_capabilities[server_name].get(
                    'completionProvider', False):
                continue

            if self.is_auto_complete():
                return self.async_completion(server_name, context)

            return self.sync_completion(server_name, context)

        return []

    def sync_completion(self, server_name, context):
        self.request_lsp_completion(server_name, context, False)
        cnt = 0
        while True:
            cnt += 1
            if cnt > 10:
                # request timeout
                break
            if self.vim.vars['deoplete#source#vim_lsp#_requested']:
                if match_context(
                        context,
                        self.vim.vars['deoplete#source#vim_lsp#_context']
                ):
                    context['is_async'] = False
                    return self.process_candidates()
            time.sleep(0.01)
        return []

    def async_completion(self, server_name, context):
        # Async
        if context['is_async']:
            if self.vim.vars['deoplete#source#vim_lsp#_requested']:
                if match_context(
                        context,
                        self.vim.vars['deoplete#source#vim_lsp#_context']
                ):
                    context['is_async'] = False
                    # self.vim.call('deoplete#auto_complete')
                    return self.process_candidates()

                # old position completion
                self.request_lsp_completion(server_name, context, True)

            # dissmiss completion
            return []

        # request language server
        self.request_lsp_completion(server_name, context, True)
        return []

    def request_lsp_completion(self, server_name, context, is_async):
        self.vim.vars['deoplete#source#vim_lsp#_requested'] = False
        context['is_async'] = is_async

        self.vim.call(
            'deoplete_vim_lsp#request',
            server_name,
            create_option_to_vimlsp(server_name),
            create_context_to_vimlsp(context),
        )

    def process_candidates(self):
        candidates = []
        results = self.vim.vars['deoplete#source#vim_lsp#_results']

        # response is `CompletionList`
        if isinstance(results, dict):
            if 'items' not in results:
                self.print_error(
                    'LSP results does not have "items" key:{}'.format(
                        str(results)))
                return candidates
            items = results['items']

        # response is `CompletionItem[]`
        elif isinstance(results, list):
            items = results

        # invalid response
        else:
            return candidates

        if items is None:
            return candidates

        for rec in items:
            if rec.get('insertText', ''):
                if rec.get('insertTextFormat', 0) != 1:
                    word = rec.get('entryName', rec.get('label'))
                else:
                    word = rec['insertText']
            else:
                word = rec.get('entryName', rec.get('label'))

            item = {
                'word': re.sub(r'\([^)]*\)', '', word),
                'abbr': rec['label'],
                'dup': 0,
            }

            if 'kind' in rec:
                item['kind'] = LSP_KINDS[rec['kind'] - 1]

            if 'detail' in rec and rec['detail']:
                item['info'] = rec['detail']
                if self.vim.vars['deoplete#sources#vim_lsp#show_info']:
                    item['menu'] = rec['detail']

            candidates.append(item)
        return candidates

    def is_auto_complete(self):
        return self.vim.call(
            'deoplete#custom#_get_option',
            'auto_complete',
        )


def create_option_to_vimlsp(server_name):
    return {'name': 'deoplete_lsp_{}'.format(server_name)}


def create_context_to_vimlsp(context):
    return {
        'curpos': context['position'],
        'lnum': context['position'][1],
        'col': context['position'][2],
        'bufnr': context['bufnr'],
        'changedtick': context['changedtick'],
        'typed': context['input'],
        'filetype': context['filetype'],
        'filepath': context['bufpath']
    }


def match_context(deoplete_context, vim_lsp_context):
    position_key_deoplete = '{}:{}'.format(
        deoplete_context['position'][1],
        deoplete_context['position'][2],
    )
    position_key_lsp = '{}:{}'.format(
        vim_lsp_context['lnum'],
        vim_lsp_context['col'],
    )
    if position_key_deoplete == position_key_lsp:
        return True
    return False
