"""Explicit manual routes and geometry checks. NO search, routing solver or autorouter.
Each route call supplies the net, layer, width and engineer-selected waypoints.
"""
import sys,json,math,itertools
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path.cwd()));sys.path.insert(0,str(Path('output/layout_v074m').resolve()))
from geometry import parse_source,path_points,pad_polygon,local,transform,MM
from shapely.affinity import rotate,translate
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
class Board:
 def __init__(self,name):
  self.name=name;self.b=json.load(open('output/pcb_v082_dedicated_planes/after_layout.json'))['boards'][name];b=self.b;self.sources=json.load(open('output/pcb_v082_dedicated_planes/footprints.json'))
  self.P={c['designator']:{'x':c['x']*MM,'y':c['y']*MM,'rotation':c['rotation'],'layer':c['layer']}for c in b['components']}
  self.L={c['designator']:local(self.sources[c['footprint']['uuid']])for c in b['components']};self.pads={};self.tracks=[];self.vias=[];self.fills=[];self.group='';self.ids={};self.moves={};self.padMoves={}
  self.layers=[1,15,16,2]if name!='blade'else[1,2]
  for r,p in self.P.items():
   counts=defaultdict(int)
   for q in b['pads'][r]:
    n=q['padNumber'];key=r+'.'+n;counts[key]+=1
    if counts[key]>1:key+='~'+str(counts[key]-1)
    pp=(q['x']*MM,q['y']*MM);a=min((x for nn,x,d in self.L[r]['pads']if nn==n),key=lambda a:transform(a,p).centroid.distance(Point(*pp)));poly=transform(a,p)
    self.pads[key]={'net':q['net'],'layer':q['layer'],'p':pp,'poly':poly,'ref':r}
  self.rows=parse_source(b['source']);outline=next(a for h,a in self.rows if h['type']=='POLY'and a.get('layerId')==11);self.outline=Polygon([(x*MM,y*MM)for x,y in path_points(outline['path'])]);self.holes=[]
  for h,a in self.rows:
   if h['type']=='PAD':self.pads[a['num']]={'net':a['netName'],'layer':a['layerId'],'p':(a['centerX']*MM,a['centerY']*MM),'poly':pad_polygon(a),'ref':a['num']}
   if h['type']=='FILL'and a.get('layerId')==12:
    for p in a['path']:
     if p[0]=='CIRCLE':self.holes.append(Point(p[1]*MM,p[2]*MM).buffer(p[3]*MM))
  for r,p in self.P.items():
   for h,a in parse_source(self.sources[next(c['footprint']['uuid']for c in b['components']if c['designator']==r)]):
    if h['type']=='FILL'and a.get('layerId')==12:
     for pa in a['path']:
      if pa[0]=='CIRCLE':self.holes.append(transform(Point(pa[1]*MM,pa[2]*MM).buffer(pa[3]*MM),p))
 def rotate180(self,ref):
  c=self.P[ref];c['rotation']=(c['rotation']+180)%360;self.moves[ref]=c.copy()
  for p in self.pads.values():
   if p['ref']==ref:p['p']=(2*c['x']-p['p'][0],2*c['y']-p['p'][1]);p['poly']=rotate(p['poly'],180,origin=(c['x'],c['y']))
 def move(self,ref,dx,dy):
  c=self.P[ref];c['x']+=dx;c['y']+=dy;self.moves[ref]=c.copy()
  for p in self.pads.values():
   if p['ref']==ref:p['p']=(p['p'][0]+dx,p['p'][1]+dy);p['poly']=translate(p['poly'],dx,dy)
 def move_pad(self,key,x,y,layer=None):
  p=self.pads[key];dx=x-p['p'][0];dy=y-p['p'][1];self.padMoves[key]={'x':x,'y':y,'old':p['p']};p['p']=(x,y);p['poly']=translate(p['poly'],dx,dy)
  if layer is not None:self.padMoves[key].update({'layer':layer,'oldLayer':p['layer']});p['layer']=layer
 def pt(self,a):return self.pads[a]['p']if isinstance(a,str)else tuple(a)
 def tr(self,net,l,w,*nodes):
  assert l in [1,2] and net, ("Inner planes cannot contain routing",l,net)
  keys=[n for n in nodes if isinstance(n,str)]
  assert all(self.pads[k]['net']==net for k in keys),(net,keys)
  label=' > '.join(keys) or self.group;ps=[self.pt(n)for n in nodes]
  for a,b in zip(ps,ps[1:]):
   if math.dist(a,b)>.0001:self.tracks.append({'net':net,'layer':l,'width':w,'points':[a,b],'label':label,'group':self.group})
 def cn(self,l,w,*nodes):
  nets={self.pads[n]['net']for n in nodes if isinstance(n,str)};assert len(nets)==1 and ''not in nets,(nodes,nets);self.tr(nets.pop(),l,w,*nodes)
 def via(self,net,x,y,d=.5,h=.2):
  if not any(v['net']==net and math.dist((x,y),(v['x'],v['y']))<.001 for v in self.vias):self.vias.append({'net':net,'x':x,'y':y,'diameter':d,'hole':h,'group':self.group})
  return (x,y)
 def esc(self,k,x,y,w=.127,d=.5,h=.2):
  p=self.pads[k];self.cn(p['layer'],w,k,(x,y));self.via(p['net'],x,y,d,h);return(x,y)
 def fan(self,k,delta=.8,w=.25):
  p=self.pads[k];c=self.P[p['ref']];x,y=p['p'];dx,dy=x-c['x'],y-c['y'];n=math.hypot(dx,dy);assert n>.01
  return self.esc(k,x+dx/n*delta,y+dy/n*delta,w)
 def fill(self,net,l,points):self.fills.append({'net':net,'layer':l,'points':points,'group':self.group})
 def objects(self):
  o=[]
  for k,p in self.pads.items():
   for l in self.layers if p['layer']==12 else[p['layer']]:o.append((p['net']or'NC:'+k,l,p['poly'],k,'pad'))
  for i,t in enumerate(self.tracks):o.append((t['net'],t['layer'],LineString(t['points']).buffer(t['width']/2,cap_style=1),f'T{i} '+t['label'],'trace'))
  for i,v in enumerate(self.vias):
   for l in self.layers:o.append((v['net'],l,Point(v['x'],v['y']).buffer(v['diameter']/2),f'V{i}','via'))
  for i,f in enumerate(self.fills):o.append((f['net'],f['layer'],Polygon(f['points']),f'F{i}','fill'))
  return o
 def audit(self):
  o=self.objects();tree=STRtree([a[2]for a in o]);errors=[]
  for i,a in enumerate(o):
   for j in tree.query(a[2].buffer(.1523)):
    j=int(j)
    if j<=i:continue
    b=o[j]
    if a[1]!=b[1]or a[0]==b[0]or(a[4]=='pad'and b[4]=='pad'):continue
    d=a[2].distance(b[2])
    if d<.152:errors.append({'a':a[3],'an':a[0],'b':b[3],'bn':b[0],'layer':a[1],'gap':round(d,4),'axy':tuple(round(v,2)for v in a[2].centroid.coords[0]),'bxy':tuple(round(v,2)for v in b[2].centroid.coords[0])})
   if a[4]=='pad':continue
   if not self.outline.buffer(-.299).covers(a[2]):errors.append({'edge':a[3],'net':a[0]})
   for q in self.holes:
    if a[2].distance(q)<.3:errors.append({'hole':a[3],'net':a[0]})
  for i,v in enumerate(self.vias):
   for j,b in enumerate(self.vias[:i]):
    if math.dist((v['x'],v['y']),(b['x'],b['y']))-(v['hole']+b['hole'])/2<.299:errors.append({'drill':[i,j]})
  return errors
 def save(self):
  es=self.audit();Path('output/pcb_v082_dedicated_planes/'+self.name+'_routes.json').write_text(json.dumps({'moves':self.moves,'padMoves':self.padMoves,'tracks':self.tracks,'vias':self.vias,'fills':self.fills,'errors':es},ensure_ascii=False,indent=2));print(self.name,'tracks',len(self.tracks),'vias',len(self.vias),'errors',len(es));print(json.dumps(es,ensure_ascii=False,indent=2)[:15000])
 def dump(self,refs=None):
  for k,p in self.pads.items():
   if refs is None or p['ref'] in refs:print(k,p['net'],p['layer'],tuple(round(x,4)for x in p['p']))
