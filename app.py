"""NuExtract-1.5-tiny résumé demo — runs on GitHub Codespaces (CPU).

Two extraction modes (toggleable), both return raw JSON via json_schema-constrained
decoding (guaranteed valid + bounded — the 0.5B can't loop forever):
  - "essentials": the form-relevant fields (fast, ~40 s)
  - "full":       everything in the résumé, structured (summary, responsibilities,
                  project descriptions, soft skills, awards, publications, ... ~90 s)

PDF -> PyMuPDF text -> local llama-server (NuExtract-1.5-tiny) -> JSON -> small web UI.
"""
import json
import time
import urllib.error
import urllib.request

import fitz  # pymupdf
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import vendor  # vendor-side JD-relevance masked preview

LLAMA = "http://127.0.0.1:8080"
STR = {"type": "string"}


def _arr(items, maxn):
    return {"type": "array", "maxItems": maxn, "items": items}


def _obj(props):
    return {"type": "object", "properties": props}


# --- ESSENTIALS (form-relevant) ---------------------------------------------
TEMPLATE_ESSENTIALS = json.dumps({
    "name": "", "email": "", "phone": "", "location": "", "linkedin": "",
    "education": [{"institution": "", "degree": "", "field": "", "grade": ""}],
    "experience": [{"company": "", "title": "", "start_date": "", "end_date": ""}],
    "projects": [{"name": ""}],
    "certifications": [{"name": "", "issuer": ""}],
    "skills": [], "languages": [],
}, indent=4)

SCHEMA_ESSENTIALS = _obj({
    "name": STR, "email": STR, "phone": STR, "location": STR, "linkedin": STR,
    "education": _arr(_obj({"institution": STR, "degree": STR, "field": STR, "grade": STR}), 6),
    "experience": _arr(_obj({"company": STR, "title": STR, "start_date": STR, "end_date": STR}), 12),
    "projects": _arr(_obj({"name": STR}), 15),
    "certifications": _arr(_obj({"name": STR, "issuer": STR}), 15),
    "skills": _arr(STR, 40),
    "languages": _arr(STR, 10),
})

# --- FULL (everything in the résumé) ----------------------------------------
TEMPLATE_FULL = json.dumps({
    "name": "", "email": "", "phone": "", "location": "", "linkedin": "", "github": "", "website": "",
    "summary": "",
    "experience": [{"company": "", "title": "", "employment_type": "", "location": "",
                    "start_date": "", "end_date": "", "responsibilities": []}],
    "education": [{"institution": "", "degree": "", "field": "", "grade": "",
                   "location": "", "start_date": "", "end_date": ""}],
    "skills": [], "soft_skills": [],
    "projects": [{"name": "", "description": "", "technologies": [], "url": ""}],
    "certifications": [{"name": "", "issuer": "", "date": ""}],
    "languages": [{"name": "", "proficiency": ""}],
    "awards": [{"title": "", "issuer": "", "date": ""}],
    "publications": [{"title": "", "venue": "", "date": ""}],
}, indent=4)

SCHEMA_FULL = _obj({
    "name": STR, "email": STR, "phone": STR, "location": STR, "linkedin": STR, "github": STR,
    "website": STR, "summary": STR,
    "experience": _arr(_obj({
        "company": STR, "title": STR, "employment_type": STR, "location": STR,
        "start_date": STR, "end_date": STR, "responsibilities": _arr(STR, 12)}), 15),
    "education": _arr(_obj({
        "institution": STR, "degree": STR, "field": STR, "grade": STR,
        "location": STR, "start_date": STR, "end_date": STR}), 8),
    "skills": _arr(STR, 60),
    "soft_skills": _arr(STR, 25),
    "projects": _arr(_obj({"name": STR, "description": STR, "technologies": _arr(STR, 20), "url": STR}), 20),
    "certifications": _arr(_obj({"name": STR, "issuer": STR, "date": STR}), 25),
    "languages": _arr(_obj({"name": STR, "proficiency": STR}), 12),
    "awards": _arr(_obj({"title": STR, "issuer": STR, "date": STR}), 15),
    "publications": _arr(_obj({"title": STR, "venue": STR, "date": STR}), 15),
})

MODES = {"essentials": (TEMPLATE_ESSENTIALS, SCHEMA_ESSENTIALS),
         "full": (TEMPLATE_FULL, SCHEMA_FULL)}


def _llama_ready(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(LLAMA + "/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _loads_salvage(s: str):
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
    """Small models sometimes repeat items — drop exact duplicates in every list."""
    for key, items in list(d.items()):
        if not isinstance(items, list):
            continue
        seen, out = set(), []
        for it in items:
            k = json.dumps(it, sort_keys=True) if isinstance(it, (dict, list)) else str(it).strip().lower()
            if k and k not in seen:
                seen.add(k)
                out.append(it)
        d[key] = out
    return d


def extract(text: str, mode: str) -> dict:
    template, schema = MODES.get(mode, MODES["essentials"])
    prompt = f"<|input|>\n### Template:\n{template}\n### Text:\n{text}\n\n<|output|>\n"
    payload = {
        "prompt": prompt, "n_predict": 4096, "temperature": 0.0, "cache_prompt": True,
        "json_schema": schema,  # forces VALID JSON; maxItems caps arrays (no infinite loop)
        "stop": ["<|end-output|>", "<|input|>", "<|end|>"],
    }
    req = urllib.request.Request(
        LLAMA + "/completion", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    out = json.loads(urllib.request.urlopen(req, timeout=900).read().decode("utf-8")).get("content", "")
    s = out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = _loads_salvage(s)
    if isinstance(parsed, dict):
        return _dedup(parsed)
    return {"_raw": out, "_parse_error": True}


HTML = """<!doctype html><html><head><meta charset=utf-8><title>Résumé Extraction — NuExtract-tiny</title>
<style>body{font-family:system-ui,Segoe UI,sans-serif;background:#f5f7fb;color:#1f2937;margin:0}
header{background:#0b1020;color:#fff;padding:16px 24px}header h1{margin:0;font-size:17px}
header p{margin:4px 0 0;color:#9aa4b2;font-size:13px}main{max-width:920px;margin:0 auto;padding:24px}
.drop{background:#fff;border:2px dashed #cbd5e1;border-radius:12px;padding:24px;text-align:center;cursor:pointer}
.btn{background:#0d9488;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer;margin-top:12px}
.btn:disabled{opacity:.6}.card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-top:16px}
.f{margin-bottom:8px}.f label{font-size:11px;color:#6b7280;display:block}.f input{width:100%;padding:7px 9px;border:1px solid #e5e7eb;border-radius:7px}
.chip{display:inline-block;padding:4px 10px;border-radius:999px;background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46;font-size:13px;margin:3px}
pre{background:#0b1020;color:#cbd5e1;padding:12px;border-radius:10px;overflow:auto;font-size:12px;max-height:420px}
.t{float:right;font-size:12px;color:#0d9488;font-weight:700}h3{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin:14px 0 8px}
.seg{display:inline-flex;border:1px solid #cbd5e1;border-radius:999px;overflow:hidden;margin-top:10px}
.seg button{border:0;background:#fff;padding:7px 16px;font-weight:600;cursor:pointer;font-size:13px;color:#6b7280}
.seg button.on{background:#0d9488;color:#fff}
.masked{filter:blur(6px);user-select:none;pointer-events:none;transition:filter .25s}
.masked.revealed{filter:none;user-select:auto;pointer-events:auto}
.reveal{background:#f59e0b;color:#111;border:0;border-radius:7px;padding:3px 11px;font-size:12px;font-weight:700;cursor:pointer;margin-left:8px}
.hint{font-size:11px;color:#9a3412;margin-top:6px}</style></head><body>
<header><h1>Smart Résumé Extraction — NuExtract-1.5-tiny</h1>
<p>Local generative model · GitHub Codespaces (CPU) · no paid API · two modes · <a href="/vendor" style="color:#7dd3fc">🏢 Vendor JD-match view →</a></p></header>
<main>
<div class=drop onclick="document.getElementById('f').click()">
  <input type=file id=f accept=.pdf style=display:none>
  <div><b>Drop / choose a résumé PDF</b></div>
  <div id=fn style=color:#6b7280;font-size:13px;margin-top:6px></div>
  <div class=seg onclick="event.stopPropagation()">
    <button data-m=essentials class=on onclick="setMode('essentials')">Essentials · ~40s</button>
    <button data-m=full onclick="setMode('full')">Full details · ~90s</button>
  </div><br>
  <button class=btn id=go onclick="event.stopPropagation();go()">Parse &amp; extract</button>
  <div style=color:#6b7280;font-size:12px;margin-top:8px>CPU model — Essentials ~40 s, Full ~90 s. That's normal.</div>
</div>
<div id=out></div></main>
<script>
let chosen=null,mode='essentials';const $=i=>document.getElementById(i);
$('f').onchange=e=>{chosen=e.target.files[0];$('fn').textContent=chosen?'Selected: '+chosen.name:''};
function setMode(m){mode=m;document.querySelectorAll('.seg button').forEach(b=>b.classList.toggle('on',b.dataset.m===m))}
async function go(){if(!chosen){alert('Choose a PDF');return}
 const b=$('go');b.disabled=true;b.textContent='Parsing… ('+(mode==='full'?'~90s':'~40s')+')';$('out').innerHTML='';
 try{const fd=new FormData();fd.append('file',chosen);fd.append('mode',mode);
  const d=await(await fetch('/parse-resume',{method:'POST',body:fd})).json();
  const r=d.raw||{};
  if(r._parse_error){$('out').innerHTML='<div class=card><b>Could not parse the model output cleanly — please try again.</b><pre>'+(r._raw||'')+'</pre></div>';return}
  const ed=(r.education||[{}])[0]||{};
  const chips=a=>(a||[]).map(s=>'<span class=chip>'+(typeof s==='string'?s:(s.name||s.title||''))+'</span>').join('')||'<span style=color:#6b7280>none</span>';
  $('out').innerHTML='<div class=card><span class=t>'+d.mode+' · '+(d.elapsed_ms/1000).toFixed(1)+'s</span>'
   +'<h3>Contact <button class=reveal id=rv onclick="reveal()">🔓 Reveal contact</button></h3>'
   +'<div class=masked id=pii>'+inp('Name',r.name)+inp('Email',r.email)+inp('Phone',r.phone)+inp('LinkedIn',r.linkedin)+'</div>'
   +'<div class=hint id=hh>🔒 Contact hidden — in production this reveals only after the recruiter unlocks (pays).</div>'
   +'<h3>Education</h3>'+inp('Degree',ed.degree)+inp('Field',ed.field)+inp('Grade',ed.grade)
   +'<h3>Skills</h3>'+chips(r.skills)+'<h3>Certifications</h3>'+chips(r.certifications)
   +'<h3>Projects</h3>'+chips(r.projects)
   +'</div><div class=card><h3>Raw JSON ('+d.mode+')</h3><pre>'+JSON.stringify(d.raw,null,2)+'</pre></div>';
 }catch(e){$('out').innerHTML='<div class=card>Error: '+e+'</div>'}
 finally{b.disabled=false;b.textContent='Parse & extract'}}
function reveal(){$('pii').classList.add('revealed');$('rv').style.display='none';$('hh').textContent='🔓 Contact revealed (unlocked).'}
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
async def parse_resume(file: UploadFile = File(...), mode: str = Form("essentials")):
    mode = mode if mode in MODES else "essentials"
    data = await file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    t = time.time()
    raw = extract(text, mode)
    return {"engine": "nuextract-1.5-tiny", "mode": mode,
            "elapsed_ms": int((time.time() - t) * 1000), "raw": raw}


VENDOR_HTML = """<!doctype html><html><head><meta charset=utf-8><title>Vendor — JD match</title>
<style>body{font-family:system-ui,Segoe UI,sans-serif;background:#f5f7fb;color:#1f2937;margin:0}
header{background:#0b1020;color:#fff;padding:16px 24px}header h1{margin:0;font-size:17px}
header a{color:#7dd3fc;font-size:13px;text-decoration:none}main{max-width:1200px;margin:0 auto;padding:24px}
textarea{width:100%;min-height:90px;padding:10px;border:1px solid #cbd5e1;border-radius:8px;font:inherit}
.btn{background:#0d9488;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer;margin-top:10px}
.btn:disabled{opacity:.6}.row{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px}
.col{flex:1;min-width:330px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px}
.col h3{margin:0 0 8px;font-size:12px;text-transform:uppercase;color:#6b7280}
.col img{width:100%;border:1px solid #eee;border-radius:6px}.muted{color:#6b7280;font-size:13px}</style></head><body>
<header><h1>🏢 Vendor — JD relevance preview</h1>
<div><a href="/">← Trainer extraction</a> · masked résumé with JD-matched skills boxed (semantic, no hardcoding)</div></header>
<main>
<label class=muted>Paste the Job Description:</label>
<textarea id=jd placeholder="e.g. Looking for a Data Scientist with cloud, deep learning, computer vision and NLP experience to build ML pipelines..."></textarea>
<input type=file id=f accept=.pdf style=margin-top:10px><span class=muted id=fn></span><br>
<button class=btn id=go onclick="vgo()">Match &amp; mask</button>
<div id=out></div></main>
<script>
const $=i=>document.getElementById(i);
$('f').onchange=e=>{$('fn').textContent=e.target.files[0]?' '+e.target.files[0].name:''};
async function vgo(){
 const f=$('f').files[0];if(!f){alert('Choose a résumé PDF');return}
 const b=$('go');b.disabled=true;b.textContent='Matching… (~5s)';$('out').innerHTML='';
 try{const fd=new FormData();fd.append('file',f);fd.append('jd',$('jd').value);
  const d=await(await fetch('/vendor-preview',{method:'POST',body:fd})).json();
  let h='<p class=muted>'+d.matched+' JD-relevant terms highlighted · '+(d.elapsed_ms/1000).toFixed(1)+'s · contact blurred</p>';
  d.pages.forEach((p,i)=>{h+='<div class=row><div class=col><h3>Original (page '+(i+1)+')</h3><img src="'+p.original+'"></div>'
   +'<div class=col><h3>Masked + JD-highlighted</h3><img src="'+p.masked+'"></div></div>'});
  $('out').innerHTML=h;
 }catch(e){$('out').innerHTML='<p>Error: '+e+'</p>'}
 finally{b.disabled=false;b.textContent='Match & mask'}}
</script></body></html>"""


@app.get("/vendor", response_class=HTMLResponse)
def vendor_page():
    return VENDOR_HTML


@app.post("/vendor-preview")
def vendor_preview(file: UploadFile = File(...), jd: str = Form("")):
    data = file.file.read()
    t = time.time()
    res = vendor.make_preview(data, jd.strip() or "skills experience")
    res["elapsed_ms"] = int((time.time() - t) * 1000)
    return res


if __name__ == "__main__":
    print("waiting for llama-server (tiny) to load...", flush=True)
    for _ in range(120):
        if _llama_ready():
            print("model ready.", flush=True)
            break
        time.sleep(2)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
