;;; init.el --- Emacs configuration -*- lexical-binding: t -*-

(require 'cl-lib)

;; UI chrome, frame defaults, GC bump, and package-enable-at-startup live in
;; early-init.el (it runs before the first frame).

(setq use-short-answers t)

(setq completion-ignore-case t
      disabled-command-function nil
      epa-pinentry-mode 'loopback
      history-delete-duplicates t
      inhibit-splash-screen t
      initial-major-mode 'org-mode
      kill-buffer-query-functions nil
      load-prefer-newer t
      read-buffer-completion-ignore-case t
      read-file-name-completion-ignore-case t
      ring-bell-function #'ignore
      save-abbrevs 'silently
      temporary-file-directory "/tmp/"
      user-full-name "Spencer Boucher"
      user-mail-address "spencer@spencerboucher.com"
      vc-follow-symlinks t)

(setq-default fill-column 80
              indent-tabs-mode nil)

(add-hook 'emacs-startup-hook
          (defun my-reset-gc-cons-threshold ()
            (setq gc-cons-threshold (* 16 1024 1024))))

(defun my--repl-exit-hook (f)
  "Close current buffer when `exit' from process."
  (let ((f f))
    (when (ignore-errors (get-buffer-process (current-buffer)))
      (set-process-sentinel (get-buffer-process (current-buffer))
                            (lambda (proc change)
                              (when (string-match (rx (any "finished" "exited")) change)
                                (funcall f)))))))

(defun my--repl-mode ()
  "Activate a bundle of features for REPLs."
  (centered-cursor-mode -1)
  (company-mode)
  (my--repl-exit-hook #'kill-buffer-and-window)
  (rainbow-delimiters-mode-enable)
  (smartparens-mode)
  (visual-line-mode))

;; load-path: add elpa/ and site-lisp/ subdirs (created if missing).
(mapc (defun add-to-load-path (dir)
        (let ((default-directory (expand-file-name dir user-emacs-directory)))
          (unless (file-directory-p default-directory)
            (make-directory default-directory t))
          (normal-top-level-add-subdirs-to-load-path)))
      '("elpa" "site-lisp"))

;; package.el archives. (package-enable-at-startup is set in early-init.el.)
(require 'package)
(setq package-archives
      '(("melpa" . "https://melpa.org/packages/")
        ("melpa-stable" . "https://stable.melpa.org/packages/")
        ("gnu" . "https://elpa.gnu.org/packages/")
        ("nongnu" . "https://elpa.nongnu.org/nongnu/")))
(unless (bound-and-true-p package--initialized)
  (package-initialize))
;; First run on a fresh elpa/ has no archive cache yet; fetch it once so that
;; use-package's :ensure can install packages.
(unless package-archive-contents
  (package-refresh-contents))

;; use-package is built into Emacs 29+; no need to bootstrap-install it.
;; Enable :ensure everywhere and allow :vc git installs (Emacs 30 package-vc).
(require 'use-package)
(setq use-package-always-ensure t)

(use-package diminish
  :config
  (diminish 'centered-cursor-mode))

;; tree-sitter foundation
;; treesit-auto installs grammars on demand and sets major-mode-remap-alist +
;; auto-mode-alist for python/js/ts/tsx/json/yaml/bash/css/etc. Modes with a
;; tree-sitter grammar get the *-ts-mode variant; everything else falls back to
;; the classic mode. R has no native r-ts-mode (ESS issue #1239) -> stays
;; ess-r-mode. jtsx (loaded later) prepends its own jsx/tsx :mode entries so it
;; wins for .jsx/.tsx.
(use-package treesit-auto
  :custom
  (treesit-auto-install 'prompt)
  :config
  (treesit-auto-add-to-auto-mode-alist 'all)
  (global-treesit-auto-mode))

;; evil

(use-package evil
  :demand t
  :bind
  (:map evil-insert-state-map
   ("C-a" . beginning-of-visual-line)
   ("C-k" . kill-visual-line)
   ("C-v" . clipboard-yank)
   :map evil-menu-state-map
   ("/" . evil-search-forward)
   ("?" . evil-search-backward)
   (":" . evil-ex)
   ("C-d" . evil-scroll-down)
   ("C-u" . evil-scroll-up)
   ("G" . evil-goto-line)
   ("N" . evil-search-previous)
   ("gg" . evil-goto-first-line)
   ("j" . evil-next-line)
   ("k" . evil-previous-line)
   ("n" . evil-search-next)
   :map evil-motion-state-map
   ("ge" . evil-operator-eval)
   ("go" . evil-operator-org-capture)
   :map evil-normal-state-map
   ("$" . evil-end-of-visual-line)
   ("[ SPC" . evil-insert-line-below)
   ("] SPC" . evil-insert-line-above)
   ("[b" . bs-cycle-previous)
   ("]b" . bs-cycle-next)
   ("^" . evil-first-non-blank-of-visual-line)
   ("[f" . evil-unimpaired-previous-file)
   ("]f" . evil-unimpaired-next-file)
   ("ge" . evil-operator-eval)
   ("go" . evil-operator-org-capture)
   ("gx" . goto-address-at-point)
   ("j" . evil-next-visual-line)
   ("k" . evil-previous-visual-line)
   :map evil-operator-state-map
   ("oc" . toggle-cursorline)
   ("oh" . toggle-highlights)
   ("ol" . toggle-number)
   ("ow" . toggle-wrap)
   :map evil-view-state-map
   ("C-f" . evil-scroll-page-down)
   ("C-b" . evil-scroll-page-up)
   ("C-e" . evil-scroll-line-down)
   ("C-y" . evil-scroll-line-up))
  :init
  (setq evil-search-module 'evil-search
        evil-symbol-word-search t
        evil-want-C-u-scroll t
        evil-want-C-w-delete nil
        evil-want-C-w-in-emacs-state t
        evil-want-keybinding nil)
  :config
  (defun evil-insert-line-above ()
    (interactive)
    (evil-insert-newline-below)
    (forward-line -1))
  (defun evil-insert-line-below ()
    (interactive)
    (evil-insert-newline-above)
    (forward-line +1))
  (defun evil-unimpaired-previous-file ()
    (interactive)
    (-if-let (filename (evil-unimpaired-find-relative-filename -1))
        (find-file filename)
      (user-error "No previous file")))
  (defun evil-unimpaired-next-file ()
    (interactive)
    (-if-let (filename (evil-unimpaired-find-relative-filename 1))
        (find-file filename)
      (user-error "No next file")))
  (defun evil-unimpaired-find-relative-filename (offset)
    (when buffer-file-name
      (let* ((directory (f-dirname buffer-file-name))
             (files (f--files directory (not (s-matches? "^\\.?#" it))))
             (index (+ (-elem-index buffer-file-name files) offset))
             (file (and (>= index 0) (nth index files))))
        (when file
          (f-expand file directory)))))
  (evil-define-command toggle-cursorline ()
    (interactive)
    (setq evil-inhibit-operator t)
    (if (eq evil-this-operator 'evil-change)
        (if hl-line-mode (hl-line-mode -1))))
  (evil-define-command toggle-highlights ()
    (interactive)
    (setq evil-inhibit-operator t)
    (evil-ex-nohighlight))
  (evil-define-command toggle-number ()
    (interactive)
    (setq evil-inhibit-operator t)
    (if (eq evil-this-operator 'evil-change)
        (if display-line-numbers-mode
            (display-line-numbers-mode -1)
          (display-line-numbers-mode +1))))
  (evil-define-command toggle-wrap ()
    (interactive)
    (setq evil-inhibit-operator t)
    (if (eq evil-this-operator 'evil-change)
        (toggle-truncate-lines)))
  (defmacro define-and-bind-text-object (key start-regex end-regex)
    (let ((inner-name (make-symbol "inner-name"))
          (outer-name (make-symbol "outer-name")))
      `(progn
         (evil-define-text-object ,inner-name (count &optional beg end type)
           (evil-select-paren ,start-regex ,end-regex beg end type count nil))
         (evil-define-text-object ,outer-name (count &optional beg end type)
           (evil-select-paren ,start-regex ,end-regex beg end type count nil))
         (define-key evil-inner-text-objects-map ,key (quote ,inner-name))
         (define-key evil-outer-text-objects-map ,key (quote ,outer-name)))))
  (define-and-bind-text-object ">" "%>%" "%>%")
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
  (evil-mode)
  (evil-set-initial-state 'process-menu-mode 'menu)
  (fset 'evil-visual-update-x-selection 'ignore)
  (setq evil-echo-state nil
        evil-emacs-state-tag "E"
        evil-ex-search-vim-style-regexp t
        evil-insert-state-tag "I"
        evil-motion-state-tag "M"
        evil-normal-state-tag "N"
        evil-operator-state-tag "O"
        evil-visual-state-tag "V")
  :diminish evil-collection-unimpaired-mode)

(use-package bind-map
  :demand t
  :config
  (bind-map leader-map
    :evil-keys ("SPC")
    :evil-states (menu motion normal view visual))
  (bind-keys
   :map leader-map
    ("[" . evil-toggle))
  (defun evil-toggle ()
    (interactive)
    (if (or (evil-menu-state-p)
            (evil-emacs-state-p))
        (evil-normal-state)
      (evil-menu-state)))
  (setq bind-map-default-map-suffix "-localleader-map"
        bind-map-default-evil-states '(menu motion normal view visual)))

;; Workspaces: project.el + tab-bar + tabspaces (replaces projectile +
;; perspective + persp-projectile). A tab-bar tab == a workspace; tabspaces gives
;; project-per-tab plus per-tab buffer isolation (the old bs "persp-files" list).
(use-package tab-bar
  :ensure nil
  :init
  (setq tab-bar-show nil                 ; doom-modeline shows the tab name
        tab-bar-new-tab-choice "*scratch*"
        tab-bar-close-button-show nil
        tab-bar-new-button-show nil)
  :config
  (tab-bar-mode 1)
  (tab-bar-rename-tab "scratch")         ; was persp-initial-frame-name "scratch"
  (defun my-tab-current-name ()
    "Name of the current tab-bar tab (replaces (persp-name (persp-curr)))."
    (alist-get 'name (tab-bar--current-tab)))
  (defun my-tab-switch-or-create (name)
    "Switch to tab NAME, creating it if absent (replaces persp-switch)."
    (interactive "sTab: ")
    (if (member name (mapcar (lambda (tab) (alist-get 'name tab)) (tab-bar-tabs)))
        (tab-bar-switch-to-tab name)
      (tab-bar-new-tab)
      (tab-bar-rename-tab name))))

(use-package project
  :ensure nil
  :bind
  (:map leader-map
   ("p" . project-prefix-map)            ; was projectile-command-map
   ("i" . tabspaces-switch-to-buffer))   ; was projectile-ibuffer (workspace-scoped)
  :init
  ;; "switch project => its own workspace tab" (the persp-projectile headline),
  ;; plus find-file/dired/grep like projectile's switch menu.
  (setq project-switch-commands
        '((tabspaces-open-or-create-project-and-workspace "Open in workspace" ?P)
          (project-find-file        "Find file" ?f)
          (project-dired            "Dired"     ?d)
          (project-find-regexp      "Grep"      ?g)
          (project-switch-to-buffer "Buffer"    ?b)
          (project-eshell           "Eshell"    ?e)
          (magit-project-status     "Magit"     ?m)))
  :config
  ;; No my-projectile-exclude-tramp advice needed: project.el is lazy/on-demand
  ;; and never globally scans buffers, so there is nothing to disable on remote.
  (setq project-vc-extra-root-markers '(".project")))

(use-package tabspaces
  :hook (after-init . tabspaces-mode)
  :commands (tabspaces-switch-or-create-workspace
             tabspaces-open-or-create-project-and-workspace
             tabspaces-switch-to-buffer)
  :custom
  (tabspaces-use-filtered-buffers-as-default t) ; switch-to-buffer => workspace-only
  (tabspaces-default-tab "scratch")             ; was persp-initial-frame-name
  (tabspaces-remove-to-default t)
  (tabspaces-include-buffers '("*scratch*"))
  (tabspaces-session nil)                       ; match current (non-persisted) behavior
  (tabspaces-keymap-prefix nil)                 ; we bind our own C-b map below
  :config
  ;; consult source: only current-workspace buffers (replaces bs persp-files).
  (with-eval-after-load 'consult
    (defvar consult--source-workspace
      (list :name "Workspace" :narrow ?w :history 'buffer-name-history
            :category 'buffer :state #'consult--buffer-state :default t
            :items (lambda ()
                     (consult--buffer-query
                      :predicate #'tabspaces--local-buffer-p
                      :sort 'visibility :as #'buffer-name)))
      "Workspace-local buffers for `consult-buffer'.")
    (add-to-list 'consult-buffer-sources 'consult--source-workspace)))

;; hydra removed: all interactive menus migrated to transient (built-in).

;; tmux-style workspace/window prefix under C-b (replaces perspective-map, plus
;; the hydra-persp / window-resize / window-rotate hydras -> transient). Bound in
;; evil-motion-state-map so normal/visual inherit it (the user moved scrolling
;; onto the custom 'view state, freeing C-b for the tmux leader).
(use-package emacs
  :ensure nil
  :after (tab-bar evil)
  :init
  (defvar tab-prefix-leader-map (make-sparse-keymap)
    "tmux-style workspace/window map (replaces perspective-map).")
  :config
  (require 'transient)
  ;; cycle workspace tabs (was hydra-persp); C-p/C-n stay open.
  (transient-define-prefix my/tab-transient ()
    "Cycle workspace tabs."
    [("C-p" "Previous" tab-bar-switch-to-prev-tab :transient t)
     ("C-n" "Next"     tab-bar-switch-to-next-tab :transient t)
     ("q" "Quit" transient-quit-one)
     ("<escape>" "Quit" transient-quit-one)])
  ;; resize windows (was hydra-evil-window-resize); sticky.
  (transient-define-prefix my/window-resize-transient ()
    "Resize windows."
    [("C-h" "Left"  windsize-left  :transient t)
     ("C-j" "Down"  windsize-down  :transient t)
     ("C-k" "Up"    windsize-up    :transient t)
     ("C-l" "Right" windsize-right :transient t)
     ("q" "Quit" transient-quit-one)
     ("<escape>" "Quit" transient-quit-one)])
  ;; rotate layout (was hydra-evil-window-rotate); sticky.
  (transient-define-prefix my/window-rotate-transient ()
    "Rotate window layout."
    [("SPC" "Rotate" rotate-layout :transient t)
     ("q" "Quit" transient-quit-one)
     ("<escape>" "Quit" transient-quit-one)])
  (bind-keys
   :map tab-prefix-leader-map
   ("%"   . evil-window-split)            ; unchanged
   ("\""  . evil-window-vsplit)           ; unchanged
   ("&"   . tab-bar-close-tab)            ; was persp-kill
   (","   . tab-bar-rename-tab)           ; was persp-rename
   ("w"   . tab-bar-switch-to-tab)        ; was persp-switch (creates on new name)
   ("C-p" . my/tab-transient)             ; was hydra-persp (C-p/C-n cycle)
   ("C-n" . my/tab-transient)
   ("C-h" . my/window-resize-transient)   ; was hydra-evil-window-resize
   ("C-j" . my/window-resize-transient)
   ("C-k" . my/window-resize-transient)
   ("C-l" . my/window-resize-transient)
   ("SPC" . my/window-rotate-transient)   ; was hydra-evil-window-rotate
   :map evil-motion-state-map
   ("C-b" . tab-prefix-leader-map))       ; was persp-mode-prefix-key "C-b"
  ;; Frame title shows the current tab name (was (persp-name (persp-curr))).
  (defun my-frame-title-format ()
    (concat
     "Emacs ❯ "
     (format "%s ❯ " (my-tab-current-name))
     (cond ((buffer-file-name)
            (file-name-nondirectory buffer-file-name))
           ((member major-mode '(eshell-mode eat-mode term-mode))
            (abbreviate-file-name default-directory))
           ("%b"))))
  (setq frame-title-format '((:eval (my-frame-title-format)))))

;; doom-modeline - modern, actively maintained modeline (replaces spaceline)
;; Original spaceline features mapped to doom-modeline equivalents:
;; - persp-name, workspace-number → doom-modeline-persp-name, doom-modeline-workspace-name
;; - evil-state → doom-modeline-modal (built-in)
;; - anzu (search count) → doom-modeline-enable-word-count + evil-anzu integration
;; - buffer-modified, buffer-id, remote-host → built-in
;; - major-mode → doom-modeline-major-mode-icon
;; - flycheck errors → doom-modeline-checker-simple-format
;; - minor-modes → doom-modeline-minor-modes
;; - version-control → built-in vcs segment
;; - org-clock → built-in support
;; - which-function → doom-modeline-env-enable-python etc.
;; - python-pyvenv → doom-modeline-env-python-executable
;; - battery → doom-modeline-battery
;; - selection-info → doom-modeline-enable-word-count
;; - line-column, buffer-position → built-in
(use-package doom-modeline
  :ensure t
  :init
  (doom-modeline-mode 1)
  :config
  (setq doom-modeline-height 22   ; tighter bar (bump if icons ever clip)
        doom-modeline-bar-width 3
        ;; Workspace name comes from tab-bar now; persp vars are no-ops without
        ;; perspective.el, so disable them and keep the tab-name segment.
        doom-modeline-persp-name nil
        doom-modeline-persp-icon nil
        doom-modeline-workspace-name t
        ;; Window number (was window-number)
        doom-modeline-window-width-limit 85
        ;; Buffer info (was buffer-modified, buffer-size, buffer-id, remote-host)
        doom-modeline-buffer-file-name-style 'truncate-upto-project
        doom-modeline-buffer-state-icon t
        doom-modeline-buffer-modification-icon t
        ;; Major mode (was major-mode)
        doom-modeline-major-mode-icon t
        doom-modeline-major-mode-color-icon t
        ;; Minor modes (was minor-modes - disabled like before, only shown when active)
        doom-modeline-minor-modes nil
        ;; VCS (was version-control)
        doom-modeline-vcs-max-length 20
        ;; Flycheck/Flymake (was flycheck-error, flycheck-warning, flycheck-info)
        doom-modeline-checker-simple-format nil  ; show counts, not just icon
        ;; Word count on selection - off (was on; trimmed as noise)
        doom-modeline-enable-word-count nil
        ;; Environment versions - keep Python (your core), drop the rest
        doom-modeline-env-version t
        doom-modeline-env-enable-python t
        doom-modeline-env-enable-ruby nil
        doom-modeline-env-enable-go nil
        doom-modeline-env-enable-rust nil
        ;; Modal state (was evil-state fallback)
        doom-modeline-modal t
        doom-modeline-modal-icon t
        doom-modeline-modal-modern-icon t
        ;; Battery (was battery :when active)
        doom-modeline-battery t
        ;; Time (optional, if you want)
        doom-modeline-time nil
        ;; Misc
        doom-modeline-buffer-encoding nil
        doom-modeline-indent-info nil
        doom-modeline-total-line-number nil
        doom-modeline-lsp t
        doom-modeline-github nil
        doom-modeline-mu4e nil  ; you don't read mail in Emacs
        doom-modeline-irc nil   ; you don't use IRC/ERC
        ))

;; Display battery in modeline
(display-battery-mode 1)

;; anzu - show search match count (integrates with doom-modeline)
(use-package anzu
  :config
  (global-anzu-mode 1))

;; evil-anzu - evil search integration with anzu
(use-package evil-anzu
  :after (evil anzu))

;; nerd-icons (icons for doom-modeline, dired, completion, etc.).
;; Point it at the installed "Hack Nerd Font Mono" instead of the default
;; "Symbols Nerd Font Mono" (which isn't installed) so glyphs actually render.
;; If you ever run `M-x nerd-icons-install-fonts', drop this and use the default.
(use-package nerd-icons
  :config
  (setq nerd-icons-font-family "Hack Nerd Font Mono"))

;; other packages

(use-package advice
  :ensure nil
  :config
  (setq ad-redefinition-action 'accept))

(use-package aggressive-indent :disabled
  :config
  (add-hook 'prog-mode-hook #'aggressive-indent-mode)
  (aggressive-indent-global-mode)
  (setq aggressive-indent-excluded-modes
        '(org-mode
          poly-head-tail-mode
          python-mode
          scala-mode
          sql-interactive-mode
          sql-mode
          vimrc-mode))
  :diminish aggressive-indent-mode)

(use-package align
  :ensure nil
  :config
  (defun align-to-colon (begin end)
    "Align region to colon (:) signs"
    (interactive "r")
    (align-regexp
     begin end
     (rx (group (zero-or-more (syntax whitespace))) ":") 1 1 ))
  (defun align-to-comma (begin end)
    "Align region to comma  signs"
    (interactive "r")
    (align-regexp
     begin end
     (rx "," (group (zero-or-more (syntax whitespace))) ) 1 1 ))
  (defun align-to-comma-before (begin end)
    "Align region to equal signs"
    (interactive "r")
    (align-regexp
     begin end
     (rx (group (zero-or-more (syntax whitespace))) ",") 1 1 ))
  (defun align-to-equals (begin end)
    "Align region to equal signs"
    (interactive "r")
    (align-regexp
     begin end
     (rx (group (zero-or-more (syntax whitespace))) "=") 1 1 ))
  (defun align-to-hash (begin end)
    "Align region to hash ( => ) signs"
    (interactive "r")
    (align-regexp
     begin end
     (rx (group (zero-or-more (syntax whitespace))) "=>") 1 1 ))
  (defun align-to-whitespace (start end)
    "Align columns by whitespace"
    (interactive "r")
    (align-regexp
     start end
     (rx (group (zero-or-more (syntax whitespace)))
         (syntax whitespace)) 1 0 t)))

(use-package anzu
  :config
  (setq anzu-cons-mode-line-p nil
        anzu-replace-to-string-separator "→")
  :diminish anzu-mode)

(use-package apples-mode
  :if (eq system-type 'darwin)
  :commands apples-mode)

;; arch-packer is unmaintained
(use-package arch-packer :disabled
  :commands arch-packer-list-packages)

(use-package auth-source
  :ensure nil
  :config
  (defun auth-source-password (host login)
    "Get a password from authinfo."
    (interactive)
    (let* ((found (auth-source-search :host host :login login :max 1))
           (secret (plist-get (nth 0 found) :secret)))
      (if (functionp secret)
          (funcall secret)
        secret)))
  (setq auth-sources `(,(expand-file-name "~/.authinfo.gpg"))))

(use-package autorevert
  :ensure nil
  :config
  (global-auto-revert-mode)
  :diminish auto-revert-mode)

(use-package base16-tomorrow-night-theme
  :ensure base16-theme
  :config
  (load-theme 'base16-tomorrow-night t))

(use-package bind-key)

(use-package browse-url
  :ensure nil
  :config
  (setq browse-url-browser-function #'browse-url-firefox))

(use-package bs
  :ensure nil
  :config
  (make-variable-buffer-local 'bs-default-configuration)
  (setq-default bs-default-configuration "files-and-scratch")
  (setq bs-string-marked "→")
  ;; Per-workspace file list now keys on tabspaces' tab-local buffers instead of
  ;; perspective buffers. (consult-buffer's "Workspace" source is the primary UI;
  ;; this keeps `bs' working too.)
  (with-eval-after-load 'tabspaces
    (add-to-list 'bs-configurations
                 '("workspace-files" nil nil nil bs-visits-workspace nil))
    (defun bs-visits-workspace (buffer)
      (with-current-buffer buffer
        (not (and (tabspaces--local-buffer-p buffer)
                  (buffer-file-name buffer)))))
    (setq-default bs-default-configuration "workspace-files")))

(use-package calendar
  :config
  (evil-set-initial-state 'calendar-mode 'emacs)
  (bind-keys
   :map calendar-mode-map
    ("." . calendar-goto-today)
    ("?" . calendar-goto-info-node)
    ("C-," . (lambda () (interactive) (calendar-backward-month 1)))
    ("C-." . (lambda () (interactive) (calendar-forward-month 1)))
    ;; ("C-h" . (lambda () (interactive) (calendar-backward-day 1)))
    ("C-j" . (lambda () (interactive) (calendar-forward-week 1)))
    ("C-k" . (lambda () (interactive) (calendar-backward-week 1)))
    ("C-l" . (lambda () (interactive) (calendar-forward-day 1)))
    ("h" . (lambda () (interactive) (calendar-backward-day 1)))
    ("j" . (lambda () (interactive) (calendar-forward-week 1)))
    ("k" . (lambda () (interactive) (calendar-backward-week 1)))
    ("l" . (lambda () (interactive) (calendar-forward-day 1))))
  (setq calendar-week-start-day 1))

;; calfw is unmaintained
(use-package calfw :disabled)

(use-package centered-cursor-mode
  :config
  (global-centered-cursor-mode)
  :diminish centered-cursor-mode)

(use-package cider
  :pin melpa-stable
  :mode
  ("clj$" . clojure-mode)
  :bind
  (:map cider-repl-mode-map
   ("C-p" . cider-repl-previous-matching-input)
   ("C-n" . cider-repl-next-matching-input)
   ("C-r" . cider-repl-previous-matching-input))
  :config
  (add-hook 'cider-repl-mode-hook #'my--repl-mode)
  (evil-set-initial-state 'cider-repl-mode 'insert)
  (evil-set-initial-state 'cider-stacktrace-mode 'emacs)
  (setq cider-default-repl-command "lein"
        cider-eval-result-prefix "→ "
        cider-inject-dependencies-at-jack-in nil))

;; Claude Code integration (subscription via the `claude' CLI, run in `eat').
;; claude-code-ide opens an MCP bridge so Claude can use Emacs's own xref /
;; tree-sitter / imenu / project info and live (eglot) flymake diagnostics, and
;; reviews edits via ediff. Not on MELPA -> installed with :vc.
(use-package claude-code-ide
  :vc (:url "https://github.com/manzaltu/claude-code-ide.el" :rev :newest)
  :commands (claude-code-ide
             claude-code-ide-menu
             claude-code-ide-toggle
             claude-code-ide-continue
             claude-code-ide-resume
             claude-code-ide-stop
             claude-code-ide-list-sessions
             claude-code-ide-switch-to-buffer
             claude-code-ide-send-prompt
             claude-code-ide-insert-at-mentioned
             claude-code-ide-check-status
             claude-code-ide-show-debug)
  :bind ("C-c C-'" . claude-code-ide-menu)
  :init
  (setq claude-code-ide-terminal-backend 'eat       ; reuse the existing eat setup
        claude-code-ide-diagnostics-backend 'auto)  ; detect eglot/flymake vs flycheck
  ;; SPC a ... ("AI / Claude") leader subprefix. In :init so the keys exist at
  ;; startup; the commands autoload on first use via :commands.
  (bind-keys
   :map leader-map
   ("aa" . claude-code-ide-menu)               ; transient menu (everything)
   ("as" . claude-code-ide)                    ; start (toggles if running)
   ("at" . claude-code-ide-toggle)             ; show/hide window
   ("ar" . claude-code-ide-insert-at-mentioned) ; send region/selection (visual)
   ("ap" . claude-code-ide-send-prompt)        ; prompt from minibuffer
   ("ac" . claude-code-ide-continue)           ; continue recent conversation
   ("aR" . claude-code-ide-resume)             ; resume a prior conversation
   ("al" . claude-code-ide-list-sessions)      ; list/switch active sessions
   ("ab" . claude-code-ide-switch-to-buffer)   ; jump to this project's buffer
   ("aq" . claude-code-ide-stop)               ; stop session
   ("a?" . claude-code-ide-check-status)       ; verify CLI install
   ("ad" . claude-code-ide-show-debug))        ; WebSocket debug buffer
  :config
  (setq claude-code-ide-use-ide-diff t
        claude-code-ide-show-claude-window-in-ediff t
        claude-code-ide-switch-tab-on-ediff t)
  ;; Expose Emacs MCP tools to Claude (xref, xref-apropos, project-info,
  ;; imenu-list-symbols, treesit-info). Diagnostics are a separate always-on
  ;; native tool (getDiagnostics), not registered here.
  (claude-code-ide-emacs-tools-setup)
  ;; The Claude buffer is an eat buffer (already evil emacs-state via the eat
  ;; block). Only the debug buffer needs a state; 'menu matches j/k lists.
  (with-eval-after-load 'evil
    (evil-set-initial-state 'claude-code-ide-debug-mode 'menu)))

(with-eval-after-load 'which-key
  (which-key-add-key-based-replacements "SPC a" "AI / Claude"))

(use-package comint
  :ensure nil
  :commands comint-mode
  :config
  (add-hook 'comint-mode-hook #'my--repl-mode)
  (add-hook 'comint-mode-hook
            (defun my-comint-mode ()
              (evil-define-key 'insert comint-mode-map
                (kbd "C-n") #'comint-next-matching-input-from-input
                (kbd "C-p") #'comint-previous-matching-input-from-input
                (kbd "C-r") #'comint-history-isearch-backward-regexp)
              (evil-define-key 'normal comint-mode-map
                (kbd "G") (lambda () (interactive)
                            (goto-char (cdr comint-last-prompt))
                            (comint-bol))
                (kbd "RET") (lambda () (interactive)
                              (goto-char (cdr comint-last-prompt))
                              (comint-bol)
                              (evil-append-line 1)))))
  (add-hook 'evil-insert-state-entry-hook (lambda () (when (member major-mode my-comint-modes) (hl-line-mode -1))))
  (add-hook 'evil-insert-state-exit-hook (lambda () (when (member major-mode my-comint-modes) (hl-line-mode 1))))
  (set-face-bold 'comint-highlight-input nil)
  (setq comint-move-point-for-output t
        comint-prompt-read-only t
        comint-scroll-to-bottom-on-input t
        comint-scroll-to-bottom-on-output t
        comint-output-filter-functions '(ansi-color-process-output
                                         comint-postoutput-scroll-to-bottom
                                         comint-watch-for-password-prompt)
        my-comint-modes '(inferior-ess-mode
                          inferior-python-mode)))

;; corfu - modern in-buffer completion (replaces company)
(use-package corfu
  :init
  (global-corfu-mode)
  :bind
  (:map corfu-map
   ("C-n" . corfu-next)
   ("C-p" . corfu-previous)
   ("C-d" . corfu-scroll-down)
   ("C-u" . corfu-scroll-up)
   ("C-f" . corfu-complete)
   ("RET" . corfu-insert)
   ("<tab>" . corfu-next)
   ("S-<tab>" . corfu-previous))
  :config
  (setq corfu-auto t
        corfu-auto-prefix 2
        corfu-auto-delay 0.1
        corfu-cycle t
        corfu-quit-at-boundary 'separator
        corfu-preview-current nil)
  ;; Evil compatibility
  (with-eval-after-load 'evil
    (defun evil-corfu-complete (_) (corfu-insert))
    (setq evil-complete-previous-func #'corfu-previous
          evil-complete-next-func #'corfu-next)))

;; cape - completion at point extensions (replaces company backends)
(use-package cape
  :init
  (add-to-list 'completion-at-point-functions #'cape-dabbrev)
  (add-to-list 'completion-at-point-functions #'cape-file)
  (add-to-list 'completion-at-point-functions #'cape-keyword)
  :bind
  (:map evil-insert-state-map
   ("C-x C-f" . cape-file)))

;; corfu-terminal - terminal support for corfu
(use-package corfu-terminal
  :unless (display-graphic-p)
  :config
  (corfu-terminal-mode 1))

(use-package compile
  :ensure nil
  :config
  (add-hook 'compilation-filter-hook
            (defun my-colorize-compilation ()
              "Colorize from `compilation-filter-start' to `point'."
              (let ((inhibit-read-only t))
                (ansi-color-apply-on-region compilation-filter-start (point)))))
  :diminish compilation-in-progress)

(use-package conf-mode
  :mode
  ("[Bb]rewfile$" . conf-space-mode)
  ("Procfile" . conf-colon-mode)
  :commands conf-mode
  :config
  (add-hook 'conf-mode-hook #'pseudo-prog-mode))

(use-package crontab-mode
  :config
  (add-hook 'crontab-mode-hook #'pseudo-prog-mode))

(use-package csv-mode
  :mode
  ("csv$" . csv-mode)
  :bind
  (:map csv-mode-localleader-map
   ("s" . csv-sort-fields)
   ("r" . csv-reverse-region)
   ("k" . csv-kill-fields)
   ("a" . csv-align-fields)
   ("u" . csv-unalign-fields)
   ("t" . csv-transpose))
  :config
  (add-hook 'csv-mode-hook #'pseudo-prog-mode)
  (add-hook 'csv-mode-hook
            (defun my-csv-mode ()
              (csv-highlight)
              (csv-align-fields nil (buffer-end -1) (buffer-end +1))))
  (bind-map-for-major-mode csv-mode :evil-keys (","))
  (defun csv-highlight (&optional separator)
    "Highlight fields in a CSV."
    (interactive (list (when current-prefix-arg (read-char "Separator: "))))
    (font-lock-mode 1)
    (let* ((separator (or separator ?\,))
           (n (count-matches (string separator) (point-at-bol) (point-at-eol)))
           (colors (cl-loop for i from 0 to 1.0 by (/ 2.0 n) collect
                            (apply #'color-rgb-to-hex (color-hsl-to-rgb i 0.3 0.5)))))
      (cl-loop for i from 2 to n by 2
               for c in colors
               for r = (format "^\\([^%c\n]+%c\\)\\{%d\\}" separator separator i)
               do (font-lock-add-keywords nil `((,r (1 '(face (:foreground ,c))))))))))

(use-package custom
  :ensure nil
  :config
  (add-hook 'Custom-mode-hook
            (defun my-custom-mode ()
              (evil-set-initial-state 'Custom-mode 'normal)
              (evil-define-key 'normal custom-mode-map
                (kbd "<tab>") #'widget-forward
                (kbd "<backtab>") #'widget-backward
                (kbd "C-k") #'widget-backward
                (kbd "C-j") #'widget-forward)))
  (setq custom-safe-themes t
        custom-file (expand-file-name "custom.el" user-emacs-directory)
        custom-raised-buttons nil)
  (load custom-file 'no-error 'no-message))

(use-package diff-mode
  :ensure nil
  :config
  (add-hook 'diff-mode-hook #'whitespace-mode))

(use-package dired
  :ensure nil
  :commands dired
  :bind
  (:map leader-map
   ("fe" . file-explorer))
  :config
  (add-hook 'dired-mode-hook
            (defun my-dired-mode ()
              (set (make-variable-buffer-local 'evil-search-module) 'isearch)
              (toggle-truncate-lines)))
  (defun file-explorer ()
    "Open the files workspace."
    (interactive)
    (my-tab-switch-or-create "files")
    (dired "~"))
  (evil-set-initial-state 'dired-mode 'menu)
  (evil-define-key 'menu dired-mode-map
    ;; peep-dired disabled - package unmaintained
    (kbd "C-c C-u") #'revert-buffer
    (kbd "G") (lambda () (interactive)
                (evil-goto-line)
                (dired-previous-line 1))
    (kbd "K") #'dired-do-kill-lines
    (kbd "RET") #'dired-find-alternate-file
    (kbd "g/") (defun go-root () (interactive)
                      (find-alternate-file
                       (expand-file-name "/")))
    (kbd "gb") (defun go-bin () (interactive)
                      (find-alternate-file
                       (expand-file-name "~/bin")))
    (kbd "gd") (defun go-downloads () (interactive)
                      (find-alternate-file
                       (expand-file-name "~/Downloads")))
    (kbd "gg") (defun go-top () (interactive)
                      (evil-goto-first-line)
                      (dired-next-line 3))
    (kbd "gh") (defun go-home () (interactive)
                      (find-alternate-file
                       (expand-file-name "~/")))
    (kbd "go") (defun go-org () (interactive)
                      (find-alternate-file org-directory))
    (kbd "gr") (defun go-repos () (interactive)
                      (find-alternate-file
                       (expand-file-name "~/repos")))
    (kbd "gt") (defun go-tmp () (interactive)
                      (find-alternate-file
                       (expand-file-name "/tmp")))
    (kbd "gv") (defun go-videos () (interactive)
                      (find-alternate-file
                       (expand-file-name "~/Videos")))
    (kbd "gx") (defun go-dropbox () (interactive)
                      (find-alternate-file
                       (expand-file-name "~/Dropbox")))
    (kbd "h") (lambda () (interactive)
                (let ((parent (dired-current-directory)))
                  (find-alternate-file "..")
                  (dired-goto-file parent)))
    (kbd "i") (lambda () (interactive)
               (wdired-change-to-wdired-mode)
               (evil-insert))
    (kbd "j") #'dired-next-line
    (kbd "k") #'dired-previous-line
    (kbd "l") #'dired-find-alternate-file
    (kbd "p") nil)
  (put 'dired-find-alternate-file 'disabled nil)
  (set-face-bold 'dired-directory t)
  (set-face-bold 'dired-mark t)
  (setq dired-dwim-target t
        dired-isearch-filenames t
        dired-listing-switches "-Ahl --group-directories-first"
        dired-marker-char 8594
        wdired-allow-to-change-permissions t))

;; dired-k is unmaintained - consider diff-hl for git status in dired
(use-package dired-k :disabled
  :after dired
  :config
  (add-hook 'dired-after-readin-hook #'dired-k-no-revert)
  (set-face-attribute
   'dired-k-directory nil
   :foreground 'unspecified
   :inherit 'dired-directory)
  (setq dired-k-human-readable t
        dired-k-padding 1))

(use-package dired-narrow
  :bind
  (:map dired-mode-map
   ("f" . dired-narrow)))

(use-package dired-subtree
  :bind
  (:map dired-mode-map
   ("i" . dired-subtree-insert)
   ("q" . dired-subtree-remove))
  :config
  (setq dired-subtree-use-backgrounds nil))

(use-package dired-x
  :ensure nil
  :bind
  (:map leader-map
   ("C-d" . dired-jump-other-window)
   ("d" . dired-jump))
  :config
  (evil-define-key 'menu dired-mode-map
    (kbd "zh") #'dired-omit-mode)
  (setq-default dired-omit-files (concat dired-omit-files "\\|^\\..+$"))
  (defun my-dired-omit-diminish (&rest _)
    "Diminish dired-omit-mode after startup."
    (diminish 'dired-omit-mode))
  (advice-add 'dired-omit-startup :after #'my-dired-omit-diminish))

(use-package doc-view
  :ensure nil
  :mode
  ("pdf$" . doc-view-mode))

(use-package docker
  :bind-keymap
  ("C-c d" . docker-command-map))

;; docker-tramp is obsolete - use built-in tramp-container instead
(use-package tramp-container
  :ensure nil
  :after tramp)

(use-package dockerfile-mode
  :mode
  ("Dockerfile" . dockerfile-mode))

(use-package easy-escape
  :init
  (add-hook 'lisp-mode-hook 'easy-escape-minor-mode)
  :commands easy-escape-minor-mode)

(use-package ein :disabled
  :config
  (add-hook 'ein:connect-mode-hook #'ein:jedi-setup)
  (setq ein:complete-on-dot t
        ein:console-args nil))

(use-package eldoc
  :commands eldoc-mode
  :init
  (add-hook 'prog-mode-hook #'eldoc-mode)
  :config
  (setq eldoc-idle-delay 0)
  :diminish eldoc-mode)

;; Eglot - built-in LSP client (Emacs 29+), replaces Elpy
(use-package eglot
  :ensure nil  ; built-in since Emacs 29
  :hook
  ((python-mode . eglot-ensure)
   (python-ts-mode . eglot-ensure)
   ;; JavaScript / TypeScript / React (jtsx modes derive from the ts modes).
   (js-ts-mode . eglot-ensure)
   (typescript-ts-mode . eglot-ensure)
   (tsx-ts-mode . eglot-ensure)
   (jtsx-jsx-mode . eglot-ensure)
   (jtsx-tsx-mode . eglot-ensure)
   (jtsx-typescript-mode . eglot-ensure))
  :config
  ;; Python LSP = basedpyright (types/completion); ruff lint comes from
  ;; flymake-ruff, ruff format from apheleia. Install: uv tool install
  ;; basedpyright ruff. JS/TS uses eglot's default typescript-language-server
  ;; (npm i -g typescript-language-server typescript).
  (add-to-list 'eglot-server-programs
               '((python-mode python-ts-mode)
                 . ("basedpyright-langserver" "--stdio")))
  ;; The python localleader (,) must work in BOTH python-mode and python-ts-mode
  ;; (tree-sitter opens .py in python-ts-mode). Create the map, then bind into it.
  (bind-map python-mode-localleader-map
    :evil-keys (",")
    :major-modes (python-mode python-ts-mode))
  (bind-keys
   :map python-mode-localleader-map
   ("g" . xref-find-definitions)
   ("r" . eglot-rename)
   ("f" . eglot-format)
   ("a" . eglot-code-actions)
   ("h" . python-indent-shift-left)
   ("l" . python-indent-shift-right)
   ("p" . my-python-repl)     ; start IPython/drepl REPL (defined in Python section)
   ("m" . my-marimo-edit))    ; marimo edit --watch in an eat buffer
  (setq eglot-autoshutdown t
        eglot-events-buffer-size 0)  ; disable logging for performance
  :diminish)

(use-package easy-hugo
  :config
  (setq easy-hugo-basedir "~/blog"
        easy-hugo-url "https://spencerboucher.com"
        easy-hugo-previewtime "300"))

(use-package enh-ruby-mode
  :mode ("rb$" "Guardfile" "Rakefile")
  :interpreter "ruby"
  :config
  (setq enh-ruby-bounce-deep-indent t))

(use-package ensime :disabled
  :commands ensime-mode
  :init
  (add-hook 'scala-mode-hook #'ensime-mode)
  :config
  (add-hook 'ensime-mode-hook
            (defun my-ensime-mode ()
              (evil-normalize-keymaps)
              (setup-yas-with-backends)))
  (evil-make-overriding-map ensime-mode-map)
  (evil-set-initial-state 'ensime-inf-mode 'insert)
  (set-face-attribute
   'ensime-errline-highlight nil
   :underline 'unspecified
   :inherit 'flycheck-error)
  (set-face-attribute
   'ensime-implicit-highlight nil
   :underline 'unspecified)
  (set-face-attribute
   'ensime-warnline-highlight nil
   :underline 'unspecified
   :inherit 'flycheck-warning)
  (setq ensime-auto-generate-config t
        ensime-implicit-gutter-icons nil
        ensime-typecheck-when-idle nil))

(use-package epg-config
  :ensure nil
  :config
  (setq epg-gpg-home-directory (expand-file-name "~/.gnupg")
        epg-gpg-program "gpg2"))

(use-package esh-help
  :after eshell
  :config
  (setup-esh-help-eldoc))

(use-package eshell
  :ensure nil
  :commands eshell
  :config
  (add-hook 'eshell-after-prompt-hook #'eshell-protect-prompt)
  (add-hook 'eshell-mode-hook #'my--repl-mode)
  (add-hook 'eshell-mode-hook
            (defun my-eshell-mode ()
              (bind-keys
               :map eshell-mode-map
                ("C-;" . delete-window)
                ("C-c" . eshell-interrupt-process)
                ([remap eshell-pcomplete] . completion-at-point))
              (evil-define-key 'insert eshell-mode-map
                (kbd "C-n") #'eshell-next-matching-input-from-input
                (kbd "C-p") #'eshell-previous-matching-input-from-input
                (kbd "C-r") #'consult-history)
              (evil-define-key 'normal eshell-mode-map
                (kbd "C-r") #'consult-history
                (kbd "G") (lambda () (interactive) (goto-char eshell-last-output-end))
                (kbd "RET") (lambda () (interactive)
                              (goto-char eshell-last-output-end)
                              (evil-append-line 1)))))
  (defun eshell-protect-prompt ()
    (let ((inhibit-field-text-motion t))
      (add-text-properties
       (point-at-bol)
       (point)
       '(rear-nonsticky t
                        inhibit-line-move-field-capture t
                        field output
                        read-only t
                        front-sticky (field inhibit-line-move-field-capture)))))
  (setq eshell-banner-message ""
        eshell-cmpl-ignore-case t
        eshell-glob-case-insensitive t
        eshell-hist-ignoredups t
        eshell-plain-echo-behavior t
        eshell-scroll-show-maximum-output nil))

(use-package eshell-fringe-status
  :commands eshell-fringe-status-mode
  :init
  (add-hook 'eshell-mode-hook #'eshell-fringe-status-mode))

(use-package eshell-prompt-extras
  :after esh-opt
  :config
  (defun my-eshell-theme ()
    "A eshell-prompt lambda theme."
    (concat
     "\n"
     (propertize
      user-login-name
      'font-lock-face '(:weight bold))
     (propertize
      (concat "@" (car (split-string system-name "\\.")))
      'font-lock-face '(:foreground "MediumSeaGreen" :weight bold))
     (propertize
      (concat ":" (eshell-tildify (eshell/pwd)))
      'font-lock-face
      `(:foreground ,(face-foreground 'eshell-ls-directory-face) :weight bold))
     (when (and (eshell-search-path "git")
                (locate-dominating-file (eshell/pwd) ".git"))
       (propertize
        (concat " " (epe-git-branch))
        'font-lock-face '(:weight bold)))
     "\n"
     (propertize
      (format-time-string "%H:%M ")
      'font-lock-face '(:weight bold))
     (when (fboundp 'epe-venv-p)
       (when (and (epe-venv-p) venv-current-name)
         (propertize
          (concat "(" venv-current-name ") ")
          'font-lock-face
          '(:foreground "MediumSeaGreen" :weight bold))))
     (propertize
      (if (= (user-uid) 0) "# " "❯ ")
      'font-lock-face '(:weight bold))))
  (defun eshell-tildify (pwd)
    (interactive)
    (let* ((home (expand-file-name (getenv "HOME")))
           (home-len (length home)))
      (if (and
           (>= (length pwd) home-len)
           (equal home (substring pwd 0 home-len)))
          (concat "~" (substring pwd home-len))
        pwd)))
  (setq eshell-highlight-prompt nil
        eshell-prompt-function #'my-eshell-theme
        eshell-prompt-regexp "^.*[#❯] $"))

(use-package ess-site
  :ensure ess
  :mode
  (".[Rr]$" . r-mode)
  (".[Rr]profile$" . r-mode)
  (".jl$" . ess-julia-mode)
  :config
  (add-hook 'ess-R-post-run-hook #'ess-execute-screen-options)
  (add-hook 'ess-R-post-run-hook (apply-partially #'my--repl-exit-hook #'kill-buffer-and-window))
  (add-hook 'inferior-ess-mode-hook
            (defun my-inferior-ess-mode-hook ()
              (setq-local comint-use-prompt-regexp nil)
              (setq-local inhibit-field-text-motion nil)))
  (bind-keys
   :map inferior-ess-mode-map
    ("C-c C-c" . ess-interrupt))
  (evil-define-key 'insert ess-mode-map
    (kbd "C-.") (lambda () (interactive)
                  (insert " %>%")
                  (ess-roxy-newline-and-indent)))
  (evil-set-initial-state 'ess-help-mode 'normal)
  (evil-set-initial-state 'inferior-ess-mode 'insert)
  (setq ess-describe-at-point-method 'tooltip
        ess-R-font-lock-keywords '((ess-R-fl-keyword:keywords . t)
                                   (ess-R-fl-keyword:constants . t)
                                   (ess-R-fl-keyword:modifiers . t)
                                   (ess-R-fl-keyword:fun-defs . t)
                                   (ess-R-fl-keyword:assign-ops . t)
                                   (ess-R-fl-keyword:%op% . t)
                                   (ess-fl-keyword:fun-calls . t)
                                   (ess-fl-keyword:numbers . t)
                                   (ess-fl-keyword:operators . t)
                                   (ess-fl-keyword:delimiters . t)
                                   (ess-fl-keyword:= . t)
                                   (ess-R-fl-keyword:F&T . t))
        inferior-ess-r-font-lock-keywords '((ess-R-fl-keyword:keywords . t)
                                            (ess-R-fl-keyword:constants . t)
                                            (ess-R-fl-keyword:modifiers . t)
                                            (ess-R-fl-keyword:fun-defs . t)
                                            (ess-R-fl-keyword:assign-ops . t)
                                            (ess-R-fl-keyword:%op% . t)
                                            (ess-fl-keyword:fun-calls . t)
                                            (ess-fl-keyword:numbers . t)
                                            (ess-fl-keyword:operators . t)
                                            (ess-fl-keyword:delimiters . t)
                                            (ess-fl-keyword:= . t)
                                            (ess-R-fl-keyword:F&T . t))
        ess-R-smart-operators nil
        ess-S-quit-kill-buffers-p t
        inferior-ess-same-window nil))

(use-package ess-rutils
  :ensure ess
  :after ess
  :bind
  (:map ess-mode-localleader-map
   ("d" . ess-rdired))
  :config
  (bind-map-for-major-mode ess-mode :evil-keys (",")))

(use-package esup
  :commands esup
  :config
  (evil-define-key 'normal esup-mode-map
    (kbd "C-j") #'esup-next-result
    (kbd "C-k") #'esup-previous-result
    (kbd "q") #'kill-buffer-and-window))

(use-package evalator
  :commands evalator)

(use-package evil-anzu
  :after evil)

(use-package evil-args
  :after evil
  :bind
  (:map evil-inner-text-objects-map
   ("a" . evil-inner-arg)
   :map evil-outer-text-objects-map
   ("a" . evil-outer-arg)))

(use-package evil-collection
  :init
  (setq evil-collection-setup-minibuffer t)
  :config
  (evil-collection-init))

(use-package evil-commentary
  :after evil
  :config
  (evil-commentary-mode)
  :diminish evil-commentary-mode)

;; evil-ediff removed - evil-collection handles ediff integration

(use-package evil-expat
  :after evil)

(use-package evil-extra-operator
  :after evil
  :config
  (bind-keys
   :map evil-normal-state-map
    ("g@" . evil-operator-macro)
    ("gs" . evil-operator-sort))
  (evil-define-operator evil-operator-macro (beg end)
    :move-point nil
    (interactive "<r>")
    (evil-ex-normal beg end last-kbd-macro))
  (evil-define-operator evil-operator-sort (beg end)
    :move-point nil
    (interactive"<r>")
    (sort-lines nil beg end))
  (setq evil-extra-operator-eval-modes-alist
        '((cider-mode cider-eval-region)
          (emacs-lisp-mode eval-region)
          (ess-julia-mode ess-eval-region nil)
          (ess-r-mode ess-eval-region nil)
          (python-mode python-shell-send-region)
          (scala-mode ensime-inf-eval-region)
          (sql-mode sql-send-region))))

(use-package evil-indent-plus
  :after evil
  :config
  (evil-indent-plus-default-bindings))

(use-package evil-lion
  :after evil
  :config
  (setq evil-lion-left-align-key (kbd "g a")
        evil-lion-right-align-key (kbd "g A"))
  (evil-lion-mode))

(use-package evil-mc
  :after evil
  :config
  (global-evil-mc-mode)
  :diminish evil-mc-mode)

(use-package evil-smartparens
  :after evil
  :commands evil-smartparens-mode
  :init
  (add-hook 'smartparens-enabled-hook #'evil-smartparens-mode)
  :diminish evil-smartparens-mode)

(use-package evil-surround
  :after evil
  :config
  (global-evil-surround-mode))

(use-package evil-terminal-cursor-changer
  :after evil
  :config
  (setq evil-normal-state-cursor 'box))

(use-package evil-textobj-column
  :after evil
  :bind
  (:map evil-inner-text-objects-map
   ("c" . evil-textobj-column-word)
   ("C" . evil-textobj-column-WORD)))

(use-package evil-visualstar
  :after evil
  :config
  (global-evil-visualstar-mode))

;; envrc - direnv integration (replaces exec-path-from-shell)
;; Automatically loads .envrc per-project for environment variables
(use-package envrc
  :init
  (envrc-global-mode)
  :config
  ;; Ensure PATH and other essentials are inherited at startup
  (when (memq window-system '(mac ns x))
    (dolist (var '("PATH" "MANPATH" "SSH_AUTH_SOCK" "GPG_AGENT_INFO"
                   "LANG" "LANGUAGE" "LC_ALL" "EDITOR"
                   "MAINDB_PW" "MOBILE_PW"))
      (when-let ((value (getenv var)))
        (setenv var value))))
  ;; Update exec-path from PATH
  (setq exec-path (append (parse-colon-path (getenv "PATH")) (list exec-directory))))

(use-package f
  :ensure nil
  :after yasnippet)

;; fabric is unmaintained
(use-package fabric :disabled)

(use-package faces
  :ensure nil
  :config
  (set-face-attribute
   'header-line nil
   :background 'unspecified
   :inherit 'mode-line)
  (set-face-bold 'header-line t)
  (set-face-bold 'mode-line-buffer-id t))

(use-package files
  :ensure nil
  :bind
  (:map global-map
   ("C-q" . save-buffers-kill-terminal)
   :map leader-map
   ("fl" . find-library)
   ("k" . kill-buffer-and-window)
   ("ll" . load-library))
  :config
  (add-to-list 'safe-local-variable-values '(after-save-hook . org-babel-tangle))
  (if (eq system-type 'darwin)
      (progn
        (setq delete-by-moving-to-trash t
              insert-directory-program "gls"
              trash-directory (expand-file-name "~/.Trash")))
    (setq insert-directory-program "ls"))
  (setq auto-save-default nil
        auto-save-file-name-transforms
        `(("." ,(expand-file-name "autosaves" user-emacs-directory) t))
        make-backup-files nil))

;; flymake (built-in) replaces flycheck. Eglot reports diagnostics through
;; flymake natively, so LSP buffers (python/js/ts) "just work".
(use-package flymake
  :ensure nil
  :commands flymake-mode
  :bind
  (:map evil-normal-state-map
   ("]l" . flymake-goto-next-error)
   ("[l" . flymake-goto-prev-error)
   :map leader-map
   ("e" . consult-flymake))            ; list + e/w/n narrowing + preview + search
  :init
  (add-hook 'prog-mode-hook #'flymake-mode)
  :config
  ;; Custom rounded-dot fringe indicator (was the flycheck bitmap). flymake has
  ;; only error+warning bitmap vars; notes use a face.
  (define-fringe-bitmap 'my-flymake-fringe-indicator
    (vector #b00000000 #b00000000 #b00000000 #b00000000 #b00000000 #b00000000
            #b00011100 #b00111110 #b00111110 #b00111110 #b00011100 #b00000000
            #b00000000 #b00000000 #b00000000 #b00000000 #b00000000))
  (setq flymake-error-bitmap   '(my-flymake-fringe-indicator compilation-error)
        flymake-warning-bitmap '(my-flymake-fringe-indicator compilation-warning)
        flymake-indicator-type 'fringes
        flymake-fringe-indicator-position 'left-fringe
        flymake-no-changes-timeout 0.5   ; recheck latency (was display-errors-delay 0)
        flymake-start-on-save-buffer t
        elisp-flymake-byte-compile-load-path load-path)  ; was flycheck 'inherit
  ;; Diagnostics list buffers in evil 'menu state with j/k (was flycheck-error-list-mode).
  (evil-set-initial-state 'flymake-diagnostics-buffer-mode 'menu)
  (evil-set-initial-state 'flymake-project-diagnostics-mode 'menu)
  (dolist (mapsym '(flymake-diagnostics-buffer-mode-map
                    flymake-project-diagnostics-mode-map))
    (when (boundp mapsym)
      (evil-define-key 'menu (symbol-value mapsym)
        (kbd "j")   #'next-line
        (kbd "k")   #'previous-line
        (kbd "RET") #'flymake-goto-diagnostic
        (kbd "S")   #'flymake-show-diagnostic   ; native SPC clashes w/ leader -> S
        (kbd "gg")  #'evil-goto-first-line
        (kbd "G")   #'evil-goto-line
        (kbd "q")   #'quit-window)))
  :diminish flymake-mode)

;; Don't run the elisp checkdoc backend (was flycheck-disabled-checkers); keep
;; the byte-compile backend.
(add-hook 'emacs-lisp-mode-hook
          (lambda ()
            (remove-hook 'flymake-diagnostic-functions #'elisp-flymake-checkdoc t)))

;; ruff diagnostics for Python through flymake (was the flake8 lint axis). eglot
;; resets backends when it manages a buffer, so re-add ruff after eglot turns on.
(use-package flymake-ruff
  :after eglot
  :hook ((python-mode . flymake-ruff-load)
         (python-ts-mode . flymake-ruff-load))
  :config
  (add-hook 'eglot-managed-mode-hook
            (lambda ()
              (when (derived-mode-p 'python-mode 'python-ts-mode)
                (flymake-ruff-load)))))

;; flycheck-haskell / flycheck-ledger removed. Haskell diagnostics would come
;; from haskell-language-server via eglot; ledger linting is dropped.

;; jinx - modern spell-checking (replaces flyspell)
;; Much faster, uses enchant, integrates with Vertico for corrections
(use-package jinx
  :hook ((text-mode . jinx-mode)
         (prog-mode . jinx-mode))
  :bind
  (("C-;" . jinx-correct)
   ("M-$" . jinx-correct)
   :map evil-normal-state-map
   ("z=" . jinx-correct))
  :config
  (setq jinx-languages "en_US")
  :diminish jinx-mode)

;; flx-ido removed - using orderless with Vertico instead

(use-package fontawesome
  :commands consult-unicode-search)

(use-package foreman-mode
  :commands
  (foreman
   foreman-start)
  :config
  (evil-set-initial-state 'foreman-mode 'menu)
  (evil-define-key 'menu foreman-mode-map
    (kbd "C-c C-u") #'revert-buffer
    (kbd "G") (lambda () (interactive)
                (evil-goto-line)
                (evil-previous-line))
    (kbd "j") #'foreman-next-line
    (kbd "k") #'foreman-previous-line
    (kbd "p") nil
    (kbd "x") #'foreman-kill-proc))

(use-package frame
  :ensure nil
  :bind
  ("<s-return>" . toggle-frame-fullscreen)
  ("s-t" . nil)
  ("s-u" . my/transparency-transient)
  :config
  (add-hook 'window-configuration-change-hook
            (defun my-font-scale-on-frame-width ()
              (if (< (frame-width) 80)
                  (text-scale-set -0.85)
                (text-scale-set 0))))
  (defun set-frame-alpha (inc)
    "Increase or decrease the selected frame transparency"
    (let* ((alpha (or (frame-parameter (selected-frame) 'alpha) 100))
           (next-alpha (cond ((not alpha) 100)
                             ((> (- alpha inc) 100) 100)
                             ((< (- alpha inc) 0) 0)
                             (t (- alpha inc)))))
      (set-frame-parameter (selected-frame) 'alpha next-alpha)))
  ;; frame-title-format is set by the tab block (shows the workspace/tab name).
  (setq frame-resize-pixelwise t
        ns-use-native-fullscreen nil)
  (require 'transient)
  (defun my/transparency--header ()
    "Live ALPHA header (re-evaluated on each transient redisplay)."
    (format "ALPHA: %s" (or (frame-parameter nil 'alpha) 100)))
  (transient-define-prefix my/transparency-transient ()
    "Adjust frame transparency (replaces hydra-transparency)."
    [:description my/transparency--header
     ["Step"
      ("j"   "+ more"  (lambda () (interactive) (set-frame-alpha +1)) :transient t)
      ("k"   "- less"  (lambda () (interactive) (set-frame-alpha -1)) :transient t)
      ("C-j" "++ more" (lambda () (interactive) (set-frame-alpha +5)) :transient t)
      ("C-k" "-- less" (lambda () (interactive) (set-frame-alpha -5)) :transient t)]
     ["Set"
      ("=" "Set to value"
       (lambda (value)
         (interactive "nTransparency value 0-100 (opaque): ")
         (set-frame-parameter (selected-frame) 'alpha value)))
      ("q" "Quit" transient-quit-one)
      ("<escape>" "Quit" transient-quit-one)]]))

;; diff-hl - git diff indicators (replaces git-gutter)
;; Better Magit integration, also provides dired support (replaces dired-k)
(use-package diff-hl
  :hook ((prog-mode . diff-hl-mode)
         (text-mode . diff-hl-mode)
         (dired-mode . diff-hl-dired-mode)
         (magit-pre-refresh . diff-hl-magit-pre-refresh)
         (magit-post-refresh . diff-hl-magit-post-refresh))
  :bind
  (:map evil-normal-state-map
   ("]c" . diff-hl-next-hunk)
   ("[c" . diff-hl-previous-hunk)
   :map leader-map
   ("g" . my/git-transient))
  :config
  (require 'transient)
  ;; Git / diff-hl menu (was hydra-diff-hl). magit-* run and exit; the *diff-hl*
  ;; window cleanup that the hydra ran on :post is run by the exiting suffixes.
  (defun my/diff-hl--quit-cleanup ()
    (condition-case nil (delete-windows-on "*diff-hl*") (error nil)))
  (transient-define-suffix my/diff-hl-quit ()
    (interactive) (my/diff-hl--quit-cleanup))
  (transient-define-prefix my/git-transient ()
    "Git / diff-hl menu (replaces hydra-diff-hl)."
    [["Magit"
      ("b" "Branch" (lambda () (interactive) (my/diff-hl--quit-cleanup) (call-interactively #'magit-branch)))
      ("c" "Commit" (lambda () (interactive) (my/diff-hl--quit-cleanup) (call-interactively #'magit-commit)))
      ("F" "Pull"   (lambda () (interactive) (my/diff-hl--quit-cleanup) (call-interactively #'magit-pull)))
      ("f" "Fetch"  (lambda () (interactive) (my/diff-hl--quit-cleanup) (call-interactively #'magit-fetch)))
      ("p" "Push"   (lambda () (interactive) (my/diff-hl--quit-cleanup) (call-interactively #'magit-push)))
      ("v" "Status" (lambda () (interactive) (my/diff-hl--quit-cleanup) (call-interactively #'magit-status)))
      ("l" "Log"    (lambda () (interactive) (my/diff-hl--quit-cleanup) (call-interactively #'magit-log)))]
     ["Hunk"
      ("d" "Diff"     diff-hl-diff-goto-hunk     :transient t)
      ("s" "Stage"    diff-hl-stage-current-hunk :transient t)
      ("r" "Revert"   diff-hl-revert-hunk        :transient t)
      ("j" "Next"     diff-hl-next-hunk          :transient t)
      ("k" "Previous" diff-hl-previous-hunk      :transient t)
      ("gg" "First"   (lambda () (interactive) (evil-goto-first-line) (diff-hl-next-hunk)) :transient t)
      ("G"  "Last"    (lambda () (interactive) (evil-goto-line) (diff-hl-previous-hunk)) :transient t)]
     ["Quit"
      ("q"   "Quit" my/diff-hl-quit)
      ("<escape>" "Quit" my/diff-hl-quit)]])
  ;; Use fringe indicators
  (diff-hl-flydiff-mode 1)
  (setq diff-hl-fringe-bmp-function #'diff-hl-fringe-bmp-from-type
        diff-hl-side 'right)
  :diminish diff-hl-mode)

;; git-modes provides gitconfig-mode, gitignore-mode, and gitattributes-mode
(use-package git-modes
  :mode
  ("git/config$" . gitconfig-mode)
  ("gitconfig$" . gitconfig-mode)
  ("gitmodules$" . gitconfig-mode)
  ("/git/config$" . gitconfig-mode)
  ("git/info/exclude$" . gitignore-mode)
  ("gitignore$" . gitignore-mode)
  ("/git/ignore$" . gitignore-mode)
  :config
  (add-hook 'gitconfig-mode-hook #'pseudo-prog-mode)
  (add-hook 'gitconfig-mode-hook
            (defun my-gitconfig-mode ()
              (setq tab-width 2)))
  (add-hook 'gitignore-mode-hook #'pseudo-prog-mode))

(use-package graphviz-dot-mode
  :mode
  ("dot$" . graphviz-dot-mode))

(use-package haskell-mode
  :mode
  ("hs$" . haskell-mode))

(use-package haskell-snippets
  :after haskell-mode)

;; Modern completion framework: Vertico + Consult + Marginalia + Orderless
;; (replaces Helm and IDO)

(use-package vertico
  :init
  (vertico-mode)
  :config
  (setq vertico-cycle t
        vertico-resize nil)
  :bind
  (:map vertico-map
   ("C-j" . vertico-next)
   ("C-k" . vertico-previous)
   ("C-l" . vertico-insert)
   ("C-d" . vertico-scroll-up)
   ("C-u" . vertico-scroll-down)
   ("<escape>" . minibuffer-keyboard-quit)))

(use-package orderless
  :config
  (setq completion-styles '(orderless basic)
        completion-category-defaults nil
        completion-category-overrides '((file (styles partial-completion)))))

(use-package marginalia
  :init
  (marginalia-mode)
  :bind
  (:map minibuffer-local-map
   ("M-A" . marginalia-cycle)))

(use-package consult
  :bind
  (:map leader-map
   ("ff" . consult-find)
   ("fr" . consult-recent-file)
   ("fb" . consult-buffer)
   ("fl" . consult-line)
   ("fg" . consult-ripgrep)
   ("fo" . consult-outline)
   ("fi" . consult-imenu)
   ("fm" . consult-mark)
   ("fy" . consult-yank-pop)
   ("oc" . org-capture)
   :map global-map
   ("M-g g" . consult-goto-line)
   ("M-g M-g" . consult-goto-line)
   ("M-s l" . consult-line)
   ("M-s r" . consult-ripgrep))
  :config
  (setq consult-narrow-key "<"
        consult-preview-key "M-."))

;; consult-flycheck removed: consult ships consult-flymake (bound to SPC e).

(use-package embark
  :bind
  (("C-." . embark-act)
   ("C-;" . embark-dwim)
   ("C-h B" . embark-bindings))
  :config
  (setq prefix-help-command #'embark-prefix-help-command))

(use-package embark-consult
  :after (embark consult)
  :hook
  (embark-collect-mode . consult-preview-at-point-mode))

(use-package help
  :ensure nil
  :config
  (evil-define-key 'motion help-mode-map
    (kbd "<tab>") #'forward-button))

(use-package hideshow :disabled
  :commands hs-minor-mode
  :init
  (add-hook 'prog-mode-hook
            (defun hs-minor-mode-maybe ()
              (unless (eq major-mode 'poly-head-tail-mode)
                (hs-minor-mode))))
  :diminish hs-minor-mode)

(use-package hl-line
  :ensure nil
  :commands hl-line-mode
  :init
  (add-hook 'prog-mode-hook #'hl-line-mode))

(use-package ialign)

(use-package ibuffer
  :ensure nil
  :bind
  (:map leader-map
   ("C-i" . ibuffer-other-window))
  :config
  (add-hook 'ibuffer-mode-hook
            (defun my-ibuffer-mode ()
              (ibuffer-switch-to-saved-filter-groups "default")))
  (evil-set-initial-state 'ibuffer-mode 'menu)
  (evil-make-overriding-map ibuffer-mode-map 'menu)
  (evil-define-key 'menu ibuffer-mode-map
    (kbd "\\") #'ibuffer-filter-disable
    (kbd "C-c C-u") #'ibuffer-update
    (kbd "G") (lambda () (interactive)
                (evil-goto-line)
                (ibuffer-backward-line 1))
    (kbd "K") #'ibuffer-do-kill-lines
    (kbd "gg") (defun go-top () (interactive)
                      (evil-goto-first-line)
                      (ibuffer-forward-line 1))
    (kbd "j") #'ibuffer-forward-line
    (kbd "k") #'ibuffer-backward-line
    (kbd "p") nil)
  (setq ibuffer-default-sorting-mode 'major-mode
        ibuffer-marked-char 8594
        ibuffer-default-shrink-to-minimum-size t
        ibuffer-expert t
        ibuffer-show-empty-filter-groups nil))

;; IDO packages removed - using Vertico stack instead

;; image+ is unmaintained, use built-in image-mode instead
(use-package image+ :disabled
  :config
  (imagex-auto-adjust-mode))

(use-package imenu
  :commands imenu
  :config
  (setq-default imenu-auto-rescan t))

(use-package java-snippets
  :commands java-snippets-initialize
  :init
  (add-hook 'java-mode-hook #'java-snippets-initialize))

(use-package json-mode
  :mode
  ("json$" . json-mode)
  :config
  (add-hook 'json-mode-hook #'pseudo-prog-mode)
  (setq json-reformat:indent-width 2))

(use-package tex-mode
  :ensure nil
  :config
  (add-hook 'latex-mode-hook #'pseudo-prog-mode))

(use-package latex-preview-pane
  :commands latex-preview-pane-mode
  :init
  (bind-map-for-major-mode latex-mode :evil-keys (","))
  (bind-keys
   :map latex-mode-localleader-map
    ("p" . latex-preview-pane-mode))
  :config
  (setq pdf-latex-command "xelatex"
        shell-escape-mode "-shell-escape")
  :diminish
  (latex-preview-pane-mode . "preview-pane"))

(use-package launchctl
  :if (eq system-type 'darwin)
  :commands launchctl
  :bind
  (:map leader-map
   ("lc" . launchctl))
  :config
  (evil-define-key 'menu launchctl-mode-map
    (kbd "C-c C-u") #'launchctl-refresh
    (kbd "G") (lambda () (interactive)
                (evil-goto-line)
                (previous-line)))
  (setq launchctl-filter-regex "^my-.*")
  (evil-set-initial-state 'launchctl-mode 'menu))

(use-package less-css-mode
  :mode
  ("less$" . less-css-mode)
  :config
  (add-hook 'less-css-mode-hook #'pseudo-prog-mode)
  (setq less-css-compile-at-save t))

;; Use built-in display-line-numbers-mode (replaces deprecated linum-mode)
(use-package display-line-numbers
  :ensure nil
  :hook (prog-mode . display-line-numbers-mode)
  :config
  ;; Show relative line numbers in normal mode, absolute in insert mode
  (defun my-display-line-numbers-relative ()
    (setq display-line-numbers 'relative))
  (defun my-display-line-numbers-absolute ()
    (setq display-line-numbers t))
  (add-hook 'evil-normal-state-entry-hook #'my-display-line-numbers-relative)
  (add-hook 'evil-insert-state-entry-hook #'my-display-line-numbers-absolute)
  (add-hook 'evil-insert-state-exit-hook #'my-display-line-numbers-relative)
  (setq-default display-line-numbers-type 'relative
                display-line-numbers-width 4))

(use-package lisp-mode
  :ensure nil
  :mode
  ("el$" . emacs-lisp-mode)
  :bind
  (:map emacs-lisp-mode-localleader-map
   ("l" . load-this-file)
   ("r" . recompile-this-file))
  :config
  (add-hook 'emacs-lisp-mode-hook
            (defun my-emacs-lisp-mode ()
              (setq evil-symbol-word-search t)))
  (add-hook 'emacs-lisp-mode-hook
            (defun my-use-package-imenu ()
              "Recognize use-package in imenu."
              (interactive)
              (when (s-ends-with? "init.el" buffer-file-name)
                (add-to-list
                 'imenu-generic-expression
                 '(nil "^\\s-*(\\(use-package\\)\\s-+\\(\\(\\sw\\|\\s_\\)+\\)" 2)))))
  (bind-map-for-major-mode emacs-lisp-mode :evil-keys (","))
  (defun load-this-file ()
    "Reload the current file."
    (interactive)
    (load-file buffer-file-name))
  (defun recompile-this-file ()
    "Byte recompile the current file."
    (interactive)
    (byte-recompile-file buffer-file-name t)))

(use-package logview
  :mode
  ("log$" . logview-mode)
  :commands logview-mode
  :bind
  (:map logview-mode-map
   ("j" . logview-next-entry)
   ("k" . logview-previous-entry)
   ("n" . logview-add-include-name-filter)
   ("N" . logview-add-exclude-name-filter)))

(use-package lorem-ipsum
  :bind
  (:map leader-map
   ("lil" . lorem-ipsum-insert-list)
   ("lip" . lorem-ipsum-insert-paragraphs)
   ("lis" . lorem-ipsum-insert-sentences)))

(use-package lua-mode
  :mode
  ("lua$" . lua-mode))

(use-package macro-math)

(use-package macrostep
  :bind
  (:map emacs-lisp-mode-localleader-map
   ("e" . macrostep-expand))
  :config
  (add-hook 'macrostep-mode-hook
            (defun my-macrostep-mode ()
              (evil-make-overriding-map macrostep-keymap 'normal)
              (evil-normalize-keymaps)))
  :diminish
  (macrostep-mode . "macrostep"))

(use-package magit
  :commands
  (magit-commit-popup
   magit-log-popup)
  :config
  (add-hook 'with-editor-mode-hook #'evil-insert-state)
  (evil-define-key 'menu git-rebase-mode-map
    (kbd "SPC") nil
    (kbd "C-j") #'git-rebase-move-line-down
    (kbd "C-k") #'git-rebase-move-line-up)
  (setq magit-push-always-verify nil
        magit-save-repository-buffers 'dontask)
  (with-eval-after-load 'origami
    (bind-keys
     :map evil-normal-state-map
     ("<tab>" . nil))))

(use-package magit-gh-pulls :disabled
  :after magit)

(use-package magithub :disabled
  :after magit
  :config
  (magithub-feature-autoinject t))

(use-package markdown-mode
  :mode
  ("md$" . markdown-mode)
  :config
  (add-hook 'markdown-mode-hook #'pseudo-prog-mode)
  (add-hook 'markdown-mode-hook #'my-prose-mode)
  (setq markdown-enable-math t
        markdown-footnote-location 'header))

;; menu-bar-mode is disabled in early-init.el.

(use-package message
  :ensure nil
  :commands message-mode
  :config
  (set-face-bold 'message-header-name t))

(use-package midnight
  :config
  (midnight-mode)
  (setq clean-buffer-list-delay-general 1
        clean-buffer-list-delay-special 500))

(use-package minibuffer
  :ensure nil
  :bind
  (:map minibuffer-local-map
   ("<escape>" . keyboard-escape-quit)
   ("C-a" . beginning-of-visual-line)
   ("C-n" . next-complete-history-element)
   ("C-p" . previous-complete-history-element)
   ("C-v" . yank))
  :config
  (add-hook 'eval-expression-minibuffer-setup-hook #'eldoc-mode)
  (add-hook 'minibuffer-setup-hook
            (defun my-minibuffer-setup-hook ()
              (setq cursor-in-non-selected-windows nil
                    cursor-type 'bar
                    gc-cons-threshold most-positive-fixnum)
              (visual-line-mode)))
  (add-hook 'minibuffer-exit-hook
            (defun my-minibuffer-exit-hook ()
              (setq gc-cons-threshold 800000)))
  (setq completion-styles '(partial-completion)))

(use-package minimap
  :commands minimap-mode
  :config
  (setq minimap-highlight-line nil
        minimap-window-location 'right)
  :diminish minimap-mode)

(use-package multicolumn
  :bind
  (:map leader-map
   ("mc" . multicolumn-delete-other-windows-and-split-with-follow-mode)))

(use-package mustache
  :after ox-blog)

(use-package niceify-info
  :commands niceify-info
  :init
  (add-hook 'Info-selection-hook #'niceify-info))

(use-package nxml-mode
  :ensure nil
  :mode
  ("xml$" . nxml-mode)
  :config
  (add-hook 'nxml-mode-hook #'pseudo-prog-mode))

(use-package ob-browser
  :after ob-core)

(use-package ob-async
  :after ob-core)

(use-package ob-core
  :ensure org
  :after org
  :bind
  (:map org-mode-map
   ("C-c C-z" . org-babel-switch-to-session-with-code))
  :config
  (add-hook 'org-babel-after-execute-hook #'org-redisplay-inline-images)
  (setq org-babel-clojure-backend 'cider
        org-babel-default-header-args:R '((:session . "*R*")
                                          (:tangle . "yes"))
        org-babel-hash-show-time t
        org-babel-julia-command "julia"
        org-confirm-babel-evaluate nil
        org-export-babel-evaluate nil)
  (org-babel-do-load-languages
   'org-babel-load-languages
   '((R . t)
     (calc . t)
     (clojure . t)
     (dot . t)
     (js . t)
     (julia . t)
     ;; ledger removed - ob-ledger no longer bundled with org
     (ruby . t)
     (python . t)
     (shell . t)
     (sql . t))))

(use-package ob-ipython :disabled
  :after ob-core
  :config
  (add-to-list 'org-babel-tangle-lang-exts '("ipython" . "py")))

;; on-screen is unmaintained
(use-package on-screen :disabled
  :config
  (on-screen-global-mode))

(use-package origami
  :commands origami-mode
  :bind
  (:map evil-normal-state-map
   ("<tab>" . origami-recursively-toggle-node)
   ("<backtab>" . origami-toggle-all-nodes))
  :init
  (add-hook 'prog-mode-hook #'origami-mode)
  :config
  (setq origami-fold-replacement " ▼")
  :diminish origami-mode)

(use-package org
  :ensure org
  :ensure htmlize
  :bind
  (:map leader-map
   ("os" . org-store-link)
   :map org-mode-localleader-map
   ("/" . consult-org-heading)
   ("a" . org-archive-subtree)
   ("c" . org-clock)
   ("d" . org-deadline)
   ("i" . org-insert-last-stored-link)
   ("o" . org-sort)
   ("s" . org-schedule)
   ("t" . org-todo)
   ("x" . my-org-archive-done-tasks))
  :mode
  ("org$" . org-mode)
  ("org_archive$" . org-mode)
  :init
  (setq org-directory (expand-file-name "~/Dropbox/org/")
        org-default-notes-file (concat org-directory "todo.org"))
  :config
  ;; (add-hook 'org-mode-hook #'pseudo-prog-mode)
  (add-hook 'org-mode-hook #'my-prose-mode)
  (bind-map-for-major-mode org-mode :evil-keys (","))
  (defun org-todo-w-completion () (interactive) (org-todo '(4)))
  (require 'transient)
  ;; Org heading navigation (was hydra-org-move); b/f/n/p/u stay open.
  (transient-define-prefix my/org-move-transient ()
    "Org heading navigation."
    ["Org heading navigation"
     ("b" "Prev sibling" (lambda () (interactive) (org-backward-heading-same-level 1) (org-beginning-of-line)) :transient t)
     ("f" "Next sibling" (lambda () (interactive) (org-forward-heading-same-level 1)  (org-beginning-of-line)) :transient t)
     ("n" "Next"         (lambda () (interactive) (org-next-visible-heading 1)        (org-beginning-of-line)) :transient t)
     ("p" "Previous"     (lambda () (interactive) (org-previous-visible-heading 1)    (org-beginning-of-line)) :transient t)
     ("u" "Up"           (lambda () (interactive) (outline-up-heading 1)              (org-beginning-of-line)) :transient t)
     ("q" "Quit" transient-quit-one)
     ("<escape>" "Quit" transient-quit-one)])
  ;; Org structural move (was hydra-org-nav); h/j/k/l stay open.
  (transient-define-prefix my/org-nav-transient ()
    "Org move subtree."
    ["Org move subtree"
     ("h" "Move in"   org-metaleft  :transient t)
     ("j" "Move down" org-metadown  :transient t)
     ("k" "Move up"   org-metaup    :transient t)
     ("l" "Move out"  org-metaright :transient t)
     ("q" "Quit" transient-quit-one)
     ("<escape>" "Quit" transient-quit-one)])
  (bind-keys
   :map org-mode-localleader-map
   ("b" . my/org-move-transient) ("f" . my/org-move-transient)
   ("n" . my/org-move-transient) ("p" . my/org-move-transient)
   ("u" . my/org-move-transient)
   ("h" . my/org-nav-transient) ("j" . my/org-nav-transient)
   ("k" . my/org-nav-transient) ("l" . my/org-nav-transient))
  (defun my-org-archive-done-tasks ()
    (interactive)
    (org-map-entries
     (lambda ()
       (org-archive-subtree)
       (setq org-map-continue-from (outline-previous-heading)))
     "/DONE" 'file))
  (evil-define-key 'normal org-mode-map
    (kbd "$") #'org-end-of-line
    (kbd "A") (lambda () (interactive) (org-end-of-line) (evil-insert-state))
    (kbd "I") (lambda () (interactive) (org-beginning-of-line) (evil-insert-state))
    (kbd "RET") #'org-return
    (kbd "^") #'org-beginning-of-line
    (kbd "{") #'org-backward-paragraph
    (kbd "}") #'org-forward-paragraph)
  (let ((lob (expand-file-name "lob.org" user-emacs-directory)))
    (when (file-exists-p lob) (org-babel-lob-ingest lob)))
  (set-face-attribute 'org-document-title nil :height 'unspecified)
  (set-face-attribute
   'secondary-selection nil
   :background 'unspecified
   :foreground 'unspecified
   :inherit 'font-lock-type-face)
  (set-face-bold 'org-level-1 t)
  (set-face-bold 'org-todo t)
  (set-face-underline 'org-link t)
  (setq org-archive-file-header-format nil
        org-archive-location "%s_archive::datetree/"
        org-confirm-elisp-link-function nil
        org-cycle-separator-lines 2
        org-deadline-warning-days 0
        org-edit-src-content-indentation 0
        org-ellipsis " ▼"
        org-file-apps '(("\\.wmv\\'" . "mpv \"%s\"")
                        ("\\.mov\\'" . "mpv \"%s\""))
        org-hide-emphasis-markers t
        org-image-actual-width 600
        org-imenu-depth 3
        org-irc-link-to-logs t
        org-level-color-stars-only t
        org-link-frame-setup '((file . find-file))
        org-log-done t
        org-outline-path-complete-in-steps nil
        org-special-ctrl-a/e t
        org-src-content-indentation 0
        org-src-fontify-natively t
        org-src-preserve-indentation nil
        org-startup-folded nil
        org-startup-with-inline-images t
        org-tags-column -80
        org-time-stamp-custom-formats
        '("<%A %B %d %Y>" . "<%a %B %d %Y %H:%M>")
        org-todo-keywords
        '((sequence "TODO(t)" "|" "DONE(d)")
          (sequence "BLOCKED(b)" "|")
          (sequence "|" "CANCELED(c)"))))

(use-package evil-org
  :ensure t
  :after org
  :config
  (add-hook 'org-mode-hook 'evil-org-mode)
  (add-hook 'evil-org-mode-hook
            (lambda ()
              (evil-org-set-key-theme)))
  (require 'evil-org-agenda)
  (evil-org-agenda-set-keys)
  :diminish evil-org-mode)

(use-package org-agenda
  :ensure org
  :commands org-agenda
  :bind
  (:map leader-map
   ("oa" . org-agenda-list))
  :init
  (add-hook 'org-agenda-mode-hook #'hl-line-mode)
  (evil-set-initial-state 'org-agenda-mode 'menu)
  (setq org-agenda-files `(,org-directory))
  :config
  (setq org-agenda-span 'month
        org-agenda-skip-scheduled-if-done t
        org-agenda-start-on-weekday nil))

(use-package org-bullets :disabled
  :after org
  :config
  (add-hook 'org-mode-hook #'org-bullets-mode)
  (setq org-bullets-bullet-list '("●" "○" "▶" "▷" "◆" "◇" "■" "□")))

(use-package org-capture
  :ensure org
  :after org
  :config
  (add-hook 'org-capture-mode-hook #'evil-insert-state)
  (defun capture-to-new-file (path)
    (let ((name (read-string "Name: ")))
      (expand-file-name (format "%s.org" name) path)))
  (evil-set-initial-state 'org-capture-mode 'insert)
  (setq org-capture-templates
        `(("t" "Add a TODO task" entry
           (file org-default-notes-file)
           "* TODO %?"
           :unnarrowed t)
          ("T" "Add a TODO task with link to current point" entry
           (file org-default-notes-file)
           "* TODO %A\n  %?"
           :unnarrowed t)
          ("w" "Add a work task" entry
           (file "work.org")
           "* TODO %?"
           :unnarrowed t)
          ("W" "Add a work task with link to current point" entry
           (file "work.org")
           "* TODO %A\n  %?"
           :unnarrowed t)
          ("s" "Add to shopping List" entry
           (file "shopping.org")
           "* TODO %?"
           :unnarrowed t)
          ("x" "Add a shipment to track" entry
           (file "shipments.org")
           "* %?"
           :unnarrowed t)
          ("a" "Add an audition" entry
           (file "auditions.org")
           "* TODO %?"
           :unnarrowed t)
          ("f" "Add feedback" entry
           (file "feedback.org")
           "* %?"))))

(use-package org-capture-pop-frame :disabled)

;; org-eldoc is now built into org-mode since version 9.5+
(use-package org-eldoc :disabled
  :ensure nil
  :after org
  :config
  (setq org-eldoc-breadcrumb-separator " • "))

(use-package org-habit
  :ensure org
  :after org
  :config
  (setq org-habit-show-habits-only-for-today t))

(use-package org-journal
  :after org
  :bind
  (:map leader-map
   ("oj" . org-journal-persp)
   :map org-journal-mode-localleader-map
   ("f" . org-journal-open-next-entry)
   ("b" . org-journal-open-previous-entry))
  :config
  (bind-map-for-major-mode org-journal-mode :evil-keys (","))
  (defun org-journal-persp()
    "Open the org workspace and start a journal entry."
    (interactive)
    (my-tab-switch-or-create "org")
    (org-journal-new-entry nil))
  (evil-set-initial-state 'org-journal-mode 'insert)
  (setq org-journal-dir "~/Dropbox/org/journal/"
        org-journal-file-format "%Y-%m-%d.org"
        org-journal-find-file #'find-file))

(use-package org-mime :disabled
  :ensure org
  :after org)

(use-package org-projectile :disabled
  :bind
  (:map leader-map
   ("o p" . org-projectile-project-todo-completing-read))
  :config
  (push (org-projectile-project-todo-entry) org-capture-templates)
  (setq org-projectile-projects-file "~/Dropbox (Personal)/org/projects.org"
        org-agenda-files (append org-agenda-files (org-projectile-todo-files))))

;; org-projectile-helm removed - using consult instead

(use-package org-table
  :ensure org
  :commands orgtbl-mode
  :diminish orgtbl-mode)

(use-package org-table-sticky-header
  :commands org-table-sticky-header-mode
  :init
  (add-hook 'org-mode-hook #'org-table-sticky-header-mode)
  :diminish org-table-sticky-header-mode)

(use-package osx-browse
  :if (eq system-type 'darwin)
  :commands osx-browse-url
  :init
  (fset #'browse-url #'osx-browse-url)
  :config
  (setq browse-url-dwim-always-confirm-extraction nil))

(use-package ox-gfm
  :after ox)

(use-package ox-latex
  :ensure org
  :after ox
  :config
  (add-to-list 'org-latex-classes
               '("deedy-resume"
                 "\\documentclass{deedy-resume}
[NO-DEFAULT-PACKAGES] [NO-PACKAGES]"
                 ("\\section{%s}" . "\\section*{%s}")
                 ("\\subsection{%s}" . "\\subsection*{%s}")))
  (setq org-latex-listings 'minted
        org-latex-minted-options
        '(("breaklines")
          ("frame" "lines")
          ("linenos")
          ("style" "colorful"))
        org-latex-packages-alist
        '(("" "minted")
          ("" "upquote"))
        org-latex-pdf-process
        '("xelatex -shell-escape -interaction nonstopmode -output-directory %o %f"
          "xelatex -shell-escape -interaction nonstopmode -output-directory %o %f"
          "xelatex -shell-escape -interaction nonstopmode -output-directory %o %f")))

(use-package ox-publish
  :ensure org
  :after ox)

(use-package ox-reveal
  :after ox)

;; ox-rss is no longer bundled with org-mode
(use-package ox-rss :disabled
  :after ox)

(use-package ox-twbs
  :after ox)

(use-package page-break-lines
  :config
  (global-page-break-lines-mode)
  :diminish page-break-lines-mode)

(use-package paradox
  :commands
  (paradox-list-packages
   paradox-upgrade-packages)
  :config
  (evil-set-initial-state 'paradox-commit-list-mode 'menu)
  (evil-define-key 'menu paradox-commit-list-mode-map
    (kbd "G") (lambda () (interactive)
                (evil-goto-line)
                (paradox-previous-commit 1))
    (kbd "j") #'paradox-next-commit
    (kbd "k") #'paradox-previous-commit)
  (evil-set-initial-state 'paradox-menu-mode 'menu)
  (evil-define-key 'menu paradox-menu-mode-map
    (kbd "G") (lambda () (interactive)
                (evil-goto-line)
                (evil-previous-line 1))
    (kbd "j") #'paradox-next-entry
    (kbd "k") #'paradox-previous-entry)
  (setq paradox-execute-asynchronously t
        paradox-github-token t
        paradox-hide-wiki-packages t
        paradox-use-homepage-buttons nil))

(use-package pbcopy
  :if (eq system-type 'darwin)
  :config
  (turn-on-pbcopy))

;; pcmpl-git removed - unavailable package

(use-package pcmpl-homebrew
  :after eshell)

(use-package pcmpl-pip
  :after eshell)

(use-package pcomplete-extension
  :after eshell)

;; peep-dired is unmaintained
(use-package peep-dired :disabled
  :bind
  (:map peep-dired-mode-map
   ("RET" . kill-buffer-and-window)
   ("<tab>" . peep-dired)
   ("C-j" . peep-dired-scroll-page-down)
   ("C-k" . peep-dired-scroll-page-up))
  :config
  (setq peep-dired-cleanup-on-disable t
        peep-dired-enable-on-directories t
        peep-dired-ignored-extensions '("mkv" "iso" "mp4" "pyc" "DS_Store"))
  :diminish peep-dired)

(use-package pig-mode
  :mode
  ("pig$" . pig-mode)
  :config
  (add-hook 'pig-mode-hook #'pseudo-prog-mode)
  (pig-snippets-initilize)
  (setq pig-executable "pig"
        pig-executable-options '("-x" "local")
        pig-executable-prompt-regexp "^grunt> "
        pig-indent-level 4
        pig-version "0.14.0"))

(use-package pip-requirements
  :mode
  ("requirements.txt$" . pip-requirements-mode))

;; Quarto (.qmd): modern literate data-science docs (works with polymode + ESS).
;; Keep poly-markdown for .Rmd below.
(use-package quarto-mode
  :mode ("\\.qmd\\'" . poly-quarto-mode))

(use-package poly-markdown
  :mode
  (".Rmd$". poly-markdown-mode)
  :bind
  (:map poly-markdown-mode-localleader-map
   ("e" . polymode-export)
   ("j" . polymode-next-chunk-same-type)
   ("k" . polymode-previous-chunk-same-type))
  :bind-keymap
  ("M-n" . polymode-mode-map)
  :config
  ;; (add-hook 'poly-head-tail-mode-hook #'linum-mode)
  (bind-map-for-minor-mode poly-markdown-mode :evil-keys (","))
  (defun pm-ess-limit-eval-to-chunk (orig-fun &rest args)
    "Wrapper for ess-eval-functions.
Without this, apostrophes in the preceding text chunk cause
ess-mark-function, ess-send-function to fail, thinking they are inside a
string. Similarly, ess-eval-paragraph gets confused by the fence rows."
    (interactive)
    (let (res)
      (if poly-markdown-mode
          (save-restriction
            (pm-narrow-to-span)
            (setq res (apply orig-fun args)))
        (setq res (apply orig-fun args)))
      res))
  (advice-add 'ess-beginning-of-function :around #'pm-ess-limit-eval-to-chunk)
  (advice-add 'ess-eval-paragraph :around #'pm-ess-limit-eval-to-chunk)
  (advice-add 'ess-eval-region :around #'pm-ess-limit-eval-to-chunk)
  (setq polymode-display-process-buffers nil
        polymode-exporter-output-file-format "%s"))

(use-package prog-mode
  :ensure nil
  :config
  (add-hook 'prog-mode-hook #'goto-address-prog-mode)
  (add-hook 'prog-mode-hook #'prettify-symbols-mode)
  (add-hook 'prog-mode-hook #'visual-line-mode)
  (add-hook 'prog-mode-hook
            (defun my-prog-mode ()
              (setq show-trailing-whitespace t)))
  (defun pseudo-prog-mode ()
    (interactive)
    (funcall #'run-hooks 'prog-mode-hook))
  (setq prettify-symbols-unprettify-at-point 'right-edge))

(use-package puppet-mode
  :mode
  ("pp$" . puppet-mode))

;; Python (data science): python-ts-mode + IPython REPL + cell editing + marimo.
(use-package python
  :ensure nil
  :mode ("\\.py\\'" . python-mode)        ; treesit-auto remaps to python-ts-mode
  :interpreter ("python" . python-mode)
  :config
  (add-to-list 'python-shell-completion-native-disabled-interpreters "ipython")
  ;; IPython inferior shell (jupyter-console needed a missing jupyter). pet
  ;; overrides this per-project to the project venv interpreter.
  (setq python-indent-guess-indent-offset-verbose nil
        python-shell-prompt-detect-failure-warning nil
        python-shell-interpreter "ipython"
        python-shell-interpreter-args "-i --simple-prompt"))

;; pet: resolve the project's interpreter/venv (pyproject/poetry/uv/conda/.venv/
;; direnv) so eglot (basedpyright) AND the REPL use the right Python.
(use-package pet
  :config
  (add-hook 'python-base-mode-hook 'pet-mode -10))

;; code-cells: "# %%" notebook cells in plain .py; code-cells-eval dispatches to
;; whichever REPL is live (drepl / jupyter / inferior-python). Handles .ipynb too.
(use-package code-cells
  :hook ((python-mode python-ts-mode) . code-cells-mode-maybe)
  :config
  ;; Avoid clobbering evil gj/gk (line motion); use comint-style nav + eval.
  (bind-keys :map code-cells-mode-map
             ("C-c C-c" . code-cells-eval)
             ("C-c C-n" . code-cells-forward-cell)
             ("C-c C-p" . code-cells-backward-cell)))

;; drepl: rich IPython REPL (inline plots via comint-mime, no zmq build). The
;; default cell-eval target; code-cells dispatches to it automatically.
(use-package drepl)

(defun my-python-repl ()
  "Start the best available Python REPL (drepl IPython, else run-python)."
  (interactive)
  (cond ((fboundp 'drepl-ipython) (drepl-ipython))
        ((fboundp 'drepl-python)  (drepl-python))
        (t (call-interactively #'run-python))))

;; marimo has no Emacs package: edit the .py here and run the reactive UI in a
;; browser via `marimo edit --watch' in an eat buffer (bound to , m).
(defun my-marimo-edit (&optional file)
  "Run `marimo edit --watch' on FILE (default current buffer) in an eat buffer."
  (interactive)
  (let* ((file (expand-file-name (or file (buffer-file-name)
                                     (read-file-name "marimo edit: " nil nil t))))
         (default-directory (file-name-directory file))
         (bufname (format "*marimo: %s*" (file-name-nondirectory file))))
    (unless (executable-find "marimo")
      (user-error "marimo not found on PATH (pip install marimo)"))
    (if-let ((buf (get-buffer bufname)))
        (pop-to-buffer buf)
      (let ((eat-buffer-name bufname))
        (eat (format "marimo edit --watch %s" (shell-quote-argument file)))))))


;; apheleia: async format-on-save (point-stable). ruff for Python, prettier for
;; JS/TS/JSON/CSS/web-mode (all mapped out of the box). Install: uv tool install
;; ruff; npm i -g prettier.
(use-package apheleia
  :config
  (apheleia-global-mode +1))

(use-package rainbow-mode
  :commands rainbow-mode
  :diminish rainbow-mode)

(use-package rainbow-delimiters
  :commands (rainbow-delimiters-mode rainbow-delimiters-mode-enable)
  :init
  (add-hook 'prog-mode-hook #'rainbow-delimiters-mode)
  :config
  (set-face-attribute
   'rainbow-delimiters-mismatched-face nil
   :foreground "red"
   :weight 'bold)
  (set-face-attribute
   'rainbow-delimiters-unmatched-face nil
   :foreground "red"
   :weight 'bold))

(use-package rake
  :bind
  (:map leader-map
   ("rr" . rake)
   ("rf" . rake-find-task))
  :config
  (add-hook 'rake-compilation-mode-hook #'visual-line-mode))

(use-package rbenv
  :config
  (add-hook 'ruby-mode-hook #'global-rbenv-mode)
  (setq rbenv-modeline-function
        (defun rbenv--modeline-with-face (current-ruby)
          (list (propertize current-ruby 'face 'rbenv-active-ruby-face)))
        rbenv-show-active-ruby-in-modeline nil))

(use-package rebox2)

(use-package restclient
  :mode
  (".http$" . restclient-mode)
  :config
  (add-hook 'restclient-mode #'pseudo-prog-mode))

(use-package restart-emacs
  :commands restart-emacs
  :config
  (setq restart-emacs-restore-frames t))

;; rotate-layout is driven by my/window-rotate-transient (C-b SPC).
(use-package rotate
  :commands rotate-layout)

(use-package savehist
  :ensure nil
  :config
  (savehist-mode))

(use-package saveplace
  :ensure nil
  :config
  (setq save-place-file (expand-file-name "places" user-emacs-directory))
  (setq-default save-place t))

(use-package scala-mode
  :mode
  ("sbt$" . scala-mode)
  ("scala$" . scala-mode))

(use-package server
  :config
  (advice-add 'server-edit :before (lambda (&rest _) (save-buffer)))
  (remove-hook 'kill-buffer-query-functions 'server-kill-buffer-query-function)
  :diminish
  (server-buffer-clients . "client"))

(use-package sh-script
  :mode
  ("sh$" . sh-mode)
  ("zsh$" . sh-mode))

(use-package shr
  :ensure nil
  :config
  (advice-add #'shr-colorize-region :filter-args #'remove-colorize-bg-arg)
  (defun remove-colorize-bg-arg (args)
    "If more than 3 args, remove the last one (corresponding to bg color)."
    (if (> (length args) 3)
        (butlast args)
      args))
  (setq shr-bullet "• "
        shr-color-visible-luminance-min 70
        shr-width 90))

(use-package simple
  :ensure nil
  :bind
  (:map leader-map
   (":" . shell-command)
   ("k" . kill-this-buffer)
   ("td" . toggle-debug-on-error)
   ("tf" . auto-fill-mode)
   ("u" . universal-argument))
  :config
  (evil-define-key 'normal messages-buffer-mode-map
    (kbd "q") #'quit-window)
  (evil-define-key 'normal special-mode-map
    (kbd "q") #'quit-window)
  (setq mail-user-agent 'mu4e-user-agent)
  :diminish auto-fill-function overwrite-mode visual-line-mode)

(use-package smartparens
  :commands show-smartparens-mode smartparens-mode
  :init
  (add-hook 'prog-mode-hook #'show-smartparens-mode)
  (add-hook 'prog-mode-hook #'smartparens-mode)
  :config
  (require 'smartparens-config)
  (set-face-attribute
   'sp-show-pair-match-face nil
   :background 'unspecified
   :foreground "white"
   :inherit 'default
   :weight 'bold)
  (setq sp-cancel-autoskip-on-backward-movement nil)
  (sp-pair "`" nil :actions :rem)
  (with-eval-after-load 'evil
    (bind-keys
     :map evil-normal-state-map
      ("()k" . sp-splice-sexp-killing-around)
      ("()x" . sp-splice-sexp)
      ("(b" . sp-backward-barf-sexp)
      ("(k" . sp-splice-sexp-killing-backward)
      ("(s" . sp-backward-slurp-sexp)
      ("()t" . sp-transpose-sexp)
      (")b" . sp-forward-barf-sexp)
      (")k" . sp-splice-sexp-killing-forward)
      (")s" . sp-forward-slurp-sexp)))
  :diminish smartparens-mode)

(use-package smartparens-ess
  :ensure smartparens
  :after ess)

(use-package smartparens-lua
  :ensure smartparens
  :after lua-mode)

(use-package smartparens-python
  :ensure smartparens
  :after python)

(use-package smartparens-html
  :ensure smartparens
  :after web-mode)

(use-package smerge-mode
  :ensure nil
  :commands smerge-mode
  :bind
  (:map smerge-mode-map
   ("]n" . smerge-next)
   ("[n" . smerge-prev))
  :config
  (require 'transient)
  ;; Conflict menu (was hydra-merge-conflicts). j/k stay open; RET/e/m/o exit.
  (transient-define-prefix my/smerge-transient ()
    "Resolve merge conflicts."
    ["Conflicts"
     ("RET" "Keep current" smerge-keep-current)
     ("e"   "Ediff"        smerge-ediff)
     ("j"   "Next"         smerge-next :transient t)
     ("k"   "Previous"     smerge-prev :transient t)
     ("m"   "Keep mine"    smerge-keep-mine)
     ("o"   "Keep other"   smerge-keep-other)
     ("q"   "Quit"         transient-quit-one)
     ("<escape>" "Quit"    transient-quit-one)])
  ;; Open the transient deferred: calling transient-setup synchronously inside a
  ;; mode hook can race with buffer setup.
  (defun my/smerge-maybe-transient ()
    (when smerge-mode
      (run-at-time 0 nil
                   (lambda (buf)
                     (when (buffer-live-p buf)
                       (with-current-buffer buf
                         (when smerge-mode (my/smerge-transient)))))
                   (current-buffer))))
  (add-hook 'smerge-mode-hook #'my/smerge-maybe-transient))

;; smex removed - using Vertico with execute-extended-command instead
;; M-x is enhanced by Vertico + Marginalia automatically
(bind-keys
 :map leader-map
 ("x" . execute-extended-command))

(use-package snakemake-mode
  :mode
  ("^[Ss]nakefile$" . snakemake-mode))

(use-package snakemake
  :ensure snakemake-mode
  :commands snakemake-popup)

(use-package sql
  :ensure nil
  :mode
  ("ddl$" . sql-mode)
  ("hql$" . sql-mode)
  ("sql$" . sql-mode)
  :config
  (add-hook 'sql-interactive-mode-hook
            (defun my-sql-interactive-mode ()
              (toggle-truncate-lines t)))
  (evil-set-initial-state 'sql-interactive-mode 'insert)
  (setq sql-postgres-login-params
        '((user :default "postgres")
          (server :default "localhost")
          (port :default 5432)
          (database :default "postgres"))
        sql-send-terminator ";"))

(use-package sql-indent
  :after sql
  :config
  (setq sql-indent-offset 2))

(use-package sqlup-mode
  :commands sqlup-mode
  :init
  (add-hook 'sql-mode-hook #'sqlup-mode)
  (add-hook 'sql-interactive-mode-hook #'sqlup-mode)
  :diminish sqlup-mode)

(use-package ssh-config-mode
  :mode
  ("ssh/config$" . ssh-config-mode)
  ("sshd?_config$" . ssh-config-mode)
  :config
  (add-hook 'ssh-config-mode-hook #'pseudo-prog-mode))

(use-package ssh-tunnels
  :commands ssh-tunnels
  :config
  (evil-define-key 'menu ssh-tunnels-mode-map
    (kbd "C-c C-u") #'ssh-tunnels-refresh
    (kbd "G") (lambda () (interactive)
                (evil-goto-line)
                (evil-previous-line 1))
    (kbd "d") #'ssh-tunnels-kill)
  (evil-set-initial-state 'ssh-tunnels-mode 'menu)
  (setq ssh-tunnels-name-width 16
        ssh-tunnels-host-width 10))

(use-package string-utils
  :ensure nil
  :after yasnippet)

(use-package sudo-edit
  :commands sudo-edit)

(use-package systemd
  :if (eq system-type 'gnu/linux)
  :mode ("service$" . systemd-mode))                      ;

;; eat - Emulate A Terminal (modern terminal emulator)
;; Faster, 24-bit color, better mouse/Evil support
(use-package eat
  :bind
  (("C-'" . eat-pop)
   :map eat-mode-map
   ("<C-backspace>" . eat-self-input)
   ("<escape>" . eat-self-input)
   ("C-'" . delete-window)
   ("C-c" . eat-self-input)
   ("C-l" . eat-clear-buffer)
   ("C-v" . eat-yank)
   :map eat-semi-char-mode-map
   ("<C-backspace>" . eat-self-input)
   ("<escape>" . eat-self-input)
   ("C-'" . delete-window)
   ("C-l" . eat-clear-buffer)
   ("C-v" . eat-yank)
   ("M-x" . execute-extended-command))
  :init
  (defun eat-pop () (interactive)
         (let* ((name (my-tab-current-name))      ; was (persp-name (persp-curr))
                (eat-name (concat name "-eat"))
                (full-eat-name (concat "*" eat-name "*"))
                (buffer (get-buffer full-eat-name)))
           (if buffer
               (switch-to-buffer-other-window buffer)
             (progn
               (switch-to-buffer-other-window eat-name)
               (eat (getenv "SHELL"))))))
  (defun terminal () (interactive)
         (let* ((default-directory "~")
                (name "term")
                (kill-func (apply-partially #'tab-bar-close-tab-by-name name)))
           (my-tab-switch-or-create name)         ; was (persp-switch name)
           (eat (getenv "SHELL"))
           (my--repl-exit-hook kill-func)))
  (with-eval-after-load 'org
    (bind-keys
     :map org-mode-map
     ("C-'" . nil)))
  :config
  ;; Integrate with eshell
  (add-hook 'eshell-load-hook #'eat-eshell-mode)
  (add-hook 'eshell-load-hook #'eat-eshell-visual-command-mode)
  ;; Kill buffer on exit
  (add-hook 'eat-exit-hook
            (defun my-eat-kill-on-exit (process)
              (when (memq (process-status process) '(exit signal))
                (kill-buffer (process-buffer process)))))
  (add-hook 'eat-mode-hook #'my--repl-mode)
  ;; Evil integration
  (evil-set-initial-state 'eat-mode 'emacs)
  (with-eval-after-load 'evil
    (evil-define-key 'emacs eat-mode-map
      (kbd "C-z") #'eat-self-input)
    (evil-define-key 'normal eat-mode-map
      (kbd "G") (lambda () (interactive)
                  (goto-char (point-max))
                  (evil-emacs-state))
      (kbd "RET") (lambda () (interactive)
                    (evil-emacs-state))))
  (setq eat-kill-buffer-on-exit t
        eat-term-name "xterm-256color"))

;; Keep term as fallback for compatibility
(use-package term
  :disabled
  :ensure nil
  :commands ansi-term
  :bind
  (("C-'" . term-pop)
   :map term-raw-map
   ("<C-backspace>" . term-send-backward-kill-word)
   ("<backtab>" . term-send-backtab)
   ("<escape>" . term-send-esc)
   ("C-'" . delete-window)
   ("C-c" . term-interrupt-subjob)
   ("C-h" . nil)
   ("C-l" . comint-clear-buffer)
   ("C-v" . term-paste)
   ("M-x" . nil))
  :init
  (defun term-pop () (interactive)
         (let* ((name (my-tab-current-name))
                (term-name (concat name "-term"))
                (full-term-name (concat "*" term-name "*"))
                (buffer (get-buffer full-term-name)))
           (if buffer
               (switch-to-buffer-other-window buffer)
             (progn
               (switch-to-buffer-other-window term-name)
               (ansi-term (getenv "SHELL") term-name)))))
  (with-eval-after-load 'org
    (bind-keys
     :map org-mode-map
     ("C-'" . nil)))
  :config
  (add-hook 'term-exec-hook
            (defun my-set-kill-on-exit ()
              (set-process-query-on-exit-flag
               (get-buffer-process (current-buffer)) nil)))
  (add-hook 'term-mode-hook #'my--repl-mode)
  (defun term-send-backward-kill-word () (interactive)
         (term-send-raw-string "\C-w"))
  (defun term-send-backtab () (interactive)
         (term-send-esc)
         (term-send-raw-string "[Z"))
  (defun term-send-esc () (interactive)
         (term-send-raw-string "\e"))
  (evil-define-key 'emacs term-raw-map
    (kbd "C-z") #'term-send-raw)
  (evil-define-key 'normal term-raw-map
    (kbd "G") (lambda () (interactive)
                (term-send-raw-string "")
                (evil-emacs-state)
                (term-send-esc))
    (kbd "RET") (lambda () (interactive)
                  (evil-emacs-state)
                  (term-send-raw-string "")))
  (evil-set-initial-state 'term-mode 'emacs)
  (setq term-buffer-maximum-size 100000
        term-scroll-show-maximum-output t))

(use-package term-cmd :disabled
  :after term
  :init
  (defun cursor-shape (command shape)
    (when (string= "0" shape) (setq evil-emacs-state-cursor 'box))
    (when (string= "1" shape) (setq evil-emacs-state-cursor 'bar)))
  (add-to-list 'term-cmd-commands-alist '("CursorShape" . cursor-shape))
  (defun leader-toggle (command toggle)
    (when (string= "on" toggle) (bind-key "SPC" #'leader-map-prefix term-raw-map))
    (when (string= "off" toggle) (bind-key "SPC" #'term-send-raw term-raw-map)))
  (add-to-list 'term-cmd-commands-alist '("LeaderToggle" . leader-toggle)))

(use-package text-mode
  :ensure nil
  :mode
  ("txt$" . text-mode)
  :commands text-mode
  :init
  (defun my-prose-mode ()
    (interactive)
    (auto-fill-mode)
    (jinx-mode)
    (writegood-mode)
    (unless (eq major-mode 'org-mode) (orgtbl-mode)))
  :config
  (add-hook 'text-mode-hook #'pseudo-prog-mode)
  (add-hook 'text-mode-hook #'my-prose-mode))

(use-package tramp
  :ensure nil
  :commands tramp-mode
  :init
  (setq tramp-ssh-controlmaster-options "")
  :config
  (add-to-list 'tramp-remote-path 'tramp-own-remote-path)
  (setq tramp-default-method "sshx"
        vc-handled-backends '(Git)))

;; vundo - modern undo visualization (replaces unmaintained undo-tree)
(use-package vundo
  :bind
  (:map leader-map
   ("C-u" . vundo))
  :config
  (setq vundo-glyph-alist vundo-unicode-symbols
        vundo-compact-display t)
  ;; Evil-style navigation in vundo buffer
  (with-eval-after-load 'evil
    (evil-define-key 'normal vundo-mode-map
      "h" #'vundo-backward
      "j" #'vundo-next
      "k" #'vundo-previous
      "l" #'vundo-forward
      "q" #'vundo-quit
      (kbd "RET") #'vundo-confirm)))

(use-package uniquify
  :ensure nil
  :config
  (setq uniquify-buffer-name-style 'forward))

(use-package uuidgen
  :commands uuidgen)

(use-package vagrant)

(use-package vagrant-tramp
  :after tramp)

;; vertica removed (stale old-job Uber tooling).

(use-package vimrc-mode
  :mode
  ("vimrc$" . vimrc-mode))

(use-package virtualenvwrapper
  :commands venv-initialize-eshell)

(use-package vlf-setup
  :ensure vlf)

(use-package warnings
  :config
  (add-to-list 'warning-suppress-types '(yasnippet backquote-change)))

;; JavaScript / TypeScript / React: jtsx layers JSX/TSX editing (tag wrap/rename/
;; auto-close) on the built-in tree-sitter ts modes. Eglot + typescript-language-
;; server handle LSP; apheleia formats with prettier. Run M-x
;; jtsx-install-treesit-language once per grammar if treesit-auto didn't.
(use-package jtsx
  :mode (("\\.jsx?\\'" . jtsx-jsx-mode)
         ("\\.tsx\\'"  . jtsx-tsx-mode)
         ("\\.ts\\'"   . jtsx-typescript-mode))
  :commands jtsx-install-treesit-language
  :custom
  (js-indent-level 2)
  (typescript-ts-mode-indent-offset 2))

(use-package web-mode
  :mode
  ("css$" . web-mode)
  ("html$" . web-mode)
  ("mustache$" . web-mode)
  :config
  (setq web-mode-code-indent-offset 2
        web-mode-comment-style 2
        web-mode-css-indent-offset 2
        web-mode-enable-css-colorization t
        web-mode-enable-engine-detection t
        web-mode-markup-indent-offset 2))

(use-package which-key
  :ensure nil  ; built into Emacs 30
  :config
  (bind-keys
   :map leader-map
    ("?" . which-key-show-top-level))
  (which-key-add-key-based-replacements
    "(" "Sexp backward"
    "()" "Sexp around"
    ")" "Sexp forward"
    "SPC f" "Find"
    "SPC g" "Git"
    "SPC li" "Lorem Ipsum"
    "SPC o" "Org")
  (which-key-mode)
  :diminish which-key-mode)

(use-package whitespace
  :bind
  (:map leader-map
   ("w" . delete-trailing-whitespace))
  :init
  (add-hook 'before-save-hook #'delete-trailing-whitespace)
  :config
  (set-face-background 'whitespace-space 'unspecified)
  :diminish whitespace-mode)

;; windsize-* are driven by my/window-resize-transient (C-b C-h/j/k/l).
(use-package windsize
  :commands
  (windsize-down
   windsize-left
   windsize-right
   windsize-up)
  :config
  (setq windsize-cols 5
        windsize-rows 5))

(use-package writegood-mode
  :commands writegood-mode
  :diminish writegood-mode)

(use-package writeroom-mode
  :commands writeroom-mode)

(use-package xwidget
  :ensure nil
  :config
  (evil-define-key 'menu xwidget-webkit-mode-map
    (kbd "j") #'xwidget-webkit-scroll-up
    (kbd "k") #'xwidget-webkit-scroll-down)
  (evil-set-initial-state 'xwidget-webkit-mode 'menu))

(use-package yaml-mode
  :mode
  ("yaml$" . yaml-mode)
  ("yml$" . yaml-mode)
  :config
  (add-hook 'yaml-mode-hook #'pseudo-prog-mode)
  (setq yaml-block-literal-electric-alist '(("|" . "-"))))

(use-package yankpad
  :commands yankpad-insert
  :config
  (setq yankpad-file (expand-file-name "yankpad.org" user-emacs-directory)))

(use-package yasnippet
  :commands yas-minor-mode
  :bind
  (:map leader-map
   ("y" . yas-insert-snippet))
  :init
  (add-hook 'my-prose-mode #'yas-minor-mode)
  (add-hook 'prog-mode-hook #'yas-minor-mode)
  (add-hook 'pseudo-prog-mode #'yas-minor-mode)
  :config
  (add-hook 'snippet-mode-hook #'pseudo-prog-mode)
  (add-hook 'yas-before-expand-snippet-hook #'evil-insert-state)
  (add-hook 'yas-minor-mode-hook (apply-partially #'yas-activate-extra-mode #'fundamental-mode))
  (setq yas-trigger-symbol "→"
        yas-verbosity 0
        yas-wrap-around-region nil)
  (yas-reload-all)
  :diminish yas-minor-mode)

(provide 'init)
