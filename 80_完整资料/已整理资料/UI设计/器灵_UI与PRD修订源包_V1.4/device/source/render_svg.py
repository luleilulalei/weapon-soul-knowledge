from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,json
from PIL import Image
P=Path(__file__).resolve().parent.parent
files=sorted((P/'boards').glob('*.svg'))+sorted((P/'screens').glob('*.svg'))
def render(p):
 subprocess.run(['inkscape',str(p),'--export-type=png','--export-filename='+str(p.with_suffix('.png'))],check=True,capture_output=True)
 with Image.open(p.with_suffix('.png')) as im: im.verify()
 return str(p.relative_to(P))
with ThreadPoolExecutor(max_workers=4) as pool: rendered=list(pool.map(render,files))
(P/'qa/svg_render_validation.json').write_text(json.dumps({'status':'pass','renderer':'Inkscape','svg_count':len(rendered),'files':rendered},ensure_ascii=False,indent=2))
print('Rendered and verified',len(rendered),'SVGs')
