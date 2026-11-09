function! deoplete_vim_lsp#log(...) abort
    if !empty(g:deoplete#sources#vim_lsp#log)
        call writefile([strftime('%c') . ':' . json_encode(a:000)], g:deoplete#sources#vim_lsp#log, 'a')
    endif
endfunction

let s:timer = -1
let s:request = {}

" Disown the pending request and reset the published result.
function! deoplete_vim_lsp#clear() abort
    call timer_stop(s:timer)
    " Callbacks may outlive the request; do not let them retain the buffer copy.
    let s:request.lines = []
    let s:request = {}
    let g:deoplete#source#vim_lsp#_items = []
    let g:deoplete#source#vim_lsp#_incomplete = 0
    let g:deoplete#source#vim_lsp#_done = 0
endfunction

function! deoplete_vim_lsp#request(server_name, complete_position) abort
    call deoplete_vim_lsp#clear()
    let l:server = lsp#get_server_info(a:server_name)
    let l:request = {
        \ 'bufnr': bufnr('%'),
        \ 'position': lsp#get_position(),
        \ 'complete_position': a:complete_position,
        \ 'input': strpart(getline('.'), 0, col('.') - 1),
        \ 'changedtick': b:changedtick,
        \ 'lines': getline(1, '$'),
        \ 'published': 0,
        \ }
    let s:request = l:request
    let s:timer = timer_start(1000, function('s:finish_request', [l:request, [], 1]))
    call lsp#send_request(a:server_name, {
        \ 'method': 'textDocument/completion',
        \ 'params': {
        \   'textDocument': lsp#get_text_document_identifier(),
        \   'position': l:request.position,
        \ },
        \ 'on_notification': function('s:handle_completion', [l:server, l:request]),
        \ })
endfunction

" The buffer is as requested, apart from text typed after the requested input.
function! s:is_current(request) abort
    let l:input = strpart(getline('.'), 0, col('.') - 1)
    if a:request.bufnr != bufnr('%') || a:request.position.line + 1 != line('.')
        \ || stridx(l:input, a:request.input) != 0
        return 0
    endif
    if a:request.changedtick == b:changedtick
        return 1
    endif
    " Typing changes the tick too. Undo the typed growth and compare the rest,
    " so results (and their additional edits) are not reused after other edits.
    let l:lines = getline(1, '$')
    let l:lines[line('.') - 1] = a:request.input . strpart(getline('.'), strlen(l:input))
    return l:lines ==# a:request.lines
endfunction

function! deoplete_vim_lsp#matches_context() abort
    return !empty(s:request) && s:is_current(s:request)
endfunction

function! s:finish_request(request, items, incomplete, ...) abort
    if a:request isnot s:request || a:request.published
        return
    endif
    call timer_stop(s:timer)
    let g:deoplete#source#vim_lsp#_items = a:items
    let g:deoplete#source#vim_lsp#_incomplete = a:incomplete
    let g:deoplete#source#vim_lsp#_done = 1
    " A timer call passes its timer ID: end the wait but let a slow reply publish once.
    let a:request.published = !a:0
    if index(['i', 'ic', 'ix'], mode()) >= 0
        call deoplete#auto_complete()
    endif
endfunction

function! s:handle_completion(server, request, data) abort
    if a:request isnot s:request || a:request.published
        return
    endif
    try
        if !has_key(a:data, 'response') || !has_key(a:data.response, 'result')
            if lsp#client#is_error(get(a:data, 'response', {}))
                call deoplete_vim_lsp#log('completion error', a:data.response)
            endif
            call s:finish_request(a:request, [], 1)
            return
        endif
        let l:result = a:data.response.result
        if !s:is_current(a:request) || l:result isnot v:null && type(l:result) != type([])
            \ && (type(l:result) != type({}) || type(get(l:result, 'items', v:null)) != type([]))
            call s:finish_request(a:request, [], 1)
            return
        endif
        let l:options = {
            \ 'server': a:server,
            \ 'position': a:request.position,
            \ 'response': a:data['response'],
            \ }
        let l:completion = lsp#omni#get_vim_completion_items(l:options)
        " Only remove leading text that Deoplete already keeps before its keyword start.
        let l:offset = max([0, a:request.complete_position - (l:completion['startcol'] - 1)])
        let l:prefix = strpart(getline('.'), l:completion['startcol'] - 1, l:offset)
        let l:items = map(l:completion['items'], 'extend(v:val, {"word": stridx(v:val.word, l:prefix) == 0 ? strpart(v:val.word, l:offset) : v:val.word})')
        call s:finish_request(a:request, l:items, l:completion['incomplete'])
    catch
        call s:finish_request(a:request, [], 1)
        call deoplete_vim_lsp#log('handle error', v:exception, v:throwpoint)
    endtry
endfunction
