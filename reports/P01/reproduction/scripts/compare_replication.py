"""Compare replication security outcomes with measured-v2, excluding timing."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if Path(args.name).name != args.name or args.name in ('.', '..', 'measured-v2'):
        parser.error('Specify a separate result directory name')
    original = ROOT / 'experiment/results/measured-v2'
    replica = ROOT / 'experiment/results' / args.name
    def outcomes(directory):
        rows = json.loads((directory / 'runs.json').read_text())
        assert len(rows) == 720 and len({r['run_id'] for r in rows}) == 720
        return {r['run_id']: {'case': r['case'], 'ack': r['ack'],
                             'post': {k: {f: v[f] for f in ('allowed', 'reason')} for k, v in r['post'].items()},
                             'truth': {k: v for k, v in r['truth'].items() if k != 'admission_ms'}} for r in rows}
    assert outcomes(original) == outcomes(replica), 'Security outcomes differ'
    def verdicts(directory):
        rows = json.loads((directory / 'verifier_receipts.json').read_text())
        assert len(rows) == 1440
        return {(r['run_id'], r['feed']): r['evaluation']['verdict'] for r in rows}
    assert verdicts(original) == verdicts(replica), 'Closure verdicts differ'
    report = {'replication': args.name, 'runs': 720, 'evaluations': 1440,
              'security_outcomes_match': True, 'verdicts_match': True,
              'timing_compared': False, 'independent_attack_samples': False}
    (replica / 'comparison.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
