"""Independent read-only connectivity check on the exported native copper Gerbers."""
from engine import *
import re,zipfile,pickle,ast,importlib
from shapely.affinity import translate
O=Path(__file__).resolve().parent
src=Path('output/pcb_pour_v074p3b/gerber_check.py').read_text();tree=ast.parse(src);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='gerber');exec(compile(ast.Module(body=[fn],type_ignores=[]),str(O/'gerber_reader'), 'exec'))
results={};render={}
for name in ['main','power','blade']:
 b=importlib.import_module(name).b;z=zipfile.ZipFile(O/'delivery'/(name+'_V081_Gerber.zip'));assert z.testzip()is None;anchors=[]
 for k,p in b.pads.items():
  if not p['net']:continue
  for l in b.layers if p['layer']==12 else[p['layer']]:anchors.append((p['net'],l,p['p'],k))
 for i,v in enumerate(b.vias):
  for l in b.layers:anchors.append((v['net'],l,(v['x'],v['y']),'via'+str(i)))
 layers={1:'Gerber_TopLayer.GTL',2:'Gerber_BottomLayer.GBL',15:'Gerber_InnerLayer1.G1',16:'Gerber_InnerLayer2.G2'};res={};graphs={};miss=[];shorts=[];render[name]={}
 for l in b.layers:
  fn=next(n for n in z.namelist()if n.endswith(layers[l]));g,_=gerber(z.read(fn).decode());render[name][l]=g;ps=list(g.geoms)if hasattr(g,'geoms')else[g];tree=STRtree(ps);labels=defaultdict(set)
  for n,ll,pt,k in anchors:
   if ll!=l:continue
   hits=[int(i)for i in tree.query(Point(pt).buffer(.00004))if ps[int(i)].distance(Point(pt))<.00004]
   if not hits:miss.append([n,l,k,pt])
   for i in hits:labels[i].add(n);graphs[(k,l)]=(l,i)
  for i,ns in labels.items():
   if len(ns)>1:shorts.append({'layer':l,'nets':sorted(ns),'bounds':ps[i].bounds})
  res[l]={'area_mm2':round(g.area,4),'copper_islands':len(ps),'labelled_islands':len(labels)}
 nodes=set(graphs.values());parents={i:i for i in nodes}
 def root(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 seen={}
 for(k,l),i in graphs.items():
  if k in seen:parents[root(i)]=root(seen[k])
  else:seen[k]=i
 nets=defaultdict(set)
 for n,l,pt,k in anchors:
  if(k,l)in graphs:nets[n].add(root(graphs[k,l]))
 split={n:len(p)for n,p in nets.items()if len(p)>1}
 results[name]={'layers':res,'uncovered_pad_via_anchors':miss,'cross_net_copper_islands':shorts,'split_nets':split};print(name,{'missing':len(miss),'shorts':len(shorts),'split':split},flush=True)
(O/'manufacturing_connectivity.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));(O/'manufacturing_geometry.pickle').write_bytes(pickle.dumps(render))
assert all(not r['uncovered_pad_via_anchors']and not r['cross_net_copper_islands']and not r['split_nets']for r in results.values())
