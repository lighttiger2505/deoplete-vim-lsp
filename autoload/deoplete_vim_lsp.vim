let s:request_id = 0
let s:requesting = 0
let s:timer_id = -1
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
  " wait for completion resolve.
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

  " clear timer if timer is runnning.
  if s:timer_id != -1
    call timer_stop(s:timer_id)
    let s:timer_id = -1
  endif

  " create new timer.
  let [s:server_name_, s:opt_, s:ctx_, s:request_id_] = [a:server_name, a:opt, a:ctx, a:request_id]
  function! s:tick(timer_id)
    let s:timer_id = -1

    let s:requesting = 1
    call lsp#send_request(s:server_name_, {
          \ 'method': 'textDocument/completion',
          \     'params': {
          \       'textDocument': lsp#get_text_document_identifier(),
          \       'position': lsp#get_position(),
          \     },
          \     'on_notification': function('s:handle_completion', [s:server_name_, s:opt_, s:ctx_, s:request_id_]),
          \   })
  endfunction
  let s:timer_id = timer_start(g:deoplete#sources#vim_lsp#debounce, function('s:tick'), { 'repeat': 1 })
endfunction

function! s:handle_completion(server_name, opt, ctx, request_id, data) abort
  let s:requesting = 0

  " use latest waiting request.
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
    let g:deoplete#sources#vim_lsp#_results_id = a:request_id
    let g:deoplete#sources#vim_lsp#_results = []
    return
  endif
  let g:deoplete#sources#vim_lsp#_results_id = a:request_id
  let g:deoplete#sources#vim_lsp#_results = a:data['response']['result']
  call deoplete#send_event('InsertEnter', [])
endfunction

