#!/usr/bin/env python3
"""Python replay of ONLY the prototype slash-candidate thresholds.
Not C# execution, not a gameplay replay, and not a calibrated physical IMU model.
Uses fixture's declared axes, zero bias, 1-second static prefix and no pose context.
"""
import csv, json, math, pathlib
root=pathlib.Path(__file__).resolve().parents[1]
p=root/'unity/Assets/SpiritIMU/Resources/sample_raw.csv'
rows=list(csv.DictReader(p.open()))
assert len(rows)>=101
for r in rows[:101]:
    assert sum(float(r[k])**2 for k in ['gx','gy','gz'])<12**2
    assert abs(math.sqrt(sum(float(r[k])**2 for k in ['ax','ay','az']))-1)<.12
armed=True;last=-10000;out=[]
for r in rows[101:]:
    t=int(r['tMs']);x,y,z=(float(r[k]) for k in ['gx','gy','gz'])
    if math.sqrt(x*x+y*y+z*z)<12: armed=True
    action=None
    if armed and t-last>=300:
        if x>120 and abs(x)>1.4*abs(y) and abs(x)>1.4*abs(z): action='DownSlash'
        elif abs(z)>120 and abs(z)>1.4*abs(x) and abs(z)>1.4*abs(y): action='LeftSlash' if z>0 else 'RightSlash'
    if action:
        armed=False;last=t;out.append({'tMs':t,'candidate':action,'source':'synthetic Python replay'})
assert out and {e['candidate'] for e in out}=={'LeftSlash','RightSlash','DownSlash'}
assert all(b['tMs']-a['tMs']>=300 for a,b in zip(out,out[1:]))
result={'scope':'Independent Python slash-candidate replay; C# and Unity not executed; no gameplay/pose/physical accuracy assertion','rows':len(rows),'durationMs':int(rows[-1]['tMs'])-int(rows[0]['tMs']),'events':out}
(root/'validation/python_candidate_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
