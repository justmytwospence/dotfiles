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
  { "coder/claudecode.nvim", dependencies = { "folke/snacks.nvim" }, opts = {} },
  { "folke/snacks.nvim", opts = { statuscolumn = { enabled = false } } },
  {
    "nvim-lualine/lualine.nvim",
    config = function()
      local theme = "16color"
      local summaries, pending, again = {}, {}, {}
      local helper = vim.fn.expand("~/.local/bin/git-status-line")
      local function scan_git_summary(dir)
        if pending[dir] then
          again[dir] = true
          return
        end
        if vim.fn.executable(helper) ~= 1 then
          summaries[dir] = "!"
          return
        end
        pending[dir] = true
        local ok = pcall(vim.system, { helper, "-f", "plain" }, { cwd = dir, text = true }, function(result)
          vim.schedule(function()
            pending[dir] = nil
            local text = vim.trim(result.stdout or "")
            summaries[dir] = (result.code == 0 or (result.code == 1 and text == "")) and text or "!"
            require("lualine").refresh({ place = { "statusline" } })
            if again[dir] then
              again[dir] = nil
              scan_git_summary(dir)
            end
          end)
        end)
        if not ok then
          pending[dir] = nil
          again[dir] = nil
          summaries[dir] = "!"
        end
      end
      local function refresh_git_summary()
        if vim.bo.buftype ~= "" or vim.api.nvim_buf_get_name(0):match("^%a+://") then
          vim.b.git_summary_dir = nil
          return
        end
        local name = vim.api.nvim_buf_get_name(0)
        local dir = name == "" and vim.fn.getcwd() or vim.fn.fnamemodify(name, ":h")
        vim.b.git_summary_dir = dir
        scan_git_summary(dir)
      end
      local function git_summary_highlights()
        vim.api.nvim_set_hl(0, "GitSummaryDirty", { ctermfg = 3, fg = "#d7af00" })
        vim.api.nvim_set_hl(0, "GitSummaryAhead", { ctermfg = 2, fg = "#87af87" })
        vim.api.nvim_set_hl(0, "GitSummaryError", { ctermfg = 1, fg = "#d75f5f" })
      end
      git_summary_highlights()
      vim.api.nvim_create_autocmd("ColorScheme", {
        group = vim.api.nvim_create_augroup("git_summary_colors", { clear = true }),
        callback = git_summary_highlights,
      })
      local function git_summary(component)
        -- Only parse cached plain tokens; never collect Git during redraw.
        -- lualine supplies the component: restore its mode-aware section color.
        local reset = component and component:get_default_hl() or "%*"
        local text = summaries[vim.b.git_summary_dir] or ""
        local fields = {}
        for field in text:gmatch("%S+") do
          local group
          if text == "!" then
            group = "GitSummaryError"
          elseif #fields > 0 then
            if field == "*" then
              group = "GitSummaryDirty"
            elseif field:match("^↑[1-9][0-9]*$") then
              group = "GitSummaryAhead"
            elseif field == "!" or field:match("^↓[1-9][0-9]*$") then
              group = "GitSummaryError"
            end
          end
          -- lualine function components are formats: escape literal branch %.
          local literal = field:gsub("%%", "%%%%")
          fields[#fields + 1] = group and ("%#" .. group .. "#" .. literal .. reset) or literal
        end
        return table.concat(fields, " ")
      end
      vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost", "FocusGained", "DirChanged" }, {
        group = vim.api.nvim_create_augroup("git_summary", { clear = true }),
        callback = refresh_git_summary,
      })
      vim.schedule(function()
        local dir = vim.b.git_summary_dir
        if not dir or (summaries[dir] == nil and not pending[dir]) then
          refresh_git_summary()
        end
      end)
      require("lualine").setup({
        options = {
          theme = theme,
          icons_enabled = false,
          component_separators = { left = "|", right = "|" },
          section_separators = { left = "", right = "" },
        },
        sections = {
          lualine_a = { "mode" },
          lualine_b = { git_summary, "diagnostics" },
          lualine_c = { "filename" },
          lualine_x = { "encoding", "fileformat", "filetype" },
          lualine_y = { "progress" },
          lualine_z = { "location" },
        },
        tabline = {
          lualine_a = { "buffers" },
        },
      })
    end,
  },
})
