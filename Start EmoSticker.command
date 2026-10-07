#!/bin/bash
# Double-click on a Mac. Finds python3 (Homebrew's first, then the system's) and runs EmoSticker.
cd "$(dirname "$0")"
for py in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$py" >/dev/null 2>&1; then exec "$py" emosticker.py "$@"; fi
done
echo "Python 3 was not found. Install it from https://www.python.org/downloads/ or with: brew install python"
read -r -p "Press Enter to close"
