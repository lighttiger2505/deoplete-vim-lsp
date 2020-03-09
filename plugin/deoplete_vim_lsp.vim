if exists('g:loaded_deoplete_vim_lsp')
  finish
endif
let g:loaded_deoplete_vim_lsp = 1

let g:deoplete#sources#vim_lsp#log = get(g:, 'deoplete#sources#vim_lsp#log', '')

autocmd BufEnter * call deoplete#send_event('BufEnter', ['lsp'])
