import bpy,json,math,os
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parent;O=R.parent/'renders'
bpy.ops.wm.open_mainfile(filepath=str(R/'Spirit_V04_V074P3B_review.blend'))
s=bpy.context.scene;cam=s.camera;s.render.engine='CYCLES';s.cycles.samples=16;s.cycles.use_denoising=True
s.render.image_settings.file_format='PNG';s.render.film_transparent=False
s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.1,.13,.16,1);s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.6
for o in bpy.data.collections['03_REVIEW_VOLUMES_NOT_FIT_APPROVAL'].objects:o.hide_render=True
for n in ['P14_fit_coupon','P16_adapter_height_shim_0p3']:bpy.data.objects[n].hide_render=True
orig={o:(o.location.copy(),o.hide_render)for o in bpy.data.objects}
def reset():
 for o,(loc,h)in orig.items():o.location=loc;o.hide_render=h
 bpy.context.view_layer.update()
def obj(p):return next(o for o in bpy.data.objects if o.name.startswith(p))
def render(name,pos,target,scale,xy=(1100,1500)):
 if os.getenv('SPIRIT_RENDER_ONLY') and os.getenv('SPIRIT_RENDER_ONLY')!=name:return
 cam.location=pos;back=(Vector(pos)-Vector(target)).normalized();right=Vector((0,1,0)).cross(back).normalized();up=back.cross(right);cam.rotation_euler=Matrix((right,up,back)).transposed().to_euler();cam.data.ortho_scale=scale;s.render.resolution_x,s.render.resolution_y=xy;s.render.resolution_percentage=100;s.render.filepath=str(O/name);bpy.ops.render.render(write_still=True);print('RENDERED',name,flush=True)
# Closed core with removable cap.
for o in bpy.data.objects:
 if o.name.startswith(('ADAPTER_','P15_')):o.hide_render=True
obj('P11').hide_render=False
render('01_core.png',(120,-15,440),(0,96,0),222)
reset()
# Three groups, with board and its carrier visibly separated.
for p in ['P01','P04','P05','P06','P12','P13','UNCONFIRMED_USER','LRA_LD']:obj(p).location.x-=85
for o in bpy.data.objects:
 if o.name.startswith('display '):o.location.x-=85
for p in ['P02','P07','P08','P09','P10','NFC_ANTENNA','NFC_CONTROL','BATTERY_MAX','SPEAKER_20mm']:obj(p).location.x+=85
for o in bpy.data.objects:
 if o.name.startswith(('ADAPTER_','P15_')):o.location.x+=10;o.location.y+=18
render('02_exploded.png',(115,35,520),(3,118,-4),335,(1800,1450))
reset()
# Actual PCB ears and new support frame side by side.
for o in bpy.data.objects:
 if o.type in ['MESH','CURVE']:o.hide_render=not(o.name.startswith(('PCB_','P03_','FASTENER_PCB','WASHER_PCB','NUT_PCB')))
obj('P03').location.x+=61
for o in bpy.data.objects:
 if o.name.startswith(('FASTENER_PCB','WASHER_PCB','NUT_PCB')):o.hide_render=True
render('03_board_carrier.png',(110,80,340),(29,140,-3),133,(1500,1100))
reset()
# Connector section view: hidden outer shell, shifted shroud reveals the two boards.
for o in bpy.data.objects:
 if o.type in ['MESH','CURVE']:o.hide_render=not(o.name.startswith(('PCB_','ADAPTER_','P15_')))
obj('P15').location.x+=32
render('04_interface.png',(90,152,240),(13,190,0),92,(1600,1200))
reset()
for p in ['P02','P07','P10','NFC_ANTENNA','NFC_CONTROL']:obj(p).hide_render=True
for o in bpy.data.objects:
 if o.name.startswith(('ADAPTER_','P15_')):o.hide_render=True
render('05_open_rear.png',(-115,25,-470),(0,97,-3),225)
reset()
render('06_head.png',(125,245,200),(0,181,0),105,(1400,1200))
reset()
print('RENDER_COMPLETE',flush=True)
