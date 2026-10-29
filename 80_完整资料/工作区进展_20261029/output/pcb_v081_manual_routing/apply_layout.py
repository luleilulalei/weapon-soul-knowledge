from run import call,O
import json,time,base64
B=json.loads((O/'before.json').read_text())['boards'];M=json.loads((O/'layout_plan.json').read_text())
out={}
for name in ['main','power','blade']:
 b=B[name];by={c['designator']:c for c in b['components']};id=b['uuid']
 call("if((await eda.dmt_Project.getCurrentProjectInfo())?.uuid!=='71258413d4d54bf2b2153098bd2b9fa5')throw Error('Project changed');await __v081Open("+json.dumps(id)+");return true;")
 m=list(M[name].items())
 for start in range(0,len(m),20):
  changes=[{'id':by[r]['primitiveId'],'ref':r,'old':{k:by[r][k] for k in ['x','y','rotation']},'next':{'x':x/.0254,'y':y/.0254,'rotation':a}} for r,(x,y,a) in m[start:start+20]]
  code="const changes="+json.dumps(changes)+";if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=="+json.dumps(id)+")throw Error('Board changed');const all=JSON.parse(JSON.stringify(await eda.pcb_PrimitiveComponent.getAll()));for(const c of changes){const p=all.find(p=>p.primitiveId===c.id);if(!p||Math.abs(p.x-c.old.x)>.01||Math.abs(p.y-c.old.y)>.01)throw Error('Stale '+c.ref);}for(const c of changes)await eda.pcb_PrimitiveComponent.modify(c.id,c.next);return changes.map(c=>c.ref);"
  print(name,call(code),flush=True);time.sleep(6)
 call('if(!await eda.pcb_Document.save())throw Error("Save failed");return true;')
 out[name]=call("const b={uuid:"+json.dumps(id)+",source:await eda.sys_FileManager.getDocumentSource(),components:await eda.pcb_PrimitiveComponent.getAll(),netlist:await eda.pcb_Net.getNetlist(),layers:await eda.pcb_Layer.getAllLayers(),pads:{},drc:await eda.pcb_Drc.check(true,false,true)};for(const c of JSON.parse(JSON.stringify(b.components)))b.pads[c.designator]=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.primitiveId);return b;")
 (O/'after_layout.json').write_text(json.dumps({'boards':out},ensure_ascii=False,indent=2))
 print(name,'saved and captured',flush=True)
call("await __v081Open('5354a7bf4c630a18');return true;")
f=call("const f=await eda.sys_FileManager.getProjectFile('V081_Layout_Checkpoint',undefined,'epro2');return await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(String(r.result).split(',')[1]);r.onerror=rej;r.readAsDataURL(f);});")
(O/'V081_调整布局后检查点.epro2').write_bytes(base64.b64decode(f))
print('layout checkpoint exported',flush=True)
