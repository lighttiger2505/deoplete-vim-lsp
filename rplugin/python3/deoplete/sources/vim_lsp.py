import re
import time

from deoplete.source.base import Base


class Source(Base):
    def __init__(self, vim):
        Base.__init__(self, vim)

        self.name = 'lsp'
        self.mark = '[lsp]'
        self.rank = 500
        self.is_volatile = True
        self.events = ['BufEnter']
        self.vars = {}

        self.server_names = None
        self.server_capabilities = {}
        self.clean_state()

    def on_event(self, context):
        if context['event'] == 'BufEnter':
            # Refetch so a restarted server's trigger characters take effect.
            self.server_names = None
            self.server_capabilities = {}
            self.clean_state()

    def get_input_pattern(self, filetype):
        if self.input_pattern or self.input_patterns:
            return Base.get_input_pattern(self, filetype)

        triggers = [char for server_name in self.running_servers()
                    for char in self.trigger_characters(server_name)]
        if not triggers:
            return ''
        return '(?:' + '|'.join(re.escape(char) for char in triggers) + ')$'

    def running_servers(self):
        if not self.server_names:
            self.server_names = self.vim.call('lsp#get_allowed_servers')

        running = []
        for server_name in self.server_names:
            if server_name not in self.server_capabilities:
                # Capabilities can only be obtained when the server is running.
                if self.vim.call('lsp#get_server_status', server_name) != 'running':
                    continue
                self.server_capabilities[server_name] = self.vim.call(
                    'lsp#get_server_capabilities', server_name)
            running.append(server_name)
        return running

    def gather_candidates(self, context):
        for server_name in self.running_servers():
            completion_provider = self.server_capabilities[server_name].get(
                    'completionProvider', False)
            if completion_provider is False or completion_provider is None:
                continue

            if self.is_auto_complete():
                return self.async_completion(server_name, context)
            return self.sync_completion(server_name, context)

        return []

    def clean_state(self):
        self.requested_context = None
        self.vim.call('deoplete_vim_lsp#clear')

    def sync_completion(self, server_name, context):
        self.request_lsp_completion(server_name, context)
        cnt = 0
        while True:
            cnt += 1
            if cnt > 10:
                # request timeout
                break
            if self.vim.vars['deoplete#source#vim_lsp#_done']:
                context['is_async'] = False
                return self.vim.vars['deoplete#source#vim_lsp#_items']
            time.sleep(0.01)
        return []

    def async_completion(self, server_name, context):
        if not self.match_context(context):
            self.request_lsp_completion(server_name, context)
            return []

        now_input = context['input']
        if now_input != self.prev_input() and len(now_input) and now_input[-1] in self.trigger_characters(server_name):
            self.log('trigger characters')
            self.request_lsp_completion(server_name, context)
            return []

        if self.vim.vars['deoplete#source#vim_lsp#_done']:
            if (now_input == self.prev_input() or not
                    self.vim.vars['deoplete#source#vim_lsp#_incomplete']):
                items = self.vim.vars['deoplete#source#vim_lsp#_items']
                return items
            else:
                self.log('incomplete response')
                self.request_lsp_completion(server_name, context)
                return []

        return []

    def request_lsp_completion(self, server_name, context):
        self.log('request completion')

        # The bridge resets the previous request and its result itself.
        self.requested_context = context
        self.vim.call(
            'deoplete_vim_lsp#request',
            server_name,
            context['complete_position'],
        )

    def is_auto_complete(self):
        return self.vim.call(
            'deoplete#custom#_get_option',
            'auto_complete',
        )

    def log(self, val):
        if not self.vim.vars['deoplete#sources#vim_lsp#log']:
            return
        self.vim.call('deoplete_vim_lsp#log', val)

    def trigger_characters(self, server_name):
        capabilities = self.server_capabilities[server_name]
        completion_provider = capabilities.get('completionProvider')
        if isinstance(completion_provider, dict):
            return list(completion_provider.get('triggerCharacters', []))
        return []

    def prev_input(self):
        return self.requested_context.get('input', '')

    def match_context(self, context):
        before_context = self.requested_context
        if not before_context:
            return False
        if context['bufnr'] != before_context['bufnr']:
            return False

        pattern = re.compile(r'\w+\Z')
        def keywd(typed):
            match = pattern.search(typed)
            if match:
                return match.group()
            return ""
        beforeKw = keywd(before_context['input'])
        afterKw = keywd(context['input'])

        self.log(str([
            'before:',
            before_context['input'],
            beforeKw,
            before_context['position'][1],
            before_context['position'][2],
        ]))
        self.log(str([
            'after :',
            context['input'],
            afterKw,
            context['position'][1],
            context['position'][2],
        ]))

        # start input
        if pattern.sub('', before_context['input']) != pattern.sub('', context['input']):
            return False
        if (beforeKw != afterKw) and (not afterKw.startswith(beforeKw)):
            return False
        # lnum
        if context['position'][1] != before_context['position'][1]:
            return False
        # column
        if before_context['position'][2] > context['position'][2]:
            return False
        return True
