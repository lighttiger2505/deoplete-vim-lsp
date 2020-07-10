# deoplete-vim-lsp

deoplete source for vim-lsp

## Warning

Old style sources like the old deoplete-vim-lsp have been deprecated.
So the latest deoplete-vim-lsp will only work with the latest deoplete.nvim
**Please update deoplete-vim-lsp.**

See [commit](https://github.com/Shougo/deoplete.nvim/commit/7f1d4d8b1f5dbf344f2d0d1f4b8c5d6a0aaa24a6)

## Install

### requirements

- [deoplete.nvim](https://github.com/Shougo/deoplete.nvim)
- [vim-lsp](https://github.com/prabirshrestha/vim-lsp)

### .vimrc

For vim-plug

```vim
Plug 'Shougo/deoplete.nvim'
Plug 'prabirshrestha/vim-lsp'

Plug 'lighttiger2505/deoplete-vim-lsp'
```

For dein.vim

```vim
call dein#add('Shougo/deoplete.nvim')
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
      \ 'allowlist': ['python']
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
     \ 'allowlist': ['go'],
     \ })
    augroup END
endif
```
