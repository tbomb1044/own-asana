"""Remove: take the token out of the credential store and tell Claude to forget own-asana.

It does not touch Asana itself. The last lines tell the person how to cancel
the token there, which is the step that makes it useless everywhere.

Standard library only. Python 3.8 or later.
"""

import sys

from . import config, credstore, entry
from .setup import ConsoleIO, _yes

USAGE = (
    "own-asana remove takes only this option:",
    "  --window   keep the window open at the end until Enter is pressed",
    "It takes nothing else. Nothing was changed.",
)


def run_remove(io, pkg_dir=None, store=credstore):
    pkg_dir = pkg_dir or config.package_dir()
    io.say("own-asana: remove")
    io.say("=================")
    io.say("")
    if not store.store_name():
        io.say("This works on Windows and on a Mac only. Nothing was changed.")
        return 1
    io.say("This takes own-asana off this computer:")
    io.say("  - the stored Asana token is deleted from %s" % store.store_name())
    io.say("  - Claude is told to stop using own-asana in:  " + config.claude_folder(pkg_dir))
    io.say("Nothing in Asana is changed.")
    io.say("")
    if not _yes(io.ask("Go ahead? Type Y and press Enter: ")):
        io.say("Stopped. Nothing was changed.")
        return 1

    problems = 0
    try:
        had_token = store.delete()
        io.say("Token: deleted." if had_token else "Token: there was none stored.")
    except credstore.CredStoreError as err:
        problems += 1
        io.say("Token: could not be deleted. " + str(err))
    try:
        outcome = config.remove_from_mcp_file(pkg_dir)
        io.say("Claude's list: own-asana removed." if outcome != "absent"
               else "Claude's list: own-asana was not on it.")
    except (OSError, config.McpFileError) as err:
        problems += 1
        io.say("Claude's list: could not be changed. " + str(err))
    config.delete_settings(pkg_dir)

    io.say("")
    io.say("Two things left for you:")
    io.say("  1. Cancel the token in Asana, so it stops working everywhere:")
    io.say("     go to https://app.asana.com/0/my-apps , find the token under")
    io.say('     "Personal access tokens", and delete it ("Deauthorize").')
    io.say("  2. Delete this own-asana folder, then close Claude completely and open it")
    io.say("     again. Until you do, a Claude chat that was already open can still use")
    io.say("     own-asana.")
    return 0 if problems == 0 else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        options = entry.parse(argv, (entry.WINDOW,))
    except entry.UsageError:
        for line in USAGE:
            print(line)
        if entry.WINDOW in argv and entry.is_terminal():
            entry.wait_for_enter()
        return 2
    window = entry.WINDOW in options
    if window:
        entry.set_window_title("own-asana remove")
    try:
        code = run_remove(ConsoleIO())
    except (KeyboardInterrupt, EOFError):
        print("")
        print("Stopped.")
        code = 1
    if window:
        entry.wait_for_enter()
    return code


if __name__ == "__main__":
    sys.exit(main())
