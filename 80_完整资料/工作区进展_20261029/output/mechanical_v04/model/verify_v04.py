import bpy,bmesh,json,itertools,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent;OUT=ROOT.parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Spirit_V04_V074P3B_review.blend'))
parts=[o for o in bpy.data.objects if o.type=='MESH'and o.name.startswith('P')and len(o.name)>2 and o.name[1:3].isdigit()and not o.name.startswith(('P14','P11','P16'))]
proxies=[o for o in bpy.data.collections['02_UNPRINTED_DUMMY_COMPONENTS'].objects if o.type=='MESH']
def bbox(o):
 p=[o.matrix_world@Vector(v)for v in o.bound_box];return [min(v[i]for v in p)for i in range(3)]+[max(v[i]for v in p)for i in range(3)]
def volume(o):
 bm=bmesh.new();bm.from_mesh(o.data);v=abs(bm.calc_volume(signed=True));bm.free();return v

cache={}
def tree(o):
 if o.name not in cache:
  vs=[o.matrix_world@v.co for v in o.data.vertices]
  cache[o.name]=(BVHTree.FromPolygons(vs,[tuple(p.vertices)for p in o.data.polygons],all_triangles=False),vs[0])
 return cache[o.name]
def inside(p,t):
 hit=t.find_nearest(p)
 return bool(hit[0] is not None and (p-hit[0]).dot(hit[1])<-.0001)
def intersect(a,b):
 aa,bb=bbox(a),bbox(b)
 if any(min(aa[i+3],bb[i+3])-max(aa[i],bb[i])<.0001 for i in range(3)):return 0
 ta,va=tree(a);tb,vb=tree(b)
 if not ta.overlap(tb) and not inside(va,tb) and not inside(vb,ta):return 0
 q=a.copy();q.data=a.data.copy();bpy.context.scene.collection.objects.link(q);bpy.context.view_layer.objects.active=q
 m=q.modifiers.new('collision','BOOLEAN');m.operation='INTERSECT';m.solver='EXACT';m.object=b
 try:bpy.ops.object.modifier_apply(modifier=m.name);v=volume(q)
 except Exception as e:v=-1
 bpy.data.objects.remove(q,do_unlink=True);return v
mesh=[]
for o in parts:
 bm=bmesh.new();bm.from_mesh(o.data);bad=[list(o.matrix_world@e.verts[0].co)for e in bm.edges if not e.is_manifold]
 seen=set();cc=0
 for v in bm.verts:
  if v in seen:continue
  cc+=1;todo=[v];seen.add(v)
  while todo:
   for e in todo.pop().link_edges:
    for w in e.verts:
     if w not in seen:seen.add(w);todo.append(w)
 mesh.append({'part':o.name,'components':cc,'bad_edges':len(bad),'bad_locations':bad[:12]});bm.free()
collisions=[]
offboard=[o for o in proxies if not o.name.startswith('PCB_')]
onboard=[o for o in proxies if o.name.startswith('PCB_')]
services=[bpy.data.objects[n] for n in ['FPC_NO_FRONT_COMPONENTS','J104_PLUG_SERVICE','J201_PLUG_SERVICE','J3_PLUG_SERVICE','J110_PLUG_SERVICE','J2_PLUG_SERVICE','ADAPTER_J702_PLUG_SERVICE']]
pairs=list(itertools.combinations(parts,2))+[(a,b)for a in parts for b in proxies]+list(itertools.combinations(offboard,2))+[(a,b)for a in offboard for b in onboard]+[(a,service)for a in parts+proxies for service in services if not (a.name=='PCB_J8' and service.name=='FPC_NO_FRONT_COMPONENTS') and not (a.name=='PCB_J104' and service.name=='J104_PLUG_SERVICE') and not (a.name=='PCB_J201' and service.name=='J201_PLUG_SERVICE') and not (a.name=='PCB_J3' and service.name=='J3_PLUG_SERVICE') and not (a.name=='PCB_J110' and service.name=='J110_PLUG_SERVICE') and not(a.name=='PCB_J2' and service.name=='J2_PLUG_SERVICE') and not(a.name=='ADAPTER_J702'and service.name=='ADAPTER_J702_PLUG_SERVICE') and 'ACTUAL_OUTLINE' not in a.name]
checked=0
for a,b in pairs:
 if 'ACTUAL_OUTLINE' in a.name and b.name.startswith('ADAPTER_') or 'ACTUAL_OUTLINE' in b.name and a.name.startswith('ADAPTER_'):continue
 checked+=1
 v=intersect(a,b)
 if v>.02 or v<0:collisions.append({'a':a.name,'b':b.name,'volume_mm3':v});print('COLLISION',a.name,b.name,round(v,3),flush=True)
r={'acceleration':'AABB then BVH surface/containment rejection, exact boolean volume for remaining pairs','mesh':mesh,'collisions':collisions,'pairs_checked':checked,'candidate_pairs':len(pairs),'intersection_reporting_threshold_mm3':.02,'boundary':'Proxy envelopes are conservative; cable sweep, print tolerance, real screen and acoustic/RF performance not validated.'};exec((ROOT/'verify_operations.py').read_text());(OUT/'verification/geometry.json').write_text(json.dumps(r,indent=2));print('VERIFY_DONE',json.dumps(mesh),flush=True)
