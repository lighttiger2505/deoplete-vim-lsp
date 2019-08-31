import re
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

get_handler = logging.FileHandler('/home/lighttiger2505/deoplete-vim-lsp.log')
logger.addHandler(get_handler)


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


class LanguageServerRequests():
    def __init__(self, vim):
        self.vim = vim

    def get_whitelisted_servers(self):
        return self.vim.call('lsp#get_whitelisted_servers')

    def get_server_capabilities(self, server_name):
        return self.vim.call('lsp#get_server_capabilities', server_name)

    def get_completion(self, server_name, context):
        self.vim.call(
            'deoplete_vim_lsp#request',
            server_name,
            create_option_to_vimlsp(server_name),
            create_context_to_vimlsp(context),
        )


class LanguageServerCache():
    def __init__(self, ls_requests):
        self.ls_requests = ls_requests
        self.capabilities = {}
        self.reflesh_whitelisted_servers()

    def server_names(self):
        return self.capabilities.keys()

    def reflesh_whitelisted_servers(self):
        srvs = self.ls_requests.get_whitelisted_servers()
        for srv in srvs:
            self.capabilities[srv] = None

    def has_completion_provider(self, server_name):
        if not self.capabilities or not self._has_server(server_name):
            self.reflesh_whitelisted_servers()
        if not self._has_server_capabilities(server_name):
            cap = self.ls_requests.get_server_capabilities(server_name)
            self.capabilities[server_name] = cap
        return self.capabilities[server_name].get('completionProvider', False)

    def _has_server(self, server_name):
        return server_name in self.capabilities

    def _has_server_capabilities(self, server_name):
        return self.capabilities.get(server_name, None) is not None


def parse_candidates(lsp_complete, is_show_info):
    candidates = []
    results = lsp_complete

    # response is `CompletionList`
    if isinstance(results, dict):
        if 'items' not in results:
            raise Exception('LSP results does not have "items" key:{}'.format(str(results)))
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
            if is_show_info:
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
