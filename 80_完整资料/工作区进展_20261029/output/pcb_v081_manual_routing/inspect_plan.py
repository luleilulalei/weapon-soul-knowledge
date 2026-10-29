from engine import *
import importlib,sys
name=sys.argv[1] if len(sys.argv)>1 else 'main';b=importlib.import_module(name).b
if '--plot' in sys.argv:
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,len(b.layers),figsize=(22,14),layout='constrained')
 nets=sorted({a[0] for a in b.objects()});colors={n:plt.get_cmap('tab20')(i%20) for i,n in enumerate(nets)}
 for ax,l in zip(axes,b.layers):
  for n,ly,poly,key,kind in b.objects():
   if ly!=l:continue
   xs,ys=poly.exterior.xy;ax.fill(xs,ys,color=colors[n],alpha=.6 if kind=='pad' else .9)
   if kind=='pad':ax.text(poly.centroid.x,poly.centroid.y,key,fontsize=3.5)
  xs,ys=b.outline.exterior.xy;ax.plot(xs,ys,color='black');ax.set_aspect('equal');ax.set_title('Layer '+str(l));ax.grid(alpha=.2);ax.set_xticks(range(-20,21,5));ax.set_yticks(range(0,51,5))
 fig.savefig('output/pcb_v081_manual_routing/'+name+'_plan.png',dpi=170)
else:
 objs=b.objects();parents=list(range(len(objs)))
 def root(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 def join(i,j):parents[root(i)]=root(j)
 tree=STRtree([o[2] for o in objs]);vertical={}
 for i,o in enumerate(objs):
  if o[4]=='via' or(o[4]=='pad' and b.pads[o[3]]['layer']==12):
   k=o[3]
   if k in vertical:join(i,vertical[k])
   else:vertical[k]=i
  for j in tree.query(o[2].buffer(.001)):
   if j<i and objs[j][0]==o[0] and objs[j][1]==o[1] and objs[j][2].distance(o[2])<.001:join(i,int(j))
 nets=defaultdict(lambda:defaultdict(set))
 for i,o in enumerate(objs):
  if o[4]=='pad' and not o[0].startswith('NC:'):nets[o[0]][root(i)].add(o[3])
 for net,groups in sorted(nets.items()):
  if len(groups)>1:print(net,len(groups),' | '.join(','.join(sorted(keys)) for keys in groups.values()))
