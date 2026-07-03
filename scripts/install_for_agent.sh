#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3, then run this script again."
  exit 1
fi

echo "Project root: $ROOT_DIR"
echo "Using Python: $($PYTHON_BIN --version)"

if [ -d ".git" ] && [ -f ".githooks/pre-commit" ]; then
  git config core.hooksPath .githooks
  echo "Enabled local pre-commit hook: blocks committing .env or staged API keys."
fi

if [ ! -d ".venv" ]; then
  echo "Creating local virtual environment: .venv"
  "$PYTHON_BIN" -m venv .venv
else
  echo "Local virtual environment already exists: .venv"
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"

echo "Preparing Python environment..."
python -m pip install --upgrade pip >/dev/null
if [ -s "requirements.txt" ]; then
  python -m pip install -r requirements.txt
fi

mkdir -p data/runs

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  ENV_CREATED="yes"
else
  ENV_CREATED="no"
fi

echo "Running local tests..."
python -m unittest discover -s tests -v

echo
echo "Setup complete."
echo
if [ "$ENV_CREATED" = "yes" ]; then
  echo "A new .env file was created here:"
else
  echo "Your existing .env file is here:"
fi
echo "$ROOT_DIR/.env"
echo
echo "Open that file and replace the placeholder values:"
echo
echo "XAI_API_KEY=your_xai_api_key_here"
echo "SOCIALDATA_API_KEY=your_socialdata_api_key_here"
echo "NANSEN_API_KEY=your_nansen_api_key_here"
echo "SURF_API_KEY=your_surf_api_key_here"
echo
echo "Direct X/Twitter API search is disabled."
echo "Use XAI_API_KEY for Grok-only search through xAI x_search."
echo "Use SOCIALDATA_API_KEY for SocialData X/Twitter search."
echo "Use NANSEN_API_KEY for Nansen on-chain research."
echo "Use SURF_API_KEY for direct Surf Data API and Surf Chat API Research 2.0."
echo
echo "After adding keys, test with:"
echo "source .venv/bin/activate"
echo "python -m twitter_research --help"
echo "python -m twitter_research ask \"why is PUMP token down this week?\" --provider surf"
echo "python -m twitter_research surf-ask \"What happened to BTC today?\" --effort medium"
