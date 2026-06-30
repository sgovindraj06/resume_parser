# 04 · Concepts explained from zero

> Every technical term in this project, explained simply. Skim the ones you know; read the
> ones you don't. Analogies first, precision second.

## AI models

### What is an "AI model"?
A file full of numbers (called **weights**) plus code that uses them. You feed it input
(text), it produces output (text). It learned its behavior from huge amounts of data during
**training**. We don't train anything here — we *use* pre-trained models.

### Parameters (the "0.5B", "2B")
The count of those numbers. **0.5B = 500 million**, 2B = 2 billion. More parameters ≈ smarter
but slower and bigger. We use a **0.5B** model so it runs on a free CPU.

### Two families: **Encoder** vs **Decoder (LLM)**
- **Encoder** (e.g., classic NER models): can only **point at words already on the page**.
  Fast, never makes things up — but it **can't infer**. If the page says "ML", it can only
  output "ML", never "Machine Learning". It also can't read "the number next to the word
  CGPA".
- **Decoder / LLM** (e.g., our NuExtract, ChatGPT): **generates** text. It can read context
  and produce something not copied word-for-word — turn "ML" into "Machine Learning", pull
  the value next to "CGPA". This *generation* ability is exactly what résumé reading needs.
  Downside: a generator *can* occasionally invent a wrong value ("hallucinate"), so we add
  safety checks.

We use a **decoder/LLM** for extraction, and a small **encoder-style embedder** for the
meaning-matching.

### NuExtract
A small LLM **fine-tuned only for extraction**: you give it a document + a JSON template,
it returns the template filled in. Because it's specialized, it's smaller and more reliable
at this one task than a general chatbot.

## Running models

### Tokens
Models don't see letters; they see **tokens** (chunks of text, roughly ¾ of a word). "Machine
learning" might be 2-3 tokens. Models read input tokens and produce output tokens one at a
time. Cost and speed are measured in tokens.

### Prefill vs Decode (why it's slow on CPU)
Generating an answer has two phases:
- **Prefill** = *reading* your input (the résumé + template). All input tokens are processed
  **in parallel** → fast.
- **Decode** = *writing* the output JSON, **one token at a time**, each depending on the last
  → **sequential, slow**. On a CPU this is the bottleneck (a few tokens/second).
That's why a longer output (Full mode) takes much longer than a short one (Essentials).

### GGUF & Quantization
- **GGUF** is a file format that packages a model so the `llama.cpp` runtime can load it
  efficiently, especially on CPUs.
- **Quantization** = storing the weights with fewer bits (e.g., 4-bit instead of 16-bit).
  It makes the file ~4× smaller and faster, with a small accuracy cost. Our model is a
  **Q4** (4-bit) GGUF — ~0.5 GB instead of ~2 GB.

### llama.cpp
An open-source program that runs GGUF models fast on normal CPUs (and GPUs). We run its
**`llama-server`**, which loads the model once and answers HTTP requests — so our web app
can just "ask" it over the network.

## Meaning & matching

### Embeddings (vectors)
An **embedding** turns a piece of text into a list of numbers (a **vector**) that captures
its *meaning*. Think of it as **coordinates in "meaning space"**: texts about similar things
land near each other. "AWS", "Azure", "cloud" cluster together; "cooking" is far away.

### Cosine similarity
A number from ~0 to 1 measuring how close two vectors point. **High = similar meaning.** We
compute it between a JD concept ("cloud") and a résumé skill ("AWS"); if it's above a
threshold, we count them as a match — **no hardcoded synonym list needed.** This is also
called **semantic search**.

### Why "no hardcoding" matters
A hardcoded table like `{"cloud": ["AWS","GCP","Azure"]}` breaks for anything you didn't
list ("OCI"? "cloud-native"?). Embeddings *understand* relatedness from how words are used,
so they generalize to any wording. That's the whole reason we use them.

### JSON-Schema-constrained decoding (grammar)
We can force the model's output to **obey a JSON shape** (these keys, arrays of at most N
items). The runtime only lets the model emit tokens that keep the JSON valid. Result:
**always-parseable JSON**, and the small model **can't loop forever** filling an array.

## Documents & images

### PDF "text layer" and bounding boxes
A normal (non-scanned) PDF stores its text **with the exact position of every word**.
PyMuPDF reads `(word, x0, y0, x1, y1)` for each word. So to "highlight a skill" we don't need
image recognition — we already know where each word sits and just draw a rectangle there.
*(Scanned/image-only PDFs have no text layer; those would need OCR first.)*

### Blurring (PII masking)
**PII** = Personally Identifiable Information (email, phone, LinkedIn). We find those words'
positions, then use **Pillow** to blur just those rectangles of the page image — like the
blurred number on a shared ID card.

## Web & infrastructure

### HTTP, server, ports
Programs talk over **HTTP** (the web's request/response protocol). A **server** waits for
requests and replies. A **port** is a numbered door on the computer: our web app listens on
**8000**, the model server on **8080**. The browser → 8000 → (internally) 8080.

### FastAPI / Uvicorn
**FastAPI** is a Python framework to define web endpoints (URLs like `/parse-resume`).
**Uvicorn** is the program that runs a FastAPI app and serves it.

### ONNX
A portable format for running small models (like our embedder) quickly without the heavy
PyTorch library. `fastembed` uses ONNX so the embedder is lightweight.

### Git, GitHub, repo, branch
- **Git** = a tool that tracks every change to your code (version history).
- **GitHub** = a website that hosts git repositories online.
- **Repo(sitory)** = the project folder under version control.
- **Branch** = a parallel copy where you make changes safely before merging to `main`.
- **Commit** = a saved snapshot with a message. **Push** = upload commits to GitHub.
  **Pull** = download the latest from GitHub.

### GitHub Codespaces & devcontainer
- **Codespaces** = a ready-to-use Linux computer in the cloud, attached to your repo, opened
  in a browser. No "install Python on my laptop" needed.
- **`.devcontainer/devcontainer.json`** = a recipe telling Codespaces how to build that
  computer (base image, what to run on creation, which ports to forward).

---

### TL;DR of the magic
1. A small **LLM** *reads* the résumé into JSON (generation, not copy-paste).
2. **Embeddings** measure *meaning* to match skills ↔ JD (no hardcoding).
3. The **PDF's own word positions** let us blur PII and box skills precisely.
4. **llama.cpp + FastAPI + Codespaces** make it run, free, in a browser.
