from pathlib import Path
from PIL import Image
import json,re
R=Path(__file__).resolve().parents[1];rows=json.loads((R/'screens.json').read_text());ids={r['id'] for r in rows};retired={'A28','A29','A20B','A30','A31'};issues=[]
assert not ids & retired
for s in rows:
 id=s['id'];svg=(R/'screens'/f'{id}.svg').read_text()
 if Image.open(R/'screens'/f'{id}.png').size!=(1688,780):issues.append(id+' dimensions')
 if re.search('保存更正|内容不准确，纠正它|要留下这段经历|允许雾光记住|重试保存这段摘要',svg):issues.append(id+' retired affordance')
 for h in s.get('hotspots',[])+s.get('events',[]):
  t=h.get('target')
  if t in retired or (t and t.startswith('A') and t not in ids):issues.append(id+' bad target '+t)
  if h in s.get('hotspots',[]) and not (0<=h['x']<=844 and 0<=h['y']<=390 and h['x']+h['w']<=844 and h['y']+h['h']<=390):issues.append(id+' bounds '+h['label'])
assert not issues,issues
out={'version':'V1.4','screens':len(rows),'retired':sorted(retired),'issues':issues,'checks':['no retired screen output or route','all app PNG sizes','hotspot bounds','visible edit/save affordances removed'],'limitations':['static UI and offline fixtures only','no hardware, live authentication, deletion execution or IMU validation','cross-object aggregate deletion combinations are not a complete runtime data model']}
(R/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(out)
