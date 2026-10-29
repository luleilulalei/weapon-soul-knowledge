import subprocess,json,sys,base64
from pathlib import Path
O=Path(__file__).resolve().parent
CLI='/Users/qijiankang/.local/bin/lceda-pro'
SESSION='cce5c8a6-b126-4ca8-a679-71eb4d993e06'
def call(code,timeout=180000):
 r=subprocess.run([CLI,'invoke','--ext-uuid','eda','--session',SESSION,'--timeout',str(timeout),'--code',code],capture_output=True,text=True,timeout=timeout/1000+30)
 if r.returncode: raise RuntimeError(r.stdout[:3000]+r.stderr[:3000])
 a=json.loads(r.stdout)
 if not a.get('ok'):raise RuntimeError(str(a)[:6000])
 return a.get('value')
if __name__=='__main__':
 p=Path(sys.argv[1]);v=call(p.read_text());p.with_suffix('.result.json').write_text(json.dumps(v,ensure_ascii=False,indent=2));print(json.dumps(v,ensure_ascii=False)[:10000])
