import { readFileSync,writeFileSync } from 'node:fs';
import { verifyClosure } from '../work/closure-baseline/src/verify-closure.mjs';
const input=JSON.parse(readFileSync(process.argv[2],'utf8'));
const output=input.map(x=>({run_id:x.run_id,feed:x.feed,evaluation:verifyClosure(x.bundle)}));
writeFileSync(process.argv[3],JSON.stringify(output,null,2));
const errors=output.filter(x=>x.evaluation.runner_state==='VALIDATION_ERROR');
console.log(JSON.stringify({evaluations:output.length,validation_errors:errors.length,first_error:errors[0]??null}));
if(errors.length)process.exitCode=1;
