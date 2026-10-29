from run import call,O
import json,sys,time,hashlib
name=sys.argv[1];plan=json.loads((O/(name+'_routes.json')).read_text());assert not plan['errors'],plan['errors']
b=json.loads((O/'after_layout.json').read_text())['boards'][name];id=b['uuid'];mf=O/(name+'_import_manifest.json')
manifest=json.loads(mf.read_text()) if mf.exists() else {'tracks':[],'vias':[]}
call("if((await eda.dmt_Project.getCurrentProjectInfo())?.uuid!=='71258413d4d54bf2b2153098bd2b9fa5')throw Error('Wrong project');await __v081Open("+json.dumps(id)+");return true;")
for kind in ['tracks','vias']:
 key=lambda p:json.dumps(p,sort_keys=True)
 desired={key(p) for p in plan[kind]}
 gone=[v for v in manifest[kind] if key(v['plan']) not in desired]
 for start in range(0,len(gone),20):
  ids=[v['id'] for v in gone[start:start+20]]
  api='pcb_PrimitiveLine' if kind=='tracks' else 'pcb_PrimitiveVia'
  live=call('const requested=new Set('+json.dumps(ids)+');return (await eda.'+api+'.getAll()).map(p=>p.getState_PrimitiveId()).filter(id=>requested.has(id));')
  if kind=='tracks' and live:call('for(const id of '+json.dumps(live)+'){await eda.pcb_PrimitiveLine.modify(id,{primitiveLock:false});}await new Promise(r=>setTimeout(r,1000));return true;')
  if live:assert call('return await eda.'+api+'.delete('+json.dumps(live)+');'),('delete failed',live)
  manifest[kind]=[v for v in manifest[kind] if v['id'] not in ids];mf.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 existing={key(v['plan']) for v in manifest[kind]}
 additions=[p for p in plan[kind] if key(p) not in existing]
 for start in range(0,len(additions),20):
  chunk=additions[start:start+20]
  code='const a='+json.dumps(chunk)+';const out=[];if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='+json.dumps(id)+")throw Error('Wrong board');"
  if kind=='tracks':code+="for(const t of a){const [a,b]=t.points;const p=await eda.pcb_PrimitiveLine.create(t.net,t.layer,a[0]/.0254,a[1]/.0254,b[0]/.0254,b[1]/.0254,t.width/.0254,true);out.push(p.getState_PrimitiveId());}"
  else:code+="for(const v of a){const p=await eda.pcb_PrimitiveVia.create(v.net,v.x/.0254,v.y/.0254,v.hole/.0254,v.diameter/.0254);out.push(p.getState_PrimitiveId());}"
  ids=call(code+'return out;')
  assert len(ids)==len(chunk)
  manifest[kind].extend({'id':x,'plan':p} for x,p in zip(ids,chunk));mf.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print(name,kind,len(manifest[kind]),'/',len(plan[kind]),flush=True);time.sleep(5)
call('if(!await eda.pcb_Document.save())throw Error("Save failed");return true;')
d=call('return {source:await eda.sys_FileManager.getDocumentSource(),drc:await eda.pcb_Drc.check(true,false,true)};');(O/(name+'_native_route_check.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));print(name,'saved native check',flush=True)
