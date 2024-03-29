;; (package-initialize)

(scroll-bar-mode -1)
(tool-bar-mode -1)

(add-to-list 'default-frame-alist '(cursor-color . "white"))
(add-to-list 'default-frame-alist '(font . "Hack-13"))
(add-to-list 'default-frame-alist '(right-divider-width . 2))
(add-to-list 'default-frame-alist '(ns-transparent-titlebar . t))
(add-to-list 'default-frame-alist '(ns-appearance . dark))

(fset #'yes-or-no-p #'y-or-n-p)

(setq completion-ignore-case t
      disabled-command-function nil
      epa-pinentry-mode 'loopback
      gc-cons-threshold most-positive-fixnum
      history-delete-duplicates t
      inhibit-splash-screen t
      initial-major-mode 'org-mode
      kill-buffer-query-functions nil
      load-prefer-newer t
      ns-use-srgb-colorspace nil
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
            (setq gc-cons-threshold 800000)))

(defun my--repl-exit-hook (f)
  "Close current buffer when `exit' from process."
  (lexical-let ((f f))
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

(eval-when-compile
  ;; load-path
  (mapc (defun add-to-load-path (dir)
          (let ((default-directory (expand-file-name dir user-emacs-directory)))
            (normal-top-level-add-subdirs-to-load-path)))
        '("elpa" "site-lisp"))

  ;; package.el
  (require 'package)
  (setq package-archives
        '(("org" . "https://orgmode.org/elpa/")
          ("melpa" . "https://melpa.org/packages/")
          ("melpa-stable" . "https://stable.melpa.org/packages/")
          ("gnu" . "https://elpa.gnu.org/packages/"))
        package-enable-at-startup nil)
  (package-initialize 'no-activate)

  ;; use-package
  (unless (package-installed-p 'use-package)
    (package-refresh-contents)
    (package-install 'use-package))
  (require 'use-package)
  (setq use-package-always-ensure t))

(use-package diminish
  :config
  (diminish 'centered-cursor-mode))

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
        (if linum-mode
            (linum-mode -1)
          (linum-mode +1))))
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

(use-package projectile
  :init
  (setq projectile-keymap-prefix "")
  :config
  (add-to-list 'projectile-ignored-projects "/usr/local")
  (bind-keys
   :map leader-map
   ("i" . projectile-ibuffer)
   ("p" . projectile-command-map))
  (defadvice projectile-on (around exlude-tramp activate)
    "This should disable projectile when visiting a remote file"
    (unless  (--any? (and it (file-remote-p it))
                     (list
                      (buffer-file-name)
                      list-buffers-directory
                      default-directory
                      dired-directory))
      ad-do-it))
  (projectile-mode)
  (setq projectile-indexing-method 'alien
        projectile-mode-line "Projectile"
        projectile-switch-project-action #'projectile-dired)
  :diminish projectile-mode)

(use-package helm-projectile
  :after helm
  :commands helm-projectile-find-file
  :bind
  (:map projectile-command-map
   ("sg" . helm-projectile-grep)
   ("ss" . helm-projectile-ag)))

(use-package helm-tail
  :after helm
  :commands helm-tail)

(use-package hydra
  :config
  (setq hydra-hint-display-type 'lv))

(use-package perspective
  :after hydra
  :bind
  (:map perspective-map ;; emulate tmux
   ("%" . evil-window-split)
   ("&" . persp-kill)
   ("," . persp-rename)
   ("\"" . evil-window-vsplit)
   ("w" . persp-switch))
  :config
  (defhydra hydra-persp
    (perspective-map)
    "Perspectives"
    ("C-p" persp-prev "Previous")
    ("C-n" persp-next "Next"))
  (defun my-frame-title-format ()
    (concat
     "Emacs ❯ "
     (if persp-mode (format "%s ❯ " (persp-name (persp-curr))))
     (cond ((buffer-file-name)
            (file-name-nondirectory buffer-file-name))
           ((member major-mode '(eshell-mode term-mode))
            (abbreviate-file-name default-directory))
           ("%b"))))
  (set-face-attribute
   'persp-selected-face nil
   :foreground 'unspecified
   :inherit 'mode-line-highlight)
  (setq frame-title-format '((:eval (my-frame-title-format)))
        persp-mode-prefix-key "C-b"
        persp-initial-frame-name "scratch"
        persp-modestring-dividers '("" "" " "))
  (persp-mode))

(use-package persp-projectile
  :demand t
  :bind
  (:map projectile-command-map
   ("p" . projectile-persp-switch-project)))

(use-package spaceline-config
  :ensure spaceline
  :config
  (spaceline-helm-mode)
  (spaceline-compile
    `(((persp-name
        workspace-number
        window-number)
       :fallback evil-state
       :face highlight-face
       :priority 100)
      (anzu :priority 95)
      auto-compile
      ((buffer-modified
        buffer-size
        buffer-id
        remote-host)
       :priority 98)
      (major-mode :priority 79)
      (process :when active)
      ((flycheck-error
        flycheck-warning
        flycheck-info)
       :when active
       :priority 89)
      (minor-modes
       :when active
       :priority 9)
      (mu4e-alert-segment :when active)
      (erc-track :when active)
      (version-control
       :when active
       :priority 78)
      (org-pomodoro :when active)
      (org-clock :when active))
    `(which-function
      (python-pyvenv :fallback python-pyenv)
      (purpose :priority 94)
      (battery :when active)
      (selection-info :priority 95)
      ((point-position
        line-column)
       :separator " | "
       :priority 96)
      (global :when active)
      (buffer-position :priority 99)
      (hud :priority 99)))
  (setq-default mode-line-format '("%e" (:eval (spaceline-ml-main)))))

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

(use-package arch-packer
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
  (with-eval-after-load 'perspective
    (add-to-list 'bs-configurations
                 '("persp-files" nil nil nil bs-visits-perspective nil))
    (defun bs-visits-perspective (buffer)
      (with-current-buffer buffer
        (not (and (member buffer (persp-buffers (persp-curr)))
                  (buffer-file-name buffer)))))
    (setq-default bs-default-configuration "persp-files")))

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

(use-package calfw)

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

(use-package company
  :commands company-mode
  :bind
  (:map company-active-map
   ("C-d" . company-next-page)
   ("C-f" . company-complete-common)
   ("C-n" . company-select-next)
   ("C-p" . company-select-previous)
   ("C-u" . company-previous-page))
  :init
  (add-hook 'prog-mode-hook #'company-mode)
  :config
  (add-hook 'prog-mode-hook
            (defun setup-yas-with-backends ()
              (defun setup-yas-with-backend (backend)
                (let ((backend (if (consp backend)
                                   backend
                                 (list backend))))
                  (if (member 'company-yasnippet backend)
                      backend
                    (append backend '(:with company-yasnippet)))))
              (setq company-backends (mapcar #'setup-yas-with-backend company-backends))))
  (set-face-attribute
   'company-preview-common nil
   :foreground 'unspecified
   :background 'unspecified
   :inherit 'company-tooltip-selection)
  (setq company-backends
        '(company-css
          company-dabbrev-code
          company-files
          company-keywords
          company-math-symbols-unicode
          company-nxml)
        company-minimum-prefix-length 2
        company-selection-wrap-around t
        company-tooltip-align-annotations t)
  (setup-yas-with-backends)
  (with-eval-after-load 'evil
    (defun evil-company-complete (_) (company-complete))
    (setq evil-complete-previous-func #'evil-company-complete
          evil-complete-next-func #'evil-company-complete))
  :diminish company-mode)

(use-package company-files
  :ensure company
  :bind
  (:map evil-insert-state-map
   ("C-x C-f" . company-files)))

(use-package company-math
  :after company
  :config
  (add-to-list 'company-backends #'company-math-symbols-unicode)
  (setup-yas-with-backends))

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
           (colors (loop for i from 0 to 1.0 by (/ 2.0 n) collect
                         (apply #'color-rgb-to-hex (color-hsl-to-rgb i 0.3 0.5)))))
      (loop for i from 2 to n by 2
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
    "Open a perspective for feeds."
    (interactive)
    (persp-switch "files")
    (dired "~"))
  (evil-set-initial-state 'dired-mode 'menu)
  (evil-define-key 'menu dired-mode-map
    (kbd "<tab>") #'peep-dired
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

(use-package dired-k
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
  (defadvice dired-omit-startup (after diminish-dired-omit activate)
    (diminish 'dired-omit-mode) dired-mode-map))

(use-package doc-view
  :ensure nil
  :mode
  ("pdf$" . doc-view-mode))

(use-package docker
  :bind-keymap
  ("C-c d" . docker-command-map)
  :config
  (docker-global-mode)
  :diminish docker-mode)

(use-package docker-tramp
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

(use-package elpy
  :pin melpa-stable
  :commands elpy-mode
  :bind
  (:map python-mode-localleader-map
   ("8" . elpy-autopep8-fix-code)
   ("g" . elpy-goto-definition)
   ("h" . python-indent-shift-left)
   ("l" . python-indent-shift-right)
   ("t" . elpy-test-run))
  :init
  (add-hook 'python-mode-hook #'elpy-mode)
  :config
  (add-hook 'elpy-mode-hook #'setup-yas-with-backends)
  (add-hook 'python-mode-hook #'elpy-mode)
  (bind-map-for-major-mode python-mode :evil-keys (","))
  (delete 'elpy-module-flymake elpy-modules)
  (evil-make-overriding-map elpy-mode-map)
  (setq elpy-disable-backend-error-display t
        elpy-rpc-backend "jedi"
        elpy-rpc-python-command "/usr/bin/python3"
        python-shell-interpreter "/usr/bin/python3"
        python-shell-interpreter-args "-i")
  (with-eval-after-load 'highlight-indentation
    (diminish 'highlight-indentation-mode))
  :diminish
  (elpy-mode . "elpy"))

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
                ([remap eshell-pcomplete] . helm-esh-pcomplete))
              (evil-define-key 'insert eshell-mode-map
                (kbd "C-n") #'eshell-next-matching-input-from-input
                (kbd "C-p") #'eshell-previous-matching-input-from-input
                (kbd "C-r") #'helm-eshell-history)
              (evil-define-key 'normal eshell-mode-map
                (kbd "C-r") #'helm-eshell-history
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

(use-package evil-ediff
  :after ediff)

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

(use-package exec-path-from-shell
  :config
  (setq exec-path-from-shell-arguments '("-l")
        exec-path-from-shell-variables
        '("EDITOR"
          "GPG_AGENT_INFO"
          "LANG"
          "LANGUAGE"
          "LC_ALL"
          "MAINDB_PW"
          "MANPATH"
          "MOBILE_PW"
          "PATH"
          "SSH_AUTH_SOCK"))
  (exec-path-from-shell-initialize))

(use-package f
  :ensure nil
  :after yasnippet)

(use-package fabric)

(use-package faces
  :ensure nil
  :config
  (set-face-attribute
   'header-line nil
   :background 'unspecified
   :inherit 'mode-line)
  ;; (set-face-attribute
  ;;  'widget-field nil
  ;;  :background 'unspecified
  ;;  :inherit 'highlight
  ;;  :box nil)
  (set-face-attribute
   'window-divider nil
   :foreground (plist-get base16-tomorrow-night-colors :base02))
  (set-face-background 'fringe (plist-get base16-tomorrow-night-colors :base00))
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

(use-package flycheck
  :commands flycheck-mode
  :bind
  (:map evil-normal-state-map
   ("]l" . flycheck-next-error)
   ("[l" . flycheck-previous-error)
   :map leader-map
   ("e" . hydra-flycheck/body))
  :init
  (add-hook 'prog-mode-hook #'flycheck-mode)
  :config
  (defhydra hydra-flycheck
    (:foreign-keys run
     :pre (progn
            (flycheck-list-errors))
     :post (progn
             (quit-windows-on "*Flycheck errors*"))
     :hint nil)
    "Errors"
    ("j" #'flycheck-next-error "Next")
    ("k" #'flycheck-previous-error "Previous")
    ("gg" #'flycheck-first-error "First")
    ("G" (progn
           (evil-goto-line)
           (flycheck-previous-error)) "Last")
    ("f" #'flycheck-error-list-set-filter "Filter")
    ("s" #'helm-flycheck "Search" :color blue)
    ("<escape>" nil)
    ("q" nil))
  (define-fringe-bitmap 'my-flycheck-fringe-indicator
    (vector #b00000000
            #b00000000
            #b00000000
            #b00000000
            #b00000000
            #b00000000
            #b00011100
            #b00111110
            #b00111110
            #b00111110
            #b00011100
            #b00000000
            #b00000000
            #b00000000
            #b00000000
            #b00000000
            #b00000000))
  (evil-set-initial-state 'flycheck-error-list-mode 'menu)
  (flycheck-define-error-level 'error
    :overlay-category 'flycheck-error-overlay
    :fringe-bitmap 'my-flycheck-fringe-indicator
    :fringe-face 'flycheck-fringe-error)
  (flycheck-define-error-level 'warning
    :overlay-category 'flycheck-warning-overlay
    :fringe-bitmap 'my-flycheck-fringe-indicator
    :fringe-face 'flycheck-fringe-warning)
  (flycheck-define-error-level 'info
    :overlay-category 'flycheck-info-overlay
    :fringe-bitmap 'my-flycheck-fringe-indicator
    :fringe-face 'flycheck-fringe-info)
  (setq flycheck-display-errors-delay 0
        flycheck-emacs-lisp-load-path 'inherit
        flycheck-flake8-maximum-line-length nil
        flycheck-scalastylerc "/usr/local/etc/scalastyle_config.xml")
  (setq-default flycheck-disabled-checkers '(emacs-lisp-checkdoc))
  :diminish flycheck-mode)

(use-package flycheck-haskell
  :after haskell-mode)

(use-package flycheck-ledger
  :after ledger-mode)

(use-package flyspell-correct-ido
  :ensure flyspell-correct
  :config
  (bind-keys
   :map flyspell-mode-map
    ("C-;" . flyspell-correct-word-generic))
  :diminish
  (flyspell-correct-auto-mode flyspell-mode))

(use-package flx-ido
  :config
  (flx-ido-mode)
  (setq flx-ido-use-faces nil))

(use-package fontawesome
  :commands helm-fontawesome)

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
  ("s-u" . hydra-transparency/body)
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
  (setq frame-resize-pixelwise t
        frame-title-format "%b"
        ns-use-native-fullscreen nil)
  (with-eval-after-load 'hydra
    (defhydra hydra-transparency
      (:columns 2)
      "\nALPHA: %(or (frame-parameter nil 'alpha) 100)\n"
      ("j" (lambda () (interactive) (set-frame-alpha +1)) "+ more")
      ("k" (lambda () (interactive) (set-frame-alpha -1)) "- less")
      ("C-j" (lambda () (interactive) (set-frame-alpha +5)) "++ more")
      ("C-k" (lambda () (interactive) (set-frame-alpha -5)) "-- less")
      ("=" (lambda (value) (interactive "nTransparency Value 0 - 100 opaque: ")
             (set-frame-parameter (selected-frame) 'alpha value))
       "Set to ?" :color blue))))

(use-package git-gutter
  :commands git-gutter-mode
  :bind
  (:map evil-normal-state-map
   ("]c" . git-gutter:next-hunk)
   ("[c" . git-gutter:previous-hunk)
   :map leader-map
   ("g" . hydra-git-gutter/body))
  :init
  (add-hook 'prog-mode-hook #'git-gutter-mode)
  :config
  (defhydra hydra-git-gutter
    (:post (progn
             (condition-case nil
                 (delete-windows-on "*git-gutter:diff*")
               (error nil))))
    "Git"
    ("b" #'magit-branch "Branch" :color blue)
    ("c" #'magit-commit "Commit" :color blue)
    ("F" #'magit-pull "Pull" :color blue)
    ("f" #'magit-fetch "Fetch" :color blue)
    ("p" #'magit-push "Push" :color blue)
    ("v" #'magit-status "Status" :color blue)
    ("l" #'magit-log "Log" :color blue)
    ("d" #'git-gutter:popup-hunk "Diff")
    ("s" #'git-gutter:stage-hunk "Stage")
    ("r" #'git-gutter:revert-hunk "Revert")
    ("j" #'git-gutter:next-hunk "Next")
    ("k" #'git-gutter:previous-hunk "Previous")
    ("gg" (progn
            (evil-goto-first-line)
            (git-gutter:next-hunk 1)) "First")
    ("G" (progn
           (evil-goto-line)
           (git-gutter:previous-hunk 1)) "Last")
    ("<escape>" nil)
    ("q" nil))
  (setq git-gutter:ask-p nil)
  :diminish git-gutter-mode)

(use-package git-gutter-fringe
  :after git-gutter
  :config
  (setq git-gutter-fr:side 'right-fringe))

(use-package gitconfig-mode
  :mode
  ("git/config$" . gitconfig-mode)
  ("gitconfig$" . gitconfig-mode)
  ("gitmodules$" . gitconfig-mode)
  ("/git/config$" . gitconfig-mode)
  :config
  (add-hook 'gitconfig-mode-hook #'pseudo-prog-mode)
  (add-hook 'gitconfig-mode-hook
            (defun my-gitconfig-mode ()
              (setq tab-width 2))))

(use-package gitignore-mode
  :mode
  ("git/info/exclude$" . gitignore-mode)
  ("gitignore$" . gitignore-mode)
  ("/git/ignore$" . gitignore-mode)
  :config
  (add-hook 'gitignore-mode-hook #'pseudo-prog-mode))

(use-package graphviz-dot-mode
  :mode
  ("dot$" . graphviz-dot-mode))

(use-package haskell-mode
  :mode
  ("hs$" . haskell-mode))

(use-package haskell-snippets
  :after haskell-mode)

(use-package helm
  :after helm-config
  :bind
  (:map helm-command-map
   (":" . helm-eval-expression-with-eldoc)
   ("o" . helm-occur)
   ("p" . helm-show-kill-ring)
   ("z" . helm-info-zsh)
   :map helm-map
   ("<escape>" . helm-keyboard-quit)
   ("C-d" . helm-next-page)
   ("C-j" . helm-next-line)
   ("C-k" . helm-previous-line)
   ("C-l" . helm-execute-persistent-action)
   ("C-n" . next-complete-history-element)
   ("C-p" . previous-complete-history-element)
   ("C-u" . helm-previous-page)
   ("C-v" . yank))
  :config
  (helm-autoresize-mode))

(use-package helm-ag
  :after helm-config
  :bind
  (:map helm-command-map
   ("g" . helm-ag)))

(use-package helm-aws
  :commands helm-aws)

(use-package helm-company
  :commands helm-company)

(use-package helm-config
  :ensure helm
  :init
  (bind-keys
   :map leader-map
    ("h" . helm-command-prefix)
    ("oc" . helm-org-capture-templates))
  :config
  (add-hook 'helm-update-hook
            (defun my-helm-update-hook ()
              (setq cursor-in-non-selected-windows nil)))
  (setq helm-completion-window-scroll-margin 3
        helm-display-header-line nil
        helm-display-source-at-screen-top nil
        helm-split-window-in-side-p t))

(use-package helm-files
  :ensure helm
  :commands
  (helm-find
   helm-find-files
   helm-for-files
   helm-multi-files
   helm-recentf)
  :bind
  (:map helm-find-files-map
   ("<C-backspace>" . backward-kill-word)
   ("C-h" . helm-find-files-up-one-level)
   ("C-l" . helm-execute-persistent-action)
   :map leader-map
   ("ff" . helm-find-files))
  :config
  (add-to-list 'helm-boring-file-regexp-list (rx line-start ".DS_Store" line-end))
  (setq helm-ff-auto-update-initial-value t))

(use-package helm-flycheck
  :commands helm-flycheck)

(use-package helm-gitignore
  :commands helm-gitignore)

(use-package helm-ispell
  :commands helm-ispell)

(use-package helm-make
  :commands helm-make)

(use-package helm-mode-manager
  :commands
  (helm-disable-minor-mode
   helm-enable-minor-mode
   helm-switch-major-mode))

(use-package helm-mu
  :commands
  (helm-mu
   helm-mu-contacts))

(use-package helm-org-rifle
  :commands
  (helm-org-rifle
   helm-org-rifle-current-buffer))

(use-package helm-sql-connect
  :commands helm-sql-connect)

(use-package helm-system-packages)

(use-package helm-systemd
  :after helm-config
  :bind
  (:map helm-command-map
   ("d" . helm-systemd)))

(use-package helm-tramp
  :commands helm-tramp)

(use-package helm-unicode
  :commands helm-unicode)

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

(use-package ido
  :ensure nil
  :config
  (add-hook 'ido-setup-hook
            (defun my-ido-setup-hook ()
              (bind-keys
               :map ido-completion-map
                ("C-n" . next-complete-history-element)
                ("C-p" . previous-complete-history-element))))
  (ido-everywhere)
  (setq ido-completion-buffer nil
        ido-enable-flex-matching t))

(use-package ido-at-point
  :config
  (ido-at-point-mode))

(use-package ido-complete-space-or-hyphen)

(use-package ido-completing-read+)

(use-package ido-grid-mode
  :config
  (add-hook 'ido-setup-hook
            (defun my-ido-gride-mode ()
              (bind-keys
               :map ido-completion-map
                ("C-j" . ido-grid-mode-down)
                ("C-k" . ido-grid-mode-up)
                ("C-h" . ido-grid-mode-left)
                ("C-l" . ido-grid-mode-right))))
  (defun ido-advice-single-line (o &rest args)
    (let ((ido-grid-mode-max-rows 1)
          (ido-grid-mode-min-rows 1)
          (ido-grid-mode-padding " • "))
      (apply o args)))
  (ido-grid-mode)
  (setq ido-grid-mode-min-rows 1
        ido-grid-mode-prefix nil))

(use-package ido-completing-read+
  :commands ido-ubiquitous-mode
  :init
  (add-hook 'ido-setup-hook #'ido-ubiquitous-mode))

(use-package image+
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

(use-package linum
  :ensure nil
  :commands linum-mode
  :init
  (add-hook 'prog-mode-hook #'linum-mode)
  :config
  (set-face-attribute
   'linum nil
   :background (plist-get base16-tomorrow-night-colors :base00)
   :underline nil))

(use-package linum-relative
  :after linum
  :config
  (add-hook 'evil-insert-state-entry-hook (lambda () (setq linum-format 'my-linum-formatter)))
  (add-hook 'evil-insert-state-exit-hook (lambda () (setq linum-format 'linum-relative)))
  (add-hook 'evil-normal-state-entry-hook (lambda () (setq linum-format 'linum-relative)))
  (defun my-linum-formatter (line-number)
    (propertize (format linum-relative-format line-number) 'face 'linum))
  (if window-system
      (setq linum-relative-format "%4s")
    (setq linum-relative-format "%4s "))
  (set-face-attribute
   'linum-relative-current-face nil
   :background 'unspecified
   :foreground 'unspecified
   :inherit 'linum)
  (setq linum-format #'my-linum-formatter
        linum-relative-current-symbol ""))

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
  (setq magit-completing-read-function #'magit-ido-completing-read
        magit-push-always-verify nil
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

(use-package menu-bar
  :ensure nil
  :config
  (menu-bar-mode -1))

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
  :ensure org-plus-contrib
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
     (ledger . t)
     (ruby . t)
     (python . t)
     (shell . t)
     (sql . t))))

(use-package ob-ipython :disabled
  :after ob-core
  :config
  (add-to-list 'org-babel-tangle-lang-exts '("ipython" . "py")))

(use-package on-screen
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
  :ensure org-plus-contrib
  :ensure htmlize
  :bind
  (:map leader-map
   ("os" . org-store-link)
   :map org-mode-localleader-map
   ("/" . helm-org-in-buffer-headings)
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
  (defhydra hydra-org-move
    (org-mode-localleader-map)
    "Org heading navigation"
    ("b" (progn (org-backward-heading-same-level 1) (org-beginning-of-line)) "Previous sibling")
    ("f" (progn (org-forward-heading-same-level 1) (org-beginning-of-line)) "Next sibling")
    ("n" (progn (org-next-visible-heading 1) (org-beginning-of-line)) "Next")
    ("p" (progn (org-previous-visible-heading 1) (org-beginning-of-line)) "Previous")
    ("u" (progn (outline-up-heading 1) (org-beginning-of-line)) "Up"))
  (defhydra hydra-org-nav
    (org-mode-localleader-map)
    "Org moving map"
    ("h" (org-metaleft) "Move in")
    ("j" (org-metadown) "Move down")
    ("k" (org-metaup) "Move up")
    ("l" (org-metaright) "Move out"))
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
  (org-babel-lob-ingest (expand-file-name "lob.org" user-emacs-directory))
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
        org-completion-use-ido t
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
  :ensure org-plus-contrib
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
  :ensure org-plus-contrib
  :after helm-org
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

(use-package org-eldoc
  :ensure org-plus-contrib
  :after org
  :config
  (setq org-eldoc-breadcrumb-separator " • "))

(use-package org-habit
  :ensure org-plus-contrib
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
    "Open a perspective for org-journal."
    (interactive)
    (persp-switch "org")
    (org-journal-new-entry nil))
  (evil-set-initial-state 'org-journal-mode 'insert)
  (setq org-journal-dir "~/Dropbox/org/journal/"
        org-journal-file-format "%Y-%m-%d.org"
        org-journal-find-file #'find-file))

(use-package org-mime :disabled
  :ensure org-plus-contrib
  :after org)

(use-package org-projectile :disabled
  :bind
  (:map leader-map
   ("o p" . org-projectile-project-todo-completing-read))
  :config
  (push (org-projectile-project-todo-entry) org-capture-templates)
  (setq org-projectile-projects-file "~/Dropbox (Personal)/org/projects.org"
        org-agenda-files (append org-agenda-files (org-projectile-todo-files))))

(use-package org-projectile-helm
  :after org-projectile)

(use-package org-table
  :ensure org-plus-contrib
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
  :ensure org-plus-contrib
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
  :ensure org-plus-contrib
  :after ox)

(use-package ox-reveal
  :after ox)

(use-package ox-rss
  :ensure org-plus-contrib
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

(use-package pcmpl-git
  :after eshell)

(use-package pcmpl-homebrew
  :after eshell)

(use-package pcmpl-pip
  :after eshell)

(use-package pcomplete-extension
  :after eshell)

(use-package peep-dired
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

(use-package python
  :ensure nil
  :mode
  ("py" . python-mode)
  :interpreter
  ("python" . python-mode)
  :config
  (add-to-list 'python-shell-completion-native-disabled-interpreters "jupyter")
  (setq python-indent-guess-indent-offset-verbose nil
        python-shell-prompt-detect-failure-warning nil
        python-shell-interpreter "jupyter-console"
        python-shell-interpreter-args "console --simple-prompt"))

(use-package python-x
  :after python
  :bind
  (:map elpy-mode-map
   ("C-c C-b" . python-shell-send-buffer)
   ("C-c C-c" . python-shell-send-paragraph-and-step)
   ("C-c C-f" . python-shell-send-defun)
   ("C-c C-j" . python-shell-send-line)
   ("C-c C-n" . python-shell-send-line-and-step)))

(use-package pyvenv)

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
   :foreground (plist-get base16-tomorrow-night-colors :base08)
   :weight 'bold)
  (set-face-attribute
   'rainbow-delimiters-unmatched-face nil
   :foreground (plist-get base16-tomorrow-night-colors :base08)
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

(use-package restclient-helm
  :mode
  (".http$" . restclient-mode)
  :config
  (add-hook 'restclient-mode #'pseudo-prog-mode))

(use-package restart-emacs
  :commands restart-emacs
  :config
  (setq restart-emacs-restore-frames t))

(use-package rotate
  :commands rotate-layout
  :init
  (defhydra hydra-evil-window-rotate
    (perspective-map)
    "Roate windows"
    ("SPC" rotate-layout "Rotate")
    ("<escape>" nil)
    ("q" nil)))

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
  (defadvice server-edit (before auto-save activate) (save-buffer))
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
  (add-hook 'smerge-mode-hook #'hydra-merge-conflicts/body)
  (defhydra hydra-merge-conflicts
    (:hint nil)
    "Conflicts"
    ("RET" smerge-keep-current "Current")
    ("e" smerge-ediff "Ediff")
    ("j" smerge-next "Next")
    ("k" smerge-prev "Previous")
    ("m" smerge-keep-mine "Mine")
    ("o" smerge-keep-other "Other")
    ("<escape>" nil)
    ("q" nil)))

(use-package smex
  :init
  (bind-keys
   :map leader-map
    ("C-x" . smex-major-mode-commands)
    ("x" . smex))
  :config
  (advice-add 'smex :around #'ido-advice-single-line)
  (advice-add 'smex-major-mode-commands :around #'ido-advice-single-line))

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

(use-package term
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
         (let* ((name (persp-name (persp-curr)))
                (term-name (concat name "-term"))
                (full-term-name (concat "*" term-name "*"))
                (buffer (get-buffer full-term-name)))
           (if buffer
               (switch-to-buffer-other-window buffer)
             (progn
               (switch-to-buffer-other-window term-name)
               (ansi-term (getenv "SHELL") term-name)))))
  (defun terminal () (interactive)
         (let* ((default-directory "~")
                (name "term")
                (kill-func (apply-partially #'persp-kill name)))
           (persp-switch name)
           (ansi-term (getenv "SHELL") name)
           (my--repl-exit-hook kill-func)))
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

(use-package term-cmd
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
    (flyspell-mode)
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

(use-package undo-tree
  :bind
  (:map leader-map
   ("C-u" . undo-tree-visualize)
   :map undo-tree-visualizer-mode-map
   ("RET" . undo-tree-visualizer-quit)
   ("h" . undo-tree-visualize-switch-branch-left)
   ("j" . undo-tree-visualize-redo)
   ("k" . undo-tree-visualize-undo)
   ("l" . undo-tree-visualize-switch-branch-right))
  :config
  (setq undo-tree-auto-save-history t
        undo-tree-history-directory-alist
        `(("." . ,(expand-file-name "undo" user-emacs-directory)))
        undo-tree-visualizer-diff t)
  :diminish undo-tree-mode)

(use-package uniquify
  :ensure nil
  :config
  (setq uniquify-buffer-name-style 'forward))

(use-package uuidgen
  :commands uuidgen)

(use-package vagrant)

(use-package vagrant-tramp
  :after tramp)

(use-package vertica
  :commands sql-vertica)

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

(use-package windsize
  :commands
  (windsize-down
   windsize-left
   windsize-right
   windsize-up)
  :init
  (defhydra hydra-evil-window-resize
    (perspective-map)
    "Resize windows"
    ("C-h" windsize-left "Left")
    ("C-j" windsize-down "Down")
    ("C-k" windsize-up "Up")
    ("C-l" windsize-right "Right")
    ("<escape>" nil)
    ("q" nil))
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
