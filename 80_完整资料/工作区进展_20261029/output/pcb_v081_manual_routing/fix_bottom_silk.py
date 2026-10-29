from run import call,O
from engine import parse_source
import json,time
plan=json.loads((O/'silkscreen_plan.json').read_text());before=json.loads((O/'before.json').read_text())['boards'];changed={}
for name in ['main','power','blade']:
 d=json.loads((O/(name+'_final_snapshot.json')).read_text());uuid=d['uuid'];items=[(h['type'],h['id'])for h,a in parse_source(d['source'])if a.get('layerId')==4 and(h['type']=='STRING'or h['type']=='ATTR'and(a.get('valueVisible')or a.get('keyVisible')))]
 call('await __v081Open('+json.dumps(uuid)+');return true;')
 for start in range(0,len(items),20):
  code='if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='+json.dumps(uuid)+')throw Error("Wrong board");'
  for kind,pid in items[start:start+20]:code+='if(!await eda.pcb_Primitive'+('String'if kind=='STRING'else'Attribute')+'.modify('+json.dumps(pid)+',{mirror:false}))throw Error("Mirror update failed");'
  call(code+'return true;');time.sleep(2)
 visible=[l['id']for l in before[name]['layers']if l['layerStatus']==1]
 call('await eda.pcb_Layer.setLayerVisible('+json.dumps(visible)+',true);await eda.pcb_Layer.selectLayer(1);return true;');time.sleep(2)
 call('if(!await eda.pcb_Document.save())throw Error("Save failed");return true;')
 changed[name]=items;print(name,'corrected bottom texts',len(items),flush=True)
 for p in plan[name]['labels']:p['mirror']=False
(O/'bottom_silk_correction.json').write_text(json.dumps(changed,indent=2));(O/'silkscreen_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
