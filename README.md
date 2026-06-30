# Résumé Intelligence Demo — Trainer & Vendor sides

A small, **fully local, no-paid-API** demo of a résumé-intelligence pipeline for a
two-sided trainer marketplace:

- **Trainer side** (`/`) — a trainer uploads their résumé PDF → a local AI model reads it
  and returns clean **structured JSON** (name, contact, education, experience, skills,
  projects, certifications). Contact details can be **masked** and revealed on "unlock".
- **Vendor side** (`/vendor`) — a recruiter pastes a **Job Description** and uploads a
  résumé → sees the résumé **rendered with contact blurred** and the **relevant skills
  outlined** (matched to the JD by *meaning*, not keyword lookup).

Everything runs on a **single free GitHub Codespace** (CPU only). No OpenAI/Gemini, no
cloud AI bill — the model runs on-device.

---

## 🚀 60-second quick start (on GitHub Codespaces)
1. Open this repo on GitHub → **`< > Code` ▸ Codespaces ▸ Create codespace** (pick the
   **4-core** machine).
2. Wait for it to build — it auto-runs `setup.sh` (installs everything + downloads the
   model). You'll see `[setup] done.`
3. In the terminal: `bash start.sh` → wait for `model ready.`
4. **Ports** tab → port **8000** → right-click → **Port Visibility ▸ Public** → open the URL.
5. Trainer view = that URL. Vendor view = add `/vendor` to the URL.

Full, click-by-click detail is in **[docs/03_SETUP_AND_RUN.md](docs/03_SETUP_AND_RUN.md)**.

---

## 📚 Documentation (read in this order)
| Doc | What it covers |
|---|---|
| **[docs/01_OVERVIEW.md](docs/01_OVERVIEW.md)** | What this project is, the problem it solves, the big picture |
| **[docs/02_ARCHITECTURE.md](docs/02_ARCHITECTURE.md)** | How it works *internally* — components, data flow, the models, why each choice |
| **[docs/03_SETUP_AND_RUN.md](docs/03_SETUP_AND_RUN.md)** | Clone & run, step by step (Codespaces + local) |
| **[docs/04_CONCEPTS_EXPLAINED.md](docs/04_CONCEPTS_EXPLAINED.md)** | Every concept explained from zero (LLM, embeddings, GGUF, FastAPI, …) |
| **[docs/05_CODE_WALKTHROUGH.md](docs/05_CODE_WALKTHROUGH.md)** | File-by-file tour of the code |

---

## 🧱 What's in this repo
```
app.py                 # the web server (FastAPI): both Trainer and Vendor views
vendor.py              # vendor-side: render PDF, blur contact, box JD-relevant skills
setup.sh               # one-time setup (runs automatically on Codespace create)
start.sh               # launches the model server + the web app
requirements.txt       # Python dependencies
.devcontainer/         # tells Codespaces how to build the environment
docs/                  # the documentation you're reading
```

> **Note:** this is a **demo** — it uses a tiny 0.5B model on a free CPU, so it's accurate
> enough to learn from but slower and lighter than production. The architecture doc explains
> how the *same design* scales up (bigger model, GPU, a real database of résumés).
