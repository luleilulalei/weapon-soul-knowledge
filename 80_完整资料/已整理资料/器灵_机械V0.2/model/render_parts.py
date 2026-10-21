import bpy,os,json
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
R=os.path.dirname(os.path.abspath(__file__));O=os.path.dirname(R)
bpy.ops.wm.open_mainfile(filepath=R+'/Spirit_EVT_mechanical_v02.blend');s=bpy.context.scene;c=s.camera
for o in s.objects:
 if o.type not in ('LIGHT','CAMERA'):o.hide_render=True
pos={'P01':(-110,90),'P02':(-40,90),'P03':(30,105),'P04':(100,105),'P05':(170,165),'P06':(170,105),'P07':(170,60),'P08':(-100,-40),'P09':(-20,-40),'P10':(55,-40),'P11':(170,10),'P12':(100,10)}
labels=[]
for f in sorted(os.listdir(R+'/stl')):
 if not f.endswith('.stl'):continue
 bpy.ops.wm.stl_import(filepath=R+'/stl/'+f);o=bpy.context.object;k=f[:3];o.location.x,o.location.y=pos[k];o.data.materials.append(bpy.data.materials['Warm ceramic | printed polymer']);labels.append((k,o.location.x,o.location.y+o.dimensions.y/2+7,list(o.dimensions)))
c.location=(20,80,500);c.rotation_euler=(Vector((20,80,0))-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=400;s.render.resolution_x=1800;s.render.resolution_y=1400;bpy.context.view_layer.update()
out=[]
for k,x,y,d in labels:
 v=world_to_camera_view(s,c,Vector((x,y,0)));out.append({'id':k,'xy':[v.x*1800,(1-v.y)*1400],'dims':d})
json.dump(out,open(R+'/part_layout_labels.json','w'),indent=2)
s.render.filepath=O+'/renders/07_print_parts_unlabelled.png';bpy.ops.render.render(write_still=True)
