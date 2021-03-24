(require 'yasnippet)

(defcustom jekyll-drafts-dir "_drafts/"
  "Subdirectory of jekyll-root-dir that contains drafts."
  :group 'jekyll
  :type 'string)

(defcustom jekyll-posts-dir "_posts/"
  "Subdirectory of jekyll-root-dir that contains posts."
  :group 'jekyll
  :type 'string)

(defcustom jekyll-root-dir (expand-file-name "~/jekyll/")
  "Path to jekyll project."
  :group 'jekyll
  :type 'directory)

(defcustom jekyll-timestamp-format "%Y-%m-%d"
  "strftime format for Jekyll timestamps."
  :group 'jekyll
  :type 'string)

(defvar jekyll--snippets-dir (file-name-directory (or load-file-name
                                                      (buffer-file-name))))

;;;###autoload
(defun jekyll--snippets-initialize ()
  (let ((snip-dir (expand-file-name "snippets" jekyll--snippets-dir)))
    (when (boundp 'yas-snippet-dirs)
      (add-to-list 'yas-snippet-dirs snip-dir t))
    (yas-load-directory snip-dir)))

;;;###autoload
(eval-after-load 'yasnippet
  '(jekyll--snippets-initialize))

(defun jekyll--sluggify (title)
  "Transform the TITLE of an article into a slug suitable for a URL."
  (let* ((lc-title (downcase title))
         (no-space (replace-regexp-in-string " +" "-" lc-title))
         (striped (replace-regexp-in-string "[',!?.:/()_;\"<>¬´¬ª@#]" "" no-space)))
    striped))

;;;###autoload
(defun jekyll-timestamp ()
  "Update existing date: timestamp on a Jekyll page or post."
  (interactive)
  (save-excursion
    (goto-char 1)
    (re-search-forward "^date:")
    (let ((beg (point)))
      (end-of-line)
      (delete-region beg (point)))
    (insert (concat " " (format-time-string jekyll-timestamp-format)))))

;;;###autoload
(defun jekyll-draft (jekyll-title)
  (interactive
   (list
    (ido-completing-read
     "Drafts: "
     (mapcar
      #'file-name-sans-extension
      (directory-files (concat jekyll-root-dir jekyll-drafts-dir) nil "^[^.]")))))
  (if (featurep 'perspective)
      (persp-switch (file-name-nondirectory (directory-file-name jekyll-root-dir))))
  (let* ((slug (jekyll--sluggify jekyll-title))
         (filename (concat slug ".md"))
         (full-filename (concat jekyll-root-dir jekyll-drafts-dir filename))
         (file-exists (file-exists-p full-filename)))
    (find-file full-filename)
    (when (not file-exists)
      (let ((snippet (yas-lookup-snippet "jekyll-frontmatter" 'markdown-mode)))
        (evil-insert-state)
        (yas-expand-snippet snippet)))))

;;;###autoload
(defun jekyll-publish ()
  (interactive)
  (if (not (string= default-directory (concat jekyll-root-dir jekyll-drafts-dir)))
      (message "Not in jekyll _drafts directory.")
    (let* ((draft-path buffer-file-name)
           (title (file-name-nondirectory draft-path))
           (date (format-time-string "%Y-%m-%d")))
      (set-visited-file-name (concat jekyll-root-dir
                                     jekyll-posts-dir
                                     date "-" title) nil t)
      (save-buffer)
      (delete-file draft-path))))

(provide 'jekyll)
