from engine import *
from shapely.prepared import prep
import random
O=Path(__file__).resolve().parent
out={}
for name in ['main','power','blade']:
 b=Board(name);rows=parse_source(b.b['source']);comp={r:transform(b.L[r]['court'],p) for r,p in b.P.items()};targets=[];fixed={3:[],4:[]};updates={}
 def rect(x,y,w,h,a):return rotate(box(x-w/2,y-h/2,x+w/2,y+h/2),a,origin=(x,y))
 for h,a in rows:
  text=a.get('text') if h['type']=='STRING' else a.get('value')if h['type']=='ATTR'and a.get('key')=='Designator'and a.get('valueVisible') else None
  if not text:continue
  ref=text if text in b.P or text in b.pads else text.split('-')[0] if text.split('-')[0] in b.P else None
  if ref:
   ly=3 if (b.P[ref]['layer']if ref in b.P else b.pads[ref]['layer']) in [1,12] else 4
   shape=comp[ref]if ref in comp else b.pads[ref]['poly'];targets.append({'id':h['id'],'kind':h['type'],'ref':ref,'text':text,'layer':ly,'shape':shape,'old':a})
  elif a.get('layerId')in [3,4]:
   if 'V080' in text or text=='V074P':
    v='V081' if text.startswith('V080')and name=='main' else 'V081 POWER'if name=='power' else 'BLADE ADAPTER V081'if 'ADAPTER' in text else'V081'
    updates[h['id']]={'text':v};text=v
   f=a.get('fontSize',24)*MM;fixed[a['layerId']].append(rect(a['x']*MM,a['y']*MM,max(.5,len(text)*f*.75+.1),f+.14,a.get('angle',0)))
 plan=[]
 for ly in [3,4]:
  copper=1 if ly==3 else 2
  ob=[g.buffer(.08)for r,g in comp.items()if b.P[r]['layer']==copper]
  ob+=[p['poly'].buffer(.12)for p in b.pads.values()if p['layer'] in [copper,12]]
  ob+= [h.buffer(.3)for h in b.holes]+[g.buffer(.1)for g in fixed[ly]]
  # Vias are treated as mask openings for conservative text placement.
  routed=json.load(open(O/(name+'_routes.json')))
  ob +=[Point(v['x'],v['y']).buffer(v['diameter']/2+.1)for v in routed['vias']]
  obs=prep(unary_union(ob));valid=b.outline.buffer(-.4);tt=[t for t in targets if t['layer']==ly];candidates={}
  for t in tt:
   g=t['shape'];cx,cy=g.centroid.coords[0];minx,miny,maxx,maxy=g.bounds;ls=[]
   for fs in [24,20]:
    f=fs*MM;w=len(t['text'])*f*.75+.12;hh=f+.12
    for angle in [0,90]:
     ww,he=(w,hh)if angle==0 else(hh,w)
     xs=[cx+i*.25 for i in range(-24,25)];ys=[cy+i*.25 for i in range(-24,25)]
     xs+=[t['old']['x']*MM];ys+=[t['old']['y']*MM]
     for x in xs:
      for y in ys:
       q=box(x-ww/2,y-he/2,x+ww/2,y+he/2)
       if not valid.covers(q)or obs.intersects(q):continue
       d=g.distance(q)
       if d>3:continue
       score=d*4+math.hypot(x-cx,y-cy)*.4+(angle==90)*.15+(24-fs)*.1
       if abs(x-t['old']['x']*MM)+abs(y-t['old']['y']*MM)<.01:score-=.6
       ls.append((score,x,y,angle,fs,q))
   candidates[t['id']]=sorted(ls,key=lambda x:x[0])[:200]
  best=None
  for trial in range(100):
   random.seed(trial);order=sorted(tt,key=lambda t:len(candidates[t['id']])*(1 if trial==0 else random.uniform(.5,1.5)));occupied=[];chosen=[];total=0
   for t in order:
    options=[v for v in candidates[t['id']]if not any(v[5].distance(z)<.1 for z in occupied)]
    if not options:continue
    q=options[0];occupied.append(q[5]);total+=q[0];chosen.append({'id':t['id'],'kind':t['kind'],'ref':t['ref'],'text':t['text'],'x':q[1],'y':q[2],'rotation':q[3],'fontSize':q[4],'layer':ly,'mirror':False})
   rank=(len(tt)-len(chosen),total)
   if best is None or rank<best[0]:best=(rank,chosen)
  print(name,ly,'missing/score',best[0],flush=True)
  missing=[t['ref']for t in tt if t['id']not in {v['id']for v in best[1]}];assert not missing,missing
  plan+=best[1]
 out[name]={'labels':plan,'texts':updates}
(O/'silkscreen_plan.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
