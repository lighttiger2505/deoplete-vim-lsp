import re

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
        self.vars = {}
        self.vim.vars['deoplete#source#vim_lsp#_results'] = []
        self.vim.vars['deoplete#source#vim_lsp#_requested'] = False

        self.server_names = None
        self.server_capabilities = {}
        self.server_infos = {}

    def gather_candidates(self, context):
        if not self.server_names:
            self.server_names = self.vim.call('lsp#get_server_names')

        for server_name in self.server_names:
            if server_name not in self.server_capabilities:
                self.server_capabilities[server_name] = self.vim.call(
                    'lsp#get_server_capabilities', server_name)
            if not self.server_capabilities[server_name].get(
                    'completionProvider', False):
                continue

            if server_name not in self.server_infos:
                self.server_infos[server_name] = self.vim.call(
                    'lsp#get_server_info', server_name)

            filetype = context['filetype']
            server_info = self.server_infos[server_name]
            if server_info.get('whitelist', []):
                if filetype not in server_info['whitelist']:
                    continue
            if server_info.get('blacklist', []):
                if filetype in server_info['blacklist']:
                    continue

            if context['is_async']:
                if self.vim.vars['deoplete#source#vim_lsp#_requested']:
                    context['is_async'] = False
                    return self.process_candidates()
                return []

            self.vim.vars['deoplete#source#vim_lsp#_requested'] = False
            context['is_async'] = True

            self.vim.call(
                'deoplete_vim_lsp#request',
                server_name,
                create_option_to_vimlsp(server_name),
                create_context_to_vimlsp(context),
            )
        return []

    def process_candidates(self):
        candidates = []
        results = self.vim.vars['deoplete#source#vim_lsp#_results']

        if not isinstance(results, dict):
            return candidates

        if 'items' not in results:
            self.print_error(
                'LSP results does not have "items" key:{}'.format(
                    str(results)))
            return candidates

        items = results['items']
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
                item['menu'] = rec['detail']

            candidates.append(item)

        return candidates


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
