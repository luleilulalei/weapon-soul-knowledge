from engine import *
from collections import Counter
O=Path(__file__).resolve().parent
before=json.loads((O/'before.json').read_text())['boards'];layout=json.loads((O/'after_layout.json').read_text())['boards'];silk=json.loads((O/'silkscreen_plan.json').read_text());results={}
def logical(d):
 arr=d['netlist'];arr=[arr]if isinstance(arr,str)else arr
 return sorted(json.dumps({k:{'ref':c['props'].get('Designator'),'footprint':c['props'].get('Footprint'),'pins':c['pinInfoMap']}for k,c in json.loads(s)['components'].items()},sort_keys=True)for s in arr)
def assignments(d):return {r:sorted((p['padNumber'],p['net'])for p in ps)for r,ps in d['pads'].items()}
def protected(rows):return {h['id']:a for h,a in rows if h['type']in ['REGION','RULE','RULE_TEMPLATE','RULE_SELECTOR','LAYER_PHYS']or(h['type']in['POLY','FILL']and a.get('layerId')in[11,12])}
for name in ['main','power','blade']:
 b=before[name];f=json.loads((O/(name+'_final_snapshot.json')).read_text());rows=parse_source(f['source']);original=parse_source(b['source']);errs=[]
 if f['drc']!=[]:errs.append('Native DRC')
 if logical(b)!=logical(f):errs.append('Logical netlist changed')
 if assignments(b)!=assignments(f):errs.append('Component pad net assignments changed')
 if protected(original)!=protected(rows):errs.append('Outline / hole / keepout / manufacturing rules changed')
 bc={c['designator']:c for c in b['components']};fc={c['designator']:c for c in f['components']};lc={c['designator']:c for c in layout[name]['components']}
 if set(bc)!=set(fc):errs.append('Component membership changed')
 for ref,c in fc.items():
  if any(c[k]!=bc[ref][k]for k in ['footprint','component','supplierId','addIntoBom']):errs.append('Component identity changed: '+ref)
  if any(abs(c[k]-lc[ref][k])>.01 for k in ['x','y','layer'])or abs((c['rotation']-lc[ref]['rotation']+180)%360-180)>.01:errs.append('Pose differs from audited layout: '+ref)
 olds={a['num']:a['netName']for h,a in original if h['type']=='PAD'};news={a['num']:a['netName']for h,a in rows if h['type']=='PAD'}
 if olds!=news:errs.append('Test pad assignments changed')
 byid={h.get('id'):a for h,a in rows};labelcheck=[]
 for p in silk[name]['labels']:
  a=byid[p['id']]
  if abs(a['x']*MM-p['x'])>.002 or abs(a['y']*MM-p['y'])>.002 or a['layerId']!=p['layer'] or a.get('mirror',False)!=p['mirror']:labelcheck.append(p['ref'])
 if labelcheck:errs.append('Silkscreen plan mismatch: '+str(labelcheck))
 widths=Counter(round(a['width'],4)for h,a in rows if h['type']=='LINE'and a.get('layerId')in[1,2,15,16]);wide=defaultdict(set)
 for h,a in rows:
  if h['type']=='LINE'and a.get('layerId')in[1,2,15,16]and round(a['width'],4)not in [5,10]:wide[round(a['width'],4)].add(a['netName'])
 shapes=Board(name);cs=[(r,c['layer'],transform(shapes.L[r]['court'],shapes.P[r]))for r,c in fc.items()];overlap=[]
 for i,(r,l,g)in enumerate(cs):
  for rr,ll,gg in cs[:i]:
   if l==ll and g.intersection(gg).area>.005:overlap.append([r,rr,round(g.intersection(gg).area,4)])
 if overlap:errs.append('Courtyard overlaps: '+str(overlap))
 results[name]={'uuid':f['uuid'],'component_count':len(fc),'native_drc_errors':len(f['drc']),'track_segments':sum(widths.values()),'vias':sum(h['type']=='VIA'for h,a in rows),'widths_mil':dict(widths),'wider_power_or_load_nets':{k:sorted(v)for k,v in wide.items()},'relocated_components':sum(any(abs(c[k]-bc[r][k])>.01 for k in ['x','y','rotation','layer'])for r,c in fc.items()),'verified_silkscreen_labels':len(silk[name]['labels']),'errors':errs}
 print(name,json.dumps(results[name],ensure_ascii=False),flush=True)
(O/'project_verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));assert all(not v['errors']for v in results.values())
