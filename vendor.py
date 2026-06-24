"""Vendor side — JD-relevance preview (SELECTIVE + CATEGORICAL).

Renders a résumé page, BLURS contact (email/phone/LinkedIn), and draws thin boxes around
the résumé terms most related to the JD. The JD is reduced to a few KEY concepts
(categories); each category gets ONE color; for each category only the TOP-K best-matching
résumé terms are boxed -> selective, grouped by color (not a wall of random boxes).
Matching = sentence-embedding cosine (fastembed bge-small) — learned meaning, NO hardcoding.

make_preview(pdf_bytes, jd) -> {"pages":[{"original","masked"}], "matched":N,
                                "categories":[{"name","color"}]}
"""
import base64
import io
import re

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ZOOM = 2.0
K_PER_CATEGORY = 10      # at most this many boxes per JD concept
FLOOR = 0.62             # min similarity to box at all
MAX_CATEGORIES = 5       # few, clean concept groups (keep <= len(PALETTE))
PALETTE = [
    (234, 88, 12), (37, 99, 235), (22, 163, 74), (147, 51, 234), (13, 148, 136), (219, 39, 119),
    (202, 138, 4), (8, 145, 178), (190, 24, 93), (101, 163, 13), (124, 58, 237), (217, 70, 239),
]
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


def _jd_categories(jd):
    chunks = re.split(r"[,;:\n.|/()]|\band\b|\bwith\b|\bincluding\b|\bsuch as\b|\bor\b|"
                      r"\bin\b|\bof\b|\bfor\b|\bto\b|\busing\b|\bexperience\b|\bexperienced\b",
                      jd, flags=re.I)
    concepts = []
    for c in chunks:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z+#.]*", c) if w.lower() not in STOP]
        # skills are short phrases (1-4 words), not whole sentence fragments
        if 1 <= len(words) <= 4:
            phrase = " ".join(words).strip()
            if len(re.sub(r"[^a-z]", "", phrase.lower())) >= 3:
                concepts.append(phrase)
    concepts = list(dict.fromkeys(concepts)) or ["skill"]
    cv = _vecs(concepts)
    cats, catv = [], []
    for t, v in zip(concepts, cv):
        # merge only near-DUPLICATE concepts; keep genuinely distinct ones separate
        if all(float(np.dot(v, x)) < 0.78 for x in catv):
            cats.append(t); catv.append(v)
        if len(cats) >= MAX_CATEGORIES:
            break
    return cats, np.array(catv)


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
    cats, catv = _jd_categories(jd)
    categories = [{"name": c, "color": "rgb(%d,%d,%d)" % PALETTE[i % len(PALETTE)]}
                  for i, c in enumerate(cats)]
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

        # selective top-K per category
        cands = _candidates(words)
        terms = list(cands.keys())
        chosen = {}
        if terms:
            sims = _vecs(terms) @ catv.T
            for ci in range(len(cats)):
                col = sims[:, ci]
                for ti in np.argsort(-col)[:K_PER_CATEGORY]:
                    if col[ti] < FLOOR:
                        break
                    t = terms[ti]
                    if t not in chosen or col[ti] > chosen[t][1]:
                        chosen[t] = (ci, float(col[ti]))

        draw = ImageDraw.Draw(img)
        drawn = set()
        for t, (ci, _) in chosen.items():
            r = cands[t]
            key = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
            if key in drawn:
                continue
            drawn.add(key)
            total += 1
            draw.rectangle([r.x0 * ZOOM - 1, r.y0 * ZOOM - 1, r.x1 * ZOOM + 1, r.y1 * ZOOM + 1],
                           outline=PALETTE[ci % len(PALETTE)], width=2)

        pages.append({"original": _b64(orig), "masked": _b64(img)})

    return {"pages": pages, "matched": total, "categories": categories}
