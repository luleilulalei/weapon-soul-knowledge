import bpy,os,json,math
from mathutils import Vector
R=os.path.dirname(os.path.abspath(__file__)); ROOT=R;OUT=os.path.dirname(R)
bpy.ops.wm.open_mainfile(filepath=R+'/Spirit_EVT_mechanical_v02.blend')
scene=bpy.context.scene;cam=scene.camera
prod=bpy.data.collections['01_PRINTED_PARTS_mm'];dum=bpy.data.collections['02_UNPRINTED_DUMMY_COMPONENTS'];viz=bpy.data.collections['04_RENDER_ONLY'];reviews=bpy.data.collections['03_REVIEW_VOLUMES_NOT_FIT_APPROVAL']
parts=list(prod.objects);dummies=list(dum.objects);report=[]
front=bpy.data.objects['P01_front_sculpted_shell'];back=bpy.data.objects['P02_rear_panel'];carrier=bpy.data.objects['P03_removable_PCB_carrier'];batt=bpy.data.objects['P04_18650_open_cradle'];ret=bpy.data.objects['P05_FPC_bare_panel_retainer'];cap=bpy.data.objects['P06_crown_blank_plug'];speak=bpy.data.objects['P07_20mm_speaker_nest'];motorseat=bpy.data.objects['P11_LRA_rear_seat'];motorcap=bpy.data.objects['P12_LRA_removable_axial_stop']
def camera(pos,target,scale):
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
s=open(R+'/build_spirit.py').read();start=s.index("camera((170,-80,440),(0,91,0),225); scene.render.filepath")
if os.environ.get('ONLY_CAVITY')=='1': start=s.index('# Front/back shell internal face render.')
exec(s[start:])
