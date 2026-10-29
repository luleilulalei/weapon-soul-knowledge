from run import call,O
import json,base64,sys,time
boards=json.loads((O/'after_layout.json').read_text())['boards'];D=O/'delivery'
for name in sys.argv[1:] or ['main','power','blade']:
 uuid=boards[name]['uuid'];call('await __v081Open('+json.dumps(uuid)+');return true;')
 for side,layers in [('top',[1,3,11,12]),('bottom',[2,4,11,12])]:
  old=call('if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='+json.dumps(uuid)+')throw Error("Wrong board");const old=(await eda.pcb_Layer.getAllLayers()).filter(l=>l.layerStatus===1).map(l=>l.id);await eda.pcb_Layer.selectLayer('+str(layers[0])+');await eda.pcb_Layer.setLayerVisible('+json.dumps(layers)+',true);return old;')
  time.sleep(3)
  try:
   code='const tab=(await eda.dmt_SelectControl.getCurrentDocumentInfo()).tabId;const b=await eda.dmt_EditorControl.getCurrentRenderedAreaImage(tab);return await new Promise((resolve,reject)=>{const f=new FileReader();f.onload=()=>resolve(String(f.result).split(",")[1]);f.onerror=reject;f.readAsDataURL(b);});'
   r=call(code);p=D/(name+'_'+side+'.webp');p.write_bytes(base64.b64decode(r));print(name,side,'captured',flush=True)
  finally:call('await eda.pcb_Layer.setLayerVisible('+json.dumps(old)+',true);await eda.pcb_Layer.selectLayer(1);return true;')
call("await __v081Open('5354a7bf4c630a18');return true;")
