;; I don't want comint-mode clobbering our font-lock with comint-highlight-input
;; face. (Changing that *face* not to be bold isn't enough).

;; So far, the least-pukey way I can figure out how to do this is to copy-pasta
;; much of comint-send-input, and modify the one tiny offending bit.  Blech. If
;; anyone reading this knows a better way, please let me know!

;; Meanwhile I have slimmed down the copy -- deleted the `no-newline` and
;; `artificial` args we don't use, and the code that could only execute if they
;; were non-nil.

(defun comint-send-input ()
  "Like `comint-send-input` but doesn't use face `comint-highlight-input'."
  (interactive)
  ;; Note that the input string does not include its terminal newline.
  (let ((proc (get-buffer-process (current-buffer))))
    (if (not proc) (user-error "Current buffer has no process")
      (widen)
      (let* ((pmark (process-mark proc))
             (intxt (if (>= (point) (marker-position pmark))
                        (progn (if comint-eol-on-send (end-of-line))
                               (buffer-substring pmark (point)))
                      (let ((copy (funcall comint-get-old-input)))
                        (goto-char pmark)
                        (insert copy)
                        copy)))
             (input (if (not (eq comint-input-autoexpand 'input))
                        ;; Just whatever's already there.
                        intxt
                      ;; Expand and leave it visible in buffer.
                      (comint-replace-by-expanded-history t pmark)
                      (buffer-substring pmark (point))))
             (history (if (not (eq comint-input-autoexpand 'history))
                          input
                        ;; This is messy 'cos ultimately the original
                        ;; functions used do insertion, rather than return
                        ;; strings.  We have to expand, then insert back.
                        (comint-replace-by-expanded-history t pmark)
                        (let ((copy (buffer-substring pmark (point)))
                              (start (point)))
                          (insert input)
                          (delete-region pmark start)
                          copy))))
        (insert ?\n)
        (comint-add-to-input-history history)
        (run-hook-with-args 'comint-input-filter-functions
                            (concat input "\n"))
        (let ((beg (marker-position pmark))
              (end (1- (point)))
              (inhibit-modification-hooks t))
          (when (> end beg)
            ;;;; The bit from comint-send-input that we DON'T want:
            ;; (add-text-properties beg end
            ;;                      '(front-sticky t
            ;;                        font-lock-face comint-highlight-input))
            (unless comint-use-prompt-regexp
              ;; Give old user input a field property of `input', to
              ;; distinguish it from both process output and unsent
              ;; input.  The terminating newline is put into a special
              ;; `boundary' field to make cursor movement between input
              ;; and output fields smoother.
              (add-text-properties
               beg end
               '(mouse-face highlight
                            help-echo "mouse-2: insert after prompt as new input"))))
          (unless comint-use-prompt-regexp
            ;; Cover the terminating newline
            (add-text-properties end (1+ end)
                                 '(rear-nonsticky t
                                                  field boundary
                                                  inhibit-line-move-field-capture t))))
        (comint-snapshot-last-prompt)
        (setq comint-save-input-ring-index comint-input-ring-index)
        (setq comint-input-ring-index nil)
        ;; Update the markers before we send the input
        ;; in case we get output amidst sending the input.
        (set-marker comint-last-input-start pmark)
        (set-marker comint-last-input-end (point))
        (set-marker (process-mark proc) (point))
        ;; clear the "accumulation" marker
        (set-marker comint-accum-marker nil)
        (funcall comint-input-sender proc input)
        ;; This used to call comint-output-filter-functions,
        ;; but that scrolled the buffer in undesirable ways.
        (run-hook-with-args 'comint-output-filter-functions "")))))

(defun my-repl-exit-hook (f)
  "Close current buffer when `exit' from process."
  (lexical-let ((f f))
    (when (ignore-errors (get-buffer-process (current-buffer)))
      (set-process-sentinel (get-buffer-process (current-buffer))
                            (lambda (proc change)
                              (when (string-match (rx (any "finished" "exited")) change)
                                (funcall f)))))))

(defun my-repl-mode ()
  "Activate a bundle of features for REPLs."
  ;; (centered-cursor-mode -1)
  ;; (company-mode)
  (my-repl-exit-hook #'kill-buffer-and-window)
  (rainbow-delimiters-mode-enable)
  (smartparens-mode)
  (visual-line-mode))

(use-package comint
  :ensure nil
  :commands comint-mode
  :config
  (add-hook 'comint-mode-hook #'my-repl-mode)
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
   ("C-v" . term-paste)
   ("M-x" . nil))
  :init
  (defun term-pop ()
    (interactive)
    (let* ((name (persp-name (persp-curr)))
           (term-name (concat name "-term"))
           (full-term-name (concat "*" term-name "*"))
           (buffer (get-buffer full-term-name)))
      (if buffer
          (switch-to-buffer-other-window buffer)
        (progn
          (switch-to-buffer-other-window term-name)
          (ansi-term (getenv "SHELL") term-name)))))
  (defun terminal ()
    (interactive)
    (let* ((default-directory "~")
           (name "term")
           (kill-func (apply-partially #'persp-kill name)))
      (persp-switch name)
      (ansi-term (getenv "SHELL") name)))
  (with-eval-after-load 'org
    (bind-keys
     :map org-mode-map
      ("C-'" . nil)))
  :config
  (add-hook 'term-exec-hook
            (defun my-set-kill-on-exit ()
              (set-process-query-on-exit-flag
               (get-buffer-process (current-buffer)) nil)))
  (add-hook 'term-mode-hook #'my-repl-mode)
  (defun term-send-backward-kill-word ()
    (interactive)
    (term-send-raw-string "\C-w"))
  (defun term-send-backtab ()
    (interactive)
    (term-send-esc)
    (term-send-raw-string "[Z"))
  (defun term-send-esc ()
    (interactive)
    (term-send-raw-string "\e"))
  (evil-define-key 'emacs term-raw-map (kbd "C-z") #'term-send-raw)
  (evil-define-key 'normal term-raw-map
    (kbd "G") (lambda () (interactive)
                (term-send-raw-string "")
                (evil-emacs-state)
                (term-send-esc))
    (kbd "RET") (lambda () (interactive)
                  (evil-emacs-state)
                  (term-send-raw-string "")))
  (evil-set-initial-state 'term-mode 'emacs)
  (setq term-buffer-maximum-size 100000))

(use-package term-cmd
  :after term
  :config
  (defun cursor-shape (command shape)
    (when (string= "0" shape) (setq evil-emacs-state-cursor 'box))
    (when (string= "1" shape) (setq evil-emacs-state-cursor 'bar)))
  (defun leader-toggle (command toggle)
    (when (string= "on" toggle) (bind-key "SPC" #'leader-map-prefix term-raw-map))
    (when (string= "off" toggle) (bind-key "SPC" #'term-send-raw term-raw-map)))
  (setq term-cmd-commands-alist
        '(("CursorShape" . cursor-shape)
          ("LeaderToggle" . leader-toggle))))

(provide 'my-repl)
