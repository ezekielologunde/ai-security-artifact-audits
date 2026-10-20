"""Evidence-producing source adapter for the registered local fixture profile."""
import json
from pathlib import Path
from runtime import connection

DOMAINS=['AUTHORITY','EXECUTION','COMMITMENT','OPERATIONAL_STATE']

def residual(id,domain,active):
    return {'id':id,'class':domain,'disposition':'EXTINGUISH','presence':'PRESENT','effect':'ACTIVE' if active else 'INERT','root_linkage':'LIVE' if active else 'ENDED','settlement':'NOT_APPLICABLE','successor_id':None,'transfer_acceptance':'NOT_APPLICABLE','evidence_refs':['readback-'+id]}

def bundle(run_dir,case,feed):
    """Two snapshots with logical order stamps, not measured wall-clock times.

    snapshot fault deliberately violates the adapter's freshness contract;
    probe obtains a second raw observation of the same registered artifact.
    Explicitly unavailable sources remain UNKNOWN in both faithful feeds.
    """
    with connection(run_dir) as c:
        root=dict(c.execute("SELECT * FROM roots WHERE id='A'").fetchone())
        queued=c.execute("SELECT COUNT(*) FROM jobs WHERE root='A' AND state='QUEUED'").fetchone()[0]
    active=json.loads((Path(run_dir)/'residual.json').read_text(encoding='utf-8'))['active']
    unavailable=case['missing_source']
    if feed=='snapshot' and case['stale_adapter']:
        active=False
    scans=[]
    for index,stamp in enumerate([110,120]):
        scans.append({'scan_id':f'scan-{index}','observed_at_ms':stamp,'sources':[{
            'source_id':'local-inventory','coverage':'PARTIAL' if unavailable else 'COMPLETE',
            'attribution_coverage':'COMPLETE','stability_witness':None,'evidence_refs':['inventory-'+str(index)],
            'residuals':[residual('artifact','OPERATIONAL_STATE',active),residual('queue','EXECUTION',bool(queued))],
            'lineage_edges':[{'from':'$root','to':'artifact','type':'DERIVED_FROM','evidence_ref':'artifact-origin'}, {'from':'$root','to':'queue','type':'DERIVED_FROM','evidence_ref':'queue-origin'}]
        }]})
    return {'spec_version':'0.3','profile_id':'RISU_AGENT_CLOSURE_V0','time_basis':'BUNDLE_MONOTONIC_MS',
            'root':{'id':'agent-A','new_business_authority':'BLOCKED' if root['cut'] or root['issuer_blocked'] else 'ACTIVE','quiesced_at_ms':100,'quiescence_evidence_ref':'issuer-cut-readback'},
            'domain_bindings':[{'domain':d,'status':'COVERED','source_ids':['local-inventory'],'evidence_ref':None} for d in DOMAINS],
            'sources':[{'id':'local-inventory','domains':DOMAINS,'stability_contract':{'type':'BOUNDED_LAG','max_visibility_lag_ms':0}}],
            'scans':scans}
