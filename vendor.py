"""Vendor side — JD-relevance preview (ACCURATE: box only real skills).

Boxes only the terms the model EXTRACTED as skills/technologies (passed in by the
caller), found at every occurrence on the page — so it never boxes random/filler words.
If a JD is given, keep only the extracted skills semantically related to it (fastembed
bge-small, learned meaning, NO hardcoding); otherwise box all of them. Contact is blurred.

make_preview(pdf_bytes, skill_terms, jd="") -> {"pages":[{"original","masked"}], "matched":N, "categories":[]}
"""
import base64
import io
import re

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ZOOM = 2.0
FLOOR = 0.60             # min similarity for a skill to count as JD-relevant
HIGHLIGHT = (37, 99, 235)
STOP = set("a an the and or for with in of to on at as by is are be this that from we you our will need "
           "experience strong looking build using used work years role into it its their have has".split())

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


def _jd_terms(jd):
    chunks = re.split(r"[,;:\n.|/()]|\band\b|\bwith\b|\bor\b|\bin\b|\bof\b|\bfor\b|\bto\b|\busing\b", jd, flags=re.I)
    out = []
    for c in chunks:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z+#.]*", c) if w.lower() not in STOP]
        if 1 <= len(words) <= 4:
            p = " ".join(words).strip()
            if len(re.sub(r"[^a-z]", "", p.lower())) >= 3:
                out.append(p)
    return list(dict.fromkeys(out))


def _select(skill_terms, jd):
    """Clean the extracted skills; if a JD is given, keep only JD-relevant ones."""
    terms = []
    for t in skill_terms:
        t = (t or "").strip()
        if len(re.sub(r"[^a-z0-9+#]", "", t.lower())) >= 2 and t.lower() not in STOP:
            terms.append(t)
    terms = list(dict.fromkeys(terms))
    jts = _jd_terms(jd) if jd and jd.strip() else []
    if not terms or not jts:
        return terms  # no JD -> box all real skills
    best = (_vecs(terms) @ _vecs(jts).T).max(axis=1)
    keep = [t for t, b in zip(terms, best) if b >= FLOOR]
    return keep or terms  # if JD matched nothing, fall back to all skills


def _b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def make_preview(pdf_bytes, skill_terms, jd="", max_pages=2):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    terms = _select(list(skill_terms or []), jd)
    pages, total = [], 0

    for pno in range(min(len(doc), max_pages)):
        page = doc[pno]
        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        orig = img.copy()
        words = page.get_text("words")
        text = page.get_text()

        # blur contact
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

        # box every occurrence of each real (extracted) skill
        draw = ImageDraw.Draw(img)
        drawn = set()
        for term in terms:
            try:
                rects = page.search_for(term)
            except Exception:
                continue
            for r in rects:
                key = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
                if key in drawn:
                    continue
                drawn.add(key)
                total += 1
                draw.rectangle([r.x0 * ZOOM - 1, r.y0 * ZOOM - 1, r.x1 * ZOOM + 1, r.y1 * ZOOM + 1],
                               outline=HIGHLIGHT, width=2)

        pages.append({"original": _b64(orig), "masked": _b64(img)})

    return {"pages": pages, "matched": total, "categories": []}
