"""Render and package authored evidence, leaving upstream corpus and papers local."""
import hashlib,json,shutil,zipfile
from pathlib import Path
import pymupdf
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
pdf=OUT/'pdf/main.pdf';doc=pymupdf.open(pdf);render=OUT/'pdf/review';render.mkdir(exist_ok=True)
issues=[];texts=[]
for n,page in enumerate(doc,1):
    page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(render/f'page-{n}.png');texts.append(page.get_text())
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            for s in line['spans']:
                x0,y0,x1,y1=s['bbox']
                if x0<10 or y0<10 or x1>page.rect.width-10 or y1>page.rect.height-10:issues.append({'page':n,'text':s['text']})
text='\n'.join(texts)
assert all(t in text for t in ['3,477','2,824','6,333','58.5','Ezekiel Ologunde'])
assert not issues and '@@' not in text and '??' not in text,issues
shutil.copyfile(pdf,OUT/'pdf/task_tool_transfer_audit.pdf')
verification=ROOT/'results/pdf_verification.json'
previous=json.loads(verification.read_text()) if verification.exists() else {}
digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
visual=previous.get('visual_review','pending') if previous.get('pdf_sha256')==digest else 'pending'
verification.write_text(json.dumps({'pages':len(doc),'issues':issues,'pdf_sha256':digest,'visual_review':visual,
    'compiler':'Portable Tectonic; native compiler platform-directory error'},indent=2),encoding='utf-8')
entries=[p for p in ROOT.glob('*') if p.is_file() and p.suffix in {'.py','.md','.json'}]
entries += [p for p in (ROOT/'results').rglob('*') if p.is_file()]
entries += [ROOT/'paper/main.tex',ROOT/'paper/acmart.cls',ROOT/'data/benchmark_manifest.json',ROOT/'data/source_manifest.json',ROOT/'data/split_profile.json',
    ROOT/'author_artifacts/data/source_manifest.json',ROOT/'author_artifacts/data/sources/outshift-open__ASTRA/files/LICENSE',ROOT/'work/frozen/lexical_baseline_v1.py']
dest=OUT/'p06_authored_benchmark_note.zip'
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(entries):z.write(p,p.relative_to(ROOT))
with zipfile.ZipFile(dest) as z:assert z.testzip() is None
with zipfile.ZipFile(OUT/'overleaf_project.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['main.tex','acmart.cls']:z.write(ROOT/'paper'/name,name)
result={'archive':dest.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
    'pages':len(doc),'pdf_sha256':digest,'raw_benchmark_and_paper_copies_included':False}
(OUT/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
