call tcomment#DefineType('markdown', '<!-- %s -->')
call tcomment#DefineType('markdown_block', g:tcommentBlockXML)
call tcomment#DefineType('markdown_inline', g:tcommentInlineXML)
nnoremap <Buffer> <LocalLeader>v :call vimproc#system_bg('reveal-md ' . expand('%'))<CR>
setlocal complete+=s
setlocal formatprg=par
setlocal spelllang=en_us
setlocal wrap
