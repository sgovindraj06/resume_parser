# Résumé Autofill demo — NuExtract-1.5-tiny on GitHub Codespaces (free, no card)

Hosts the **tiny** NuExtract model on a free GitHub Codespace (4-core CPU, ~2× HF Spaces),
with a **stable public URL** and **no credit card / no tunnel**. The 2B model stays on your
laptop. Per-résumé time on Codespaces CPU: **~45-90 s** (stable, not GPU-fast).

## One-time: put this in a GitHub repo
Codespaces runs from a GitHub repo. Easiest:
1. Create a new repo on GitHub (e.g. `resume-demo`), **Public or Private both work**.
2. Copy the contents of this `codespaces/` folder into the repo root (so `app.py`,
   `setup.sh`, `start.sh`, `requirements.txt`, and `.devcontainer/` are at the top level).
3. Commit + push.

## Run it
1. On the repo page: **Code ▸ Codespaces ▸ … ▸ New with options** → pick the **4-core**
   machine (free tier = 120 core-hours/month → ~30 h on 4-core; plenty for a demo).
2. The Codespace builds and auto-runs `setup.sh` (installs deps + downloads llama.cpp and
   the ~0.5 GB model). Wait for `[setup] done.` in the terminal.
3. In the Codespace terminal:
   ```bash
   bash start.sh
   ```
   Wait for `model ready.` then `Uvicorn running on http://0.0.0.0:8000`.
4. Open the **Ports** tab → port **8000** → right-click → **Port Visibility ▸ Public**.
   Copy its URL: `https://<your-codespace>-8000.app.github.dev`.
5. Open that URL → drop a résumé PDF → **Parse**. Share the link with your head.

## Notes
- **First parse ~45-90 s** (CPU). That's expected — it's a real generative model running
  free on-device, no cloud AI bill.
- The Codespace **sleeps after ~30 min idle**; reopen it and re-run `bash start.sh`.
- **Stop it when done** (Codespaces list → ⋯ → Stop codespace) to conserve free hours.
- Privacy: this is cloud, so it's **demo-only**; production keeps PII local.
- To go GPU-fast later (~1-4 s), the Kaggle T4 + cloudflared variant is in `../kaggle/`.
