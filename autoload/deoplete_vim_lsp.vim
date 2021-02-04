function! deoplete_vim_lsp#log(...) abort
    if !empty(g:deoplete#sources#vim_lsp#log)
        call writefile([strftime('%c') . ':' . json_encode(a:000)], g:deoplete#sources#vim_lsp#log, 'a')
    endif
endfunction

func! deoplete_vim_lsp#request(server_name, ctx) abort
   call s:completor(a:server_name, a:ctx)
endfunc

function! s:completor(server_name, ctx) abort
    let l:server = lsp#get_server_info(a:server_name)
    let l:position = lsp#get_position()
    call lsp#send_request(a:server_name, {
        \ 'method': 'textDocument/completion',
        \ 'params': {
        \   'textDocument': lsp#get_text_document_identifier(),
        \   'position': l:position,
        \ },
        \ 'on_notification': function('s:handle_completion', [l:server, l:position, a:ctx]),
        \ })
endfunction

function! s:handle_completion(server, position, ctx, data) abort
    if lsp#client#is_error(a:data) || !has_key(a:data, 'response') || !has_key(a:data['response'], 'result')
        return
    endif

    let l:options = {
        \ 'server': a:server,
        \ 'position': a:position,
        \ 'response': a:data['response'],
        \ }
    let g:deoplete#source#vim_lsp#_items = lsp#omni#get_vim_completion_items(l:options)['items']
    let g:deoplete#source#vim_lsp#_done = 1
    let g:deoplete#source#vim_lsp#_context = a:ctx

    if index(['i', 'ic', 'ix'], mode()) >= 0
        call deoplete#auto_complete()
    endif
endfunction
