from run import call,O
import json
from engine import parse_source
v=json.loads((O/'after_layout.json').read_text());b=v['boards']['main'];ids={a['num']:h['id'] for h,a in parse_source(b['source']) if h['type']=='PAD' and a.get('num') in ['TP114','TP115']};print(ids)
code="if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='5354a7bf4c630a18')throw Error('Wrong board');"
for k,y in [('TP114',6.1849),('TP115',4.9149)]:code+='await eda.pcb_PrimitivePad.modify('+json.dumps(ids[k])+',{x:-12.5/.0254,y:'+str(y)+'/.0254});'
d=call(code+"await new Promise(r=>setTimeout(r,5000));await eda.pcb_Document.save();return {source:await eda.sys_FileManager.getDocumentSource(),pads:await eda.pcb_PrimitivePad.getAll()};")
v['boards']['main']['source']=d['source'];(O/'after_layout.json').write_text(json.dumps(v,ensure_ascii=False,indent=2));(O/'debug_final_pose.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print('debug pads moved and reread')
