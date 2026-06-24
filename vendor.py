"""Vendor side — JD-relevance preview.

Renders a résumé page, BLURS contact (email/phone/LinkedIn), and draws thin
multi-color boxes around terms/phrases semantically related to the pasted Job
Description. Matching = sentence-embedding cosine (fastembed bge-small) — learned
meaning, NO hardcoded skill/synonym maps. Fast: no LLM call needed.

make_preview(pdf_bytes, jd) -> {"pages":[{"original":b64,"masked":b64}], "matched":N}
"""
import base64
import io
import re

import fitz  # pymupdf
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ZOOM = 2.0
THRESHOLD = 0.76  # bge cosines run high; ~0.76 = dense-but-relevant
PALETTE = [(234, 88, 12), (37, 99, 235), (22, 163, 74), (147, 51, 234), (13, 148, 136), (219, 39, 119)]
STOP = set("a an the the and or for with in of to on at as by is are be this that from we you our will "
           "need experience strong looking build using used work years role into it its their have has "
           "i am my me also such not but other which when where who can more most very a".split())

_emb = None


def _embedder():
    global _emb
    if _emb is None:
        from fastembed import TextEmbedding
        _emb = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _emb


def _vecs(texts):
    a = np.array(list(_embedder().embed(list(texts))), dtype=np.float32)
    a /= (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    return a


def _jd_concepts(jd: str):
    toks = re.findall(r"[A-Za-z][A-Za-z+#.]+", jd)
    uni = [t for t in toks if t.lower() not in STOP and len(t) >= 4]
    bi = [toks[i] + " " + toks[i + 1] for i in range(len(toks) - 1)
          if toks[i].lower() not in STOP and toks[i + 1].lower() not in STOP]
    seen, out = set(), []
    for t in uni + bi:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out or ["skill"]


def _candidates(words):
    cands = {}

    def add(text, rect):
        if len(re.sub(r"[^a-z0-9+#]", "", text.lower())) >= 3:
            cands.setdefault(text.strip(), rect)

    for w in words:
        if w[4].lower() not in STOP:
            add(w[4], fitz.Rect(w[0], w[1], w[2], w[3]))
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            grp = words[i:i + n]
            if grp[0][5] == grp[-1][5] and grp[0][6] == grp[-1][6]:
                add(" ".join(g[4] for g in grp),
                    fitz.Rect(grp[0][0], grp[0][1], grp[-1][2], grp[-1][3]))
    return cands


def _b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def make_preview(pdf_bytes: bytes, jd: str, threshold: float = THRESHOLD, max_pages: int = 2) -> dict:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    concepts = _jd_concepts(jd)
    cvecs = _vecs(concepts)
    pages, total = [], 0

    for pno in range(min(len(doc), max_pages)):
        page = doc[pno]
        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        orig = img.copy()
        words = page.get_text("words")
        text = page.get_text()

        # blur contact (email / phone / linkedin) — regex, no model needed
        pii = []
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        if m:
            pii.append(m.group())
        pii += [p.strip() for p in re.findall(r"\+?\d[\d ()\-]{8,}\d", text)]
        pii += [w[4] for w in words if "linkedin.com" in w[4].lower() or "github.com" in w[4].lower()]
        for val in pii:
            for r in page.search_for(val):
                bb = (int(r.x0 * ZOOM), int(r.y0 * ZOOM), int(r.x1 * ZOOM), int(r.y1 * ZOOM))
                if bb[2] > bb[0] and bb[3] > bb[1]:
                    img.paste(img.crop(bb).filter(ImageFilter.GaussianBlur(8)), (bb[0], bb[1]))

        # dense multi-color semantic highlight
        cands = _candidates(words)
        terms = list(cands.keys())
        if terms:
            sims = _vecs(terms) @ cvecs.T
            best_i, best_s = sims.argmax(axis=1), sims.max(axis=1)
            draw = ImageDraw.Draw(img)
            drawn = set()
            for t, ci, score in zip(terms, best_i, best_s):
                if score < threshold:
                    continue
                r = cands[t]
                key = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
                if key in drawn:
                    continue
                drawn.add(key)
                total += 1
                draw.rectangle([r.x0 * ZOOM - 1, r.y0 * ZOOM - 1, r.x1 * ZOOM + 1, r.y1 * ZOOM + 1],
                               outline=PALETTE[int(ci) % len(PALETTE)], width=2)

        pages.append({"original": _b64(orig), "masked": _b64(img)})

    return {"pages": pages, "matched": total}
