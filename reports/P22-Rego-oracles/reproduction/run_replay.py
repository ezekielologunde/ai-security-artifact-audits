from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent
steps=['replay_reparo_corpus.py','analyze_reparo_corpus_replay.py','followup_reparo_typed_assertions.py','analyze_reparo_typed_followup.py','run_reparo_assertion_overlay_v2.py','analyze_reparo_assertion_overlay.py','verify_results.py']
for script in steps:
    print('STEP '+script,flush=True)
    subprocess.run([sys.executable,str(root/script)],cwd=root,check=True)
