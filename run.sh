#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  Not So Quietly Disruptive — Article Studio
#  One-command launcher:  ./run.sh
# ─────────────────────────────────────────────────────────
set -e

cd "$(dirname "$0")"

PORT="${PORT:-8000}"

# ── 1. Check Python ──────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌  Python 3 is required but not installed."
    echo "   Install it from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "🐍  Found Python $PYTHON_VERSION"

# ── 2. Create virtual environment if needed ──────────────
if [ ! -d ".venv" ]; then
    echo "📦  Creating virtual environment..."
    python3 -m venv .venv
fi

# ── 3. Activate venv ─────────────────────────────────────
source .venv/bin/activate

# ── 4. Install / upgrade dependencies ────────────────────
echo "📦  Installing dependencies (this may take a moment on first run)..."
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

# ── 5. Check for .env file ───────────────────────────────
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️   No .env file found!"
    echo "   Create one with your API keys:"
    echo ""
    echo "   PREDICTIONGUARD_API_KEY=your_key_here"
    echo "   PREDICTIONGUARD_URL=https://globalpath.predictionguard.com"
    echo "   ASSEMBLYAI_API_KEY=your_key_here        (optional)"
    echo ""
    echo "   Then run ./run.sh again."
    exit 1
fi

# ── 6. Create required directories ───────────────────────
mkdir -p articles transcripts

# ── 7. Launch the server ─────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║                                                      ║"
echo "║   ✍️  Article Studio is starting...                   ║"
echo "║                                                      ║"
echo "║   Open your browser to:                              ║"
echo "║   👉  http://localhost:${PORT}                          ║"
echo "║                                                      ║"
echo "║   Press Ctrl+C to stop the server.                   ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Try to open browser automatically (non-blocking, ignore errors)
if command -v open &>/dev/null; then
    (sleep 2 && open "http://localhost:${PORT}") &
elif command -v xdg-open &>/dev/null; then
    (sleep 2 && xdg-open "http://localhost:${PORT}") &
fi

python3 -m uvicorn backend.app:app --host 0.0.0.0 --port "$PORT" --reload
