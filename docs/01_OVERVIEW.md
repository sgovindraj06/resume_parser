# 01 · Overview — what this project is and why

> Read this first. No coding knowledge needed. By the end you'll understand *what* we
> built and *why* every piece exists.

## The product idea (the "why")
Imagine a **marketplace that connects trainers with companies** (like a job board, but for
trainers/instructors). It has **two sides**:

1. **Trainer side** — a trainer signs up. Normally they'd fill a long registration form
   (skills, experience, education, certifications…). That's tedious. **Our idea: they
   just upload their résumé, and the form fills itself.** An AI reads the résumé and
   pulls out all the structured details.

2. **Vendor side** (the company / recruiter) — they have a **Job Description (JD)** and
   want to find suitable trainers. They browse résumés. But two things matter:
   - **Privacy:** the trainer's **contact details should be hidden** until the company
     actually commits (e.g., pays/unlocks). So we **mask** email/phone/LinkedIn.
   - **Relevance:** the recruiter wants to instantly see **which skills on the résumé
     match their JD**. So we **highlight** the relevant skills right on the résumé.

That's the whole product in one sentence: **read résumés automatically, mask private info,
and highlight what matters to each recruiter.**

## What this repo specifically demonstrates
This repo is a **working demo of that pipeline**, runnable for free:

| Side | URL | What it does |
|---|---|---|
| **Trainer** | `/` | Upload résumé PDF → structured JSON (the "autofill" data). Contact can be blurred and revealed on click (the "unlock" idea). |
| **Vendor** | `/vendor` | Paste a JD + upload résumé → see it rendered with **contact blurred** and **JD-relevant skills outlined**. |

## The three hard rules we followed (important!)
These constraints shaped every technical decision — your brother should understand them:

1. **Local & free — no paid AI API.** We do **not** call OpenAI/Gemini (those cost money
   per request and send data to a third party). Instead we run a small AI model **on our
   own machine**. Cost = ₹0, and résumé data never leaves the box.
2. **No "hardcoding."** We never write tables like `{"ML": "Machine Learning", "cloud":
   ["AWS","GCP"]}`. Those break the moment a résumé uses a word we didn't predict. Instead
   the system **understands meaning** using AI models (it *learns* that ML ≈ Machine
   Learning, that "cloud" relates to "AWS"). This is what makes it work across *any*
   résumé format.
3. **No fragile tricks (regex/keyword matching) for the smart parts.** Reading a résumé and
   matching skills is done by **models that understand language**, not brittle text rules.

## The pieces, in plain words
| Piece | Plain-English job |
|---|---|
| **The extractor** (NuExtract, a small AI model) | Reads the résumé text and writes out structured JSON. |
| **llama.cpp** | The "engine" that runs the AI model efficiently on a CPU. |
| **The embedder** (bge-small) | A second, tiny AI that turns words into numbers so we can measure **meaning similarity** (used to match résumé skills to the JD). |
| **PyMuPDF** | Opens the PDF, gives us the text **and the exact position of every word** (needed to draw boxes / blur). |
| **Pillow** | Draws the boxes and blurs the contact details on the rendered page image. |
| **FastAPI** | The web server that ties it together and serves the web pages. |
| **GitHub Codespaces** | A free cloud computer (from GitHub) where the whole thing runs, so anyone can open it in a browser. |

## What's a demo vs. what's "production"
- **This demo:** tiny 0.5B model, free CPU, one résumé at a time, cloud (so demo-only for
  privacy). Slower (~40-90 s per résumé).
- **Production version** (same architecture, scaled): a bigger/faster model on a GPU,
  résumés stored in a database, extraction done once when a trainer signs up (not every
  view), real login + a real "pay to unlock contact" gate, all hosted on the company's own
  servers so PII stays private.

The point of the demo is that the **architecture is the same** — you just swap the small
parts for bigger ones. See **[02_ARCHITECTURE.md](02_ARCHITECTURE.md)**.
