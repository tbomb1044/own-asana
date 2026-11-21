"""Where the token lives: the operating system's own credential store.

Windows: Credential Manager, a generic credential, kept on this computer only.
macOS:   the login keychain, a generic password.

There is no file fallback. On any other system this refuses.

What this protects against: the token sitting in a file that gets synced,
backed up, zipped, emailed or read by accident. What it does not protect
against: another program running as the same person can ask the operating
system for it. That is how both stores work.

Standard library only. Python 3.8 or later.
"""

import re
import subprocess
import sys

SERVICE = "own-asana"
ACCOUNT = "personal-access-token"
WINDOWS_TARGET = "own-asana/personal-access-token"
LABEL = "own-asana (Asana token for Claude, read only)"

# Asana tokens are digits, slashes, a colon and hex. Anything outside this small
# set is refused before it gets near a command or the store.
TOKEN_RE = re.compile(r"^[A-Za-z0-9/:._\-]{16,512}$")

_SECURITY = "/usr/bin/security"


class CredStoreError(Exception):
    pass


def looks_like_token(token):
    return bool(token) and bool(TOKEN_RE.match(token))


def store_name():
    if sys.platform == "win32":
        return "Windows Credential Manager"
    if sys.platform == "darwin":
        return "the macOS Keychain"
    return None


def save(token, keychain=None, target=None):
    if not looks_like_token(token):
        raise CredStoreError("That does not look like an Asana token.")
    if sys.platform == "win32":
        return _win_save(token, target or WINDOWS_TARGET)
    if sys.platform == "darwin":
        return _mac_save(token, keychain)
    raise CredStoreError("This tool stores its token on Windows and macOS only.")


def load(keychain=None, target=None):
    """The stored token, or None if there is none."""
    if sys.platform == "win32":
        return _win_load(target or WINDOWS_TARGET)
    if sys.platform == "darwin":
        return _mac_load(keychain)
    raise CredStoreError("This tool stores its token on Windows and macOS only.")


def delete(keychain=None, target=None):
    """Remove the stored token. True if one was removed, False if there was none."""
    if sys.platform == "win32":
        return _win_delete(target or WINDOWS_TARGET)
    if sys.platform == "darwin":
        return _mac_delete(keychain)
    raise CredStoreError("This tool stores its token on Windows and macOS only.")


# ---- macOS ------------------------------------------------------------------

def _mac_tail(keychain):
    return [keychain] if keychain else []


def _mac_save(token, keychain):
    # The token goes to `security` on its standard input, never as a command
    # argument, so it does not show in the list of running programs.
    line = 'add-generic-password -U -a "%s" -s "%s" -l "%s" -w "%s"' % (
        ACCOUNT, SERVICE, LABEL, token)
    if keychain:
        line += ' "%s"' % keychain
    try:
        done = subprocess.run([_SECURITY, "-i"], input=(line + "\n").encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise CredStoreError("Could not reach the macOS Keychain.")
    if done.returncode != 0 or _mac_load(keychain) != token:
        raise CredStoreError("The macOS Keychain did not save the token.")
    return True


def _mac_load(keychain):
    try:
        done = subprocess.run(
            [_SECURITY, "find-generic-password", "-a", ACCOUNT, "-s", SERVICE, "-w"]
            + _mac_tail(keychain),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise CredStoreError("Could not reach the macOS Keychain.")
    if done.returncode == 44:
        return None
    if done.returncode != 0:
        raise CredStoreError("The macOS Keychain did not answer.")
    token = done.stdout.decode("utf-8", "replace").strip()
    return token or None


def _mac_delete(keychain):
    try:
        done = subprocess.run(
            [_SECURITY, "delete-generic-password", "-a", ACCOUNT, "-s", SERVICE]
            + _mac_tail(keychain),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise CredStoreError("Could not reach the macOS Keychain.")
    if done.returncode == 44:
        return False
    if done.returncode != 0:
        raise CredStoreError("The macOS Keychain did not remove the token.")
    return True


# ---- Windows ----------------------------------------------------------------

_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2   # this computer only; does not roam
_ERROR_NOT_FOUND = 1168


def _win_api():
    import ctypes
    from ctypes import wintypes

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    pcred = ctypes.POINTER(CREDENTIAL)
    advapi32.CredWriteW.argtypes = [pcred, wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.POINTER(pcred)]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi32.CredDeleteW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    advapi32.CredFree.restype = None
    return ctypes, advapi32, CREDENTIAL, pcred


def _win_save(token, target):
    ctypes, advapi32, CREDENTIAL, _ = _win_api()
    blob = token.encode("utf-16-le")
    buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = CREDENTIAL()
    cred.Type = _CRED_TYPE_GENERIC
    cred.TargetName = target
    cred.Comment = LABEL
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    cred.Persist = _CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = ACCOUNT
    if not advapi32.CredWriteW(ctypes.byref(cred), 0):
        raise CredStoreError("Windows Credential Manager did not save the token (error %d)."
                             % ctypes.get_last_error())
    if _win_load(target) != token:
        raise CredStoreError("Windows Credential Manager did not save the token.")
    return True


def _win_load(target):
    ctypes, advapi32, _, pcred = _win_api()
    found = pcred()
    if not advapi32.CredReadW(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(found)):
        code = ctypes.get_last_error()
        if code == _ERROR_NOT_FOUND:
            return None
        raise CredStoreError("Windows Credential Manager did not answer (error %d)." % code)
    try:
        size = found.contents.CredentialBlobSize
        raw = ctypes.string_at(found.contents.CredentialBlob, size) if size else b""
    finally:
        advapi32.CredFree(found)
    token = raw.decode("utf-16-le", "replace").strip()
    return token or None


def _win_delete(target):
    ctypes, advapi32, _, _ = _win_api()
    if not advapi32.CredDeleteW(target, _CRED_TYPE_GENERIC, 0):
        code = ctypes.get_last_error()
        if code == _ERROR_NOT_FOUND:
            return False
        raise CredStoreError("Windows Credential Manager did not remove the token (error %d)."
                             % code)
    return True
