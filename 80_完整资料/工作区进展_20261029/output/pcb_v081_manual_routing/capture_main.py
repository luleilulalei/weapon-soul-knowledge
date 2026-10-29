from run import call,O
import base64
s=call("const t=(await eda.dmt_SelectControl.getCurrentDocumentInfo()).tabId;await eda.dmt_EditorControl.zoomToAllPrimitives(t);await new Promise(r=>setTimeout(r,1000));const b=await eda.dmt_EditorControl.getCurrentRenderedAreaImage(t);return await new Promise(r=>{const f=new FileReader();f.onload=()=>r(String(f.result).split(',')[1]);f.readAsDataURL(b);});")
(O/'main_native_current.webp').write_bytes(base64.b64decode(s));print('captured')
