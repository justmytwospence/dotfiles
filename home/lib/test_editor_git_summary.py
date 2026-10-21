"""Isolated editor summary adapters: no bootstrap, live config, or real helper."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = 'topic%name * ↑2 ↓1 !'


def formatted(reset='%*'):
    """Vim/Neovim statusline form: branch escaped, one group per suffix token, RESET after each."""
    return ('topic%%name %#GitSummaryDirty#*{r} %#GitSummaryAhead#↑2{r} '
            '%#GitSummaryError#↓1{r} %#GitSummaryError#!{r}').format(r=reset)


# Without an airline/lualine section (existing fixtures) the reset falls back to %*.
FORMATTED = formatted()
EXPECTED_HUES = {'dirty': ['yellow', 'yellow'], 'ahead': ['green', 'green'], 'error': ['red', 'red']}


def hue(color):
    """Classify a cterm index, #rrggbb value or color name as yellow, green, red or other."""
    text = str(color).strip().lower()
    if text.isdigit():
        return {1: 'red', 9: 'red', 2: 'green', 10: 'green', 3: 'yellow', 11: 'yellow'}.get(int(text), 'other')
    if re.fullmatch(r'#[0-9a-f]{6}', text):
        r, g, b = (int(text[i:i + 2], 16) for i in (1, 3, 5))
        if r > 128 and g > 128 and b < 96:
            return 'yellow'
        if g > 128 and r < 160 and b < 160:
            return 'green'
        if r > 128 and g < 128 and b < 128:
            return 'red'
        return 'other'
    return next((name for name in ('yellow', 'green', 'red') if name in text), 'other')


class EditorSummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='editor summary ')
        self.home = Path(self.tmp.name)
        helper = self.home / '.local/bin/git-status-line'
        helper.parent.mkdir(parents=True)
        helper.write_text('#!/bin/sh\n[ "$#" = 2 ] && [ "$1" = -f ] && [ "$2" = plain ] || exit 9\n'
                          'printf "call\\n" >> "$HOME/calls"\n'
                          'snapshot=$(cat "$HOME/summary"); printf "captured\\n" >> "$HOME/captured"\n'
                          '[ ! -f "$HOME/delay" ] || sleep "$(cat "$HOME/delay")"\n'
                          'printf "%s\\n" "$snapshot"\n'
                          'code=0; [ ! -f "$HOME/code" ] || code=$(cat "$HOME/code"); exit "$code"\n')
        helper.chmod(0o755)
        (self.home / 'summary').write_text(SUMMARY + '\n')
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / 'config'),
                        XDG_DATA_HOME=str(self.home / 'data'), XDG_STATE_HOME=str(self.home / 'state'))

    def tearDown(self):
        self.tmp.cleanup()

    def run_editor(self, editor, args):
        if not shutil.which(editor):
            self.skipTest(f'{editor} unavailable')
        result = subprocess.run([editor, *args], env=self.env, cwd=self.home,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_hues(self):
        colors = json.loads((self.home / 'colors.json').read_text())
        self.assertEqual({key: [hue(color) for color in value] for key, value in colors.items()},
                         EXPECTED_HUES, colors)

    # Vim: the airline block, sourced without plugins.
    @staticmethod
    def vim_block():
        source = (ROOT / 'dot_vimrc').read_text()
        start = source.index("  let g:airline_theme")
        return source[start:source.index("\nendif", start)]

    def run_vim_script(self, name, body, log=False):
        script = self.home / name
        script.write_text(self.vim_block() + body + r'''
if !empty(v:errors)
  call writefile(v:errors, expand('~/errors'))
  cquit
endif
qa!
''')
        args = ['-Nu', 'NONE', '-n', '-es']
        if log:
            args.append('-V1' + str(self.home / 'vim.log'))
        try:
            self.run_editor('vim', [*args, '-S', str(script)])
        except AssertionError as exc:
            errors = self.home / 'errors'
            vim_log = self.home / 'vim.log'
            raise AssertionError(errors.read_text() if errors.exists()
                                 else vim_log.read_text() if vim_log.exists() else str(exc)) from exc

    def test_vim_full_config_syntax_without_plugins(self):
        autoload = self.home / 'runtime/autoload'
        autoload.mkdir(parents=True)
        (autoload / 'plug.vim').write_text('function! plug#begin(...)\nendfunction\n'
                                          'function! plug#end(...)\nendfunction\n')
        colors = self.home / 'runtime/colors'
        colors.mkdir()
        (colors / 'ansi.vim').write_text('let g:colors_name = "ansi"\n')
        script = self.home / 'syntax.vim'
        script.write_text('set rtp^=' + str(self.home / 'runtime').replace(' ', '\\ ') + '\n'
                          'command! -nargs=* Plug echo ""\n'
                          'source ' + str(ROOT / 'dot_vimrc') + '\n'
                          'augroup autocommands\nautocmd!\naugroup END\n'
                          'qa!\n')
        self.run_editor('vim', ['-Nu', 'NONE', '-n', '-es', '-S', str(script)])

    def test_vim_async_cache_through_airline_expression(self):
        self.run_vim_script('test.vim', r'''
call assert_match('^%{%<SNR>\d\+_GitSummaryFormat(get(b:, "git_summary", ""))%}$', g:airline_section_b)
let expr = matchstr(g:airline_section_b, '^%{%\zs.*\ze%}$')
edit sample.txt
sleep 300m
call assert_equal('<SUMMARY>', b:git_summary)
call assert_equal(0, b:git_summary_pending)
call assert_equal('<FORMATTED>', eval(expr))
let calls = len(readfile(expand('~/calls')))
for i in range(20)
  let text = eval(expr)
endfor
call assert_equal(calls, len(readfile(expand('~/calls'))))
call writefile([''], expand('~/summary'))
call writefile(['1'], expand('~/code'))
doautocmd FocusGained
sleep 300m
call assert_equal('', b:git_summary)
call assert_equal('', eval(expr))
call delete(expand('~/.local/bin/git-status-line'))
doautocmd BufWritePost
call assert_equal('!', b:git_summary)
call assert_equal('%#GitSummaryError#!%*', eval(expr))
'''.replace('<SUMMARY>', SUMMARY).replace('<FORMATTED>', FORMATTED), log=True)

    def test_vim_format_tokens_escaping_and_highlight_config(self):
        self.run_vim_script('format.vim', r'''
function! Plain(text) abort
  return substitute(substitute(a:text, '%#\w\+#\|%\*', '', 'g'), '%%', '%', 'g')
endfunction
for [text, expected] in [
      \ ['<SUMMARY>', '<FORMATTED>'],
      \ ['!', '%#GitSummaryError#!%*'],
      \ ['*', '*'],
      \ ['* *', '* %#GitSummaryDirty#*%*'],
      \ ['! ↓1', '! %#GitSummaryError#↓1%*'],
      \ ['100%', '100%%'],
      \ ['main ↑10', 'main %#GitSummaryAhead#↑10%*'],
      \ ['', '']]
  let actual = <SID>GitSummaryFormat(text)
  call assert_equal(expected, actual, 'format of ' . string(text))
  call assert_equal(text, Plain(actual), 'plain text of ' . string(text))
endfor
function! Colors() abort
  let colors = {}
  for [name, key] in [['GitSummaryDirty', 'dirty'], ['GitSummaryAhead', 'ahead'], ['GitSummaryError', 'error']]
    let id = synIDtrans(hlID(name))
    let colors[key] = [synIDattr(id, 'fg', 'cterm'), synIDattr(id, 'fg', 'gui')]
  endfor
  return colors
endfunction
let before = Colors()
highlight clear
doautocmd ColorScheme
call assert_equal(before, Colors(), 'ColorScheme reapplies the groups')
call writefile([json_encode(before)], expand('~/colors.json'))
'''.replace('<SUMMARY>', SUMMARY).replace('<FORMATTED>', FORMATTED))
        self.assert_hues()

    def test_vim_format_resets_to_airline_section_when_defined(self):
        # hlexists() stays true once a group is defined, so the %* fallback is checked first.
        self.run_vim_script('section.vim', r'''
call assert_equal('<PLAIN>', <SID>GitSummaryFormat('<SUMMARY>'), 'no airline groups')
highlight airline_b ctermfg=4 ctermbg=5 guifg=#5f87ff guibg=#875f87
call assert_equal('<ACTIVE>', <SID>GitSummaryFormat('<SUMMARY>'), 'active window defaults')
let w:airline_active = 0
call assert_equal('<PLAIN>', <SID>GitSummaryFormat('<SUMMARY>'), 'inactive without its group')
highlight airline_b_inactive ctermfg=8 ctermbg=0 guifg=#808080 guibg=#303030
call assert_equal('<INACTIVE>', <SID>GitSummaryFormat('<SUMMARY>'), 'inactive window')
call assert_equal('%#GitSummaryError#!%#airline_b_inactive#', <SID>GitSummaryFormat('!'))
let w:airline_active = 1
call assert_equal('<ACTIVE>', <SID>GitSummaryFormat('<SUMMARY>'), 'active window')
call assert_equal('main %#GitSummaryAhead#↑10%#airline_b#', <SID>GitSummaryFormat('main ↑10'))
call assert_equal('100%%', <SID>GitSummaryFormat('100%'))
'''.replace('<SUMMARY>', SUMMARY).replace('<PLAIN>', FORMATTED)
           .replace('<ACTIVE>', formatted('%#airline_b#'))
           .replace('<INACTIVE>', formatted('%#airline_b_inactive#')))

    def require_vim_terminal(self):
        if not shutil.which('vim'):
            self.skipTest('vim unavailable')
        if '+terminal' not in subprocess.run(['vim', '--version'], capture_output=True, text=True).stdout:
            self.skipTest('vim lacks +terminal')
        (self.home / 'block.vim').write_text(self.vim_block() + '\n')

    def test_vim_terminal_cells_color_suffix_only_and_reset(self):
        self.require_vim_terminal()
        # Stand in for airline: the section expression is the whole statusline.
        (self.home / 'inner.vim').write_text(r'''
execute 'source ' . fnameescape(expand('~/block.vim'))
set laststatus=2
let &statusline = g:airline_section_b
edit sample.txt
''')
        outer = self.home / 'outer.vim'
        outer.write_text(r'''
let buf = term_start(['vim', '-Nu', 'NONE', '-n', '--not-a-term', '-S', expand('~/inner.vim')],
      \ {'term_rows': 8, 'term_cols': 60, 'env': {'TERM': 'xterm-256color', 'COLORS': '16'}})
function! Wait(buf, pattern) abort
  for i in range(600)
    for row in range(1, 8)
      if term_getline(a:buf, row) =~# a:pattern
        return row
      endif
    endfor
    sleep 10m
  endfor
  return 0
endfunction
let row = Wait(buf, '^topic%name \* ↑2 ↓1 !')
let first = row ? term_scrape(buf, row) : []
call writefile(['2'], expand('~/code'))
call term_sendkeys(buf, ":doautocmd FocusGained\<CR>")
let row = Wait(buf, '^!\s*$')
let second = row ? term_scrape(buf, row) : []
call writefile([json_encode({'first': first, 'second': second,
      \ 'rows': map(range(1, 8), 'term_getline(buf, v:val)')})], expand('~/cells.json'))
call term_sendkeys(buf, ":qa!\<CR>")
sleep 100m
qa!
''')
        self.run_editor('vim', ['-Nu', 'NONE', '-n', '-es', '-S', str(outer)])
        cells = json.loads((self.home / 'cells.json').read_text())
        first, second = cells['first'], cells['second']
        self.assertTrue(first and second, cells['rows'])
        for row in (first, second):
            self.assertTrue(all(len(cell['chars']) == 1 for cell in row), row)
        text = ''.join(cell['chars'] for cell in first)
        self.assertEqual(text.rstrip(), SUMMARY)
        default = first[len(SUMMARY)]['fg']
        self.assertEqual(hue(default), 'other', default)
        colors = {}
        for token in ('topic%name', '*', '↑2', '↓1', '!'):
            start = SUMMARY.index(token)
            colors[token] = {first[i]['fg'] for i in range(start, start + len(token))}
        self.assertEqual(colors['topic%name'], {default}, colors)
        self.assertEqual({token: {hue(fg) for fg in fgs} for token, fgs in colors.items()},
                         {'topic%name': {'other'}, '*': {'yellow'}, '↑2': {'green'},
                          '↓1': {'red'}, '!': {'red'}}, colors)
        separators = {first[i]['fg'] for i, char in enumerate(SUMMARY) if char == ' '}
        self.assertEqual(separators, {default}, 'every token resets to the statusline color')
        text = ''.join(cell['chars'] for cell in second)
        self.assertEqual(text.rstrip(), '!')
        self.assertEqual(hue(second[0]['fg']), 'red', second[0])
        self.assertEqual(second[1]['fg'], default, second[1])

    def test_vim_terminal_cells_restore_airline_section_between_and_after_tokens(self):
        self.require_vim_terminal()
        line = SUMMARY + ' tail end'
        # Airline emits %#airline_b# before the section and the bar continues after our
        # last token; the %* tail is the StatusLine reference the old reset produced.
        (self.home / 'inner.vim').write_text(r'''
execute 'source ' . fnameescape(expand('~/block.vim'))
set laststatus=2
highlight airline_b ctermfg=4 ctermbg=5
let &statusline = '%#airline_b#' . g:airline_section_b . ' tail%* end'
edit sample.txt
''')
        outer = self.home / 'outer.vim'
        outer.write_text(r'''
let buf = term_start(['vim', '-Nu', 'NONE', '-n', '--not-a-term', '-S', expand('~/inner.vim')],
      \ {'term_rows': 8, 'term_cols': 60, 'env': {'TERM': 'xterm-256color', 'COLORS': '16'}})
let cells = []
for i in range(600)
  for row in range(1, 8)
    if term_getline(buf, row) =~# '^topic%name \* ↑2 ↓1 ! tail end'
      let cells = term_scrape(buf, row)
      break
    endif
  endfor
  if !empty(cells) | break | endif
  sleep 10m
endfor
call writefile([json_encode({'cells': cells, 'rows': map(range(1, 8), 'term_getline(buf, v:val)')})],
      \ expand('~/cells.json'))
call term_sendkeys(buf, ":qa!\<CR>")
sleep 100m
qa!
''')
        self.run_editor('vim', ['-Nu', 'NONE', '-n', '-es', '-S', str(outer)])
        scraped = json.loads((self.home / 'cells.json').read_text())
        cells = scraped['cells']
        self.assertTrue(cells, scraped['rows'])
        self.assertEqual(''.join(cell['chars'] for cell in cells).rstrip(), line)

        def colors(start, stop):
            return {(cells[i]['fg'], cells[i]['bg']) for i in range(start, stop)}

        section = colors(0, len('topic%name'))
        plain = colors(len(line) - len(' end'), len(line))
        self.assertEqual(len(section), 1, section)
        self.assertEqual(len(plain), 1, plain)
        (section_fg, section_bg), = section
        (plain_fg, plain_bg), = plain
        self.assertNotEqual(section_fg, plain_fg, 'airline_b fg is distinct from StatusLine')
        self.assertNotEqual(section_bg, plain_bg, 'airline_b bg is distinct from StatusLine')
        separators = {(cells[i]['fg'], cells[i]['bg']) for i, char in enumerate(SUMMARY) if char == ' '}
        self.assertEqual(separators, section, 'spaces between tokens restore the section')
        self.assertEqual(colors(len(SUMMARY), len(SUMMARY + ' tail')), section,
                         'the bar after the last token keeps the section')
        for token, expected in (('*', 'yellow'), ('↑2', 'green'), ('↓1', 'red'), ('!', 'red')):
            start = SUMMARY.index(token)
            fgs = {cells[i]['fg'] for i in range(start, start + len(token))}
            self.assertEqual({hue(fg) for fg in fgs}, {expected}, (token, fgs))
            self.assertNotIn(section_fg, fgs, token)

    def test_vim_waits_for_stdout_close_and_queues_save(self):
        (self.home / 'delay').write_text('0.2')
        self.run_vim_script('race.vim', r'''
edit sample.txt
for i in range(100)
  if filereadable(expand('~/captured')) | break | endif
  sleep 10m
endfor
call writefile(['updated *'], expand('~/summary'))
doautocmd BufWritePost
sleep 600m
call assert_equal('updated *', b:git_summary)
call assert_equal(2, len(readfile(expand('~/calls'))))
" Exercise exit-before-output order deterministically; no real process needed.
let b:git_summary_generation = 999
let b:git_summary_pending = 1
let state = {'buf': bufnr('%'), 'dir': b:git_summary_dir, 'text': '',
      \ 'exited': 0, 'closed': 0, 'status': 2, 'generation': 999}
call <SID>GitSummaryExit(state, 0, 0)
call assert_equal('updated *', b:git_summary)
call assert_equal(1, b:git_summary_pending)
call <SID>GitSummaryOutput(state, 0, 'buffered ↑7')
call <SID>GitSummaryClose(state, 0)
call assert_equal('buffered ↑7', b:git_summary)
call assert_equal(0, b:git_summary_pending)
''')

    # Neovim: the lualine config body with a recording lualine stub.
    @staticmethod
    def nvim_body():
        source = (ROOT / 'dot_config/nvim/init.lua').read_text()
        start = source.index('      local theme =')
        return source[start:source.rindex('\n    end,')]

    def run_nvim_script(self, name, prelude, body):
        script = self.home / name
        script.write_text('local config\n'
                          'package.loaded.lualine = { setup = function(c) config = c end, refresh = function() end }\n'
                          + prelude + self.nvim_body() + body + "\nvim.cmd('qa!')\n")
        self.run_editor('nvim', ['--headless', '-u', 'NONE', '-n', '-l', str(script)])

    def test_nvim_queues_one_followup_for_save_during_scan(self):
        (self.home / 'delay').write_text('0.2')
        self.run_nvim_script('race.lua', '', r'''
vim.cmd('edit sample.txt')
assert(vim.wait(3000, function() return vim.fn.filereadable(vim.env.HOME .. '/captured') == 1 end))
vim.fn.writefile({'updated *'}, vim.env.HOME .. '/summary')
vim.api.nvim_exec_autocmds('BufWritePost', {})
assert(vim.wait(3000, function()
  return config.sections.lualine_b[1]() == 'updated %#GitSummaryDirty#*%*' and not next(pending)
end), config.sections.lualine_b[1]())
assert(#vim.fn.readfile(vim.env.HOME .. '/calls') == 2)
''')

    def test_nvim_component_restores_section_between_and_after_tokens(self):
        self.run_nvim_script('section.lua', '', r'''
local component = config.sections.lualine_b[1]
vim.cmd('edit sample.txt')
assert(vim.wait(3000, function() return component() ~= '' end))
vim.api.nvim_set_hl(0, 'FixtureSection', { ctermfg = 4, ctermbg = 5, fg = '#5f87ff', bg = '#875f87' })
local status = vim.api.nvim_get_hl(0, { name = 'StatusLine', link = false })
local section = vim.api.nvim_get_hl(0, { name = 'FixtureSection', link = false })
assert(section.fg ~= status.fg and section.bg ~= status.bg, vim.inspect({ section, status }))
-- lualine calls fn(self, is_focused): the stub stands in for its mode-aware section color.
local stub = { get_default_hl = function() return '%#FixtureSection#' end }
local calls = #vim.fn.readfile(vim.env.HOME .. '/calls')
local summary = component(stub, true)
assert(summary == '<SECTION>', summary)
assert(component() == '<FORMATTED>', component())
local function mapping(text)
  local eval = vim.api.nvim_eval_statusline(text, { highlights = true })
  local segments = {}
  for i, highlight in ipairs(eval.highlights) do
    local stop = eval.highlights[i + 1] and eval.highlights[i + 1].start or #eval.str
    local piece = eval.str:sub(highlight.start + 1, stop)
    if piece ~= '' then segments[#segments + 1] = piece .. '=' .. highlight.group end
  end
  return eval.str, table.concat(segments, '|')
end
-- lualine prepends the section highlight, so the branch ordinarily shares it; the bar continues after us.
local str, groups = mapping('%#FixtureSection#' .. summary .. ' tail')
assert(str == '<SUMMARY> tail', str)
assert(groups == 'topic%name =FixtureSection|*=GitSummaryDirty| =FixtureSection|↑2=GitSummaryAhead'
  .. '| =FixtureSection|↓1=GitSummaryError| =FixtureSection|!=GitSummaryError| tail=FixtureSection', groups)
for _ = 1, 20 do
  component(stub, true)
  component(stub, false)
end
assert(#vim.fn.readfile(vim.env.HOME .. '/calls') == calls, 'formatting never runs the helper')
vim.fn.writefile({ '!' }, vim.env.HOME .. '/summary')
vim.api.nvim_exec_autocmds('BufWritePost', {})
assert(vim.wait(3000, function() return component(stub) == '%#GitSummaryError#!%#FixtureSection#' end), component(stub))
str, groups = mapping('%#FixtureSection#' .. component(stub) .. ' tail')
assert(str == '! tail' and groups == '!=GitSummaryError| tail=FixtureSection', groups)
'''.replace('<SUMMARY>', SUMMARY).replace('<FORMATTED>', FORMATTED)
           .replace('<SECTION>', formatted('%#FixtureSection#')))

    def test_nvim_async_cache_highlights_and_escaping(self):
        self.run_nvim_script('test.lua', 'assert(loadfile(' + repr(str(ROOT / 'dot_config/nvim/init.lua')) + '))\n', r'''
local component = config.sections.lualine_b[1]
vim.cmd('edit sample.txt')
assert(vim.wait(3000, function() return component() ~= '' end))
local summary = component()
assert(summary == '<FORMATTED>', summary)
local eval = vim.api.nvim_eval_statusline(summary, { highlights = true })
assert(eval.str == '<SUMMARY>', eval.str)
local segments = {}
for i, highlight in ipairs(eval.highlights) do
  local stop = eval.highlights[i + 1] and eval.highlights[i + 1].start or #eval.str
  local text = eval.str:sub(highlight.start + 1, stop)
  if text ~= '' then segments[#segments + 1] = text .. '=' .. highlight.group end
end
local mapping = table.concat(segments, '|')
assert(mapping == 'topic%name =StatusLine|*=GitSummaryDirty| =StatusLine|↑2=GitSummaryAhead'
  .. '| =StatusLine|↓1=GitSummaryError| =StatusLine|!=GitSummaryError', mapping)
assert(config.tabline.lualine_a[1] == 'buffers')
local calls = #vim.fn.readfile(vim.env.HOME .. '/calls')
for _ = 1, 20 do
  component()
  vim.api.nvim_eval_statusline(summary, { highlights = true })
end
assert(#vim.fn.readfile(vim.env.HOME .. '/calls') == calls)
for _, case in ipairs({
  { '!', '%#GitSummaryError#!%*' },
  { '*', '*' },
  { '* *', '* %#GitSummaryDirty#*%*' },
  { '! ↓1', '! %#GitSummaryError#↓1%*' },
  { '100%', '100%%' },
  { 'main ↑10', 'main %#GitSummaryAhead#↑10%*' },
}) do
  vim.fn.writefile({ case[1] }, vim.env.HOME .. '/summary')
  vim.api.nvim_exec_autocmds('BufWritePost', {})
  assert(vim.wait(3000, function() return component() == case[2] end), case[1] .. ' -> ' .. component())
  assert(vim.api.nvim_eval_statusline(case[2], {}).str == case[1], case[2])
end
local function colors()
  local out = {}
  for key, name in pairs({ dirty = 'GitSummaryDirty', ahead = 'GitSummaryAhead', error = 'GitSummaryError' }) do
    local hl = vim.api.nvim_get_hl(0, { name = name, link = false })
    out[key] = { tostring(hl.ctermfg), hl.fg and string.format('#%06x', hl.fg) or '' }
  end
  return out
end
local before = colors()
vim.cmd('highlight clear')
vim.api.nvim_exec_autocmds('ColorScheme', {})
assert(vim.deep_equal(colors(), before), 'ColorScheme reapplies the groups')
vim.fn.writefile({ vim.json.encode(before) }, vim.env.HOME .. '/colors.json')
vim.fn.writefile({''}, vim.env.HOME .. '/summary')
vim.fn.writefile({'1'}, vim.env.HOME .. '/code')
vim.api.nvim_exec_autocmds('FocusGained', {})
assert(vim.wait(3000, function() return component() == '' end), component())
vim.fn.delete(vim.env.HOME .. '/.local/bin/git-status-line')
vim.api.nvim_exec_autocmds('BufWritePost', {})
assert(component() == '%#GitSummaryError#!%*', component())
'''.replace('<SUMMARY>', SUMMARY).replace('<FORMATTED>', FORMATTED))
        self.assert_hues()

    # Emacs: the shared summary section plus extracted consumer forms, never the init.
    @staticmethod
    def emacs_form(start_marker, end_marker):
        source = (ROOT / 'private_dot_emacs.d/init.el').read_text()
        start = source.index(start_marker)
        return source[start:source.index(end_marker, start)]

    def run_emacs_tests(self, name, elisp):
        script = self.home / name
        script.write_text(';;; ' + name + ' -*- lexical-binding: t -*-\n'
                          "(require 'cl-lib)\n(require 'subr-x)\n(require 'ert)\n"
                          '(defconst test-summary "' + SUMMARY + '")\n'
                          '(defun file-text (name)\n'
                          '  (if (file-exists-p name)\n'
                          '      (with-temp-buffer (insert-file-contents name) (buffer-string))\n'
                          '    ""))\n'
                          + self.emacs_form(';; Shared Git summary:', ';; doom-modeline -')
                          + elisp + '\n(ert-run-tests-batch-and-exit)\n')
        self.run_editor('emacs', ['--batch', '-Q', '-l', str(script)])

    def test_emacs_sync_async_nonrepo_and_tramp(self):
        self.run_emacs_tests('test.el', r'''
(ert-deftest summary-result-states ()
  (should (equal (my-git-summary--result 0 " topic *\n") "topic *"))
  (should-not (my-git-summary--result 0 "\n"))
  (should-not (my-git-summary--result 1 "\n"))
  (should (equal (my-git-summary--result 2 "") "!"))
  (should (equal (my-git-summary--result 1 "error") "!")))
(ert-deftest summary-tramp-is-quiet ()
  (let ((default-directory "/ssh:invalid:/"))
    (should-not (my-git-summary--local-directory))
    (should-not (my-git-summary-sync))
    (my-git-summary-refresh)
    (should-not my-git-summary)))
(ert-deftest summary-shared-helper-sync ()
  (with-temp-buffer
    (should (equal (my-git-summary-sync) test-summary))))
(ert-deftest summary-async-cached-no-redraw-process ()
  (with-temp-buffer
    (my-git-summary-refresh)
    ;; A dead process can still have a queued sentinel: wait for publication.
    (let ((deadline (+ (float-time) 3)))
      (while (and my-git-summary-process (< (float-time) deadline))
        (accept-process-output nil 0.1)))
    (should-not my-git-summary-process)
    (should (equal my-git-summary test-summary))
    (let ((calls (file-text (expand-file-name "~/calls"))))
      (dotimes (_ 20) (force-mode-line-update))
      (should (equal calls (file-text (expand-file-name "~/calls")))))))
(ert-deftest summary-quiet-nonrepo-sync-and-async ()
  (with-temp-file (expand-file-name "~/summary") (insert "\n"))
  (with-temp-file (expand-file-name "~/code") (insert "1\n"))
  (with-temp-buffer
    (should-not (my-git-summary-sync))
    (my-git-summary-refresh)
    (let ((deadline (+ (float-time) 3)))
      (while (and my-git-summary-process (< (float-time) deadline))
        (accept-process-output nil 0.1)))
    (should-not my-git-summary-process)
    (should-not my-git-summary))
  (with-temp-file (expand-file-name "~/summary") (insert test-summary "\n"))
  (with-temp-file (expand-file-name "~/code") (insert "0\n")))
(ert-deftest summary-unavailable-helper-sync-and-async ()
  (let ((my-git-status-line-program (expand-file-name "~/missing")))
    (with-temp-buffer
      (should (equal (my-git-summary-sync) "!"))
      (my-git-summary-refresh)
      (should (equal my-git-summary "!")))))
(with-temp-buffer
  (insert-file-contents ''' + json.dumps(str(ROOT / 'private_dot_emacs.d/init.el')) + r''')
  (emacs-lisp-mode)
  (check-parens))
''')

    def test_emacs_token_faces_doom_segment_and_eshell_prompt(self):
        self.run_emacs_tests('faces.el', r'''
;; doom-modeline stubs: only the segment macro, spacing and the active text formatter.
(defmacro doom-modeline-def-segment (name docstring &rest body)
  `(defun ,(intern (format "doom-modeline-segment--%s" name)) () ,docstring ,@body))
(defun doom-modeline-spc () " ")
(defun doom-modeline--active () t)
(defun doom-modeline-display-text (text)
  "Mirror doom-modeline 20251124.309: escape literal percent characters."
  (let ((text (string-replace "%" "%%" text)))
    (if (doom-modeline--active)
        text
      (propertize text 'face `(:inherit (mode-line-inactive
                                         ,(get-text-property 0 'face text)))))))
''' + self.emacs_form('  (doom-modeline-def-segment my-git-summary', '  ;; Native layouts') + r'''
;; Eshell prompt stubs: no eshell-prompt-extras, em-ls or virtualenv packages.
(defun eshell/pwd () default-directory)
(defface eshell-ls-directory-face '((t :foreground "blue")) "Stub directory face.")
(defvar venv-current-name nil)
''' + self.emacs_form('  (defun my-eshell-theme ()', '  (setq eshell-highlight-prompt nil') + r'''
(defconst token-faces-expected
  '(nil my-git-summary-dirty my-git-summary-ahead my-git-summary-error my-git-summary-error))
(defun token-faces (text summary property)
  "PROPERTY per token of SUMMARY where it appears in TEXT; `mixed' if not uniform."
  (let ((offset (string-match (regexp-quote summary) text))
        (start 0)
        faces)
    (should offset)
    (while (string-match "\\S-+" summary start)
      (let ((values (cl-loop for i from (match-beginning 0) below (match-end 0)
                             collect (get-text-property (+ offset i) property text))))
        (push (if (cl-every (lambda (value) (equal value (car values))) values)
                  (car values)
                'mixed)
              faces))
      (setq start (match-end 0)))
    (nreverse faces)))
(ert-deftest summary-format-token-faces ()
  (let ((text (my-git-summary-format test-summary)))
    (should (equal text test-summary))
    (dolist (property '(face font-lock-face))
      (should (equal (token-faces text test-summary property) token-faces-expected)))
    (should-not (text-properties-at (length "topic%name") text)))
  (should (equal (token-faces (my-git-summary-format "!") "!" 'face) '(my-git-summary-error)))
  (should (equal (token-faces (my-git-summary-format "*") "*" 'face) '(nil)))
  (should (equal (token-faces (my-git-summary-format "* *") "* *" 'face) '(nil my-git-summary-dirty)))
  (should (equal (token-faces (my-git-summary-format "! ↓1") "! ↓1" 'font-lock-face)
                 '(nil my-git-summary-error)))
  (should (equal (token-faces (my-git-summary-format "main ↑10") "main ↑10" 'face)
                 '(nil my-git-summary-ahead)))
  (should-not (text-properties-at 0 (my-git-summary-format "100%")))
  (should (equal (my-git-summary-format "") ""))
  (should-not (my-git-summary-format nil)))
(ert-deftest summary-doom-segment-faces-escape-and-cache ()
  (with-temp-buffer
    (should-not (doom-modeline-segment--my-git-summary))
    (setq my-git-summary test-summary my-git-summary-directory default-directory)
    (let ((segment (doom-modeline-segment--my-git-summary))
          (escaped "topic%%name * ↑2 ↓1 !"))
      (should (equal segment (concat " " escaped " ")))
      (dolist (property '(face font-lock-face))
        (should (equal (token-faces segment escaped property) token-faces-expected)))
      ;; Doom's inactive helper sets a whole-text face: token formatting must
      ;; run afterward, preserving ordinary branch and per-token suffix colors.
      (cl-letf (((symbol-function 'doom-modeline--active) (lambda () nil)))
        (let ((inactive (doom-modeline-segment--my-git-summary)))
          (should (equal inactive segment))
          (dolist (property '(face font-lock-face))
            (should (equal (token-faces inactive escaped property) token-faces-expected)))))
      ;; The trailing ! keeps help-echo alongside its token face.
      (should (equal (get-text-property (length escaped) 'help-echo segment)
                     "Shared Git summary (git-status-line)")))
    (setq my-git-summary "!")
    (should (equal (token-faces (doom-modeline-segment--my-git-summary) "!" 'face)
                   '(my-git-summary-error)))
    (setq my-git-summary test-summary my-git-summary-directory "/elsewhere/")
    (should-not (doom-modeline-segment--my-git-summary))
    (setq my-git-summary-directory default-directory)
    (let ((calls (file-text (expand-file-name "~/calls"))))
      (dotimes (_ 20) (doom-modeline-segment--my-git-summary))
      (should (equal calls (file-text (expand-file-name "~/calls")))))))
(ert-deftest summary-eshell-prompt-token-faces ()
  (let* ((default-directory (file-name-as-directory (expand-file-name "~")))
         (prompt (my-eshell-theme)))
    (should (string-match-p (regexp-quote (concat " " test-summary "\n")) prompt))
    (dolist (property '(face font-lock-face))
      (should (equal (token-faces prompt test-summary property) token-faces-expected)))
    (should (string-suffix-p "❯ " prompt)))
  (let ((default-directory "/ssh:invalid:/"))
    (should-not (string-match-p "topic" (my-eshell-theme)))))
(defun face-foreground-for (face gui)
  "Resolve FACE's defface spec for a graphical display, or the batch terminal."
  (plist-get (if gui
                 (cl-letf (((symbol-function 'window-system) (lambda (&optional _) 'ns))
                           ((symbol-function 'display-graphic-p) (lambda (&optional _) t))
                           ((symbol-function 'display-color-p) (lambda (&optional _) t))
                           ((symbol-function 'display-color-cells) (lambda (&optional _) 16777216)))
                   (face-spec-choose (get face 'face-defface-spec)))
               (face-spec-choose (get face 'face-defface-spec)))
             :foreground))
(with-temp-file (expand-file-name "~/colors.json")
  (insert (json-serialize
           (list :dirty (vector (face-foreground-for 'my-git-summary-dirty nil)
                                (face-foreground-for 'my-git-summary-dirty t))
                 :ahead (vector (face-foreground-for 'my-git-summary-ahead nil)
                                (face-foreground-for 'my-git-summary-ahead t))
                 :error (vector (face-foreground-for 'my-git-summary-error nil)
                                (face-foreground-for 'my-git-summary-error t))))))
''')
        self.assert_hues()


if __name__ == '__main__':
    unittest.main()
