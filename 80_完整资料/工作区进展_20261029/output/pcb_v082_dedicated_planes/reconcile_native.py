from run import call,O
import json,sys,math
name=sys.argv[1];uuid=json.loads((O/'after_layout.json').read_text())['boards'][name]['uuid'];a=json.loads((O/(name+'_native_delta.json')).read_text())
code='if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='+json.dumps(uuid)+')throw Error("Wrong board");'
ids=[x['id'] for x in a['remove']]
if ids:
 code+='const ids='+json.dumps(ids)+';for(const id of ids)await eda.pcb_PrimitiveLine.modify(id,{primitiveLock:false});await new Promise(r=>setTimeout(r,1500));if(!await eda.pcb_PrimitiveLine.delete(ids))throw Error("Delete failed");await new Promise(r=>setTimeout(r,3000));'
added=[]
for t in a['add']:
 if math.dist(*t['points'])<.003:continue
 p,q=t['points'];args=[t['net'],t['layer'],p[0]/.0254,p[1]/.0254,q[0]/.0254,q[1]/.0254,t['width']/.0254,True]
 code+='if(!await eda.pcb_PrimitiveLine.create(...'+json.dumps(args)+'))throw Error("Create failed");';added.append(t)
code+='await new Promise(r=>setTimeout(r,5000));if(!await eda.pcb_Document.save())throw Error("Save failed");return {source:await eda.sys_FileManager.getDocumentSource(),drc:await eda.pcb_Drc.check(true,false,true)};'
d=call(code);(O/(name+'_native_route_check.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));print('removed',len(ids),'added',len(added),flush=True)
