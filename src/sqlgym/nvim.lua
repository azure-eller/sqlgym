-- The sqlgym practice session: problem, SQL and results stacked top to bottom.
-- `sqlgym` starts it with
--   nvim <work file> -c "lua dofile('nvim.lua').start(opts)"
-- Python does the real work (loading problems, checking answers, progress)
-- through `sqlgym _load`, `sqlgym check` and `sqlgym answer`; this file is
-- only the UI. Keymaps and settings are buffer-local to sqlgym's own buffers,
-- so the user's config is untouched.

local M = {}
local S = { wins = {} } -- session state
local ns = vim.api.nvim_create_namespace("sqlgym")
local load, fit, style_sql_pane -- defined below

-- `sqlgym check` exit codes (see cli.py).
local PASSED, FAILED, SQL_ERROR, NO_QUERY = 0, 1, 2, 3

local function key(k)
  local leader = vim.g.mapleader or "\\"
  return (leader == " " and "<space>" or leader) .. k
end

local function hints(...)
  local parts = {}
  for _, h in ipairs({ ... }) do
    table.insert(parts, h[1] == ":q" and ":q quit" or key(h[1]) .. " " .. h[2])
  end
  return table.concat(parts, "   ")
end

local RUN, ANSWER, NEXT, SKIP, REDO, QUIT =
  { "r", "run & check" }, { "a", "show answer" }, { "n", "next problem" }, { "n", "skip" }, { "R", "redo" }, { ":q" }

-- Run the sqlgym CLI without blocking the UI.
local function sqlgym(args, on_done)
  local cmd = vim.list_extend(vim.deepcopy(S.opts.cmd), args)
  local width = vim.api.nvim_win_is_valid(S.wins.results or -1) and vim.api.nvim_win_get_width(S.wins.results) or 80
  vim.system(cmd, { text = true, env = { COLUMNS = tostring(width - 1) } }, function(res)
    vim.schedule(function()
      on_done(res)
    end)
  end)
end

local function set_lines(buf, lines)
  vim.bo[buf].modifiable = true
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.bo[buf].modifiable = false
end

-- Fill the results pane: a blank line under the title bar, the output, then
-- the keys for what to do next.
local function show_results(lines, hint_line)
  if hint_line then
    vim.list_extend(lines, { "", hint_line })
  end
  set_lines(S.results_buf, #lines > 0 and vim.list_extend({ "" }, lines) or {})
  if vim.api.nvim_win_is_valid(S.wins.results or -1) then
    vim.api.nvim_win_set_cursor(S.wins.results, { 1, 0 })
  end
end

local function output_lines(res)
  return vim.split((res.stdout or "") .. (res.stderr or ""), "\n", { trimempty = true })
end

local function save_sql()
  if S.sql_buf and vim.api.nvim_buf_is_valid(S.sql_buf) then
    vim.api.nvim_buf_call(S.sql_buf, function()
      vim.cmd("silent update")
    end)
  end
end

-- --- actions --------------------------------------------------------------------

function M.run()
  save_sql()
  show_results({ "Running…" })
  sqlgym({ "check", S.work_file }, function(res)
    local next_keys = ({
      [PASSED] = hints(NEXT, REDO, QUIT),
      [FAILED] = hints(RUN, ANSWER, SKIP),
      [SQL_ERROR] = hints(RUN, ANSWER, SKIP),
      [NO_QUERY] = hints(RUN, ANSWER, SKIP),
    })[res.code]
    show_results(output_lines(res), next_keys)
  end)
end

function M.answer()
  sqlgym({ "answer", S.slug }, function(res)
    local lines = vim.list_extend({ "Answer:", "" }, output_lines(res))
    show_results(lines, hints(RUN, NEXT))
  end)
end

function M.redo()
  vim.api.nvim_buf_set_lines(S.sql_buf, 0, -1, false, {})
  save_sql()
  fit() -- TextChanged only fires when the SQL pane is the current window
  show_results({ "Cleared (u to undo)." })
end

function M.next()
  save_sql()
  load({ "--after", S.slug })
end

local ACTIONS = {
  { "r", M.run, "run & check" },
  { "n", M.next, "next problem" },
  { "R", M.redo, "redo (clear your SQL)" },
  { "a", M.answer, "show answer" },
}

local function map_keys(buf)
  for _, a in ipairs(ACTIONS) do
    vim.keymap.set("n", "<leader>" .. a[1], a[2], { buffer = buf, desc = "sqlgym: " .. a[3] })
  end
end

-- --- the SQL buffer -------------------------------------------------------------

local function setup_sql_buffer(buf)
  -- LazyVim's SQL extra formats on save, which would rewrite the answer.
  vim.b[buf].autoformat = false
  -- No completion popup: it hijacks the arrow keys in insert mode, and
  -- interviews don't autocomplete for you. (blink.cmp honours this.)
  vim.b[buf].completion = false
  -- nvim's own ftplugin/sql.vim maps insert-mode <Left>/<Right> to its
  -- "drill into/out of table" completion; give the arrows back.
  for _, lhs in ipairs({ "<Left>", "<Right>" }) do
    pcall(vim.keymap.del, "i", lhs, { buffer = buf })
  end
  map_keys(buf)
  -- The SQL pane grows with your query; results take the rest.
  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI" }, {
    buffer = buf,
    callback = function()
      fit()
    end,
  })
end

-- sqlfluff (LazyVim's SQL extra lints with it) errors without a configured
-- dialect and misparses valid DuckDB even with one. DuckDB checks the query
-- on run, so skip sqlfluff for files in the work dir.
local function skip_sqlfluff(work_dir)
  local ok, lint = pcall(require, "lint")
  if ok and type(lint.linters.sqlfluff) == "table" then
    local condition = lint.linters.sqlfluff.condition
    lint.linters.sqlfluff.condition = function(ctx)
      return not vim.startswith(ctx.filename, work_dir) and (condition == nil or condition(ctx))
    end
  end
end

-- --- loading a problem ------------------------------------------------------------

local MARK_HL = {
  question = "SqlgymBold",
  table = "SqlgymBold",
}

local function render_problem(p)
  set_lines(S.problem_buf, p.lines)
  vim.api.nvim_buf_clear_namespace(S.problem_buf, ns, 0, -1)
  for _, m in ipairs(p.marks) do
    local row, kind = m[1], m[2]
    vim.api.nvim_buf_set_extmark(S.problem_buf, ns, row, 0, { end_col = #p.lines[row + 1], hl_group = MARK_HL[kind] })
  end
end

local MARGIN = "  " -- left margin in every pane (drawn as the 'statuscolumn')

local function problem_width()
  local width = vim.api.nvim_win_is_valid(S.wins.problem or -1) and vim.api.nvim_win_get_width(S.wins.problem) or 80
  return width - #MARGIN
end

-- A title bar drawn as a rule: "─ Problem 3 · easy ────────── right ─".
local function bar(label, right)
  local text = "─ " .. label:gsub("%%", "%%%%") .. " %="
  return right and text .. " " .. right .. " ─" or text
end

local function show_problem(p)
  S.slug, S.work_file = p.slug, p.work_file

  render_problem(p)
  vim.api.nvim_win_set_cursor(S.wins.problem, { 1, 0 })
  vim.wo[S.wins.problem].winbar = bar(p.header)

  -- Swap the SQL pane to this problem's file unless it's already showing.
  local path = vim.fn.fnamemodify(p.work_file, ":p")
  if vim.api.nvim_buf_get_name(S.sql_buf) ~= path then
    local old = S.sql_buf
    vim.api.nvim_win_call(S.wins.sql, function()
      vim.cmd("silent edit " .. vim.fn.fnameescape(path))
    end)
    S.sql_buf = vim.api.nvim_win_get_buf(S.wins.sql)
    if old ~= S.sql_buf then
      pcall(vim.api.nvim_buf_delete, old, {})
    end
    setup_sql_buffer(S.sql_buf)
    style_sql_pane() -- a new buffer in the window doesn't keep the pane's options
  end

  show_results({})
  vim.api.nvim_set_current_win(S.wins.sql)
  fit()
end

load = function(args)
  sqlgym(vim.list_extend({ "_load", "--width", tostring(problem_width()) }, args), function(res)
    if res.code ~= 0 then
      return show_results(output_lines(res))
    end
    local p = vim.json.decode(res.stdout)
    if p.done then
      return show_results({ "✓ You've solved everything. Nice work!" })
    end
    show_problem(p)
  end)
end

-- --- layout -------------------------------------------------------------------------

local MIN_RESULTS = 9 -- lines kept for results (title bar + 8) however long the problem or query

local function valid(win)
  return vim.api.nvim_win_is_valid(win or -1)
end

-- Rows the three panes share: the screen minus the tabline, the status line,
-- the command line and the two blank separators between panes. Worked out
-- from the screen rather than the panes' current heights, which can be off
-- for a moment (e.g. while a message briefly takes a row).
local function shared_rows()
  local tabline = (vim.o.showtabline == 2 or (vim.o.showtabline == 1 and #vim.api.nvim_list_tabpages() > 1)) and 1 or 0
  return vim.o.lines - tabline - 1 - vim.o.cmdheight - 2
end

-- Size each pane to its content: the problem and your SQL get
-- just the lines they need, and results get the rest. Long content scrolls.
-- Heights include each pane's title bar, hence the +1s.
fit = function()
  local w = S.wins
  if S.fitting or not (valid(w.problem) and valid(w.sql) and valid(w.results)) then
    return
  end
  S.fitting = true
  local total = shared_rows()
  local sql_lines = vim.api.nvim_buf_line_count(S.sql_buf) + 1
  local sql = math.max(2, math.min(sql_lines, total - 2 - MIN_RESULTS))
  local problem = math.max(2, math.min(vim.api.nvim_buf_line_count(S.problem_buf) + 1, total - sql - MIN_RESULTS))
  -- Results get what's left. (Setting the SQL height can move rows to or from
  -- the problem pane, so it's set again afterwards.)
  vim.api.nvim_win_set_height(w.problem, problem)
  vim.api.nvim_win_set_height(w.sql, sql)
  vim.api.nvim_win_set_height(w.problem, problem)
  S.fitting = false
  -- Keep the SQL pane full of query: growing it can leave lines scrolled out
  -- of view above, and blank rows below. (Deferred: nvim scrolls the window
  -- after TextChangedI.)
  vim.schedule(function()
    if not valid(w.sql) then
      return
    end
    vim.api.nvim_win_call(w.sql, function()
      local top = math.max(1, vim.api.nvim_buf_line_count(0) - (vim.api.nvim_win_get_height(0) - 1) + 1)
      if vim.fn.winsaveview().topline > top then
        vim.fn.winrestview({ topline = top })
      end
    end)
  end)
end

-- Re-wrap the prompt to the problem pane's new width.
local function rewrap()
  if not S.slug then
    return
  end
  sqlgym({ "_load", "--width", tostring(problem_width()), "--slug", S.slug }, function(res)
    if res.code == 0 then
      render_problem(vim.json.decode(res.stdout))
      fit()
    end
  end)
end

local function scratch(name)
  local buf = vim.api.nvim_create_buf(false, true) -- unlisted, buftype=nofile
  vim.api.nvim_buf_set_name(buf, name)
  vim.bo[buf].modifiable = false
  map_keys(buf)
  return buf
end

-- Plain panes: a margin instead of line numbers, no highlighted cursor line,
-- and title bars drawn as rules in the normal text colour.
local function pane_options(win, opts)
  local fillchars = vim.opt.fillchars:get()
  -- Blank separators between stacked panes: the title-bar rules divide them.
  fillchars.wbr, fillchars.eob, fillchars.horiz = "─", " ", " "
  local fill = {}
  for k, v in pairs(fillchars) do
    table.insert(fill, k .. ":" .. v)
  end
  for k, v in pairs(vim.tbl_extend("keep", opts, {
    number = true, -- needed for 'statuscolumn' to be drawn
    numberwidth = 1,
    relativenumber = false,
    statuscolumn = MARGIN,
    signcolumn = "no",
    foldcolumn = "0",
    cursorline = false,
    spell = false,
    list = false,
    fillchars = table.concat(fill, ","),
    winhighlight = "WinBar:SqlgymBar,WinBarNC:SqlgymBar",
  })) do
    vim.wo[win][k] = v
  end
end

style_sql_pane = function()
  -- With scrolloff, a pane sized to fit the query would scroll its first lines away.
  -- Long lines scroll sideways, as in the other panes, so each line of SQL is one row.
  pane_options(S.wins.sql, { winbar = bar("SQL", key("r") .. " to run"), scrolloff = 0, wrap = false })
end

function M.start(opts)
  S.opts = opts
  -- One status line at the bottom rather than one per pane. (This nvim runs
  -- only sqlgym, so session-wide options are fine; config files are untouched.)
  vim.o.laststatus = 3
  -- Resizing panes keeps the cursor's line in view, rather than the same screen rows.
  vim.o.splitkeep = "cursor"
  vim.api.nvim_set_hl(0, "SqlgymBold", { bold = true, default = true })
  vim.api.nvim_set_hl(0, "SqlgymBar", { default = true }) -- plain text, no background
  skip_sqlfluff(opts.work_dir)

  -- nvim was started on the work file: that window becomes the SQL pane.
  S.wins.sql = vim.api.nvim_get_current_win()
  S.sql_buf = vim.api.nvim_get_current_buf()
  setup_sql_buffer(S.sql_buf)

  S.problem_buf = scratch("[sqlgym problem]")
  S.results_buf = scratch("[sqlgym results]")

  vim.cmd("leftabove split")
  S.wins.problem = vim.api.nvim_get_current_win()
  vim.api.nvim_win_set_buf(S.wins.problem, S.problem_buf)
  pane_options(S.wins.problem, { wrap = false, winbar = bar("Problem") })

  vim.api.nvim_set_current_win(S.wins.sql)
  style_sql_pane()
  vim.cmd("rightbelow split")
  S.wins.results = vim.api.nvim_get_current_win()
  vim.api.nvim_win_set_buf(S.wins.results, S.results_buf)
  pane_options(S.wins.results, { wrap = false, winbar = bar("Results") })

  vim.api.nvim_set_current_win(S.wins.sql)
  fit()

  local group = vim.api.nvim_create_augroup("sqlgym", { clear = true })
  -- Other plugins (or nvim itself, e.g. when a message briefly takes a row)
  -- can resize the panes after we lay them out: lay them out again.
  vim.api.nvim_create_autocmd("WinResized", {
    group = group,
    callback = function()
      for _, win in ipairs(vim.v.event.windows) do
        if vim.tbl_contains(vim.tbl_values(S.wins), win) then
          return fit()
        end
      end
    end,
  })
  vim.api.nvim_create_autocmd("VimResized", {
    group = group,
    callback = function()
      fit()
      rewrap()
    end,
  })
  -- :q / :wq in any pane saves your SQL and closes all three, so nvim exits.
  vim.api.nvim_create_autocmd("QuitPre", {
    group = group,
    callback = function()
      local current = vim.api.nvim_get_current_win()
      if not vim.tbl_contains(vim.tbl_values(S.wins), current) then
        return -- quitting some other window (e.g. :help); leave the layout alone
      end
      save_sql()
      for _, win in pairs(S.wins) do
        if win ~= current and vim.api.nvim_win_is_valid(win) then
          vim.api.nvim_win_close(win, true)
        end
      end
    end,
  })

  vim.api.nvim_create_user_command("Sqlgym", function(cmd)
    local action = ({ run = M.run, next = M.next, redo = M.redo, answer = M.answer })[cmd.args]
    if action then
      action()
    else
      vim.notify("Usage: :Sqlgym run|next|redo|answer", vim.log.levels.WARN)
    end
  end, {
    nargs = 1,
    complete = function()
      return { "run", "next", "redo", "answer" }
    end,
  })

  load({ "--slug", opts.slug })
end

return M
