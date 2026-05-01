hi clear

let g:colors_name = 'ansi'
set notermguicolors

" ANSI color scheme -- defers all color decisions to the terminal emulator.
" Maps vim highlight groups to the 16 ANSI color indices (0-15) only.
"
" 0: Black        |   8: Bright Black (dark gray)
" 1: Red          |   9: Bright Red
" 2: Green        |  10: Bright Green
" 3: Yellow       |  11: Bright Yellow
" 4: Blue         |  12: Bright Blue
" 5: Magenta      |  13: Bright Magenta
" 6: Cyan         |  14: Bright Cyan
" 7: White (gray) |  15: Bright White
"
" GUI fallback (MacVim, gvim, termguicolors): mirrors the selenized-light
" palette set in ghostty's custom-light theme, so GUI vim looks the same as
" terminal vim running under the light ghostty palette.

let s:gui = [
  \ '#ece3cc', '#d2212d', '#489100', '#ad8900',
  \ '#0072d4', '#ca4898', '#009c8f', '#909995',
  \ '#d5cdb6', '#cc1729', '#428b00', '#a78300',
  \ '#006dce', '#c44392', '#00978a', '#3a4d53',
  \ ]

function! s:Hi(group, fg, bg, attr) abort
  let l:gfg = (a:fg is# 'NONE') ? 'NONE' : s:gui[a:fg]
  let l:gbg = (a:bg is# 'NONE') ? 'NONE' : s:gui[a:bg]
  execute 'hi' a:group
        \ 'ctermfg=' . a:fg 'ctermbg=' . a:bg 'cterm=' . a:attr
        \ 'guifg=' . l:gfg 'guibg=' . l:gbg 'gui=' . a:attr
endfunction

" Editor
call s:Hi('NonText', 0, 'NONE', 'NONE')
call s:Hi('Ignore', 'NONE', 'NONE', 'NONE')
call s:Hi('Underlined', 'NONE', 'NONE', 'underline')
call s:Hi('Bold', 'NONE', 'NONE', 'bold')
call s:Hi('Italic', 'NONE', 'NONE', 'italic')
call s:Hi('StatusLine', 15, 8, 'NONE')
call s:Hi('StatusLineNC', 15, 0, 'NONE')
call s:Hi('VertSplit', 8, 'NONE', 'NONE')
call s:Hi('TabLine', 7, 0, 'NONE')
call s:Hi('TabLineFill', 0, 'NONE', 'NONE')
call s:Hi('TabLineSel', 0, 6, 'NONE')
call s:Hi('Title', 4, 'NONE', 'bold')
call s:Hi('CursorLine', 'NONE', 0, 'NONE')
call s:Hi('Cursor', 0, 15, 'NONE')
call s:Hi('CursorColumn', 'NONE', 0, 'NONE')
call s:Hi('LineNr', 8, 'NONE', 'NONE')
call s:Hi('CursorLineNr', 6, 'NONE', 'NONE')
call s:Hi('helpLeadBlank', 'NONE', 'NONE', 'NONE')
call s:Hi('helpNormal', 'NONE', 'NONE', 'NONE')
call s:Hi('Visual', 15, 8, 'bold')
call s:Hi('VisualNOS', 15, 8, 'bold')
call s:Hi('Pmenu', 15, 0, 'NONE')
call s:Hi('PmenuSbar', 7, 8, 'NONE')
call s:Hi('PmenuSel', 15, 8, 'bold')
call s:Hi('PmenuThumb', 'NONE', 7, 'NONE')
call s:Hi('FoldColumn', 7, 'NONE', 'NONE')
call s:Hi('Folded', 12, 'NONE', 'NONE')
call s:Hi('WildMenu', 15, 0, 'NONE')
call s:Hi('SpecialKey', 0, 'NONE', 'NONE')
call s:Hi('IncSearch', 0, 1, 'NONE')
call s:Hi('CurSearch', 0, 3, 'NONE')
call s:Hi('Search', 0, 11, 'NONE')
call s:Hi('Directory', 4, 'NONE', 'NONE')
call s:Hi('MatchParen', 3, 0, 'underline')
call s:Hi('SpellBad', 'NONE', 'NONE', 'undercurl')
call s:Hi('SpellCap', 'NONE', 'NONE', 'undercurl')
call s:Hi('SpellLocal', 'NONE', 'NONE', 'undercurl')
call s:Hi('SpellRare', 'NONE', 'NONE', 'undercurl')
call s:Hi('ColorColumn', 'NONE', 8, 'NONE')
call s:Hi('SignColumn', 7, 'NONE', 'NONE')
call s:Hi('ModeMsg', 0, 15, 'bold')
call s:Hi('MoreMsg', 4, 'NONE', 'NONE')
call s:Hi('Question', 4, 'NONE', 'NONE')
call s:Hi('QuickFixLine', 14, 0, 'NONE')
call s:Hi('Conceal', 8, 'NONE', 'NONE')
call s:Hi('ToolbarLine', 15, 0, 'NONE')
call s:Hi('ToolbarButton', 15, 8, 'NONE')
call s:Hi('debugPC', 7, 'NONE', 'NONE')
call s:Hi('debugBreakpoint', 8, 'NONE', 'NONE')
call s:Hi('ErrorMsg', 1, 'NONE', 'bold,italic')
call s:Hi('WarningMsg', 11, 'NONE', 'NONE')
call s:Hi('DiffAdd', 0, 10, 'NONE')
call s:Hi('DiffChange', 0, 12, 'NONE')
call s:Hi('DiffDelete', 0, 9, 'NONE')
call s:Hi('DiffText', 0, 14, 'NONE')
call s:Hi('diffAdded', 10, 'NONE', 'NONE')
call s:Hi('diffRemoved', 9, 'NONE', 'NONE')
call s:Hi('diffChanged', 12, 'NONE', 'NONE')
call s:Hi('diffOldFile', 11, 'NONE', 'NONE')
call s:Hi('diffNewFile', 13, 'NONE', 'NONE')
call s:Hi('diffFile', 12, 'NONE', 'NONE')
call s:Hi('diffLine', 7, 'NONE', 'NONE')
call s:Hi('diffIndexLine', 14, 'NONE', 'NONE')
call s:Hi('healthError', 1, 'NONE', 'NONE')
call s:Hi('healthSuccess', 2, 'NONE', 'NONE')
call s:Hi('healthWarning', 3, 'NONE', 'NONE')

" Git gutter
call s:Hi('GitGutterAdd', 2, 'NONE', 'NONE')
call s:Hi('GitGutterChange', 3, 'NONE', 'NONE')
call s:Hi('GitGutterChangeDelete', 3, 'NONE', 'NONE')
call s:Hi('GitGutterDelete', 1, 'NONE', 'NONE')

" Syntax
call s:Hi('Comment', 8, 'NONE', 'italic')
call s:Hi('Constant', 3, 'NONE', 'NONE')
call s:Hi('Error', 1, 'NONE', 'NONE')
call s:Hi('Identifier', 9, 'NONE', 'NONE')
call s:Hi('Function', 4, 'NONE', 'NONE')
call s:Hi('Special', 13, 'NONE', 'NONE')
call s:Hi('Statement', 5, 'NONE', 'NONE')
call s:Hi('String', 2, 'NONE', 'NONE')
call s:Hi('Operator', 6, 'NONE', 'NONE')
call s:Hi('Boolean', 3, 'NONE', 'NONE')
call s:Hi('Label', 14, 'NONE', 'NONE')
call s:Hi('Keyword', 5, 'NONE', 'NONE')
call s:Hi('Exception', 5, 'NONE', 'NONE')
call s:Hi('Conditional', 5, 'NONE', 'NONE')
call s:Hi('PreProc', 13, 'NONE', 'NONE')
call s:Hi('Include', 5, 'NONE', 'NONE')
call s:Hi('Macro', 5, 'NONE', 'NONE')
call s:Hi('StorageClass', 11, 'NONE', 'NONE')
call s:Hi('Structure', 11, 'NONE', 'NONE')
call s:Hi('Todo', 0, 9, 'bold')
call s:Hi('Type', 11, 'NONE', 'NONE')

" Neovim-only highlights (treesitter, floats)
if has('nvim')
  call s:Hi('NormalFloat', 15, 0, 'NONE')
  call s:Hi('FloatBorder', 7, 0, 'NONE')
  call s:Hi('FloatShadow', 15, 0, 'NONE')

  " Treesitter
  call s:Hi('@variable', 15, 'NONE', 'NONE')
  call s:Hi('@variable.builtin', 1, 'NONE', 'NONE')
  call s:Hi('@variable.parameter', 1, 'NONE', 'NONE')
  call s:Hi('@variable.member', 1, 'NONE', 'NONE')
  call s:Hi('@constant.builtin', 5, 'NONE', 'NONE')
  call s:Hi('@string.regexp', 1, 'NONE', 'NONE')
  call s:Hi('@string.escape', 6, 'NONE', 'NONE')
  call s:Hi('@string.special.url', 4, 'NONE', 'underline')
  call s:Hi('@string.special.symbol', 13, 'NONE', 'NONE')
  call s:Hi('@type.builtin', 3, 'NONE', 'NONE')
  call s:Hi('@property', 1, 'NONE', 'NONE')
  call s:Hi('@function.builtin', 5, 'NONE', 'NONE')
  call s:Hi('@constructor', 11, 'NONE', 'NONE')
  call s:Hi('@keyword.coroutine', 1, 'NONE', 'NONE')
  call s:Hi('@keyword.function', 5, 'NONE', 'NONE')
  call s:Hi('@keyword.return', 5, 'NONE', 'NONE')
  call s:Hi('@keyword.export', 14, 'NONE', 'NONE')
  call s:Hi('@punctuation.bracket', 15, 'NONE', 'NONE')
  call s:Hi('@comment.error', 0, 9, 'NONE')
  call s:Hi('@comment.warning', 0, 11, 'NONE')
  call s:Hi('@comment.todo', 0, 12, 'NONE')
  call s:Hi('@comment.note', 0, 14, 'NONE')
  call s:Hi('@markup', 15, 'NONE', 'NONE')
  call s:Hi('@markup.strong', 15, 'NONE', 'bold')
  call s:Hi('@markup.italic', 15, 'NONE', 'italic')
  call s:Hi('@markup.strikethrough', 15, 'NONE', 'strikethrough')
  call s:Hi('@markup.heading', 4, 'NONE', 'bold')
  call s:Hi('@markup.quote', 6, 'NONE', 'NONE')
  call s:Hi('@markup.math', 4, 'NONE', 'NONE')
  call s:Hi('@markup.link.url', 5, 'NONE', 'underline')
  call s:Hi('@markup.raw', 14, 'NONE', 'NONE')
  call s:Hi('@markup.list.checked', 2, 'NONE', 'NONE')
  call s:Hi('@markup.list.unchecked', 7, 'NONE', 'NONE')
  call s:Hi('@tag', 5, 'NONE', 'NONE')
  call s:Hi('@tag.builtin', 6, 'NONE', 'NONE')
  call s:Hi('@tag.attribute', 4, 'NONE', 'NONE')
  call s:Hi('@tag.delimiter', 15, 'NONE', 'NONE')

  hi link @variable.parameter.builtin @variable.parameter
  hi link @constant Constant
  hi link @constant.macro Macro
  hi link @module Structure
  hi link @module.builtin Special
  hi link @label Label
  hi link @string String
  hi link @string.special Special
  hi link @character Character
  hi link @character.special SpecialChar
  hi link @boolean Boolean
  hi link @number Number
  hi link @number.float Float
  hi link @type Type
  hi link @type.definition Type
  hi link @attribute Constant
  hi link @attribute.builtin Constant
  hi link @function Function
  hi link @function.call Function
  hi link @function.method Function
  hi link @function.method.call Function
  hi link @operator Operator
  hi link @keyword Keyword
  hi link @keyword.operator Operator
  hi link @keyword.import Include
  hi link @keyword.type Keyword
  hi link @keyword.modifier Keyword
  hi link @keyword.repeat Repeat
  hi link @keyword.debug Exception
  hi link @keyword.exception Exception
  hi link @keyword.conditional Conditional
  hi link @keyword.conditional.ternary Operator
  hi link @keyword.directive PreProc
  hi link @keyword.directive.define Define
  hi link @punctuation.delimiter Delimiter
  hi link @punctuation.special Special
  hi link @comment Comment
  hi link @comment.documentation Comment
  hi link @markup.underline underline
  hi link @markup.link Tag
  hi link @markup.link.label Label
  hi link @markup.list Special
  hi link @diff.plus diffAdded
  hi link @diff.minus diffRemoved
  hi link @diff.delta diffChanged
endif
