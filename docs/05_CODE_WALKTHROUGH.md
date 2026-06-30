# 05 · Code walkthrough — file by file

> A tour of every file. Open each file alongside this doc. Concepts used here are explained
> in **[04_CONCEPTS_EXPLAINED.md](04_CONCEPTS_EXPLAINED.md)**.

## How the files fit together
```
.devcontainer/devcontainer.json  → tells Codespaces how to build the machine
        │  (on create) runs ↓
setup.sh                         → installs deps, downloads llama.cpp + model + embedder
        │  (you run) ↓
start.sh                         → starts llama-server (:8080) and the web app (:8000)
        │                                   │
        ▼                                   ▼
app.py (FastAPI web app)  ──HTTP──▶  llama-server (the AI model)
        │
        └── uses vendor.py for the /vendor page
```

---

## `requirements.txt` — Python libraries
```
fastapi, uvicorn   → the web server
pymupdf            → read & render PDFs (the "fitz" module), word positions
huggingface_hub    → download the model + embedder files
python-multipart   → lets FastAPI accept file uploads
pillow             → image editing (blur + draw boxes)
numpy              → math on the embedding vectors
fastembed          → the meaning-similarity embedder (bge-small, via ONNX)
```

## `.devcontainer/devcontainer.json` — the Codespace recipe
- `image` — the base Linux+Python image to start from.
- `postCreateCommand: bash setup.sh` — runs setup automatically when the Codespace is built.
- `forwardPorts: [8000]` + `portsAttributes` — exposes the web app and labels it.

## `setup.sh` — one-time setup (runs on Codespace creation)
Step by step:
1. `apt-get install libgomp1` — a system library llama.cpp needs.
2. `pip install -r requirements.txt` — the Python libs.
3. Download the **llama.cpp Linux build** (a `.tar.gz`), unpack it, find the `llama-server`
   binary, make it executable.
4. Download the **NuExtract-1.5-tiny GGUF** model (~0.5 GB) from Hugging Face (cached).
5. Pre-download the **bge-small** embedder so the first vendor request isn't slow.
Prints `[setup] done.` when finished.

## `start.sh` — launch everything
1. Locate the `llama-server` binary and set `LD_LIBRARY_PATH` so it finds its libraries.
2. Resolve the model GGUF path (already downloaded).
3. Start **`llama-server`** in the background on **port 8080** with the model
   (`-c 8192` context, CPU threads, etc.). Logs go to `/tmp/llama.log`.
4. Start **`python app.py`** — the web app on **port 8000**. It waits until the model server
   is healthy (`model ready.`) then serves.

## `app.py` — the web application (the heart)
Read it top-to-bottom; here's the map:

- **`LLAMA = "http://127.0.0.1:8080"`** — where the model server lives.
- **Templates & schemas** — `TEMPLATE_ESSENTIALS` / `TEMPLATE_FULL` (the JSON shapes we ask
  NuExtract to fill) and `SCHEMA_ESSENTIALS` / `SCHEMA_FULL` (the JSON-schema that *forces*
  valid output; `maxItems` caps arrays so the small model can't loop). `MODES` maps the two.
- **`extract(text, mode)`** — the core extraction function:
  1. builds the prompt (legacy NuExtract format: `<|input|> … <|output|>`),
  2. POSTs it to `llama-server` with the chosen `json_schema`,
  3. parses the JSON; `_loads_salvage()` recovers valid JSON if the output got cut off;
     `_dedup()` removes duplicate list items.
- **`HTML` (string)** — the Trainer-side web page: the upload box, the Essentials/Full
  toggle, and the JavaScript that calls `/parse-resume`, shows the fields, blurs the contact
  with a **Reveal** button.
- **Endpoints:**
  - `GET /` → returns the Trainer HTML page.
  - `POST /parse-resume` → reads the PDF text, runs `extract()`, returns the JSON + timing.
  - `GET /vendor` → returns the Vendor HTML page (`VENDOR_HTML`).
  - `POST /vendor-preview` → **extracts the résumé's real skills** (so we box only true
    skills), then calls `vendor.make_preview(pdf, skills, jd)` and returns the two images.
  - `GET /health` → simple "is it alive" check.
- **`if __name__ == "__main__":`** — waits for the model server, then runs Uvicorn on 8000.

## `vendor.py` — the vendor-side preview (render, blur, box)
- **`_embedder()` / `_vecs()`** — load the bge-small embedder (once) and turn texts into
  normalized vectors.
- **`_jd_terms(jd)`** — split the Job Description into short skill-like concept phrases.
- **`_select(skill_terms, jd)`** — clean the extracted skills; if a JD is given, keep only
  those whose **meaning** is close to the JD (cosine ≥ `FLOOR`); otherwise keep all.
- **`make_preview(pdf_bytes, skill_terms, jd)`** — the main function:
  1. render each page to an image (PyMuPDF), keep an untouched **original** copy,
  2. **blur** the contact regions (find email/phone/LinkedIn → Pillow Gaussian blur),
  3. for each selected skill, find **every occurrence** on the page (`page.search_for`) and
     **draw a thin box** (Pillow),
  4. return both images as base64 (`original`, `masked`) + a count.

### The key knobs (tune these to change behavior)
| Where | Knob | Effect |
|---|---|---|
| `vendor.py` | `FLOOR` (0.60) | Higher → stricter JD relevance (fewer skills boxed). |
| `vendor.py` | `HIGHLIGHT` | The box color (RGB). |
| `vendor.py` | `ZOOM` | Render resolution of the preview image. |
| `app.py` | `extract(text, "essentials"\|"full")` in `/vendor-preview` | `full` finds more skills (project tech) but is slower. |
| `app.py` | `n_predict`, `FLOOR` in schemas | Output length / strictness for extraction. |

---

## Suggested learning path (do these in order)
1. **Run it** (doc 03) and watch the terminal logs — see `llama-server` boot, then a parse.
2. **Read `start.sh`** — understand the two processes.
3. **Read `app.py` `extract()`** — see how a prompt + schema becomes JSON.
4. **Read `vendor.py` `make_preview()`** — see render → blur → box.
5. **Make a tiny change** — e.g., set `FLOOR = 0.70` in `vendor.py`, restart, see fewer
   boxes. Or change `HIGHLIGHT` to a different color. Commit it on a branch.
6. **Read doc 02 again** — now the architecture will "click".

## Things to try / extend (good beginner exercises)
- Add a **color legend** or a second highlight color for a different skill group.
- Add **OCR** so scanned (image-only) résumés also work (currently needs a text-layer PDF).
- Cache extractions in a small **database** so the vendor view is instant (production idea).
- Add a **/rank** endpoint: given a JD + several résumés, score and sort them.
