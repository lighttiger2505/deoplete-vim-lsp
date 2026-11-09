" Run: LAB=<dependencies> vim -Nu NONE -i NONE -n -es -S tests/test_bridge.vim
set nocompatible encoding=utf-8
let &runtimepath = $VIMRUNTIME . ',' . $LAB . '/vim-lsp,' . fnamemodify(expand('<sfile>'), ':p:h:h')
runtime plugin/lsp.vim
runtime plugin/deoplete_vim_lsp.vim
runtime autoload/deoplete_vim_lsp.vim
call lsp#register_server({'name': 'test', 'cmd': {s->[]}, 'allowlist': ['json'], 'config': {'refresh_pattern': '\("\k*\|\k\+\)$'}})
" Capture requests instead of starting a server; vim-lsp's conversion stays real.
execute 'source ' . fnameescape(fnamemodify(expand('<sfile>'), ':p:h') . '/fixtures/autoload/lsp.vim')
let g:test_lsp_requests = []
let s:script = filter(getscriptinfo(), {i,v -> v.name =~ '/autoload/deoplete_vim_lsp.vim$'})[0]
let s:Finish = function('<SNR>' . s:script.sid . '_finish_request')

function! s:start(...) abort
  call deoplete_vim_lsp#request('test', get(a:000, 0, 0))
  return g:test_lsp_requests[-1].on_notification
endfunction

function! s:reply(Callback, result) abort
  call call(a:Callback, [{'response': {'result': a:result}}])
endfunction

function! s:words() abort
  return map(copy(g:deoplete#source#vim_lsp#_items), 'v:val.word')
endfunction

function! s:assert_failed(message) abort
  call assert_equal(1, g:deoplete#source#vim_lsp#_done, a:message)
  call assert_equal([], g:deoplete#source#vim_lsp#_items, a:message)
  call assert_equal(1, g:deoplete#source#vim_lsp#_incomplete, a:message)
endfunction

" A new request publishes, and a duplicate of its reply does not.
function! s:assert_recovers() abort
  let Callback = s:start()
  call s:reply(Callback, [{'label': 'recovered'}])
  call s:reply(Callback, [{'label': 'duplicate'}])
  call assert_equal(['recovered'], s:words())
endfunction

function! s:check(line, edit_start, request_col, keyword_byte, expected, incomplete, ...) abort
  call setline(1, a:line)
  call cursor(1, strlen(a:line))
  let item = {'label': 'matchDepTypes', 'insertTextFormat': 2, 'textEdit': {'range': {'start': {'line': 0, 'character': a:edit_start}, 'end': {'line': 0, 'character': a:request_col}}, 'newText': get(a:000, 0, '"matchDepTypes"')}}
  let Callback = s:start(a:keyword_byte)
  call assert_equal({'line': 0, 'character': a:request_col}, g:test_lsp_requests[-1].params.position)
  call s:reply(Callback, {'items': [item], 'isIncomplete': a:incomplete})
  call assert_equal([a:expected], s:words())
  call assert_equal(a:incomplete, g:deoplete#source#vim_lsp#_incomplete)
  call assert_equal(1, g:deoplete#source#vim_lsp#_done)
  let managed = lsp#omni#get_managed_user_data_from_completed_item(g:deoplete#source#vim_lsp#_items[0])
  call assert_equal(item, managed.completion_item)
endfunction

call s:check('  " ', 2, 3, 3, 'matchDepTypes"', 0)
call s:check('  "m ', 2, 4, 3, 'matchDepTypes"', 0)
" Byte offsets stay correct when preceding text contains multiple-byte characters.
call s:check('é "m ', 2, 4, 4, 'matchDepTypes"', 1)
call s:check('  m ', 2, 3, 2, '"matchDepTypes"', 0)
" Replacement text may change the punctuation before Deoplete's keyword start.
call s:check('#r ', 0, 2, 1, 'rgb', 0, 'rgb(${1:})')
call s:check('#r ', 0, 2, 1, 'red', 0, 'red')

" Exercise ordinary items and InsertReplaceEdit through the real vim-lsp converter.
let s:range = {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 3}}
for item in [
      \ {'label': 'print'},
      \ {'label': 'print', 'insertText': 'print'},
      \ {'label': 'print', 'insertTextFormat': 2, 'textEdit': {'insert': s:range, 'replace': s:range, 'newText': 'print(${1:})'}},
      \ ]
  call setline(1, 'pri ')
  call cursor(1, 4)
  call s:reply(s:start(), [item])
  call assert_equal(['print'], s:words())
  call assert_equal(0, g:deoplete#source#vim_lsp#_incomplete)
  call assert_equal(item, lsp#omni#get_managed_user_data_from_completed_item(g:deoplete#source#vim_lsp#_items[0]).completion_item)
endfor

" Items can have different replacement starts; trim their shared text individually.
call setline(1, '#r ')
call cursor(1, 3)
let s:items = [
      \ {'label': 'red', 'textEdit': {'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 2}}, 'newText': 'red'}},
      \ {'label': 'rgb', 'textEdit': {'range': {'start': {'line': 0, 'character': 1}, 'end': {'line': 0, 'character': 2}}, 'newText': 'rgb'}},
      \ ]
call s:reply(s:start(1), {'items': s:items, 'isIncomplete': v:false})
call assert_equal(['red', 'rgb'], s:words())

" Only the newest request publishes, in any reply order.
call setline(1, 'pri ')
call cursor(1, 4)
let s:Old = s:start()
let s:New = s:start()
call assert_equal('textDocument/completion', g:test_lsp_requests[-1].method)
call s:reply(s:Old, [{'label': 'old'}])
call assert_equal(0, g:deoplete#source#vim_lsp#_done)
call s:reply(s:New, [{'label': 'new'}])
call s:reply(s:Old, [{'label': 'old'}])
call assert_equal(['new'], s:words())

" Clearing disowns a pending request and resets a published result.
let s:Callback = s:start()
call deoplete_vim_lsp#clear()
call s:reply(s:Callback, [{'label': 'cleared'}])
call assert_equal(0, g:deoplete#source#vim_lsp#_done)
call assert_equal([], g:deoplete#source#vim_lsp#_items)
call s:assert_recovers()
call deoplete_vim_lsp#clear()
call assert_equal([0, [], 0], [g:deoplete#source#vim_lsp#_done, g:deoplete#source#vim_lsp#_items, g:deoplete#source#vim_lsp#_incomplete])

" Bad envelopes and results finish immediately and stay retryable.
for data in [v:null, [], {}, {'response': v:null}, {'response': []},
      \ {'response': {'result': 42}}, {'response': {'result': 'invalid'}},
      \ {'response': {'result': {'items': {}, 'isIncomplete': v:false}}},
      \ {'response': {'result': {'items': []}}},
      \ {'response': {'result': [{'textEdit': {}}]}},
      \ {'response': {'error': {'code': -32800, 'message': 'cancelled'}}}]
  let s:Callback = s:start()
  let s:threw = ''
  try
    call call(s:Callback, [data])
  catch
    let s:threw = v:exception
  endtry
  call assert_equal('', s:threw, string(data))
  call s:assert_failed(string(data))
  call s:reply(s:Callback, [{'label': 'replayed'}])
  call s:assert_failed(string(data))
  call s:assert_recovers()
endfor

" A null result is valid LSP, unlike a malformed result.
call s:reply(s:start(), v:null)
call assert_equal([1, [], 0], [g:deoplete#source#vim_lsp#_done, g:deoplete#source#vim_lsp#_items, g:deoplete#source#vim_lsp#_incomplete])

" Server errors are logged.
let g:deoplete#sources#vim_lsp#log = tempname()
call call(s:start(), [{'response': {'error': {'code': -32603, 'message': 'failed'}}}])
call assert_match('completion error.*failed', join(readfile(g:deoplete#sources#vim_lsp#log)))
call delete(g:deoplete#sources#vim_lsp#log)
let g:deoplete#sources#vim_lsp#log = ''

" The timeout ends the wait; a late reply still publishes once.
let s:Callback = s:start()
sleep 1100m
call s:assert_failed('timeout')
call s:reply(s:Callback, [{'label': 'late'}])
call s:reply(s:Callback, [{'label': 'duplicate'}])
call assert_equal(['late'], s:words())

" A timer left over from an older request cannot end a newer one.
let s:Old = s:start()
let s:Captured = get(s:Old, 'args')[1]
let s:New = s:start()
call s:Finish(s:Captured, [], 1, 0)
call assert_equal(0, g:deoplete#source#vim_lsp#_done)
call s:reply(s:New, [{'label': 'newest'}])
call assert_equal(['newest'], s:words())

" Replacing or deleting the prefix, or leaving the line, makes a reply stale.
for change in ['replace', 'delete', 'line']
  call setline(1, ['header', 'pri tail'])
  call cursor(2, 4)
  let s:Callback = s:start()
  if change ==# 'line'
    call cursor(1, 4)
  else
    call setline(2, change ==# 'replace' ? 'pro tail' : 'pr tail')
    call cursor(2, change ==# 'replace' ? 4 : 3)
  endif
  call s:reply(s:Callback, [{'label': 'stale'}])
  call s:assert_failed(change)
  call s:assert_recovers()
endfor

" Growing the prefix (also multibyte) keeps the reply to the original request.
for prefix in ['pri', 'pré']
  call setline(1, ['header', prefix . ' tail'])
  call cursor(2, strlen(prefix) + 1)
  let s:Callback = s:start()
  call setline(2, prefix . 'nt tail')
  call cursor(2, strlen(prefix) + 3)
  call s:reply(s:Callback, [{'label': 'print'}])
  call assert_equal(['print'], s:words())
endfor

" A pending request must not publish into another buffer, even before BufEnter is processed.
let s:Callback = s:start()
noautocmd new
call setline(1, 'pri ')
call cursor(1, 4)
call s:reply(s:Callback, [{'label': 'wrong_buffer'}])
call s:assert_failed('wrong buffer')
call s:assert_recovers()

if !empty(v:errors)
  call writefile(v:errors, $LAB . '/bridge-errors.txt')
  cquit
endif
qa!
