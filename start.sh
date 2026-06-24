#!/usr/bin/env bash
# Launch the llama-server (NuExtract-1.5-tiny) + the web app.
set -e

LS=$(find llamacpp -name 'llama-server' -type f | head -1)
if [ -z "$LS" ]; then echo "llama-server not found — run: bash setup.sh"; exit 1; fi
export LD_LIBRARY_PATH="$(dirname "$LS"):$LD_LIBRARY_PATH"

GGUF=$(python -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('QuantFactory/NuExtract-1.5-tiny-GGUF','NuExtract-1.5-tiny.Q4_K_M.gguf'))")

echo "[start] llama-server (tiny) on :8080 ..."
"$LS" -m "$GGUF" -c 3072 -t 4 --host 127.0.0.1 --port 8080 > /tmp/llama.log 2>&1 &

echo "[start] web app on :8000 (waits for the model, then serves) ..."
python app.py
