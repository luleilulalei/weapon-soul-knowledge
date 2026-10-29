from run import call,O
import json
code="""if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='5354a7bf4c630a18')throw Error('Wrong board');const results=[];
for(const p of await eda.pcb_PrimitivePour.getAll()){if(!p.getState_PourName().startsWith('V081_'))continue;const x=-19.65/.0254,y=.35/.0254,r=19.65/.0254,t=49.65/.0254;const poly=eda.pcb_MathPolygon.createPolygon([x,y,'L',r,y,r,t,x,t,x,y]);await eda.pcb_PrimitivePour.modify(p.getState_PrimitiveId(),{complexPolygon:poly});await new Promise(r=>setTimeout(r,2000));const q=await eda.pcb_PrimitivePour.get(p.getState_PrimitiveId());const z=await q.rebuildCopperRegion();results.push({name:q.getState_PourName(),rebuilt:z!==undefined});await new Promise(r=>setTimeout(r,3000));}
await eda.pcb_Document.save();return {results,filled:await eda.pcb_PrimitivePoured.getAll(),source:await eda.sys_FileManager.getDocumentSource(),drc:await eda.pcb_Drc.check(true,false,true)};"""
d=call(code);(O/'main_native_poured_check.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print(d['results']);print('filled',len(d['filled']));print([(v['name'],v.get('count'))for v in d['drc']])
