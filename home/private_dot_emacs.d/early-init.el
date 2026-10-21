;;; early-init.el --- Pre-init UI, GC, and package setup -*- lexical-binding: t -*-

;; Runs before the first frame and before package.el activation. Keep this file
;; small: GC tuning, native-comp quieting, package bootstrap flags, and UI chrome
;; / frame defaults that should be set before any frame is drawn (avoids a flash).

;; Disable GC during startup; init.el resets it on `emacs-startup-hook'.
(setq gc-cons-threshold most-positive-fixnum)

;; Keep native compilation quiet (Emacs 30 native-comps by default).
(setq native-comp-async-report-warnings-errors 'silent)

;; package.el is initialized explicitly in init.el; don't auto-activate at startup.
(setq package-enable-at-startup nil)

;; Strip UI chrome before the first frame.
(menu-bar-mode -1)
(when (fboundp 'scroll-bar-mode) (scroll-bar-mode -1))
(when (fboundp 'tool-bar-mode) (tool-bar-mode -1))

;; Initial-frame defaults (were add-to-list calls at the top of init.el).
(setq default-frame-alist
      '((cursor-color . "white")
        (font . "Hack-13")
        (right-divider-width . 2)
        (ns-transparent-titlebar . t)
        (ns-appearance . dark)))

(provide 'early-init)
;;; early-init.el ends here
