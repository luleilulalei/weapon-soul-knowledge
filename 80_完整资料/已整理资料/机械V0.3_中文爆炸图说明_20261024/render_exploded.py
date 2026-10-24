import bpy,math,json,os
from pathlib import Path
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parent
SRC=Path('/Users/qijiankang/Documents/器灵/机械V0.3_V074H结构评审_20261024/model/Spirit_V03_V074H_review.blend')
bpy.ops.wm.open_mainfile(filepath=str(SRC));s=bpy.context.scene;cam=s.camera
for o in bpy.data.objects:
 if o.name.startswith('P14') or o.name.startswith(('FPC_NO_','NFC_PLUG','RF_REVIEW','BATTERY_UPPER')):o.hide_render=True

def obj(prefix):return next(o for o in bpy.data.objects if o.name.startswith(prefix))
def translate(prefix,xyz):o=obj(prefix);o.location+=Vector(xyz);return o
# Each group is separated laterally for explanation. Original meshes remain unchanged.
for p in ['P04','P06','UNCONFIRMED_USER']:translate(p,(-190,0,0))
translate('P05',(-190,-48,0))
for o in bpy.data.objects:
 if o.name.startswith('display '):o.location.x-=190
# Show the interior of the front housing, preserving its fitted motor and sound duct.
flip=Matrix.Translation(Vector((-95,0,0)))@Matrix.Rotation(math.pi,4,'Y')
for p in ['P01','P12','P13','LRA_LD']:
 o=obj(p);o.matrix_world=flip@o.matrix_world
translate('P03',(26,0,-5))
for p in ['P07','P10','NFC_ANTENNA','NFC_CONTROL','BATTERY_MAX']:translate(p,(95,0,0))
translate('P08',(95,0,0));translate('SPEAKER_20',(68,0,0));translate('P09',(42,0,0))
translate('P02',(190,0,0));translate('P11',(0,15,0))
# Brighter explanatory materials without modifying the underlying geometry.
for n in ['Warm ceramic | printed polymer','Graphite polymer']:
 m=bpy.data.materials.get(n)
 if m:
  col=(.55,.60,.62,1) if 'Graphite'in n else(.78,.77,.71,1)
  m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=col
s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.film_transparent=True;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
s.render.resolution_x=3000;s.render.resolution_y=1600;s.render.resolution_percentage=100
pos=Vector((135,60,650));target=Vector((0,103,0));cam.location=pos;b=(pos-target).normalized();r=Vector((0,1,0)).cross(b).normalized();u=b.cross(r);cam.rotation_euler=Matrix((r,u,b)).transposed().to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=485
# Blender's ortho_scale follows horizontal dimension for landscape output. Auto-fit by bounding projection.
bpy.context.view_layer.update()
visible=[o for o in bpy.data.objects if o.type=='MESH'and not o.hide_render]
for _ in range(3):
 p=[world_to_camera_view(s,cam,o.matrix_world@Vector(v))for o in visible for v in o.bound_box]
 spanx=max(v.x for v in p)-min(v.x for v in p);spany=max(v.y for v in p)-min(v.y for v in p)
 cam.data.ortho_scale*=max(spanx/.94,spany/.91)
 bpy.context.view_layer.update()
anchors={}
def mark(n,prefix,point=None):
 o=obj(prefix);v=Vector(point)if point else o.matrix_world@(sum((Vector(v)for v in o.bound_box),Vector())/8)
 q=world_to_camera_view(s,cam,v);anchors[n]=[q.x*3000,(1-q.y)*1600]
for n,p in [('A1','P06'),('A2','UNCONFIRMED_USER'),('A3','P05'),('B1','P01'),('B2','P12'),('B3','P13'),('C1','PCB_J7'),('C2','PCB_V074H'),('C3','P03'),('C4','PCB_U1'),('D1','NFC_CONTROL'),('D2','NFC_ANTENNA'),('D3','P10'),('D4','BATTERY_MAX'),('D5','P08'),('E1','P02'),('C0','P11')]:mark(n,p)
mark('A3','P05',(-171,90.5,10.25))
mark('C3','P03',(46,145,-12.4))
(R/'anchors.json').write_text(json.dumps(anchors,indent=2))
s['DIAGRAM_ONLY']='Lateral exploded display; front shell flipped to show interior; retainer and speaker separated. Not assembly travel or new CAD geometry.'
if os.getenv('SPIRIT_ANCHORS_ONLY')=='1':raise SystemExit
s.render.filepath=str(R/'exploded_native.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(R/'Spirit_V03_exploded_explanation.blend'))
print('EXPLANATION_RENDER_DONE',flush=True)
