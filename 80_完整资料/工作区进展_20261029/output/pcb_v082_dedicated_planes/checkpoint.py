from run import call,O
import json,base64,hashlib,sys
name=sys.argv[1]
d=call("const f=await eda.sys_FileManager.getProjectFile("+json.dumps(name)+",undefined,'epro2');if(!f||f.size<10000)throw Error('Backup failed');return {name:f.name,size:f.size,base64:await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(String(r.result).split(',')[1]);r.onerror=rej;r.readAsDataURL(f);})};")
raw=base64.b64decode(d.pop('base64'));path=O/(name+'.epro2');assert not path.exists();path.write_bytes(raw);d.update({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest()});(O/(name+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));print(d)
