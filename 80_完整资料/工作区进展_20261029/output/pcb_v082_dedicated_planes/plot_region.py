from engine import *
import importlib,sys
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
name=sys.argv[1];b=importlib.import_module(name).b;layer=int(sys.argv[2]);xmin,xmax,ymin,ymax=map(float,sys.argv[3:7]);fig,ax=plt.subplots(figsize=(13,13));nets=sorted({a[0] for a in b.objects()});colors={n:plt.get_cmap('tab20')(i%20)for i,n in enumerate(nets)}
for n,l,poly,k,kind in b.objects():
 if l!=layer or not poly.intersects(box(xmin,ymin,xmax,ymax)):continue
 ax.fill(*poly.exterior.xy,color=colors[n],alpha=.65 if kind=='pad'else .9)
 if kind=='pad':ax.text(poly.centroid.x,poly.centroid.y,k+'\n'+n,fontsize=6,ha='center')
 if kind=='via':ax.text(poly.centroid.x,poly.centroid.y,k,fontsize=6,color='black')
ax.set_xlim(xmin,xmax);ax.set_ylim(ymin,ymax);ax.set_aspect('equal');ax.set_xticks([x/2 for x in range(int(xmin*2),int(xmax*2)+1)]);ax.set_yticks([x/2 for x in range(int(ymin*2),int(ymax*2)+1)]);ax.tick_params(labelsize=7);ax.grid(alpha=.3);fig.savefig('output/pcb_v082_dedicated_planes/region.png',dpi=150)
