"""
Tests for the interactive CLI prompt auto-responder.

The critical cases:
1. Arrow-key selection menus (create-vite, clack, inquirer) — 'y' does
   nothing and bare Enter selects the highlighted option, which for
   create-vite is "Cancel operation" (the agent was cancelling its own
   scaffold).
2. Enter must be '\\r' (carriage return) — raw-mode TUIs do not accept
   '\\n', they just redraw the menu forever.
3. TUIs redraw the menu on every keypress, so the output buffer contains
   stale frames; only the LAST frame reflects the real cursor position.
"""
from runtime import _detect_cli_prompt, _detect_menu_answer, _parse_menu_options


# Real clack-style output (as produced by create-vite) — options are
# prefixed with box-drawing characters: "│  ● Cancel operation"
CREATE_VITE_DIR_NOT_EMPTY = """\
npx -y create-vite@latest ./ --template react
│
◆  Current directory is not empty. Please choose how to proceed:
│  ● Cancel operation
│  ○ Remove existing files and continue
│  ○ Ignore files and continue
└
"""

# After one ↓ keypress the TUI repaints: the buffer now holds the stale
# frame on top and the current frame (cursor on "Remove existing files")
# below it.
CREATE_VITE_REDRAWN_FRAMES = """\
◆  Current directory is not empty. Please choose how to proceed:
│  ● Cancel operation
│  ○ Remove existing files and continue
│  ○ Ignore files and continue
│  ○ Cancel operation
│  ● Remove existing files and continue
│  ○ Ignore files and continue
└
"""


def test_create_vite_menu_navigates_to_ignore_files():
    """Must arrow-down twice to 'Ignore files and continue', never 'y'."""
    answer = _detect_cli_prompt(CREATE_VITE_DIR_NOT_EMPTY)
    assert answer == '\x1b[B\x1b[B\r', f"expected ↓↓⏎(CR), got {answer!r}"


def test_parse_menu_options_strips_box_prefixes():
    """Options behind clack box-drawing prefixes must be parsed."""
    options = _parse_menu_options(CREATE_VITE_DIR_NOT_EMPTY)
    assert [o['label'] for o in options] == [
        'Cancel operation',
        'Remove existing files and continue',
        'Ignore files and continue',
    ]
    assert [o['selected'] for o in options] == [True, False, False]


def test_parse_menu_options_uses_only_last_redrawn_frame():
    """Stale frames from TUI repaints must be ignored — only the last
    frame's cursor position counts."""
    options = _parse_menu_options(CREATE_VITE_REDRAWN_FRAMES)
    assert [o['selected'] for o in options] == [False, True, False], options
    # Cursor is on index 1 (Remove); Ignore is index 2 → one ↓ then Enter
    assert _detect_menu_answer(CREATE_VITE_REDRAWN_FRAMES) == '\x1b[B\r'


def test_menu_with_no_safe_option_asks_user():
    """Unknown menus must return None (ask the user), not a blind answer."""
    text = """\
◆ Choose deletion mode:
● Delete everything permanently
○ Delete and purge backups
"""
    assert _detect_cli_prompt(text) is None
    assert _detect_menu_answer(text) is None


def test_menu_preferred_option_already_selected():
    """If the safe option is already highlighted, just press Enter (CR)."""
    text = """\
◆ Current directory is not empty. Please choose how to proceed:
● Ignore files and continue
○ Cancel operation
"""
    assert _detect_cli_prompt(text) == '\r'


def test_framework_select_menu_accepts_default():
    """'Select a framework' pickers accept the highlighted default."""
    text = """\
? Select a framework:
❯   React
    Vue
    Svelte
"""
    assert _detect_cli_prompt(text) == '\r'


def test_plain_yn_prompt_still_answers_yes():
    """Classic y/N confirmations (no menu markers) keep working — with CR."""
    assert _detect_cli_prompt("Ok to proceed? (y)") in ('y\r', '\r')
    assert _detect_cli_prompt("Do you want to continue? [Y/n]") == 'y\r'


def test_dir_not_empty_without_menu_still_answers_yes():
    """Old-style text-only overwrite prompts (no radio menu) answer 'y'."""
    assert _detect_cli_prompt("The directory is not empty. Overwrite? (y/N) ") == 'y\r'


def test_no_answer_contains_linefeed():
    """No auto-answer may end with '\\n' — raw-mode TUIs ignore it."""
    prompts = [
        CREATE_VITE_DIR_NOT_EMPTY,
        "Ok to proceed? (y)",
        "Do you want to continue? [Y/n]",
        "Project name: ",
        "Press enter to continue...",
        "Are you sure? ",
    ]
    for p in prompts:
        ans = _detect_cli_prompt(p)
        if ans is not None:
            assert '\n' not in ans, f"{p!r} → {ans!r} contains \\n"
