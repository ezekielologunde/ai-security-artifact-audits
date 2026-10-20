"""Portable wrapper; original measured implementation remains byte-for-byte intact."""
import argparse,importlib.util,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--repeats',type=int,default=5)
 p.add_argument('--name',required=True,help='New result directory name, e.g. replication-001')
 p.add_argument('--node',default=shutil.which('node'))
 args=p.parse_args()
 if args.repeats<1:p.error('--repeats must be positive')
 if not args.name or Path(args.name).name!=args.name or args.name in ['.','..']:p.error('--name must be a directory name without path separators')
 if not args.node:p.error('Node 20+ is required on PATH, or pass --node /path/to/node')
 if not (ROOT/'datasets/upstream/agenttrap/hf_dataset/data/tasks.jsonl').exists():p.error('Run python scripts/restore_data.py first')
 if not (ROOT/'work/closure-baseline/node_modules/ajv').exists():p.error('Install baseline dependencies with npm install --ignore-scripts in work/closure-baseline')
 sys.path.insert(0,str(ROOT/'experiment'))
 spec=importlib.util.spec_from_file_location('measured_runner',ROOT/'experiment/run_experiment.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.NODE=Path(args.node)
 sys.argv=[str(ROOT/'experiment/run_experiment.py'),'--repeats',str(args.repeats),'--name',args.name]
 module.main()
if __name__=='__main__':main()
