"""Set up: ask for the token in a hidden prompt, check it, store it, tell Claude.

It says plainly, before the first question, that Claude will be able to change
things in the chosen workspace and not only look, and that Claude asks before
a big change.

This runs in its own window, outside Claude. The token is typed here and
nowhere else. It is never printed, never written to a file, and never passed
as a command argument. When it is started without a window of its own (by a
pipe, a file or a program), it stops before the first question.

`--check` looks without asking or changing anything, so the folder and Python
can be checked before the window is opened.

Everything the person reads on screen is in this file, in plain words.

Standard library only. Python 3.8 or later.
"""

import datetime
import getpass
import sys

from . import config, credstore, entry
from .asana import AsanaClient, AsanaError

MAX_TOKEN_TRIES = 3

HOW_TO_GET_A_TOKEN = """\
First, make the token in Asana. Use your OWN practice's Asana login, not your
employer's.

  1. In your web browser, sign in to Asana with your own practice's login.
  2. Go to this address:  https://app.asana.com/0/my-apps
     (or: click your photo at the top right, then Settings, then Apps,
     then the link to the developer console)
  3. Under "Personal access tokens", click "Create new token".
  4. Give it a name such as "Claude on my computer". If there is a box to
     agree to the terms, tick it. Then click "Create token".
  5. Copy the token. Asana shows it only this once.
"""


def how_to_paste(platform=None):
    """The lines shown above the hidden token question, for this kind of computer."""
    if (platform or sys.platform) == "darwin":
        return ("Press Command and V to paste it, then Enter. Nothing shows as you paste;",
                "that is normal.")
    return ("Press Ctrl+V to paste it, then Enter. Nothing shows as you paste; that is",
            "normal. If Ctrl+V does nothing, right-click once instead.")


def clean_token(entered):
    """What was pasted, without spaces, line breaks or stray control characters.

    A paste can bring a line break with it, and a paste key that the window did
    not take as "paste" can leave an invisible character behind. Neither is ever
    part of a token.
    """
    return "".join(ch for ch in (entered or "") if ch.isprintable() and not ch.isspace())


USAGE = (
    "own-asana set-up takes only these options:",
    "  --window   keep the window open at the end until Enter is pressed",
    "  --check    look only: say whether set-up can run in this folder",
    "It takes nothing else. Never put a token on a command line.",
    "Nothing was changed.",
)


class ConsoleIO(object):
    """The real screen and keyboard.

    With require_terminal, a question is never asked of a pipe or a file: the
    answers, and above all the token, are typed by a person in a real window.
    """

    def __init__(self, require_terminal=False):
        self._require_terminal = require_terminal

    def _needs_a_person(self):
        if self._require_terminal and not entry.is_terminal():
            raise entry.NoTerminal()

    def say(self, text=""):
        print(text)
        sys.stdout.flush()

    def ask(self, prompt):
        self._needs_a_person()
        return input(prompt)

    def ask_hidden(self, prompt):
        self._needs_a_person()
        return getpass.getpass(prompt)


def _yes(answer):
    return answer.strip().lower() in ("y", "yes")


def why_not_here(pkg_dir, store):
    """The lines to show if Set up must not run in this folder, or None if it may.

    Looks only. It reads no token and changes nothing.
    """
    folder = config.claude_folder(pkg_dir)
    if not store.store_name():
        return ["This works on Windows and on a Mac only. Nothing was changed."]
    if config.looks_like_firm_folder(folder):
        return [
            "Stop: this looks like a Claude folder that a firm you work for set up:",
            "  " + folder,
            "own-asana belongs in your OWN practice's Claude folder, not the firm's.",
            "Move the own-asana folder there and run Set up again. Nothing was changed.",
        ]
    try:
        config._read_mcp(config.mcp_path(pkg_dir))
    except config.McpFileError as err:
        return [str(err), "Ask for help before going on. Nothing was changed."]
    return None


def run_check(io, pkg_dir=None, store=credstore):
    """`--check`: say whether Set up can run here. Asks nothing, changes nothing."""
    pkg_dir = pkg_dir or config.package_dir()
    problem = why_not_here(pkg_dir, store)
    if problem:
        for line in problem:
            io.say(line)
        return 1
    io.say("own-asana check: ready")
    io.say("  Python:  %d.%d.%d" % tuple(sys.version_info[:3]))
    io.say("  Folder:  " + config.claude_folder(pkg_dir))
    io.say("Nothing was changed. Set up can now be opened in its own window.")
    return 0


def run_setup(io, pkg_dir=None, python_exe=None, store=credstore, make_client=None,
              today=None):
    """Returns 0 when set up, 1 when stopped. Never raises for an expected problem."""
    pkg_dir = pkg_dir or config.package_dir()
    python_exe = python_exe or sys.executable
    make_client = make_client or (lambda provider: AsanaClient(provider))
    today = today or datetime.date.today().isoformat()
    folder = config.claude_folder(pkg_dir)

    io.say("own-asana: set up")
    io.say("==================")
    io.say("")

    problem = why_not_here(pkg_dir, store)
    if problem:
        for line in problem:
            io.say(line)
        return 1

    io.say("This lets Claude work in your own Asana whenever you open this folder in Claude:")
    io.say("  " + folder)
    io.say("There Claude can do what you can do yourself: look, and also add, change,")
    io.say("complete and delete. It asks you before any big change: a delete, an archive,")
    io.say("more than three items at once, or anything you did not ask for.")
    io.say("")
    if not _yes(io.ask("Is that the Claude folder for your own practice? Type Y and press Enter: ")):
        io.say("Stopped. Put the own-asana folder inside your own practice's Claude folder,")
        io.say("then run Set up again. Nothing was changed.")
        return 1
    io.say("")

    io.say(HOW_TO_GET_A_TOKEN)
    client = None
    me = None
    token = None
    for attempt in range(MAX_TOKEN_TRIES):
        io.say("Now the token.")
        for line in how_to_paste():
            io.say(line)
        entered = io.ask_hidden("Token: ")
        candidate = clean_token(entered)
        if not credstore.looks_like_token(candidate):
            io.say("")
            io.say("That did not come through as an Asana token. Copy it again in Asana,")
            io.say("then paste it here again.")
            io.say("")
            continue
        io.say("")
        io.say("Checking with Asana...")
        candidate_client = make_client(lambda value=candidate: value)
        try:
            me = candidate_client.me()
        except AsanaError as err:
            if err.kind == "unauthorized":
                io.say("Asana did not accept that token. Make a new one and try again.")
                io.say("")
                continue
            io.say(err.message)
            io.say("Nothing was saved. Try again later.")
            return 1
        client, token = candidate_client, candidate
        break
    if client is None:
        io.say("Stopped after %d tries. Nothing was saved." % MAX_TOKEN_TRIES)
        return 1

    name = str(me.get("name") or "")
    email = str(me.get("email") or "")
    workspaces = [ws for ws in (me.get("workspaces") or [])
                  if str(ws.get("gid") or "").isdigit()]
    io.say("")
    io.say("This token belongs to:  %s  <%s>" % (name, email))
    if not workspaces:
        io.say("It cannot see any Asana workspace, so there is nothing to connect.")
        io.say("Nothing was saved.")
        return 1

    if len(workspaces) == 1:
        chosen = workspaces[0]
        io.say("It can see one workspace:  %s" % chosen.get("name"))
    else:
        io.say("It can see these workspaces:")
        for index, workspace in enumerate(workspaces, 1):
            io.say("  %d. %s" % (index, workspace.get("name")))
        io.say("Claude will be able to work in ONE of them through own-asana, and no other.")
        answer = io.ask("Which one is your own practice's? Type its number and press Enter: ")
        try:
            chosen = workspaces[int(answer.strip()) - 1]
            if int(answer.strip()) < 1:
                raise IndexError
        except (ValueError, IndexError):
            io.say("That was not one of the numbers. Nothing was saved. Run Set up again.")
            return 1

    io.say("")
    io.say('About to connect:  "%s"  signed in as  %s' % (chosen.get("name"), email or name))
    io.say("Claude will be able to change things there, not only look.")
    answer = io.ask("Is that your OWN practice's Asana, and not your employer's? "
                    "Type YES and press Enter: ")
    if answer.strip().lower() != "yes":
        io.say("Stopped. Nothing was saved.")
        io.say("If you made the token in the wrong Asana login, delete it there")
        io.say("(https://app.asana.com/0/my-apps) and start again.")
        return 1

    try:
        store.save(token)
    except credstore.CredStoreError as err:
        io.say(str(err))
        io.say("Nothing was saved.")
        return 1
    try:
        config.save_settings({
            "workspace_gid": str(chosen.get("gid")),
            "workspace_name": str(chosen.get("name") or ""),
            "account_name": name,
            "account_email": email,
            "set_up_on": today,
        }, pkg_dir)
        mcp_file = config.add_to_mcp_file(python_exe, pkg_dir)
    except (OSError, config.McpFileError) as err:
        try:
            store.delete()
        except credstore.CredStoreError:
            pass
        config.delete_settings(pkg_dir)
        io.say("Could not finish writing the settings (%s)." % type(err).__name__)
        io.say("The token was removed again. Nothing is left behind.")
        return 1

    io.say("")
    io.say("Done.")
    io.say("  The token is stored in %s. It is not in any file." % store.store_name())
    io.say("  Claude was told about own-asana in:  " + mcp_file)
    io.say("")
    io.say("What to do now:")
    io.say("  1. Close Claude completely and open it again.")
    io.say("  2. In Claude, click Code, open this same folder, and start a new chat.")
    io.say("  3. If Claude asks whether to use a new server called own-asana, say yes.")
    io.say('  4. Ask Claude: "Use own-asana and tell me which Asana account you see."')
    io.say("")
    io.say("If you ever move or rename this folder, run Set up again.")
    io.say("To take it off this computer, run Remove from this same folder.")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        options = entry.parse(argv, (entry.WINDOW, entry.CHECK))
        if entry.CHECK in options and entry.WINDOW in options:
            raise entry.UsageError()
    except entry.UsageError:
        for line in USAGE:
            print(line)
        if entry.WINDOW in argv and entry.is_terminal():
            entry.wait_for_enter()
        return 2

    if entry.CHECK in options:
        return run_check(ConsoleIO())

    window = entry.WINDOW in options
    if window:
        entry.set_window_title("own-asana set-up")
    try:
        code = run_setup(ConsoleIO(require_terminal=True))
    except entry.NoTerminal:
        for line in entry.NEEDS_ITS_OWN_WINDOW:
            print(line)
        code = 1
    except (KeyboardInterrupt, EOFError):
        print("")
        print("Stopped. If a token was being entered, it was not saved.")
        code = 1
    except Exception as err:  # noqa: BLE001 - say so in the window before it closes
        if not window:
            raise
        print("")
        print("Stopped by an unexpected problem (%s)." % type(err).__name__)
        print("To be sure nothing is left behind, run Remove from this same folder.")
        code = 1
    if window:
        entry.wait_for_enter()
    return code
