import bpy,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;O=R.parent/'renders';O.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'Spirit_V03_V074K_review.blend'));s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=16;s.cycles.use_denoising=True;s.render.resolution_percentage=100
cam=s.camera
bpy.data.objects['P11_keyed_top_dust_cap'].hide_render=True
for o in bpy.data.objects:
 if o.name.startswith('P14'):o.hide_render=True

def shot(name,pos,target,scale,w,h):
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;s.render.resolution_x=w;s.render.resolution_y=h;s.render.filepath=str(O/name);bpy.ops.render.render(write_still=True)
shot('整机与配件定位壳.png',(135,-35,410),(0,108,0),250,1100,1500)
for o in bpy.data.objects:
 if o.type=='MESH':o.hide_render=not(o.name.startswith('PCB_')or o.name.startswith('ADAPTER_'))
for o in bpy.data.objects:
 if o.type=='CURVE':o.hide_render=True
shot('对接触点与适配板.png',(75,120,220),(0,184,2),80,1300,1200)
for o in bpy.data.objects:
 if o.type=='MESH':o.hide_render=not(o.name.startswith('ADAPTER_')or o.name.startswith('P15_'))
bpy.data.objects['P15_adapter_alignment_carrier'].location.x+=29
shot('适配板与定位壳分解.png',(60,170,120),(14,199,2),73,1300,1000)
