" settings
let g:netrw_bufsettings = 'number'
let g:netrw_liststyle = 1

set clipboard=unnamedplus,unnamed
set cursorline
set diffopt=filler,vertical
set fillchars=vert:\ ,fold:─
set guifont=Hack\ 11
set guioptions-=aegimrLtT
set list listchars=tab:\ \ ,trail:·,extends:❯,precedes:❮
set nogdefault
set omnifunc=syntaxcomplete#Complete
set relativenumber
set scrolloff=10
set smartcase
set spelllang=en_us
set splitbelow
set splitright
set undodir=~/.vim/undo
set undofile
set viewoptions=cursor,folds,slash,unix

" plugins
filetype off
let mapleader = "\<Space>"
let maplocalleader  =  ","
set encoding=utf-8
set nocompatible
call plug#begin('~/.vim/plugins')

Plug 'chriskempson/base16-vim'

Plug 'airblade/vim-gitgutter'
let g:gitgutter_realtime = 1

Plug 'ap/vim-css-color', {'for': ['css', 'less', 'sass', 'scss']}

Plug 'bruno-/vim-husk'

Plug 'chrisbra/csv.vim', {'for': 'csv'}
let g:csv_autocmd_arrange = 1
let g:csv_autocmd_arrange_size = 1024 * 1024
let g:csv_hiGroup = 'CSVFocus'
let g:csv_highlight_column = 'y'

Plug 'christoomey/vim-sort-motion'
let g:sort_motion_flags = 'ui'

Plug 'ctrlpvim/ctrlp.vim' | Plug 'amiorin/ctrlp-z'
let g:ctrlp_cmd = 'CtrlPLastMode'
let g:ctrlp_follow_symlinks = 1
let g:ctrlp_open_multiple_files = 'i'
let g:ctrlp_open_new_file = 'r'
let g:ctrlp_regexp = 1
let g:ctrlp_show_hidden = 1
let g:ctrlp_working_path_mode = 'a'
nnoremap <Leader>sd :CtrlPZ<Cr>
nnoremap <Leader>sf :CtrlPF<Cr>

Plug 'chr4/nginx.vim'

Plug 'davidhalter/jedi-vim', {'for': 'python'}
let g:jedi#goto_assignments_command = '<LocalLeader>g'
let g:jedi#goto_definitions_command = '<LocalLeader>d'
let g:jedi#popup_on_dot = 0
let g:jedi#rename_command = '<LocalLeader>r'
let g:jedi#usages_command = '<LocalLeader>n'
let g:jedi#use_tabs_not_buffers = 0

Plug 'derekwyatt/vim-scala'

Plug 'dzeban/vim-log-syntax'

Plug 'exu/pgsql.vim'
let g:sql_type_default = 'pgsql'

Plug 'guns/vim-clojure-static', {'for': 'clojure'}

Plug 'guns/vim-sexp', {'for': 'clojure'}

Plug 'haya14busa/vim-asterisk'

Plug 'jelera/vim-javascript-syntax', {'for': 'javascript'}

Plug 'jpalardy/vim-slime'
let g:slime_python_ipython = 1
let g:slime_target = 'tmux'

Plug 'junegunn/vim-easy-align'
nmap ga <Plug>(EasyAlign)
vmap ga <Plug>(EasyAlign)

Plug 'junegunn/vim-oblique'
let g:oblique#incsearch_highlight_all = 1
let g:oblique#very_magic = 1

Plug 'junegunn/vim-pseudocl'

Plug 'kien/rainbow_parentheses.vim'

Plug 'myusuf3/numbers.vim'
let g:numbers_exclude = ['help', 'mail', 'qf', 'terminal']

Plug 'michaeljsmith/vim-indent-object'

Plug 'mitsuhiko/vim-jinja'

Plug 'pangloss/vim-javascript', {'for': 'javascript'}
let g:javascript_enable_domhtmlcss = 1

Plug 'qpkorr/vim-bufkill'

Plug 'raimondi/delimitmate'

Plug 'rking/ag.vim', {'on': 'Ag'}
nnoremap <Leader>/ :Ag<Space>

Plug 'rstacruz/vim-opinion'

Plug 'scrooloose/syntastic', {'on': 'Errors'}
let g:syntastic_aggregate_errors = 1
let g:syntastic_always_populate_loc_list = 1
let g:syntastic_check_on_open = 1
let g:syntastic_error_symbol = '✗'
let g:syntastic_python_checkers = ['python', 'pep8', 'pyflakes', 'pep257']
let g:syntastic_python_pep8_args = '--ignore = E128,E501'
let g:syntastic_style_error_symbol = '✗'
let g:syntastic_style_warning_symbol = '✗'
let g:syntastic_warning_symbol = '✗'
nnoremap <Leader>e :Errors<CR>

Plug 'simnalamburt/vim-mundo', {'on': ['MundoToggle', 'MundoShow']}
nnoremap <Leader>u :MundoToggle<CR>

if (system('uname') =~ "Darwin")
  Plug 'sjl/vitality.vim'
  let g:vitality_always_assume_iterm = 1
endif

Plug 'stephpy/vim-yaml', {'for': 'yaml'}
let g:yaml_imit_spell = 1

Plug 'tell-k/vim-autopep8', {'for': 'python'}
let g:autopep8_disable_show_diff = 0

Plug 'terryma/vim-multiple-cursors'

Plug 'coderifous/textobj-word-column.vim'

Plug 'tomtom/tcomment_vim'

Plug 'tpope/vim-eunuch'

Plug 'tpope/vim-fugitive'
nnoremap <Leader>gc :Git commit<CR>
nnoremap <Leader>gd :Git diff<CR>
nnoremap <Leader>gl :Git pull<CR>
nnoremap <Leader>gm :Gmove<Space>
nnoremap <Leader>gp :Git push<CR>
nnoremap <Leader>gr :Gread<CR>
nnoremap <Leader>gs :Gstatus<CR>
nnoremap <Leader>gw :Gwrite<CR>

Plug 'tpope/vim-git'

Plug 'tpope/vim-haml'

Plug 'tpope/vim-jdaddy', {'for': 'json'}

Plug 'tpope/vim-repeat'

Plug 'tpope/vim-sensible'

Plug 'tpope/vim-sexp-mappings-for-regular-people', {'for': 'clojure'}

Plug 'tpope/vim-surround'

Plug 'tpope/vim-unimpaired'

Plug 'tpope/vim-vinegar'

Plug 'vim-airline/vim-airline'
let g:airline#extensions#tabline#enabled = 1

Plug 'vim-airline/vim-airline-themes'

Plug 'vim-scripts/rangemacro'

Plug 'vim-scripts/restore_view.vim'

Plug 'wellle/targets.vim'

Plug 'xolox/vim-lua-ftplugin', {'for': 'lua'}

if v:version >=  704
  Plug 'sirver/ultisnips' | Plug 'honza/vim-snippets'
  let g:UltiSnipsJumpBackwardTrigger = '<S-tab>'
  let g:UltiSnipsJumpForwardTrigger = '<tab>'
endif

call plug#end()
runtime! plugin/sensible.vim
runtime! plugin/opinion.vim

" theme
colorscheme base16-tomorrow-night
let base16colorspace=256
set background=dark

highlight CSVColumnEven ctermfg=lightgray
highlight CSVColumnOdd ctermfg=gray
highlight CSVFocus ctermfg=2
highlight CursorLineNr ctermbg=NONE guibg=NONE
highlight Folded ctermbg=NONE
highlight GitGutterAdd ctermbg=NONE guibg=NONE
highlight GitGutterChange ctermbg=NONE guibg=NONE
highlight GitGutterChangeDelete ctermbg=NONE guibg=NONE
highlight GitGutterDelete ctermbg=NONE guibg=NONE
highlight LineNr ctermbg=NONE guibg=NONE guibg=NONE
highlight Normal ctermbg=NONE
highlight Search ctermfg=black
highlight SignChange ctermbg=NONE
highlight SignColumn ctermbg=NONE

" mappings

" ctrl-backspace
noremap! <C-h> <C-w>

nnoremap g@ :set operatorfunc=LinewiseMacro<CR>g@
function! LinewiseMacro(type, ...)
  if a:0
    '<,'>normal @q
  elseif a:type == 'line'
    '[,']normal @q
  endif
endfunction

" j/k visual lines bar
nnoremap j gj
nnoremap k gk

" switch history search mappings
cnoremap <C-n> <Down>
cnoremap <C-p> <Up>
cnoremap <Down> <C-n>
cnoremap <Up> <C-p>

" weaponize awk
nnoremap <Leader>a :%!awk<Space>
vnoremap <Leader>a :!awk<Space>

" clean trailing whitespace
nnoremap <Leader>w mz:%s/\s\+$//<cr>:let @/=''<cr>`z

" paste many times over selected text
xnoremap <expr> p 'pgv"'.v:register.'y`>'
xnoremap <expr> P 'Pgv"'.v:register.'y`>'

" autocommands
augroup autocommands
  autocmd!

  " refresh vimrc on save
  autocmd BufWritePost ~/.vimrc source ~/.vimrc

  " filetypes
  autocmd BufNewFile,BufRead *.ipy set filetype=python
  autocmd BufNewFile,BufRead *.md set filetype=markdown
  autocmd BufNewFile,BufRead *.vrt set filetype=xml

  " cursor shape on Linux
  if (system('uname') =~ "linux")
    autocmd VimEnter,InsertLeave * silent execute '!echo -ne "\e[1 q"' | redraw!
    autocmd InsertEnter,InsertChange *
          \ if v:insertmode == 'i' |
          \   silent execute '!echo -ne "\e[5 q"' | redraw! |
          \ elseif v:insertmode == 'r' |
          \   silent execute '!echo -ne "\e[3 q"' | redraw! |
          \ endif
    autocmd VimLeave * silent execute '!echo -ne "\e[ q"' | redraw!
  endif
augroup end
