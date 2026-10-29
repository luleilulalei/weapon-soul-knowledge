from engine import *
import ast,re,zipfile,pickle
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MP
from matplotlib.patches import PathPatch
from shapely.geometry.polygon import orient
from shapely.affinity import scale
O=Path(__file__).resolve().parent;D=O/'delivery'
src=Path('output/pcb_pour_v074p3b/gerber_check.py').read_text();tree=ast.parse(src);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='gerber');fn=ast.get_source_segment(src,fn)
fn=fn.replace("name,p=v[2:].split('*',1);a=p.rstrip('*').split(',');", "name,p=v[2:].split('*',1)\n    if name=='RoundRect':continue\n    a=p.rstrip('*').split(',');")
fn=fn.replace("else:g=macros[typ]", "elif typ=='RoundRect':g=Polygon([(p[1],p[2]),(p[3],p[4]),(-p[1],-p[2]),(-p[3],-p[4])]).buffer(p[0]/2,quad_segs=48)\n    else:g=macros[typ]")
exec(fn)
def draw(ax,g,color,mirror=False):
 if mirror:g=scale(g,xfact=-1,yfact=1,origin=(0,0))
 ps=list(g.geoms)if hasattr(g,'geoms')else[g];vs=[];codes=[]
 for p in ps:
  if p.is_empty:continue
  if p.geom_type!='Polygon':continue
  p=orient(p,sign=1)
  for ring in [p.exterior,*p.interiors]:
   xy=list(ring.coords);vs+=xy;codes+=[MP.MOVETO]+[MP.LINETO]*(len(xy)-2)+[MP.CLOSEPOLY]
 if vs:ax.add_patch(PathPatch(MP(vs,codes),facecolor=color,edgecolor='none',rasterized=True))
copper=pickle.loads((O/'manufacturing_geometry.pickle').read_bytes());stats={}
for name in ['main','power','blade']:
 b=Board(name);z=zipfile.ZipFile(D/(name+'_V081_Gerber.zip'));holes=[]
 for filename in z.namelist():
  if not filename.endswith('.DRL')or '_Via.'in filename:continue
  tool=None;sizes={}
  for line in z.read(filename).decode().splitlines():
   m=re.fullmatch(r'T(\d+)C([\d.]+)',line)
   if m:sizes[int(m[1])]=float(m[2]);continue
   m=re.fullmatch(r'T(\d+)',line)
   if m:tool=int(m[1]);continue
   if line.startswith('X'):
    xy=[tuple(map(float,m))for m in re.findall(r'X(-?[\d.]+)Y(-?[\d.]+)',line)];assert len(xy)in[1,2],line
    holes.append((Point(*xy[0])if len(xy)==1 else LineString(xy)).buffer(sizes[tool]/2,quad_segs=48))
 hole=unary_union(holes)
 for side,l,silk,mask in [('top',1,'GTO','GTS'),('bottom',2,'GBO','GBS')]:
  sg,_=gerber(z.read(next(n for n in z.namelist()if n.endswith('.'+silk))).decode());mg,_=gerber(z.read(next(n for n in z.namelist()if n.endswith('.'+mask))).decode());g=copper[name][l];exposed=g.intersection(mg);mirror=side=='bottom'
  fig,ax=plt.subplots(figsize=(8,10),facecolor='#10232e');ax.set_facecolor('#10232e');draw(ax,b.outline,'#114735',mirror);draw(ax,g,'#21654c',mirror);draw(ax,exposed,'#d9b86c',mirror);draw(ax,sg.intersection(b.outline),'#f3f5ee',mirror);draw(ax,hole,'#10232e',mirror)
  xmin,ymin,xmax,ymax=b.outline.bounds;ax.set(xlim=(xmin-.7,xmax+.7),ylim=(ymin-.7,ymax+.7),aspect='equal');ax.axis('off');fig.subplots_adjust(left=.01,right=.99,bottom=.01,top=.99);fig.savefig(D/(name+'_'+side+'.png'),dpi=180,facecolor=fig.get_facecolor());plt.close(fig)
  stats[name+'_'+side]={'silkscreen_area_mm2':round(sg.area,3),'mask_opening_area_mm2':round(mg.area,3)};print(name,side,'rendered',flush=True)
(O/'render_verification.json').write_text(json.dumps(stats,indent=2))
