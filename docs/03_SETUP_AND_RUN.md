# 03 · Setup & Run — step by step

> For a beginner. Two ways to run it: **(A) GitHub Codespaces** (easiest, in the browser,
> nothing to install) and **(B) on your own computer**. Start with A.

---

## A) Run it on GitHub Codespaces (recommended)

### Step 0 — You need a free GitHub account
Sign up at <https://github.com> if you don't have one. No credit card needed for Codespaces
(free tier = 120 core-hours/month).

### Step 1 — Get the code into *your* GitHub
You have two options:
- **Fork it** (if it's someone else's repo): open the repo page → click **Fork** (top
  right) → this makes a copy under your account.
- **Or it's already your repo** (e.g. `github.com/<you>/resume_parser`) → skip forking.

### Step 2 — Create a Codespace
1. On your repo page, click the green **`< > Code`** button.
2. Choose the **Codespaces** tab → click **…** (three dots) → **New with options…**
3. Set **Machine type = 4-core** (the 2-core one works too, just slower). → **Create codespace**.
4. A VS Code editor opens **in your browser**. Wait while it builds (a few minutes). During
   the build it automatically runs `setup.sh`, which:
   - installs the Python libraries,
   - downloads the **llama.cpp** runtime,
   - downloads the **AI model** (~0.5 GB),
   - downloads the **embedder** (used by the vendor view).
   You'll know it's done when the terminal prints **`[setup] done.`**

> If you don't see a terminal: top menu **☰ ▸ Terminal ▸ New Terminal**.

### Step 3 — Start the app
In the Codespace terminal, run:
```bash
bash start.sh
```
Watch for:
- `model ready.`  ← the AI model finished loading
- `Uvicorn running on http://0.0.0.0:8000`  ← the web app is up

**Leave this terminal running** — closing it / pressing `Ctrl+C` stops the server.

### Step 4 — Make the website public & open it
1. Click the **Ports** tab (bottom panel, next to "Terminal").
2. Find port **8000** → **right-click** the row → **Port Visibility ▸ Public**.
   *(This lets anyone with the link open it — needed if you want to share it.)*
3. Hover the **Forwarded Address** for 8000 → click the 🌐 / copy icon. The URL looks like:
   `https://<your-codespace-name>-8000.app.github.dev`

### Step 5 — Use it
- **Trainer view** = that URL. Upload a résumé PDF → choose **Essentials** or **Full** →
  **Parse**. First parse takes ~40-90 s (CPU). You'll see the fields + raw JSON; the contact
  is blurred with a **🔓 Reveal contact** button.
- **Vendor view** = the same URL with **`/vendor`** added. Paste a Job Description → upload a
  résumé → **Match & mask** → side-by-side: original vs. masked résumé with the JD-relevant
  skills boxed.

### Step 6 — Stop / restart (save your free hours!)
- **Stop when done:** <https://github.com/codespaces> → find your codespace → **⋯ ▸ Stop**.
- **Restart later:** open the codespace again → run **`bash start.sh`** (no need to re-run
  `setup.sh`). It sleeps after ~30 min idle, so do this ~5 min before showing it to anyone.

---

## B) Run it on your own computer (advanced / optional)
You need: **git**, **Python 3.11**, and the standalone **llama.cpp** binary for your OS.
```bash
git clone https://github.com/<you>/resume_parser.git
cd resume_parser
pip install -r requirements.txt
bash setup.sh        # downloads llama.cpp + the model + embedder
bash start.sh        # starts the model server + the web app
# open http://localhost:8000
```
> On Windows, `setup.sh`/`start.sh` are bash scripts — run them in **Git Bash** or WSL, and
> use the Windows llama.cpp build instead of the Linux one if you adapt it.

---

## Cloning & contributing (for your brother to actually work on it)
```bash
# 1. Clone YOUR fork
git clone https://github.com/<your-username>/resume_parser.git
cd resume_parser

# 2. Make a branch for your change (never work directly on main)
git checkout -b my-experiment

# 3. Edit files (e.g. tweak FLOOR in vendor.py), then:
git add -A
git commit -m "describe what you changed"
git push -u origin my-experiment

# 4. On GitHub, open a Pull Request to merge your branch.
```
**Tip:** you can edit + run in the Codespace directly (changes live there). To save them to
GitHub, `git add/commit/push` from the Codespace terminal.

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `llama-server not found` | `setup.sh` didn't finish — run `bash setup.sh` again and watch for errors. |
| Page shows "You don't have access" / sign-in | Port 8000 is still **Private** → set it **Public** (Step 4). |
| Parse hangs forever | The model server isn't up. Make sure `start.sh` printed `model ready.`. Check `/tmp/llama.log`. |
| "Could not parse the model output" | The tiny model occasionally stumbles on a résumé — just try again. |
| Vendor view errors about `fastembed` | Re-run `bash setup.sh` (it installs/pre-downloads the embedder). |
| Everything is slow | Expected on free CPU. It's a real AI model running on-device — see the architecture doc for the production speed-up path. |

## The two ports, explained
- **8080** — the AI model server (`llama-server`). **Keep it Private.** The web app talks to
  it internally; nobody else should.
- **8000** — the web app you actually use. **Make it Public** to share the link.
