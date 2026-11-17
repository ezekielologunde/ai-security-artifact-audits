import argparse,json
from pathlib import Path
from .core import analyze

def main():
    parser=argparse.ArgumentParser(description='Revision-bound documentation/artifact consistency overlay')
    parser.add_argument('command',choices=['analyze'])
    parser.add_argument('--snapshot',required=True,type=Path)
    parser.add_argument('--scanner-report',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    snapshot=json.loads(args.snapshot.read_text(encoding='utf-8'))
    report=json.loads(args.scanner_report.read_text(encoding='utf-8')) if args.scanner_report else None
    result=analyze(snapshot,report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'claims':len(result['overlay']['claim_assessments']),'scanner_binding':result['overlay']['scanner_binding'],'output':str(args.output)}))

if __name__=='__main__':main()
