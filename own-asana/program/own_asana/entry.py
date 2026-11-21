"""How Set up and Remove are started, and the few options they take.

They are started in one of two ways:

  - by a launcher in the own-asana folder that the person double-clicks, or
  - by Claude, which opens a new window with one fixed command and then stays
    out of it. The person types every answer in that window, not in a chat.

Options (nothing else is accepted):

  --window   keep the window open at the end until Enter is pressed
  --check    Set up only: look, ask nothing, change nothing, and say whether
             Set up can run in this folder

The token is never an option. Anything that is not on the list above is
refused, and what was typed is not repeated on screen.

Standard library only. Python 3.8 or later.
"""

import sys

WINDOW = "--window"
CHECK = "--check"

NEEDS_ITS_OWN_WINDOW = (
    "",
    "Stopped. This has to run in its own window, where you type the answers",
    "yourself. It was started without one. Nothing was changed.",
)


class UsageError(Exception):
    pass


class NoTerminal(Exception):
    """A question was about to be asked, but there is no keyboard to answer it."""


def parse(argv, allowed):
    """The options given, as a set. Anything not in `allowed` raises UsageError.

    The error carries no text on purpose: if someone put a token on the command
    line by mistake, it must not be echoed back.
    """
    chosen = set()
    for item in argv:
        if item not in allowed:
            raise UsageError()
        chosen.add(item)
    return chosen


def is_terminal(stream=None):
    """True when answers come from a keyboard in a real window, not a pipe or a file."""
    if stream is None:
        stream = sys.stdin
    try:
        if stream is None or not stream.isatty():
            return False
    except (AttributeError, ValueError, OSError):
        return False
    if sys.platform == "win32":
        return _is_windows_console(stream)
    return True


def _is_windows_console(stream):
    """On Windows the "nothing" device (NUL) also claims to be a terminal. A real
    console is the only thing that has a console mode, so ask for it."""
    try:
        import ctypes
        import msvcrt
        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_ulong()
        return bool(ctypes.windll.kernel32.GetConsoleMode(ctypes.c_void_p(handle),
                                                          ctypes.byref(mode)))
    except Exception:  # noqa: BLE001 - could not ask; isatty() already said yes
        return True


def set_window_title(text):
    """Name the window, so the person can find it. Windows only; never fails."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.SetConsoleTitleW(str(text)))
    except Exception:  # noqa: BLE001 - a title is never worth stopping for
        return False


def wait_for_enter():
    """Hold the window open until the person has read it."""
    print("")
    try:
        input("Press Enter to close this window. ")
    except (EOFError, KeyboardInterrupt):
        pass
