"""Expose primary-method passages and non-boilerplate artifact candidates."""
import html,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for path in sorted((ROOT/'data').glob('*.html')):
    raw=path.read_text(encoding='utf-8')
    text=html.unescape(re.sub('<[^>]+>',' ',raw));text=re.sub(r'\s+',' ',text)
    (path.with_suffix('.txt')).write_text(text,encoding='utf-8')
    print('\nPAPER',path.stem)
    for pattern in ['artifact','available','ASTRA','limitation','future work','data availability']:
        matches=list(re.finditer(pattern,text,re.I))
        for m in matches[:2]:print(text[max(0,m.start()-100):m.end()+260])
    links=sorted(set(re.findall(r'href="(https?://[^"]+)"',raw)))
    print('EXTERNAL ARTIFACT LINKS',[x for x in links if any(k in x for k in ['zenodo','anonymous','huggingface','dataset','agntcy'])][:15])
