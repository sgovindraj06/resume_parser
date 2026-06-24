#!/usr/bin/env bash
# Runs once when the Codespace is created (postCreateCommand).
set -e

echo "[setup] system deps..."
sudo apt-get update -qq && sudo apt-get install -y -qq unzip libgomp1

echo "[setup] python deps..."
pip install -r requirements.txt

echo "[setup] downloading llama.cpp linux cpu build..."
curl -sL -o /tmp/llama.zip https://github.com/ggml-org/llama.cpp/releases/download/b9768/llama-b9768-bin-ubuntu-x64.zip
rm -rf llamacpp && mkdir -p llamacpp && unzip -oq /tmp/llama.zip -d llamacpp && rm /tmp/llama.zip
find llamacpp -name 'llama-server' -type f -exec chmod +x {} \;

echo "[setup] pre-downloading NuExtract-1.5-tiny GGUF (~0.5 GB)..."
python -c "from huggingface_hub import hf_hub_download; hf_hub_download('QuantFactory/NuExtract-1.5-tiny-GGUF','NuExtract-1.5-tiny.Q4_K_M.gguf')"

echo "[setup] done.  Next:  bash start.sh"
