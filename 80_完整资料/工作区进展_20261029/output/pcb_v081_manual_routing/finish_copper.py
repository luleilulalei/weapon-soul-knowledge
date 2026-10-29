from pathlib import Path
import subprocess,sys
O=Path(__file__).resolve().parent
for script,args in [('power.py',[]),('import_routes.py',['power']),('pour_reload.py',['power']),('import_routes.py',['blade']),('pour_reload.py',['blade'])]:
 print('STAGE',script,*args,flush=True);subprocess.run([sys.executable,str(O/script),*args],check=True)
