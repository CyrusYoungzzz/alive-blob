#!/usr/bin/env bash
# Alive Blob — launch all modules
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# Activate venv
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

# Load .env if exists (API keys etc.)
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Ensure characters dir exists
mkdir -p characters

echo "🚀 Starting Alive Blob..."

# 1. FastAPI Server (port 8080)
echo "[1/3] Starting FastAPI server on :8080..."
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload &
SERVER_PID=$!

# Wait for server to be ready
for i in $(seq 1 10); do
  if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "  ✅ Server ready"
    break
  fi
  sleep 1
done

# 2. Blob Engine (port 8000)
echo "[2/3] Starting Blob Engine on :8000..."
PYTHONPATH="$ROOT_DIR:$ROOT_DIR/blob-engine" python -c "
import asyncio
from blob_engine.engine import BlobEngine
engine = BlobEngine(characters_dir='$ROOT_DIR/characters')
asyncio.run(engine.start())
" &
ENGINE_PID=$!
sleep 1
echo "  ✅ Engine ready"

# 3. Eye App (kiosk mode on Pi only)
CHROMIUM_BIN=$(command -v chromium-browser 2>/dev/null || command -v chromium 2>/dev/null || true)
if [ -n "$CHROMIUM_BIN" ]; then
  echo "[3/3] Starting Eye App in kiosk mode..."
  DISPLAY=:0 "$CHROMIUM_BIN" --kiosk --disable-infobars --noerrdialogs \
    --password-store=basic \
    "http://localhost:8080/eye-app/" &
  EYE_PID=$!
else
  echo "[3/3] Chromium not found — open Eye App manually:"
  echo "  → http://localhost:8080/eye-app/"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Alive Blob is running!"
echo "  📱 手机控制面板: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):8080"
echo "  👁  Eye App:     http://localhost:8080/eye-app/"
echo "  ⚙  API:         http://localhost:8080/api/status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop all services"

# Cleanup on exit
trap "echo '🛑 Shutting down...'; kill $SERVER_PID $ENGINE_PID ${EYE_PID:-} 2>/dev/null; exit 0" INT TERM
wait
