(defun centered-cursor-mode-off () (centered-cursor-mode -1))

(evil-define-state menu
  "Minimal Evil state for navigating menus and lists."
  :cursor (nil)
  :enable (emacs)
  :entry-hook (hl-line-mode)
  :tag "≡")

(evil-define-state view
  "Emacs state with a few extras."
  :cursor (nil)
  :enable (emacs)
  :entry-hook (centered-cursor-mode-off)
  :tag "+")

(provide 'my-evil)
