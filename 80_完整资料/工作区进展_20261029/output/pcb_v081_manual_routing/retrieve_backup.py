from run import call,O
import json,base64,hashlib
b=call('return __v081Backup;')
data=base64.b64decode(b.pop('base64'))
assert len(data)==b['fileSize']
(O/'修改前_当前V080E完整备份.epro2').write_bytes(data)
b['sha256']=hashlib.sha256(data).hexdigest()
(O/'before.json').write_text(json.dumps(b,ensure_ascii=False,indent=2))
print(json.dumps({'fileSize':len(data),'sha256':b['sha256'],'boards':{k:len(v['components']) for k,v in b['boards'].items()}},ensure_ascii=False))
