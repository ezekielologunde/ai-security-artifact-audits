"""Package only the authored scorer audit, with no raw advice text or unrelated studies."""
import hashlib,json,shutil,zipfile
from pathlib import Path
import pymupdf
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output'
if __name__=='__main__':
    pdf=OUT/'pdf/main.pdf';doc=pymupdf.open(pdf);assert len(doc)==2
    issues=[];text=''
    for number,page in enumerate(doc,1):
        text+=page.get_text()
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    x0,y0,x1,y1=span['bbox']
                    if x0<10 or y0<10 or x1>page.rect.width-10 or y1>page.rect.height-10:issues.append({'page':number,'text':span['text']})
    assert not issues and '??' not in text
    assert all(s in text for s in ['Ezekiel Ologunde','439','450','19','39','None','overall'])
    target=OUT/'pdf/helpbench_scoring_audit.pdf';shutil.copyfile(pdf,target);digest=hashlib.sha256(target.read_bytes()).hexdigest()
    verification={'pages':len(doc),'pdf_sha256':digest,'issues':issues,'visual_review':'Both rendered pages inspected: readable text and table, no clipping or overlapping content.',
      'compiler':'Portable Tectonic 0.17.0; desktop editor also reported compilation success','generated_ACM_class_in_public_sources':False}
    (ROOT/'results/pdf_verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    names=['README.md','HELPBENCH_RESEARCH_DECISION.md','HELPBENCH_RESULTS.md','HELPBENCH_SCORER_PROTOCOL.json','HELPBENCH_ID_AMENDMENT.json','HELPBENCH_AGGREGATE_AMENDMENT.json',
      'scorer_overlay.py','audit_helpbench_scorer.py','verify_helpbench_scorer.py','summarize_helpbench_effect.py','download_helpbench.py','source_io.py','requirements-helpbench.txt','package_helpbench_note.py',
      'data/helpbench_manifest.json','data/helpbench/files/LICENSE','work/frozen/audit_helpbench_scorer_v1.py','paper/main.tex',
      'results/helpbench_scorer_audit.json','results/helpbench_endpoint_records.jsonl','results/helpbench_conditional_aggregate.json','results/helpbench_scorer_verification.json','results/helpbench_upstream_junit.xml','results/helpbench_initial_failure.json','results/pdf_verification.json']
    archive=OUT/'authored_helpbench_audit_review.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(ROOT/name,name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    with zipfile.ZipFile(OUT/'overleaf_project.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT/'paper/main.tex','main.tex');z.writestr('BUILD.txt','Use main.tex with the standard installed acmart class. Preliminary technical report; not ACM-published or peer reviewed.\n')
    result={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'pdf_pages':len(doc),'pdf_sha256':digest,
      'raw_advice_text_or_other_studies_included':False,'independent_external_review':False}
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
