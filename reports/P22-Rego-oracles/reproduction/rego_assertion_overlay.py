"""Generate typed native assertions under an explicitly selected decision contract.

Copyright 2026 Ezekiel Ologunde. MIT; see the authored-code licence notice.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

HELPERS='''_typed_contract_denied(a, d) if {
    is_boolean(a)
    is_set(d)
    a == false
}
_typed_contract_denied(a, d) if {
    is_boolean(a)
    is_set(d)
    count(d) > 0
}
_typed_contract_permitted(a, d) if {
    is_boolean(a)
    is_set(d)
    a == true
    count(d) == 0
}
'''

def generate(package,cases,contract):
    if contract!='bool-allow-deny-overrides':raise ValueError('An explicit supported decision contract is required')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*',package):raise ValueError('Unsupported package spelling')
    output=['package '+package,'import rego.v1','',HELPERS]
    seen=set()
    for case in cases:
        ident=case['case_id']
        if not re.fullmatch('[A-Za-z0-9_]+',ident) or ident in seen:raise ValueError('Invalid or duplicate case identity')
        seen.add(ident)
        expected=case['expected']
        if expected not in ('allow','deny') or not isinstance(case['input'],dict):raise ValueError('Explicit expected decision and JSON-object input required')
        helper='_typed_contract_permitted' if expected=='allow' else '_typed_contract_denied'
        value=json.dumps(case['input'],ensure_ascii=True,sort_keys=True,allow_nan=False)
        output.append('test_typed_assertion_'+ident+' if {\n    '+helper+'(allow, deny) with input as '+value+'\n}\n')
    return '\n'.join(output)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True)
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--contract',choices=['bool-allow-deny-overrides'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    cases=json.loads(args.cases.read_text(encoding='utf-8'))
    text=generate(args.package,cases,args.contract)
    args.output.write_text(text,encoding='utf-8')
    print(json.dumps({'cases':len(cases),'contract':args.contract,'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'application_contract_inferred':False}))

if __name__=='__main__':main()
