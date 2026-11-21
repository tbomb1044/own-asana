#!/bin/sh
# own-asana on a Mac. Double-click to run. It opens in Terminal.
cd "$(dirname "$0")" || exit 1
if ! python3 -I program/check_python.py >/dev/null 2>&1; then
  echo ""
  echo "own-asana needs Python 3.8 or later, and this Mac does not have it yet."
  echo "If a box just appeared offering to install developer tools, click Install,"
  echo "wait for it to finish, then double-click this file again."
  echo "Nothing was changed."
  echo ""
  printf "Press Enter to close. "
  read _
  exit 1
fi
python3 -I -B "program/run_remove.py"
echo ""
printf "Press Enter to close. "
read _
