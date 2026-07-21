#!/bin/bash
# Install OpenAgent on macOS/Linux.
# Usage: curl -fsSL https://raw.githubusercontent.com/haseeb-heaven/open-agent/main/install.sh | bash
set -e

echo "Installing OpenAgent..."

if command -v npm &> /dev/null; then
  npm install -g @haseeb_heaven/open-agent
  echo "Installed via npm. Run: openagent"
elif command -v brew &> /dev/null; then
  brew tap haseeb-heaven/openagent
  brew install openagent
  echo "Installed via Homebrew. Run: openagent"
else
  echo "Please install Node.js 22+ first: https://nodejs.org" >&2
  exit 1
fi
