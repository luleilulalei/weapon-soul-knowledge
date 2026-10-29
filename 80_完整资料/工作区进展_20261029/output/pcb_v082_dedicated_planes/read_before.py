from run import call,O
import json
old=O.parent/'pcb_v081_manual_routing'
boards=json.loads((old/'after_layout.json').read_text())['boards'];out={'boards':{}}
for name,b in boards.items():
 code="if((await eda.dmt_Project.getCurrentProjectInfo())?.uuid!=='71258413d4d54bf2b2153098bd2b9fa5')throw Error('Wrong project');await __v081Open("+json.dumps(b['uuid'])+");const b={uuid:(await eda.dmt_SelectControl.getCurrentDocumentInfo()).uuid,source:await eda.sys_FileManager.getDocumentSource(),components:await eda.pcb_PrimitiveComponent.getAll(),layers:await eda.pcb_Layer.getAllLayers(),netlist:await eda.pcb_Net.getNetlist(),pads:{}};for(const c of JSON.parse(JSON.stringify(b.components)))b.pads[c.designator]=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.primitiveId);return b;"
 d=call(code);assert d['uuid']==b['uuid'];out['boards'][name]=d
 (O/'before.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(name,len(d['components']),len(d['source']),flush=True)
