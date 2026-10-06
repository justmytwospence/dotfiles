" Airline theme using only ANSI terminal colors.
" Defers to the terminal palette -- no hardcoded hex values.
"
" Format: [guifg, guibg, ctermfg, ctermbg, opts]
" We only care about cterm values (indices 2-4).

let g:airline#themes#ansi#palette = {}

" Normal mode: white on dark gray
let s:N1 = ['', '', 15, 8, 'bold']
let s:N2 = ['', '', 7, 0, '']
let s:N3 = ['', '', 7, 'NONE', '']
let g:airline#themes#ansi#palette.normal = airline#themes#generate_color_map(s:N1, s:N2, s:N3)

" Insert mode: black on cyan
let s:I1 = ['', '', 0, 6, 'bold']
let s:I2 = s:N2
let s:I3 = s:N3
let g:airline#themes#ansi#palette.insert = airline#themes#generate_color_map(s:I1, s:I2, s:I3)

" Visual mode: black on magenta
let s:V1 = ['', '', 0, 5, 'bold']
let s:V2 = s:N2
let s:V3 = s:N3
let g:airline#themes#ansi#palette.visual = airline#themes#generate_color_map(s:V1, s:V2, s:V3)

" Replace mode: black on red
let s:R1 = ['', '', 0, 1, 'bold']
let s:R2 = s:N2
let s:R3 = s:N3
let g:airline#themes#ansi#palette.replace = airline#themes#generate_color_map(s:R1, s:R2, s:R3)

" Inactive windows
let s:IA = ['', '', 8, 0, '']
let g:airline#themes#ansi#palette.inactive = airline#themes#generate_color_map(s:IA, s:IA, s:IA)

" Tabline
let g:airline#themes#ansi#palette.tabline = {
      \ 'airline_tab':     ['', '', 7,    0,    ''],
      \ 'airline_tabsel':  ['', '', 15,   8,    'bold'],
      \ 'airline_tabfill': ['', '', 8,    'NONE', ''],
      \ 'airline_tabmod':  ['', '', 0,    6,    'bold'],
      \ }
