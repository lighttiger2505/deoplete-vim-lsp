# deoplete-vim-lsp

deoplete source for vim-lsp

## Install

### requirements

- [deoplete.nvim](https://github.com/Shougo/deoplete.nvim)
- [vim-lsp](https://github.com/prabirshrestha/vim-lsp)

### .vimrc

For vim-plug

```vim
Plug 'Shougo/deoplete.nvim'
Plug 'prabirshrestha/async.vim'
Plug 'prabirshrestha/vim-lsp'

Plug 'lighttiger2505/deoplete-vim-lsp'
```

For dein.vim

```vim
call dein#add('Shougo/deoplete.nvim')
call dein#add('prabirshrestha/async.vim')
call dein#add('prabirshrestha/vim-lsp')

call dein#add('lighttiger2505/deoplete-vim-lsp')
```

#### setting example

```vim
let g:deoplete#enable_at_startup = 1

" For python language server
if (executable('pyls'))
    let s:pyls_path = fnamemodify(g:python_host_prog, ':h') . '/'. 'pyls'
    augroup LspPython
        autocmd!
        autocmd User lsp_setup call lsp#register_server({
      \ 'name': 'pyls',
      \ 'cmd': {server_info->['pyls']},
      \ 'whitelist': ['python']
      \ })
    augroup END
endif

" For bingo(go language server)
if (executable('bingo'))
    augroup LspGo
        autocmd!
        autocmd User lsp_setup call lsp#register_server({
     \ 'name': 'go-lang',
     \ 'cmd': {server_info->['bingo', '-disable-func-snippet', '-mode', 'stdio']},
     \ 'whitelist': ['go'],
     \ })
    augroup END
endif
```
