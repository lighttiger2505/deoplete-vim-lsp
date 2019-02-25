let s:request_id = 0
let s:requesting = 0
let s:next_request = {}

let g:deoplete#sources#vim_lsp#_results = []
let g:deoplete#sources#vim_lsp#_results_id = -1

function! deoplete_vim_lsp#request(server_name, opt, ctx) abort
  let s:request_id = (s:request_id + 1) % 1000
  call s:completor(a:server_name, a:opt, a:ctx, s:request_id)
endfunc

function! deoplete_vim_lsp#is_finished()
  return s:request_id == g:deoplete#sources#vim_lsp#_results_id
endfunction

function! s:completor(server_name, opt, ctx, request_id) abort
  " skip if requesting.
  if s:requesting == 1
    let s:next_request = {
          \ 'server_name': a:server_name,
          \ 'opt': a:opt,
          \ 'ctx': a:ctx,
          \ 'request_id': a:request_id,
          \ }
    return
  endif
  let s:next_request = {}

  " send request.
  let s:requesting = 1
  let [s:server_name_, s:opt_, s:ctx_, s:request_id_] = [a:server_name, a:opt, a:ctx, a:request_id]
  function! s:tick(timer_id)
    call lsp#send_request(s:server_name_, {
          \ 'method': 'textDocument/completion',
          \     'params': {
          \       'textDocument': lsp#get_text_document_identifier(),
          \       'position': { 'line': line('.') - 1, 'character': col('.') - 1 },
          \     },
          \     'on_notification': function('s:handle_completion', [s:server_name_, s:opt_, s:ctx_, s:request_id_]),
          \   })
  endfunction
  call timer_start(g:deoplete#sources#vim_lsp#debounce, function('s:tick'), { 'repeat': 1 })
endfunction

function! s:handle_completion(server_name, opt, ctx, request_id, data) abort
  let s:requesting = 0

  " fallback to latest waiting request.
  if has_key(s:next_request, 'server_name')
    call s:completor(
          \ s:next_request.server_name,
          \ s:next_request.opt,
          \ s:next_request.ctx,
          \ s:next_request.request_id
          \ )
    return
  endif

  if lsp#client#is_error(a:data) || !has_key(a:data, 'response') || !has_key(a:data['response'], 'result')
    return
  endif
  let g:deoplete#sources#vim_lsp#_results_id = a:request_id
  let g:deoplete#sources#vim_lsp#_results = a:data['response']['result']
  call deoplete#send_event('InsertEnter')
endfunction

