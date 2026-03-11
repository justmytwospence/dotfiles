" MacVim GUI theme -- auto-switch with macOS appearance
" Terminal vim is unaffected (uses ANSI colorscheme via .vimrc)

set termguicolors

function! s:SetAppearanceTheme()
  if v:os_appearance == 1
    set background=dark
    colorscheme Tomorrow-Night
  else
    set background=light
    colorscheme solarized
  endif
endfunction

call s:SetAppearanceTheme()

autocmd OSAppearanceChanged * call s:SetAppearanceTheme()
