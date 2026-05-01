" settings
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

Plug 'airblade/vim-gitgutter'
let g:gitgutter_realtime = 1

Plug 'ap/vim-css-color', {'for': ['css', 'less', 'sass', 'scss']}

Plug 'aymericbeaumet/vim-symlink'

Plug 'bruno-/vim-husk'

Plug 'chaoren/vim-wordmotion'

Plug 'chrisbra/csv.vim', {'for': 'csv'}
let g:csv_autocmd_arrange = 1
let g:csv_autocmd_arrange_size = 1024 * 1024
let g:csv_hiGroup = 'CSVFocus'
let g:csv_highlight_column = 'y'

Plug 'christoomey/vim-sort-motion'
let g:sort_motion_flags = 'iu'

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

Plug 'jremmen/vim-ripgrep'

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

Plug 'PhilRunninger/nerdtree-visual-selection'

Plug 'ryanoasis/vim-devicons'

Plug 'scrooloose/nerdtree-project-plugin'

Plug 'tiagofumo/vim-nerdtree-syntax-highlight'

Plug 'Xuyuanp/nerdtree-git-plugin'

Plug 'pangloss/vim-javascript', {'for': 'javascript'}
let g:javascript_enable_domhtmlcss = 1

Plug 'qpkorr/vim-bufkill'

Plug 'raimondi/delimitmate'

nnoremap <Leader>/ :Rg<Space>

Plug 'rstacruz/vim-opinion'

Plug 'simnalamburt/vim-mundo', {'on': ['MundoToggle', 'MundoShow']}
nnoremap <Leader>u :MundoToggle<CR>

Plug 'stephpy/vim-yaml', {'for': 'yaml'}
let g:yaml_imit_spell = 1

Plug 'mg979/vim-visual-multi'

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
nnoremap <Leader>gs :Git<CR>
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

if !has('nvim')
  Plug 'vim-airline/vim-airline'
  let g:airline_theme = 'ansi'
  let g:airline#extensions#tabline#enabled = 1
endif

Plug 'vim-scripts/rangemacro'

Plug 'vim-scripts/restore_view.vim'

Plug 'chriskempson/vim-tomorrow-theme'

Plug 'wellle/targets.vim'

Plug 'xolox/vim-lua-ftplugin', {'for': 'lua'}

call plug#end()
runtime! plugin/sensible.vim
runtime! plugin/opinion.vim

" theme
set notermguicolors
set background=dark
colorscheme ansi
highlight Identifier cterm=NONE
highlight Statement cterm=NONE

" mappings

" save
noremap <Leader>s :update<CR>

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

  " cursor shape (block=normal, bar=insert, underline=replace)
  let &t_SI = "\e[5 q"
  let &t_SR = "\e[3 q"
  let &t_EI = "\e[1 q"
  autocmd VimEnter * silent! execute '!echo -ne "\e[1 q"' | redraw!
  autocmd VimLeave * silent! execute '!echo -ne "\e[5 q"' | redraw!
augroup end
