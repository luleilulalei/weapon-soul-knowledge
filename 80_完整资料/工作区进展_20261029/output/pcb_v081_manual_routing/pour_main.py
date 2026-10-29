from run import call,O
import json
code="""if((await eda.dmt_Project.getCurrentProjectInfo())?.uuid!=='71258413d4d54bf2b2153098bd2b9fa5')throw Error('Wrong project');await __v081Open('5354a7bf4c630a18');
const specs=[['GND',1,'V081_GND_L1'],['GND',15,'V081_GND_L2'],['+3V3',16,'V081_3V3_L3'],['GND',2,'V081_GND_L4']];
const out=[];for(const [net,layer,name] of specs){let p=(await eda.pcb_PrimitivePour.getAll()).find(x=>x.getState_PourName()===name);if(!p){const poly=eda.pcb_MathPolygon.createPolygon(['R',-19.65/.0254,.35/.0254,39.3/.0254,49.3/.0254,0,0]);p=await eda.pcb_PrimitivePour.create(net,layer,poly,'solid',false,name,5,10,false);if(!p)throw Error('Pour create failed');await new Promise(r=>setTimeout(r,2000));}await p.rebuildCopperRegion();out.push(p.getState_PrimitiveId());await new Promise(r=>setTimeout(r,2000));}
await eda.pcb_Document.save();return {pours:out,source:await eda.sys_FileManager.getDocumentSource(),drc:await eda.pcb_Drc.check(true,false,true)};"""
d=call(code);(O/'main_native_poured_check.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print('pours',d['pours']);print([(v['name'],v.get('count'))for v in d['drc']])
