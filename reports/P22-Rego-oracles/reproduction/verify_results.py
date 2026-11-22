from pathlib import Path
import json
root=Path(__file__).resolve().parent
expected=json.loads((root/'EXPECTED.json').read_text())
checked=0
for name,fields in expected.items():
    actual=json.loads((root/'results'/name).read_text())
    for key,value in fields.items():
        assert actual[key]==value,(name,key,actual[key],value)
        checked+=1
print(json.dumps(dict(aggregate_fields_verified=checked,all_equal=True)))
