# Run via exec from verify_v04.py after static fit checks.
import hashlib
cap=bpy.data.objects['P11_keyed_top_dust_cap']
cap_collisions=[]
for o in parts+proxies:
 if o.name.startswith(('P15_','ADAPTER_')):continue
 v=intersect(cap,o)
 if v>.02 or v<0:cap_collisions.append({'a':cap.name,'b':o.name,'volume_mm3':v})
moving=[o for o in parts+proxies if o.name.startswith(('P15_','ADAPTER_'))]
fixed=[o for o in parts+proxies if o not in moving]
locs={o:o.location.copy()for o in moving};sweep=[]
for dy in [1,2,3,5,8,12,16]:
 for o in moving:o.location=locs[o]+Vector((0,dy,0));cache.pop(o.name,None)
 bpy.context.view_layer.update();bad=[]
 for a in moving:
  for b in fixed:
   v=intersect(a,b)
   if v>.02 or v<0:bad.append({'a':a.name,'b':b.name,'volume_mm3':v})
 sweep.append({'withdrawal_mm':dy,'collisions':bad})
for o in moving:o.location=locs[o];cache.pop(o.name,None)
bpy.context.view_layer.update()
carrier=bpy.data.objects['P15_Hanxia_keyed_adapter_carrier'];front=bpy.data.objects['P01_front_shell'];saved=carrier.matrix_world.copy()
from mathutils import Matrix
# Wrong orientation is blocked with the male pin tip still 2.5 mm before female face.
carrier.matrix_world=Matrix.Translation((0,5,3.95))@Matrix.Rotation(math.pi,4,'Y')@Matrix.Translation((0,0,-3.95))@saved
bpy.context.view_layer.update();cache.pop(carrier.name,None);wrong=intersect(carrier,front)
carrier.matrix_world=Matrix.Translation((0,-.5,0))@saved;bpy.context.view_layer.update();cache.pop(carrier.name,None);over=intersect(carrier,front)
carrier.matrix_world=saved;bpy.context.view_layer.update();cache.pop(carrier.name,None)
# This is an assembly envelope, not blade strength, clearance tolerance or physical qualification.
r['operation_checks']={'cap_collisions':cap_collisions,'nominal_axial_sweep':sweep,'wrong_orientation_stop_volume_mm3':wrong,'overtravel_half_mm_stop_volume_mm3':over,'scope':'Nominal geometry only; no tolerance stack, cable flexibility or structural load analysis.'}
r['native_model_sha256']=hashlib.sha256((ROOT/'Spirit_V04_V074P3B_review.blend').read_bytes()).hexdigest()
def overall(objs):
 bb=[bbox(o)for o in objs];lo=[min(x[i]for x in bb)for i in range(3)];hi=[max(x[i+3]for x in bb)for i in range(3)];return dict(min=lo,max=hi,xyz_mm=[hi[i]-lo[i]for i in range(3)])
r['core_with_cap_bbox']=overall([o for o in parts+proxies if not o.name.startswith(('P15_','ADAPTER_'))]+[cap])
r['core_with_adapter_bbox']=overall(parts+proxies)
print('OPERATION_CHECKS',json.dumps(r['operation_checks']),flush=True)
