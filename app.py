"""NuExtract-1.5-tiny résumé demo — runs on GitHub Codespaces (CPU).

FastAPI app: ingest a PDF (PyMuPDF) -> NuExtract-1.5-tiny via a local llama-server
(standalone llama.cpp Linux build, started by start.sh) -> JSON -> small web UI.
Serves on :8000; Codespaces forwards that port to a stable public URL.
"""
import json
import time
import urllib.error
import urllib.request

import fitz  # pymupdf
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

LLAMA = "http://127.0.0.1:8080"

TEMPLATE = json.dumps(
    {
        "name": "", "email": "", "phone": "", "location": "", "linkedin": "",
        "education": [{"institution": "", "degree": "", "field": "", "grade": ""}],
        "experience": [{"company": "", "title": "", "start_date": "", "end_date": ""}],
        "projects": [{"name": ""}],
        "certifications": [{"name": "", "issuer": ""}],
        "skills": [], "languages": [],
    },
    indent=4,
)


def _llama_ready(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(LLAMA + "/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


# Constrains the model to VALID JSON; maxItems caps arrays so the 0.5B physically
# cannot loop the same entry forever (the cause of the unparseable output).
SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"}, "email": {"type": "string"},
        "phone": {"type": "string"}, "location": {"type": "string"},
        "linkedin": {"type": "string"},
        "education": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
            "institution": {"type": "string"}, "degree": {"type": "string"},
            "field": {"type": "string"}, "grade": {"type": "string"}}}},
        "experience": {"type": "array", "maxItems": 12, "items": {"type": "object", "properties": {
            "company": {"type": "string"}, "title": {"type": "string"},
            "start_date": {"type": "string"}, "end_date": {"type": "string"}}}},
        "projects": {"type": "array", "maxItems": 15, "items": {"type": "object", "properties": {
            "name": {"type": "string"}}}},
        "certifications": {"type": "array", "maxItems": 15, "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "issuer": {"type": "string"}}}},
        "skills": {"type": "array", "maxItems": 40, "items": {"type": "string"}},
        "languages": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
    },
}


def _loads_salvage(s: str):
    """Parse JSON; if the model truncated/looped (unclosed structure), recover the
    largest valid prefix by trimming to a '}' boundary and closing open brackets."""
    try:
        return json.loads(s)
    except Exception:
        pass
    for end in range(len(s) - 1, 0, -1):
        if s[end] == "}":
            frag = s[: end + 1]
            cand = frag + "]" * max(0, frag.count("[") - frag.count("]")) \
                        + "}" * max(0, frag.count("{") - frag.count("}"))
            try:
                return json.loads(cand)
            except Exception:
                continue
    return None


def _dedup(d: dict) -> dict:
    """Small models sometimes repeat list items — drop exact duplicates."""
    for key in ("experience", "education", "projects", "certifications"):
        items = d.get(key)
        if isinstance(items, list):
            seen, out = set(), []
            for it in items:
                k = json.dumps(it, sort_keys=True)
                if k not in seen:
                    seen.add(k)
                    out.append(it)
            d[key] = out
    return d


def extract(text: str) -> dict:
    prompt = f"<|input|>\n### Template:\n{TEMPLATE}\n### Text:\n{text}\n\n<|output|>\n"
    payload = {
        "prompt": prompt, "n_predict": 4096, "temperature": 0.0, "cache_prompt": True,
        # json_schema forces VALID JSON; maxItems caps arrays so the 0.5B can't loop forever
        "json_schema": SCHEMA,
        "stop": ["<|end-output|>", "<|input|>", "<|end|>"],
    }
    req = urllib.request.Request(
        LLAMA + "/completion", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    out = json.loads(urllib.request.urlopen(req, timeout=600).read().decode("utf-8")).get("content", "")
    s = out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = _loads_salvage(s)
    if isinstance(parsed, dict):
        return _dedup(parsed)
    return {"_raw": out, "_parse_error": True}


HTML = """<!doctype html><html><head><meta charset=utf-8><title>Résumé Autofill — NuExtract-tiny</title>
<style>body{font-family:system-ui,Segoe UI,sans-serif;background:#f5f7fb;color:#1f2937;margin:0}
header{background:#0b1020;color:#fff;padding:16px 24px}header h1{margin:0;font-size:17px}
header p{margin:4px 0 0;color:#9aa4b2;font-size:13px}main{max-width:920px;margin:0 auto;padding:24px}
.drop{background:#fff;border:2px dashed #cbd5e1;border-radius:12px;padding:24px;text-align:center;cursor:pointer}
.btn{background:#0d9488;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer;margin-top:12px}
.btn:disabled{opacity:.6}.card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-top:16px}
.f{margin-bottom:8px}.f label{font-size:11px;color:#6b7280;display:block}.f input{width:100%;padding:7px 9px;border:1px solid #e5e7eb;border-radius:7px}
.chip{display:inline-block;padding:4px 10px;border-radius:999px;background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46;font-size:13px;margin:3px}
pre{background:#0b1020;color:#cbd5e1;padding:12px;border-radius:10px;overflow:auto;font-size:12px;max-height:360px}
.t{float:right;font-size:12px;color:#0d9488;font-weight:700}h3{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin:14px 0 8px}</style></head><body>
<header><h1>Smart Résumé Autofill — NuExtract-1.5-tiny</h1>
<p>Local generative extraction model · running free on GitHub Codespaces (CPU) · no paid API</p></header>
<main>
<div class=drop onclick="document.getElementById('f').click()">
  <input type=file id=f accept=.pdf style=display:none>
  <div><b>Drop / choose a résumé PDF</b></div>
  <div id=fn style=color:#6b7280;font-size:13px;margin-top:6px></div>
  <button class=btn id=go onclick="event.stopPropagation();go()">Parse &amp; autofill</button>
  <div style=color:#6b7280;font-size:12px;margin-top:8px>CPU model — first parse takes ~45-90 s. That's normal.</div>
</div>
<div id=out></div></main>
<script>
let chosen=null;const $=i=>document.getElementById(i);
$('f').onchange=e=>{chosen=e.target.files[0];$('fn').textContent=chosen?'Selected: '+chosen.name:''};
async function go(){if(!chosen){alert('Choose a PDF');return}
 const b=$('go');b.disabled=true;b.textContent='Parsing… (~1 min)';$('out').innerHTML='';
 try{const fd=new FormData();fd.append('file',chosen);
  const d=await(await fetch('/parse-resume',{method:'POST',body:fd})).json();
  const r=d.raw||{};
  if(r._parse_error){$('out').innerHTML='<div class=card><b>Could not parse the model output cleanly — please try again.</b><pre>'+(r._raw||'')+'</pre></div>';return}
  const ed=(r.education||[{}])[0]||{};
  const chips=a=>(a||[]).map(s=>'<span class=chip>'+(typeof s==='string'?s:(s.name||''))+'</span>').join('')||'<span style=color:#6b7280>none</span>';
  $('out').innerHTML='<div class=card><span class=t>'+(d.elapsed_ms/1000).toFixed(1)+'s</span><h3>Contact</h3>'
   +inp('Name',r.name)+inp('Email',r.email)+inp('Phone',r.phone)+inp('LinkedIn',r.linkedin)
   +'<h3>Education</h3>'+inp('Degree',ed.degree)+inp('Field',ed.field)+inp('Grade',ed.grade)
   +'<h3>Skills</h3>'+chips(r.skills)+'<h3>Certifications</h3>'+chips(r.certifications)
   +'<h3>Projects</h3>'+chips(r.projects)
   +'</div><div class=card><h3>Raw JSON</h3><pre>'+JSON.stringify(d,null,2)+'</pre></div>';
 }catch(e){$('out').innerHTML='<div class=card>Error: '+e+'</div>'}
 finally{b.disabled=false;b.textContent='Parse & autofill'}}
function inp(l,v){return '<div class=f><label>'+l+'</label><input value="'+((v??'')+'').replace(/"/g,'&quot;')+'"></div>'}
</script></body></html>"""

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


@app.get("/health")
def health():
    return {"status": "ok", "model_ready": _llama_ready()}


@app.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
    data = await file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    t = time.time()
    raw = extract(text)
    return {"engine": "nuextract-1.5-tiny", "elapsed_ms": int((time.time() - t) * 1000), "raw": raw}


if __name__ == "__main__":
    print("waiting for llama-server (tiny) to load...", flush=True)
    for _ in range(120):
        if _llama_ready():
            print("model ready.", flush=True)
            break
        time.sleep(2)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
