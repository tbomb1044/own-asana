# own-asana

A small tool that lets Claude read one more Asana account: your own.

Claude's built-in Asana connector can be signed in to one Asana account at a
time. If that one is signed in to an employer's or a client's Asana, own-asana
gives Claude a second, separate way to read your own practice's Asana. The
built-in connector stays as it is.

It runs on Windows and on a Mac, in Claude's Code tab (Claude Code). It needs
Python 3.8 or later and nothing else: standard library only, no packages.

## What it does, and what it cannot do

- It reads projects, tasks and comments in the one Asana workspace you choose
  when you set it up. Anything in another workspace is refused.
- It is read only. There is no tool, and no code, that adds, changes,
  completes or deletes anything in Asana. It only ever sends GET requests, and
  only to `app.asana.com`.
- It works only in a chat opened on the folder it was set up in. Other folders
  and other chats do not get it.
- It talks to Asana straight from your computer. Nothing goes to anyone else.

## Where your Asana token lives

own-asana uses an Asana personal access token. A token works like a password
for your whole Asana account, and Asana does not let a token be limited, so
own-asana is what keeps it to reading one workspace.

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

The usual way is a short request that you paste into Claude, in a chat opened
on that folder. Claude downloads `own-asana.zip` from this repository's
Releases page, checks its SHA-256, unpacks it into a folder called `own-asana`
and opens the set-up in a window of its own. You make the token in Asana and
answer a few questions in that window. Then you close Claude and open it
again.

To do the same by hand on Windows, in PowerShell, from your own practice's
folder:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/tbomb1044/own-asana/releases/download/v1.2.0/own-asana.zip" -OutFile "own-asana.zip"
(Get-FileHash "own-asana.zip" -Algorithm SHA256).Hash
Expand-Archive "own-asana.zip" -DestinationPath "own-asana"
py -3 -I -B own-asana\program\run_setup.py
```

On a Mac, in Terminal:

```sh
curl -fsSL -o own-asana.zip "https://github.com/tbomb1044/own-asana/releases/download/v1.2.0/own-asana.zip"
shasum -a 256 own-asana.zip
unzip -q own-asana.zip -d own-asana
python3 -I -B own-asana/program/run_setup.py
```

Go on only if the SHA-256 is the one below.

On Windows, fetch the zip with PowerShell as shown, not with a web browser.
Windows marks files that a browser downloads, and Smart App Control then
blocks the launchers inside. If that happens, do not switch anything off.

## Checking the download

`own-asana.zip` for version 1.2.0 has this SHA-256:

```
7d843e01d7222c9ecd21fb795a469b104b8ff252f5dccc180a343379a88e2101
```

Windows: `(Get-FileHash "own-asana.zip" -Algorithm SHA256).Hash` (capital
letters or small, it is the same value). Mac: `shasum -a 256 own-asana.zip`.
If the value is different, delete the file and do not unpack it.

The zip holds exactly the files in the `own-asana` folder of this repository.
`python3 -B make_zip.py` writes the same zip, byte for byte, from the source.

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

## What is in the folder

| File | What it is |
|---|---|
| `READ ME FIRST.txt` | One page, plain words. |
| `Set up on Windows.cmd`, `Set up on Mac.command` | Start the set-up by double-click. |
| `Remove on Windows.cmd`, `Remove on Mac.command` | Start Remove by double-click. |
| `program/run_setup.py`, `program/run_remove.py` | What both routes run. `--check` looks only and changes nothing. |
| `program/own_asana/asana.py` | The only code that talks to Asana. GET only, `app.asana.com` only. |
| `program/own_asana/server.py` | The local server Claude talks to. Seven read tools, pinned to one workspace. |
| `program/own_asana/credstore.py` | Windows Credential Manager and the macOS Keychain. No file fallback. |
| `program/own_asana/setup.py`, `remove.py`, `config.py`, `entry.py` | The set-up and remove windows, and the small settings file (never the token). |
