"""Where things are, and the small settings file (which never holds the token).

Layout on the person's computer:

    <their own Claude folder>/        <- the folder they open in Claude
        .mcp.json                     <- written by Set up; tells Claude about own-asana
        own-asana/                    <- this package
            settings.json             <- written by Set up: which workspace, which account
            program/own_asana/...     <- the code

Standard library only. Python 3.8 or later.
"""

import json
import os
import re

SERVER_NAME = "own-asana"
SETTINGS_FILE = "settings.json"
MCP_FILE = ".mcp.json"

# A Claude folder that a firm set up for its staff says so at the top of its
# CLAUDE.md, in a heading that begins "Working at" and then names the firm:
#
#     # Working at <the firm>
#
# own-asana must not be set up inside such a folder: the firm's setup keeps
# other accounts out of it. The check looks for that kind of heading, whatever
# the firm is called, so this package names no firm. It is a guard against a
# mistake, not a lock: Set up also asks the person, and shows the folder.
FIRM_HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]+working[ \t]+at[ \t]+\S", re.IGNORECASE)
FIRM_FOLDER_HEAD = 4000


def package_dir():
    """The own-asana folder (the parent of program/)."""
    here = os.path.dirname(os.path.abspath(__file__))        # .../program/own_asana
    return os.path.dirname(os.path.dirname(here))            # .../own-asana


def claude_folder(pkg_dir=None):
    return os.path.dirname(os.path.abspath(pkg_dir or package_dir()))


def settings_path(pkg_dir=None):
    return os.path.join(pkg_dir or package_dir(), SETTINGS_FILE)


def mcp_path(pkg_dir=None):
    return os.path.join(claude_folder(pkg_dir), MCP_FILE)


def server_script(pkg_dir=None):
    return os.path.join(pkg_dir or package_dir(), "program", "run_server.py")


def load_settings(pkg_dir=None):
    """The settings, or None if Set up has not been run (or the file is damaged)."""
    try:
        with open(settings_path(pkg_dir), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    gid = str(data.get("workspace_gid") or "")
    if not gid.isdigit():
        return None
    return {
        "workspace_gid": gid,
        "workspace_name": str(data.get("workspace_name") or ""),
        "account_name": str(data.get("account_name") or ""),
        "account_email": str(data.get("account_email") or ""),
        "set_up_on": str(data.get("set_up_on") or ""),
    }


def save_settings(settings, pkg_dir=None):
    allowed = ("workspace_gid", "workspace_name", "account_name", "account_email", "set_up_on")
    clean = dict((key, str(settings.get(key) or "")) for key in allowed)
    _write_json(settings_path(pkg_dir), clean)


def delete_settings(pkg_dir=None):
    try:
        os.remove(settings_path(pkg_dir))
        return True
    except OSError:
        return False


def looks_like_firm_folder(folder):
    """True when CLAUDE.md in `folder` has, near its top, a heading "Working at ..."."""
    try:
        with open(os.path.join(folder, "CLAUDE.md"), "r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(FIRM_FOLDER_HEAD)
    except OSError:
        return False
    for line in head.lstrip("\ufeff").splitlines():
        if FIRM_HEADING_RE.match(line):
            return True
    return False


class McpFileError(Exception):
    pass


def _read_mcp(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        raise McpFileError("The file %s exists but could not be read. It was left alone." % path)
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise McpFileError("The file %s is not in the expected shape. It was left alone." % path)
    return data


def add_to_mcp_file(python_exe, pkg_dir=None):
    """Add (or replace) the own-asana entry. Other entries are kept as they are."""
    path = mcp_path(pkg_dir)
    data = _read_mcp(path) or {}
    servers = data.setdefault("mcpServers", {})
    servers[SERVER_NAME] = {
        "command": python_exe,
        # -I: isolated (ignores PYTHON* variables and the user's site folder)
        # -B: writes no cache files into the folder
        "args": ["-I", "-B", server_script(pkg_dir)],
    }
    _write_json(path, data)
    return path


def remove_from_mcp_file(pkg_dir=None):
    """Remove the own-asana entry. Returns 'removed', 'deleted-file' or 'absent'."""
    path = mcp_path(pkg_dir)
    data = _read_mcp(path)
    if data is None or SERVER_NAME not in data.get("mcpServers", {}):
        return "absent"
    del data["mcpServers"][SERVER_NAME]
    if not data["mcpServers"] and list(data.keys()) == ["mcpServers"]:
        os.remove(path)
        return "deleted-file"
    _write_json(path, data)
    return "removed"


def _write_json(path, data):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(temp, path)
