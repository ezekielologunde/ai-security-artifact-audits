"""Render and package authored audit material, excluding upstream code and CSVs."""
import hashlib,json,shutil,zipfile
from pathlib import Path
import pymupdf
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
if __name__=='__main__':
    pdf=OUT/'pdf/main.pdf';doc=pymupdf.open(pdf);render=OUT/'pdf/review';render.mkdir(exist_ok=True)
    for old in render.glob('page-*.png'):old.unlink()
    issues=[];texts=[]
    for n,page in enumerate(doc,1):
        page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(render/f'page-{n}.png');texts.append(page.get_text())
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    x0,y0,x1,y1=span['bbox']
                    if x0<10 or y0<10 or x1>page.rect.width-10 or y1>page.rect.height-10:issues.append({'page':n,'text':span['text']})
    text='\n'.join(texts);assert all(s in text for s in ['614','624','50%','100%','Ezekiel Ologunde']);assert not issues,issues
    assert '??' not in text
    target=OUT/'pdf/model_identity_join_audit.pdf';shutil.copyfile(pdf,target)
    sha=hashlib.sha256(pdf.read_bytes()).hexdigest();vf=ROOT/'results/pdf_verification.json';prior=json.loads(vf.read_text()) if vf.exists() else {}
    vf.write_text(json.dumps({'pages':len(doc),'pdf_sha256':sha,'issues':issues,
        'visual_review':prior.get('visual_review','pending') if prior.get('pdf_sha256')==sha else 'pending',
        'compiler':'Portable Tectonic; native compiler platform-directory error'},indent=2),encoding='utf-8')
    entries=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in {'.py','.md','.json','.txt'}]
    entries += list((ROOT/'results').glob('*.json'))
    entries += [ROOT/'data/trace_tables_manifest.json',ROOT/'data/trace_table_profiles.json',ROOT/'data/trace_artifact_inventory.json',ROOT/'data/reading_manifest.json',ROOT/'paper/main.tex',ROOT/'paper/acmart.cls']
    archive=OUT/'authored_join_audit_review.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(entries):z.write(p,p.relative_to(ROOT))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    with zipfile.ZipFile(OUT/'overleaf_project.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['main.tex','acmart.cls']:z.write(ROOT/'paper'/name,name)
    result={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'pdf_pages':len(doc),'pdf_sha256':sha,'upstream_code_or_raw_data_included':False}
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
