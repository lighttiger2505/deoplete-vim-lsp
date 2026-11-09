Run the source tests and editor acceptance tests with Python's existing unittest
discovery. `LAB` is a dependency directory containing checkouts (or symlinks) named
`deoplete.nvim` and `vim-lsp`. Python needs `pynvim`. The optional real Vim test
also needs `nvim-yarp` and `vim-hug-neovim-rpc` in `LAB`, Vim with `+python3`, and
permission to open the local socket used by its RPC adapter.

```sh
LAB=/path/to/dependencies \
NVIM=/path/to/nvim \
VIM_BIN=/path/to/vim \
PYTHONPATH=/path/to/dependencies/deoplete.nvim/rplugin/python3 \
python3 -m unittest discover -s tests -v

LAB=/path/to/dependencies vim -Nu NONE -i NONE -n -es -S tests/test_bridge.vim
LAB=/path/to/dependencies nvim -u NONE -i NONE --headless -n -S tests/test_bridge.vim
```

Acceptance tests skip when their editor or dependency directories are unavailable.
Use `VIM_BIN` to choose the Vim executable: Vim reserves `$VIM` for its installation
directory. When needed, use a wrapper that selects Vim's matching Python shared
library before starting the editor.

Verified dependencies: Deoplete `e5a47d4`, vim-lsp `8148119`, nvim-yarp `bb5f5e0`,
vim-hug-neovim-rpc `93ae387`, pynvim 0.6.0; Vim 9.2.1202 and Neovim 0.11.5.

The integration tests use a deterministic stdio language server, real Deoplete
workers, and real vim-lsp conversion and `CompleteDone` handling. They type into
Insert mode, wait for Deoplete to process each prefix, accept with Ctrl-N/Ctrl-Y,
and assert the resulting buffer after vim-lsp's deferred handler finishes.
Neovim tests also check original completion metadata and the resolve request.

`test_bridge.vim` covers conversion and request state against captured requests:
duplicate and out-of-order replies, clearing, buffer switches, the timeout and a
late reply, malformed envelopes and results, and replies made stale by a changed
prefix or line. `test_source.py` covers when the source reuses a result and when
it sends a new request.

Not covered: external snippet engines, supplementary Unicode characters requiring
UTF-16 surrogate pairs, differing `filterText`/inserted-text prefixes, and
multiple simultaneous servers.
