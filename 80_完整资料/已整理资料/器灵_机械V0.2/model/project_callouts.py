import bpy,json,os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
R=os.path.dirname(os.path.abspath(__file__));bpy.ops.wm.open_mainfile(filepath=R+'/Spirit_EVT_mechanical_v02.blend');s=bpy.context.scene;c=s.camera
s.render.resolution_x=1100;s.render.resolution_y=1400

def save(n,cam,target,scale,pts):
 c.location=cam;c.rotation_euler=(Vector(target)-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=scale;bpy.context.view_layer.update();out=[]
 for label,title,p in pts:
  v=world_to_camera_view(s,c,Vector(p));out.append({'n':label,'label':title,'xy':[v.x*1100,(1-v.y)*1400]})
 json.dump(out,open(R+'/'+n,'w'),ensure_ascii=False,indent=2)
save('callouts.json',(-100,-70,-460),(0,94,-7),255,[('1','未布线主板 / 可拆框',(-18,95,-2)),('2','400T 受保护电池',(0,96,-15)),('3','NFC 未选型占位',(0,160,-16)),('4','8mm LRA 线性马达',(17,148,-24.175)),('5','前侧扬声器位置',(0,80,13.2)),('6','单 MIC 占位',(12,110,14)),('7','屏 FPC 回弯路径',(0,110,10)),('8','HOTHMI 裸屏 / 压框',(0,140,17.1)),('9','钝头顶口遮护试件',(0,192,0)),('10','LRA 短焊接尾部',(9.675,148,-25.8))])
save('callouts_exploded.json',(270,-100,340),(0,92,0),290,[('P01','前壳 / 螺母捕获槽',(0,115,74)),('P02','后盖 / 服务开口',(0,100,-80)),('P03','可拆主板框',(0,88.5,-1)),('P04','18650 开放托架',(0,96,-51)),('P05','FPC 裸屏压框',(0,140,46.9)),('P06','顶口遮护试件',(0,214,0)),('P07','扬声器座 / 导音道',(-42,80,11.5)),('P11','LRA 座与短尾托台',(61,148,-39.5)),('P12','LRA 可拆防脱止挡',(61,148.75,-3.1))])
