" Capture completion requests; keep the real vim-lsp conversion functions.
function! lsp#send_request(server_name, data) abort
  call add(g:test_lsp_requests, a:data)
endfunction
