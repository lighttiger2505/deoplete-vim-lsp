func! deoplete_vim_lsp#request(server_name, opt, ctx) abort
   call s:completor(a:server_name, a:opt, a:ctx)
endfunc

function! s:completor(server_name, opt, ctx) abort
    call lsp#send_request(a:server_name, {
        \ 'method': 'textDocument/completion',
        \ 'params': {
        \   'textDocument': lsp#get_text_document_identifier(),
        \   'position': lsp#get_position(),
        \ },
        \ 'on_notification': function('s:handle_completion', [a:server_name, a:opt, a:ctx]),
        \ })
endfunction

function! s:handle_completion(server_name, opt, ctx, data) abort
    if lsp#client#is_error(a:data) || !has_key(a:data, 'response') || !has_key(a:data['response'], 'result')
        return
    endif

    let l:ctx = a:ctx
    let g:deoplete#source#vim_lsp#_context = l:ctx

    let l:result = a:data['response']['result']
    let g:deoplete#source#vim_lsp#_requested = 1
    let g:deoplete#source#vim_lsp#_results = l:result

    if index(['i', 'ic', 'ix'], mode()) >= 0
        call deoplete#auto_complete()
    endif
endfunction

