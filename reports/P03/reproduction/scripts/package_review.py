"""Package authored audit work; exclude upstream unlicensed source and raw exports."""
import hashlib, json, shutil, zipfile
from pathlib import Path
import pymupdf
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
pdf=OUT/'pdf/main.pdf';doc=pymupdf.open(pdf);render=OUT/'pdf/review';render.mkdir(exist_ok=True)
issues=[];texts=[]
for n,page in enumerate(doc,1):
    page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(render/f'page-{n}.png')
    texts.append(page.get_text())
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            for span in line['spans']:
                x0,y0,x1,y1=span['bbox']
                if x0<10 or y0<10 or x1>page.rect.width-10 or y1>page.rect.height-10:issues.append({'page':n,'text':span['text']})
text='\n'.join(texts)
assert all(s in text for s in ['191,370','79,510','43','Ezekiel Ologunde'])
assert '@@' not in text and '??' not in text and not issues,issues
shutil.copyfile(pdf,OUT/'pdf/shadow_ai_dataset_audit.pdf')
verification=ROOT/'results/pdf_verification.json'
previous=json.loads(verification.read_text()) if verification.exists() else {}
pdf_hash=hashlib.sha256(pdf.read_bytes()).hexdigest()
visual=previous.get('visual_review','pending separate page inspection') if previous.get('pdf_sha256')==pdf_hash else 'pending separate page inspection'
verification.write_text(json.dumps({'pages':len(doc),'text_and_bounds_issues':issues,'pdf_sha256':pdf_hash,
    'compiler':'project-local Tectonic; native editor has platform-directory error','visual_review':visual},indent=2),encoding='utf-8')
entries=[p for folder in ['scripts','research','results','paper'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.log','.aux','.pyc','.out'}]
entries += [ROOT/'view_guard.py',ROOT/'requirements.txt',ROOT/'requirements-paper.txt',ROOT/'README.md',ROOT/'data/source_manifest.json']
dest=OUT/'p03_authored_audit_review.zip'
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(entries):z.write(p,p.relative_to(ROOT))
with zipfile.ZipFile(dest) as z:assert z.testzip() is None and not any('work/' in n or 'data/sources/' in n for n in z.namelist())
manifest={'archive':dest.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
    'paper_pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(doc),'upstream_source_and_generated_csvs_included':False}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))
with zipfile.ZipFile(OUT/'overleaf_project.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['main.tex','acmart.cls']:z.write(ROOT/'paper'/name,name)
