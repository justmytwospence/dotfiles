# Jupyter and IPython (extras: jupyter)

Installed only on a host whose chezmoi `extras` include `jupyter`
(`chezmoi init --promptString extras=jupyter`, or edit `extras` in
`~/.config/chezmoi/chezmoi.toml` and `chezmoi apply`).

- `~/.ipython/profile_default/` is the live part: IPython and kernel settings and
  `startup/startup.py`. Every IPython and Jupyter kernel reads it.
- `~/.jupyter/custom/` (custom.css, custom.js) and `~/.jupyter/nbconfig/` only
  affect the classic Notebook 6 front end and its `jupyter_contrib_nbextensions`.
  Notebook 7 and JupyterLab ignore both, and the nbextensions do not install
  against Notebook 7. They are kept for a Notebook 6 environment:

  ```sh
  uv tool install 'notebook<7' --with jupyter_contrib_nbextensions
  jupyter contrib nbextension install --user
  ```

Notebooks here are mostly marimo now (the marimo skills, `uv 'marimo'` in the
Brewfile).
