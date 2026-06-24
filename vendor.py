"""Vendor side — JD-relevance preview (selective, SINGLE color).

Renders a résumé page, BLURS contact (email/phone/LinkedIn), and boxes the résumé
terms most semantically related to the JD (top-N overall). One highlight color — no
category grouping for now (kept simple + accurate; grouping can be re-added later only
if it can be made reliable). Matching = sentence-embedding cosine (fastembed bge-small),
learned meaning, NO hardcoding.

make_preview(pdf_bytes, jd) -> {"pages":[{"original","masked"}], "matched":N, "categories":[]}
"""
import base64
import io
import re

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ZOOM = 2.0
FLOOR = 0.62             # min similarity to highlight a term
MAX_BOXES = 45           # cap total highlights per page (selective, not a wall)
HIGHLIGHT = (37, 99, 235)  # one color for all JD-relevant terms
STOP = set("a an the and or for with in of to on at as by is are be this that from we you our will need "
           "experience strong looking build using used work years role into it its their have has i am my "
           "me also such not but other which when where who can more most very".split())

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
    """Skill-like phrases from the JD (1-4 words) used as relevance reference vectors."""
    chunks = re.split(r"[,;:\n.|/()]|\band\b|\bwith\b|\bincluding\b|\bsuch as\b|\bor\b|"
                      r"\bin\b|\bof\b|\bfor\b|\bto\b|\busing\b|\bexperience\b|\bexperienced\b",
                      jd, flags=re.I)
    terms = []
    for c in chunks:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z+#.]*", c) if w.lower() not in STOP]
        if 1 <= len(words) <= 4:
            phrase = " ".join(words).strip()
            if len(re.sub(r"[^a-z]", "", phrase.lower())) >= 3:
                terms.append(phrase)
    return list(dict.fromkeys(terms)) or ["skill"]


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
                if any(g[4].lower() not in STOP for g in grp):
                    add(" ".join(g[4] for g in grp),
                        fitz.Rect(grp[0][0], grp[0][1], grp[-1][2], grp[-1][3]))
    return cands


def _b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def make_preview(pdf_bytes, jd, max_pages=2):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    jv = _vecs(_jd_terms(jd))
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

        # selective: top-N résumé terms most related to the JD (single color)
        cands = _candidates(words)
        terms = list(cands.keys())
        chosen = []
        if terms:
            best = (_vecs(terms) @ jv.T).max(axis=1)
            chosen = [terms[i] for i in np.argsort(-best) if best[i] >= FLOOR][:MAX_BOXES]

        draw = ImageDraw.Draw(img)
        drawn = set()
        for t in chosen:
            r = cands[t]
            key = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
            if key in drawn:
                continue
            drawn.add(key)
            total += 1
            draw.rectangle([r.x0 * ZOOM - 1, r.y0 * ZOOM - 1, r.x1 * ZOOM + 1, r.y1 * ZOOM + 1],
                           outline=HIGHLIGHT, width=2)

        pages.append({"original": _b64(orig), "masked": _b64(img)})

    return {"pages": pages, "matched": total, "categories": []}
