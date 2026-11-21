"""Writes own-asana.zip from the own-asana folder, the same way every time.

    python3 -B make_zip.py

The zip holds the files of own-asana/ at its root, in a fixed order, with
fixed dates and no compression, so the same source always gives the same
bytes and the same SHA-256. That is how the zip on the Releases page was
made. The script prints the SHA-256 at the end.

Standard library only. Python 3.8 or later.
"""
import hashlib
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.join(HERE, "own-asana")
OUT = os.path.join(HERE, "own-asana.zip")
FIXED = (2026, 11, 20, 0, 0, 0)
LEFT_OUT = (".DS_Store", "settings.json")


def package_files():
    found = []
    for root, dirs, names in os.walk(PACKAGE):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if name in LEFT_OUT or name.endswith(".pyc"):
                continue
            full = os.path.join(root, name)
            found.append(os.path.relpath(full, PACKAGE).replace(os.sep, "/"))
    return sorted(found)


def main():
    with zipfile.ZipFile(OUT, "w") as archive:
        for name in package_files():
            with open(os.path.join(PACKAGE, *name.split("/")), "rb") as handle:
                data = handle.read()
            info = zipfile.ZipInfo(name, FIXED)
            info.create_system = 3
            mode = 0o755 if name.endswith(".command") else 0o644
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, data, zipfile.ZIP_STORED)
            print("  %7d  %s" % (len(data), name))
    with open(OUT, "rb") as handle:
        print("sha256  " + hashlib.sha256(handle.read()).hexdigest())


if __name__ == "__main__":
    main()
