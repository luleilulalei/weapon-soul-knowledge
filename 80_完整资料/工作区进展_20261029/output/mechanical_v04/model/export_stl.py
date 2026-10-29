import bpy,math
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(R/'Spirit_V04_V074P3B_review.blend'))
for o in bpy.data.collections['01_PRINTED_PARTS_mm'].objects:
 if o.type!='MESH' or not(o.name[:1]=='P'and o.name[1:3].isdigit()):continue
 o.hide_set(False);o.hide_viewport=False;original=o.matrix_world.copy()
 if o.name.startswith('P01'):o.rotation_euler.x+=math.pi
 if o.name.startswith(('P08','P09')):o.rotation_euler.y+=math.pi/2
 bpy.context.view_layer.update();vs=[o.matrix_world@Vector(v)for v in o.bound_box];o.location-=Vector(((min(v.x for v in vs)+max(v.x for v in vs))/2,(min(v.y for v in vs)+max(v.y for v in vs))/2,min(v.z for v in vs)))
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 bpy.ops.wm.stl_export(filepath=str(R/'stl'/(o.name+'.stl')),export_selected_objects=True,apply_modifiers=True,global_scale=1,use_scene_unit=False)
 o.matrix_world=original
print('ALL_16_STLS_EXPORTED',flush=True)
