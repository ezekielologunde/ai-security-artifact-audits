def normalize(result):
    rows=[]
    for c in result['conditions']:
        tools=[t for m in c['native_messages']['data'] if m['type']=='assistant' for t in m.get('content',[]) if t.get('type')=='tool']
        assert len(tools)==1
        rows.append({'id':c['id'],'configured_effect':c['configured_effect'],'reply':c['reply'],'before':c['before'],'after':c['after'],'expected_after':c['expected_after'],'match':c['match'],'pending_seen':c['pending_request'] is not None,'pre_reply_file_unchanged':c['pre_reply_file_unchanged'],'write_advertised':c['write_advertised'],'tool_name':tools[0]['name'],'tool_input':tools[0]['state']['input'],'error_type':tools[0]['state'].get('error',{}).get('type'),'completion_observed':c['native_terminal']['type'] in ['idle','completed_tool_error']})
    return rows
