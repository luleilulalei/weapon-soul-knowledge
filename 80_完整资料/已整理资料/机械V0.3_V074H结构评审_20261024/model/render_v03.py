import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent;OUT=ROOT.parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Spirit_V03_V074H_review.blend'))
s=bpy.context.scene;cam=s.camera;s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True
s.render.image_settings.file_format='PNG';s.render.film_transparent=False
s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.12,.145,.17,1);s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.5
parts=[o for o in bpy.data.objects if o.name[:1]=='P' and o.name[1:3].isdigit()]
def obj(prefix):return next(o for o in bpy.data.objects if o.name.startswith(prefix))
def render(name,pos,target,scale,xy=(1200,1600)):
 cam.location=pos;back=(Vector(pos)-Vector(target)).normalized();right=Vector((0,1,0)).cross(back).normalized();up=back.cross(right);cam.rotation_euler=Matrix((right,up,back)).transposed().to_euler();cam.data.ortho_scale=scale;s.render.resolution_x,s.render.resolution_y=xy;s.render.resolution_percentage=100;s.render.filepath=str(OUT/'renders'/name);bpy.ops.render.render(write_still=True)
render('01_front.png',(120,-15,440),(0,96,0),222)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_location=Vector((0,96,0));area.spaces.active.region_3d.view_distance=240;area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion();area.spaces.active.region_3d.view_perspective='ORTHO'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Spirit_V03_V074H_review.blend'))
render('02_rear.png',(-130,235,-440),(0,96,-4),222)
original={o:(o.location.copy(),o.hide_render)for o in bpy.data.objects}
for prefix in ['P01','P04','P05','P06','P12','P13','UNCONFIRMED_USER','LRA_LD']:
 obj(prefix).location.x-=75
for o in bpy.data.objects:
 if o.name.startswith('display '):o.location.x-=75
for prefix in ['P02','P07','P08','P09','P10','NFC_ANTENNA','NFC_CONTROL','BATTERY_MAX']:
 obj(prefix).location.x+=75
obj('P11').location.y+=18
render('03_exploded.png',(145,40,520),(0,98,-4),280,(1800,1500))
for o,(pos,hidden)in original.items():o.location=pos;o.hide_render=hidden
for prefix in ['P02','P07','P10','NFC_ANTENNA','NFC_CONTROL']:obj(prefix).hide_render=True
render('04_internal.png',(-115,25,-470),(0,97,-3),225)
for o,(pos,hidden)in original.items():o.location=pos;o.hide_render=hidden
# Top view provides actual connector and front-key relationship, dust cover removed.
obj('P11').hide_render=True
render('05_head_ports.png',(125,245,200),(0,153,0),93,(1400,1200))
print('RENDERS_COMPLETE',flush=True)
