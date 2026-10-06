-- Share vim runtime (plugins, colorschemes, autoload)
vim.opt.rtp:prepend(vim.fn.expand("~/.vim"))
vim.opt.rtp:append(vim.fn.expand("~/.vim/after"))

-- Source shared vim config
vim.cmd("source ~/.vimrc")

-- Bootstrap lazy.nvim (neovim-only plugins)
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.uv.fs_stat(lazypath) then
  vim.fn.system({
    "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  { "claudecode.nvim", opts = {} },
  { "folke/snacks.nvim", opts = { statuscolumn = { enabled = false } } },
  {
    "nvim-lualine/lualine.nvim",
    config = function()
      local theme = "16color"
      require("lualine").setup({
        options = {
          theme = theme,
          icons_enabled = false,
          component_separators = { left = "|", right = "|" },
          section_separators = { left = "", right = "" },
        },
        tabline = {
          lualine_a = { "buffers" },
        },
      })
    end,
  },
})
