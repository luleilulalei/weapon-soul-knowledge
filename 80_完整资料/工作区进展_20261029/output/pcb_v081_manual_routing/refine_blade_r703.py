from run import call,O
import json
changes={'R703':(0,24.6,180)}
call("await __v081Open('cff5d61a47594b34');return true;")
code='const m='+json.dumps(changes)+";const cs=JSON.parse(JSON.stringify(await eda.pcb_PrimitiveComponent.getAll()));for(const [r,[x,y,a]] of Object.entries(m)){const c=cs.find(c=>c.designator===r);if(!c)throw Error(r);await eda.pcb_PrimitiveComponent.modify(c.primitiveId,{x:x/.0254,y:y/.0254,rotation:a});}await new Promise(r=>setTimeout(r,6000));await eda.pcb_Document.save();const b={uuid:'cff5d61a47594b34',source:await eda.sys_FileManager.getDocumentSource(),components:await eda.pcb_PrimitiveComponent.getAll(),netlist:await eda.pcb_Net.getNetlist(),layers:await eda.pcb_Layer.getAllLayers(),pads:{}};for(const c of JSON.parse(JSON.stringify(b.components)))b.pads[c.designator]=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.primitiveId);return b;"
b=call(code);allb=json.loads((O/'after_layout.json').read_text());allb['boards']['blade']=b;(O/'after_layout.json').write_text(json.dumps(allb,ensure_ascii=False,indent=2));(O/'blade_r703_refinement.json').write_text(json.dumps(changes,indent=2));print('refined',list(changes))
