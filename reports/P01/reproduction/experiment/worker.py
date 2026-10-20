import json,sys
from runtime import worker
print(json.dumps(worker(sys.argv[1],sys.argv[2])))
