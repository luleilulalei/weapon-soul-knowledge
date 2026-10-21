from pathlib import Path
import zipfile,hashlib,json
B=Path(__file__).resolve().parent.parent;O=B/'output';O.mkdir(exist_ok=True)
inner=O/'Spirit_V0.7.1_KiCad_Import_Project.zip'
with zipfile.ZipFile(inner,'w',zipfile.ZIP_DEFLATED,9) as z:
 for p in sorted((B/'project').rglob('*')):
  if p.is_file():z.write(p,Path('Spirit_V0.7.1_Import_Project')/p.relative_to(B/'project'))
files=[]
for folder in ['project','source','validation']:
 for p in (B/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and not p.suffix=='.pdf':files.append(p)
files += [p for p in B.iterdir() if p.is_file() and p.suffix in ['.md','.csv','.json','.pdf']]+[inner]
manifest={str(p.relative_to(B)): {'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
mp=O/'文件校验清单.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
outer=O/'器灵_麦克风精简原理图_V0.7.1.zip'
with zipfile.ZipFile(outer,'w',zipfile.ZIP_DEFLATED,9) as z:
 for p in sorted(files):z.write(p,p.relative_to(B))
 z.write(mp,'文件校验清单.json')
print(json.dumps({'file':str(outer),'size':outer.stat().st_size,'sha256':hashlib.sha256(outer.read_bytes()).hexdigest(),'files':len(files)+1,'inner_import':str(inner)},ensure_ascii=False,indent=2))
