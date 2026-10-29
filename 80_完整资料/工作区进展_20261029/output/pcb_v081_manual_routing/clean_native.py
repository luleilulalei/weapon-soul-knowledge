from run import call,O
import json,sys
name=sys.argv[1]if len(sys.argv)>1 else'main';a=json.loads((O/(name+'_native_delta.json')).read_text());ids=[x['id']for x in a['remove']]
if ids:
 code='const ids='+json.dumps(ids)+';for(const id of ids){const p=await eda.pcb_PrimitiveLine.get(id);if(!p)throw Error("Missing expected old track");await eda.pcb_PrimitiveLine.modify(id,{primitiveLock:false});}await new Promise(r=>setTimeout(r,1500));const ok=await eda.pcb_PrimitiveLine.delete(ids);await new Promise(r=>setTimeout(r,5000));if(!ok)throw Error("Delete failed");return true;'
 print(call(code))
d=call('await eda.pcb_Document.save();return {source:await eda.sys_FileManager.getDocumentSource(),drc:await eda.pcb_Drc.check(true,false,true)};');(O/(name+'_native_route_check.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));print('cleaned and checked')
