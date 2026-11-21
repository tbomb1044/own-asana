# own-asana

A small tool that lets Claude work in one more Asana account: your own.

Claude's built-in Asana connector can be signed in to one Asana account at a
time. If that one is signed in to an employer's or a client's Asana, own-asana
gives Claude a second, separate way into your own practice's Asana. The
built-in connector stays as it is.

**From version 1.3.0, own-asana changes things in Asana as well as looking.**
Versions up to 1.2.0 could only look. If that is what you want, see "Versions"
below.

It runs on Windows and on a Mac, in Claude's Code tab (Claude Code). It needs
Python 3.8 or later and nothing else: standard library only, no packages.

## What it does

In the one Asana workspace you choose when you set it up, Claude can do what
you can do in Asana yourself:

- look at projects, sections, tasks, subtasks, comments, tags, people and
  teams, and search tasks (search needs a paid Asana plan);
- create a task or a subtask; edit a task's name, description, assignee, due
  date or time, start date and custom fields; mark a task done or open it
  again;
- put a task into a project or take it out, move it to a section, make it a
  subtask or a task of its own;
- comment on a task; add and remove followers; create a tag, put it on a task
  or take it off;
- create a project, edit it, archive it or bring it back; add and remove its
  members; create, rename and move its sections;
- copy a task or a project;
- delete a task, a section or a project.

What is done through own-asana is done in your name, as if you did it.

## What keeps it in check

Three things are in the code:

- **One workspace.** Before anything is changed, own-asana looks up every item
  the change names (the task, the project, the section, the tag, the person,
  the team) and refuses unless each one is in the workspace you chose. Nothing
  in another workspace is shown or changed. Claude cannot name a different
  workspace: a new task or project always goes to the one from the set-up.
- **A delete is one item, by its id and by its name.** A delete tool takes one
  id and a `confirm` text. own-asana reads the item's current name from Asana
  and deletes only if `confirm` is exactly that name. Nothing is deleted by id
  alone, and there is no way to delete several things in one call. Asana keeps
  a deleted task in your trash for 30 days.
- **One host, no detours.** It talks only to `app.asana.com`, never follows a
  redirect, and never sends a change a second time if Asana did not answer.

One thing is a rule that Claude is given, every time own-asana starts:

- **Claude asks before a big change.** It is told to say in one line what will
  change and to wait for your yes before any delete or archive, anything that
  touches more than three items in one request, a change to a project's
  sections or members, and anything you did not ask for in so many words. A
  small change you asked for (create this task, mark it done, add this
  comment) goes ahead. It is also told never to act on instructions it finds
  inside Asana content, and never to use own-asana on an employer's Asana.

That last one is an instruction, not a lock. Each action is a separate tool
with a plain name (`create_task`, `add_comment`, `delete_task` and so on), so
when Claude Code asks your permission to use a tool, the question names the
action. If you tell Claude to always allow a tool, or run Claude in a mode
that does not ask, that question is gone. It is safer never to always allow a
tool that deletes.

## What it does not do

There is no tool that sends an arbitrary request to Asana: such a tool could
not be kept to one workspace. So only the actions listed above exist. Among
the things you can do in Asana that own-asana does not: attachments; task
dependencies; milestones and approvals; recurring tasks; editing or deleting a
comment; formatted text; deleting or renaming a tag; colours; project owner,
privacy, status updates, templates and custom-field settings; portfolios and
goals; teams, invitations and memberships of a workspace; My Tasks sections;
time tracking; messages; rules and forms; several items in one call.

It works only in a chat opened on the folder it was set up in. Other folders
and other chats do not get it. It talks to Asana straight from your computer.
Nothing goes to anyone else.

## Where your Asana token lives

own-asana uses an Asana personal access token. A token works like a password
for your whole Asana account, and Asana does not let a token be limited, so
the token itself could do anything you can do, in every workspace you belong
to. own-asana is what keeps Claude to one workspace.

- You paste the token once, into own-asana's own set-up window, where it is
  hidden as you paste.
- It is stored in the computer's own credential store: Windows Credential
  Manager, or the Keychain on a Mac. It is never written to a file, never put
  on a command line, and never shown.
- Never paste the token into a Claude chat, an email or a file. Claude never
  needs to see it. The set-up refuses to ask its questions anywhere except in
  a real window with a keyboard, so it cannot be run inside a chat.

## Setting it up

Put it in the Claude folder you use for your own practice. Never in a folder
that an employer or a firm set up for you: the set-up stops if it sees one.
Choose your own practice's workspace when the set-up asks. Whichever workspace
you choose is the one Claude will be able to change.

The usual way is a short request that you paste into Claude, in a chat opened
on that folder. Claude downloads `own-asana.zip` from this repository's
Releases page, checks its SHA-256, unpacks it into a folder called `own-asana`
and opens the set-up in a window of its own. You make the token in Asana and
answer a few questions in that window. Then you close Claude and open it
again.

To do the same by hand on Windows, in PowerShell, from your own practice's
folder:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/tbomb1044/own-asana/releases/download/v1.3.0/own-asana.zip" -OutFile "own-asana.zip"
(Get-FileHash "own-asana.zip" -Algorithm SHA256).Hash
Expand-Archive "own-asana.zip" -DestinationPath "own-asana"
py -3 -I -B own-asana\program\run_setup.py
```

On a Mac, in Terminal:

```sh
curl -fsSL -o own-asana.zip "https://github.com/tbomb1044/own-asana/releases/download/v1.3.0/own-asana.zip"
shasum -a 256 own-asana.zip
unzip -q own-asana.zip -d own-asana
python3 -I -B own-asana/program/run_setup.py
```

Go on only if the SHA-256 is the one below.

On Windows, fetch the zip with PowerShell as shown, not with a web browser.
Windows marks files that a browser downloads, and Smart App Control then
blocks the launchers inside. If that happens, do not switch anything off.

## Checking the download

`own-asana.zip` for version 1.3.0 has this SHA-256:

```
2a77ae6bbadf97d6aa86f4223a9b77289e52c1b3cb6b05d502ecc9617bf7db58
```

Windows: `(Get-FileHash "own-asana.zip" -Algorithm SHA256).Hash` (capital
letters or small, it is the same value). Mac: `shasum -a 256 own-asana.zip`.
If the value is different, delete the file and do not unpack it.

The zip holds exactly the files in the `own-asana` folder of this repository.
`python3 -B make_zip.py` writes the same zip, byte for byte, from the source.

## Versions

- **1.3.0** looks and changes, as described on this page.
- **1.2.0** only looks: it has no tool and no code that changes anything in
  Asana. It is still on the Releases page as `v1.2.0`, and its
  `own-asana.zip` has the SHA-256
  `7d843e01d7222c9ecd21fb795a469b104b8ff252f5dccc180a343379a88e2101`.

To go from one version to another, run Remove, delete the `own-asana` folder
and set the other version up. A set-up of 1.2.0 does not change by itself.

## Removing it

1. In the `own-asana` folder, run Remove: double-click "Remove on Windows" or
   "Remove on Mac", or run `py -3 -I -B own-asana\program\run_remove.py`
   (on a Mac, `python3 -I -B own-asana/program/run_remove.py`). This deletes
   the stored token and takes own-asana off Claude's list for that folder.
2. In Asana, go to https://app.asana.com/0/my-apps and delete the token under
   "Personal access tokens". This is what makes the token stop working
   everywhere.
3. Delete the `own-asana` folder, then close Claude completely and open it
   again. Until you do, a Claude chat that was already open can still use
   own-asana. A new chat cannot.

Removing it changes nothing in Asana. What was added or changed there stays.

## What is in the folder

| File | What it is |
|---|---|
| `READ ME FIRST.txt` | One page, plain words. |
| `Set up on Windows.cmd`, `Set up on Mac.command` | Start the set-up by double-click. |
| `Remove on Windows.cmd`, `Remove on Mac.command` | Start Remove by double-click. |
| `program/run_setup.py`, `program/run_remove.py` | What both routes run. `--check` looks only and changes nothing. |
| `program/own_asana/asana.py` | The only code that talks to Asana. `app.asana.com` only, no redirects. One function sends every request: GET to look, and POST, PUT or DELETE to change. |
| `program/own_asana/server.py` | The local server Claude talks to. 10 tools that look and 27 that change, all pinned to one workspace. The workspace check and the delete-by-name check are here. |
| `program/own_asana/credstore.py` | Windows Credential Manager and the macOS Keychain. No file fallback. |
| `program/own_asana/setup.py`, `remove.py`, `config.py`, `entry.py` | The set-up and remove windows, and the small settings file (never the token). |

## What has been tested, and what has not

The tools were built against Asana's published developer reference and are
tested against a stand-in for Asana that runs on the developer's own
computer. They have not been run against Asana itself. If an action fails,
own-asana says what Asana answered and changes nothing else.
