from engine import *
from collections import defaultdict
name=sys.argv[1]if len(sys.argv)>1 else 'main'
plan=json.load(open('output/pcb_v081_manual_routing/'+name+'_routes.json'));d=json.load(open('output/pcb_v081_manual_routing/'+name+'_native_route_check.json'));rows=parse_source(d['source'])
expected=defaultdict(list)
for t in plan['tracks']:expected[(t['net'],t['layer'],round(t['width'],4))].append(LineString(t['points']))
u={k:unary_union(v).buffer(.0002)for k,v in expected.items()}
bad=[];actual=defaultdict(list)
for h,a in rows:
 if h['type']!='LINE' or a.get('layerId')not in[1,2,15,16] or not a.get('netName'):continue
 k=(a['netName'],a['layerId'],round(a['width']*MM,4));g=LineString([(a['startX']*MM,a['startY']*MM),(a['endX']*MM,a['endY']*MM)])
 if k not in u or not u[k].covers(g):bad.append({'id':h['id'],'net':k[0],'layer':k[1],'points':list(g.coords),'width':k[2]})
 else:actual[k].append(g)
a={k:unary_union(v).buffer(.0002)for k,v in actual.items()};missing=[]
for t in plan['tracks']:
 k=(t['net'],t['layer'],round(t['width'],4))
 if k not in a or not a[k].covers(LineString(t['points'])):missing.append(t)
print('obsolete native',len(bad),'missing after removal',len(missing));print(json.dumps(bad,indent=2)[:12000])
json.dump({'remove':bad,'add':missing},open('output/pcb_v081_manual_routing/'+name+'_native_delta.json','w'),indent=2)
