"""An explicit feature contract for the inspected synthetic dataset revision.

Schema hygiene only: this does not certify real-world observability or remove all
statistical leakage. Identity/join fields remain outside the feature projection.
"""
FEATURES=frozenset({'timestamp','date','weekday','hour','after_hours','browser_used',
    'client_type','ja4_archetype','tls_version','destination_domain','session_duration_sec',
    'requests','dns_queries','upload_kb','download_kb','vpn_used','upload_download_ratio'})
JOIN_FIELDS=frozenset({'session_id','employee_id'})
EXCLUDED=frozenset({'session_type','minutes_since_resource','is_violation','scenario_id',
    'scenario_name','risk','trigger_reason','resource_accessed','resource_sensitivity','ai_service'})

def validate_feature_columns(columns):
    columns=set(columns)
    unexpected=columns-FEATURES
    if unexpected:raise ValueError('Undeclared or non-feature columns: '+', '.join(sorted(unexpected)))
    required={'destination_domain','upload_kb','download_kb'}
    if not required<=columns:raise ValueError('Missing required feature columns')
    return True

def project_record(row):
    unknown=set(row)-FEATURES-JOIN_FIELDS-EXCLUDED
    if unknown:raise ValueError('Unreviewed source columns: '+', '.join(sorted(unknown)))
    features={k:v for k,v in row.items() if k in FEATURES}
    validate_feature_columns(features)
    return {'features':features,'join_metadata':{k:row[k] for k in JOIN_FIELDS if k in row}}
