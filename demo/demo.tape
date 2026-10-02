# Records demo/sqlgym.gif: `vhs demo/demo.tape` (run from the repo root).
# Neovim runs with demo/nvim/init.lua (just leader = space) and scratch dirs,
# so the recording looks the same on any machine and your progress is untouched.

Output demo/sqlgym.gif

Set Shell bash
Set FontSize 16
Set Width 1200
Set Height 880
Set Padding 16
Set TypingSpeed 60ms
Set Theme "Builtin Dark"

Hide
Type "export D=$(mktemp -d) XDG_CONFIG_HOME=$PWD/demo"
Enter
Type "export XDG_DATA_HOME=$D/data XDG_STATE_HOME=$D/state SQLGYM_DATA_DIR=$D/sqlgym && clear"
Enter
Type "sqlgym open 3"
Enter
Sleep 2s
Show

Sleep 2s

# A first try: every facility.
Type "i"
Type "select * from cd.facilities"
Escape
Sleep 500ms
Type " r"
Sleep 3s

# Fix it.
Type "A"
Enter
Type "where membercost > 0"
Escape
Sleep 500ms
Type " r"
Sleep 5s
