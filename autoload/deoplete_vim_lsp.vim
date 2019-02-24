let g:deoplete_vim_lsp#debounce_timeout = get(g:, 'deoplete_vim_lsp#debounce_timeout', 100)

let s:timer_id = -1

function! deoplete_vim_lsp#request(server_name, opt, ctx) abort
  call s:completor(a:server_name, a:opt, a:ctx)
endfunc

function! s:completor(server_name, opt, ctx) abort
  if s:timer_id != -1
    call timer_stop(s:timer_id)
    let s:timer_id = -1
  endif

  let s:server_name = a:server_name
  let s:opt = a:opt
  let s:ctx = a:ctx
  let s:textDocument = lsp#get_text_document_identifier()
  let s:position = lsp#get_position()

  function! s:tick(timer)
    call lsp#send_request(s:server_name, {
                \ 'method': 'textDocument/completion',
                \     'params': {
                \       'textDocument': s:textDocument,
                \       'position': s:position,
                \     },
                \     'on_notification': function('s:handle_completion', [s:server_name, s:opt, s:ctx]),
                \   })
  endfunction

  let s:timer_id = timer_start(g:deoplete_vim_lsp#debounce_timeout, funcref('s:tick'), { 'repeat': 1 })
endfunction

function! s:handle_completion(server_name, opt, ctx, data) abort
  if lsp#client#is_error(a:data) || !has_key(a:data, 'response') || !has_key(a:data['response'], 'result')
      return
  endif

  let l:result = a:data['response']['result']
  let g:deoplete#source#vim_lsp#_requested = 1
  let g:deoplete#source#vim_lsp#_results = l:result
endfunction

