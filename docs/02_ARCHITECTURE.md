# 02 · Architecture — how it works internally

> This is the "how it actually works" doc. We go component by component, then trace a
> request end-to-end for both sides.

## Bird's-eye view
There are **two long-running programs** inside the Codespace:

```
        ┌─────────────────────────────────────────────────────────────┐
        │  GitHub Codespace (one free Linux computer in the cloud)      │
        │                                                               │
        │   ┌───────────────────┐        HTTP        ┌───────────────┐ │
   you ─┼──▶│  Web app (FastAPI) │ ─────────────────▶ │  llama-server │ │
 (browser)  │  app.py  :8000     │  "extract this"    │  :8080        │ │
        │   │                    │ ◀───────────────── │  (the AI model│ │
        │   │  + vendor.py       │     JSON back      │   NuExtract)  │ │
        │   └───────────────────┘                     └───────────────┘ │
        │         │                                                     │
        │         │ uses: PyMuPDF (read/render PDF), Pillow (draw/blur),│
        │         │       fastembed (meaning-similarity for the JD)     │
        └─────────────────────────────────────────────────────────────┘
```

1. **`llama-server`** (from llama.cpp) loads the AI model once and waits. It speaks HTTP:
   you send it text + a template, it sends back filled JSON. It listens on **port 8080**
   (internal only).
2. **The web app** (`app.py`, FastAPI) is what your browser talks to, on **port 8000**
   (made public by Codespaces). It serves the web pages and orchestrates everything.

`start.sh` launches both. The web app calls the model server over HTTP when it needs the AI.

---

## The components (what each one is and why it's there)

### 1. The extractor model — **NuExtract-1.5-tiny** (0.5B parameters)
- A small **generative language model** *fine-tuned for one job*: given a document and a
  JSON template, fill the template. It's not a chatbot — it only does extraction.
- **Why this model:** it's tiny (runs on CPU), open-source/free, and purpose-built for
  turning text into structured JSON. (Full "why" + the alternatives we rejected are in the
  concepts doc.)
- We store it as a **GGUF** file (a compressed format for running models efficiently on
  CPU). See concepts doc for GGUF/quantization.

### 2. The runtime — **llama.cpp `llama-server`**
- The program that actually runs the GGUF model on the CPU and exposes it as an HTTP API.
- We use the **official prebuilt Linux binary** (downloaded in `setup.sh`) rather than a
  Python wrapper, because the prebuilt Python wheel was compiled for newer CPUs and crashed
  on some machines. The standalone binary auto-detects the CPU and just works.

### 3. The embedder — **bge-small (via fastembed/ONNX)**
- A second, even smaller AI that converts a piece of text into a **vector** (a list of
  numbers) capturing its *meaning*. Two texts with similar meaning get similar vectors.
- **Why we need it:** to match a résumé skill to the JD by **meaning** (so "cloud" in the
  JD lights up "AWS" on the résumé) — without any hardcoded synonym table.
- It runs via **ONNX runtime**, which is lightweight (no heavy PyTorch needed).

### 4. PDF tools — **PyMuPDF (fitz)** and **Pillow (PIL)**
- **PyMuPDF** opens the PDF and gives us two things: the **text**, and **the exact pixel
  box of every word** (PDFs store text *with positions*). It also renders the page to an
  image. This is the secret to drawing boxes — we don't need a vision model to "find"
  skills; the PDF already tells us where every word is.
- **Pillow** edits that image: blurs the contact regions and draws the skill boxes.

### 5. The web server — **FastAPI + Uvicorn**
- FastAPI defines the URLs (`/`, `/parse-resume`, `/vendor`, `/vendor-preview`). Uvicorn is
  the program that actually serves it. It returns HTML pages and JSON.

### 6. The host — **GitHub Codespaces**
- A free, on-demand Linux computer tied to the repo. The `.devcontainer/` folder tells it
  how to build (which base image, what to install). It gives a public URL so anyone can
  open the demo in a browser.

---

## Data flow #1 — Trainer side (résumé → JSON)
What happens when a trainer uploads a résumé at `/` and clicks **Parse**:

```
1. Browser sends the PDF (+ mode: "essentials" or "full") to  POST /parse-resume
2. app.py reads the PDF text with PyMuPDF.
3. app.py builds a PROMPT = a JSON template + the résumé text, and sends it to llama-server.
   - It asks llama-server to obey a JSON SCHEMA (so the output is guaranteed valid JSON,
     and arrays are capped so the tiny model can't loop forever).
4. NuExtract generates the filled JSON.
5. app.py cleans it (salvage truncated JSON, drop duplicate list items) and returns it.
6. Browser shows the fields + the raw JSON. Contact is shown BLURRED with a "Reveal"
   button (the masking idea).
```
Two **modes**: *essentials* (just the form-relevant fields, faster) and *full* (everything
— summary, responsibilities, projects, awards…).

## Data flow #2 — Vendor side (JD + résumé → masked, highlighted image)
What happens at `/vendor` when a recruiter pastes a JD + uploads a résumé:

```
1. Browser sends the PDF + JD to  POST /vendor-preview
2. app.py extracts the résumé's REAL skills with NuExtract (so we box only true skills,
   never random words). -> a clean list of skill terms.
3. vendor.py:
   a. Renders the page to an image (PyMuPDF) — original copy kept.
   b. BLURS contact: finds email/phone/LinkedIn text positions, Pillow-blurs those boxes.
   c. SELECTS which skills to box:
        - embed the extracted skills AND the JD's concepts (bge-small)
        - keep skills whose meaning is close to the JD (cosine similarity >= a threshold)
          (if no JD given, keep all skills)
   d. For each kept skill, find EVERY occurrence on the page (PyMuPDF search) and draw a
      thin box (Pillow).
4. Returns two images (original + masked) as base64; the browser shows them side-by-side.
```
**Key insight:** the boxes are accurate because we box *extracted skills* (the model
decided they're skills), not "words that look similar to the JD." That's the difference
between clean highlighting and random boxes.

---

## Why these choices (the engineering reasoning)
- **Generative model, not a "find the labelled field" extractor:** a résumé says "CGPA:
  8.5" but also "graduated with 8.5" — a generative model *understands* and pulls the
  value; a rigid extractor only copies exact spans. (We tried the rigid kind first; it
  missed values, projects, and links.)
- **JSON-schema-constrained output:** small models can ramble or loop. Forcing the output
  to match a schema (with array size caps) guarantees valid, bounded JSON every time.
- **Embeddings for matching, not keyword lists:** meaning-based matching generalizes to any
  wording; a keyword table would need endless maintenance and still miss synonyms.
- **PDF text layer for boxes, not a vision model:** the PDF already knows where each word
  is — so highlighting is exact and cheap, no image-recognition model required.

## How this scales to production
| Demo (here) | Production |
|---|---|
| 0.5B model, free CPU, ~40-90 s | 4-8B model on a small GPU, ~2-5 s |
| Extract on every view | Extract **once** at signup, store JSON in a database |
| One résumé at a time | A searchable database; rank many résumés against a JD |
| "Reveal" is client-side blur | Real login + server-side gate: contact only sent after payment |
| Runs in the cloud (demo-only) | Runs on the company's own servers → PII stays private |

The boxes, the masking, the extraction, the embedding-match — **all identical**. Only the
*scale* of each part changes.
