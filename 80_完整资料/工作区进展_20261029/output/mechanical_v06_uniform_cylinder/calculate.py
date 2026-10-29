import json,math,hashlib
from pathlib import Path
O=Path(__file__).resolve().parent
old=json.load(open('output/mechanical_v05_cylinder_review/dimensions_and_checks.json'))
poses={'main':(-5.7,144,0),'power':(-5.7,74,-9)}
boards={};items=[]
def block(n,b,kind='interior'):
 items.append(dict(name=n,bounds=b,kind=kind))
for name,pose in poses.items():
 b=json.loads(json.dumps(old['boards'][name]));dx,dy,dz=[a-c for a,c in zip(pose,b['pose'])];b['pose']=pose
 for c in b['components']:
  c['bounds']=[a+d for a,d in zip(c['bounds'],[dx,dy,dz,dx,dy,dz])]
  block(name+'.'+c['ref'],c['bounds'])
 boards[name]=b;x,y,z=pose;w,h=(40,50) if name=='main' else (38,48)
 block(name+' PCB',[x-w/2,y,z,x+w/2,y+h,z+1.6])
 for i,(hx,hy,diam)in enumerate(b['holes']):
  hx+=x;hy+=y;block(f'{name} support {i}',[hx-2.5,hy-2.5,z-3.5,hx+2.5,hy+2.5,z],'mount')
  if name=='main' and i==1:
   block('main locator pin',[hx-.95,hy-.95,z,hx+.95,hy+.95,z+2.1],'mount');continue
  block(f'{name} nut {i}',[hx-2.3,hy-2.3,z-5.1,hx+2.3,hy+2.3,z-3.5],'mount')
  block(f'{name} head/washer {i}',[hx-2.4,hy-2.4,z+1.6,hx+2.4,hy+2.4,z+3.5],'mount')
  block(f'{name} screw tail {i}',[hx-1,hy-1,z-5.9,hx+1,hy+1,z-5.1],'mount')
block('screen provisional',[-17.9,161.85,18,17.9,200.15,19.8])
# Shift screen down to keep its upper edge away from the top coupling.
items[-1]['bounds'][1]-=4;items[-1]['bounds'][4]-=4
block('screen lens',[-16.6,160.4,22,16.6,193.6,23],'window')
block('NFC coil',[-14,164,-23,14,192,-22])
block('NFC ferrite',[-14,164,-22,14,192,-21.5])
block('main plug',[13.45,170.9,1.6,21.8,185.1,8.9])
block('power plug',[12.45,100.9,-7.4,20.8,115.1,-.1])
block('battery isolation sheet',[-11,74,.8,11,113,1.3])
block('power button guided stem',[-15.2,77.5,-5.4,-12.2,80.5,25.0],'button')
def radius(b):return max(math.hypot(x,z)for x in[b[0],b[3]]for z in[b[2],b[5]])
radial=[dict(name=a['name'],margin=round((30 if a['kind']in['window','button']else 27.6)-radius(a['bounds']),3))for a in items]
def overlaps(a,b):return all(min(a[i+3],b[i+3])-max(a[i],b[i])>.025 for i in range(3))
coll=[]
for a in items:
 if a['kind']!='mount':continue
 for b in items:
  if '.' in b['name'] and overlaps(a['bounds'],b['bounds']):coll.append([a['name'],b['name']])
component_pairs=[]
for a in boards['main']['components']:
 for b in boards['power']['components']:
  if overlaps(a['bounds'],b['bounds']):component_pairs.append([a['ref'],b['ref']])
wire=[]
for i in range(101):
 t=i*math.pi/200;wire.append([21.8+4*math.sin(t),.9+4*math.cos(t)])
wr=max(math.hypot(x,z)+.5 for x,z in wire)
metric=dict(outer_diameter=60,inner_diameter=55.2,wall=2.4,length=200,main_pose=poses['main'],power_pose=poses['power'],main_range=[144,194],power_range=[74,122],pcb_edge_axial_gap=22,antenna_range=[137.605,143.605],power_to_antenna_gap=15.605,battery_range=[43,112.2],battery_max=[19.1,69.2],battery_center_xz=[0,12],battery_cavity=[20.5,74],battery_to_antenna_gap=25.405,power_max_top=-.1,battery_nearest_z=2.45,battery_power_height_budget_gap=2.55,battery_to_isolation_sheet_gap=1.15,screen_center_y=177,screen_body=[35.8,38.3,1.8],screen_back_z=18,screen_to_main_height_budget_gap=9.1,screen_lens_front_z=23,screen_center_recess=7,wire_bend_allowance=4,wire_to_wall_gap=27.6-wr,minimum_outer_diameter_for_routed_wire=2*(wr+.5+2.4),main_hole_pitch=[32,42],power_hole_pitch=[30,40],mount_hole_diameter=2.2,usb_y=86,usb_z=-5.7,usb_mouth_x=19.09409694-5.7,usb_pocket=[18,12,18],blade_board_in_handle_bom=False,blade_connector_mouth_y=196.8,body_interface_y=200,blade_origin_y_mated_assumption=199.3,blade_engagement_assumption=2.5,main_fixing='3 M2 + one 1.9mm uncapped plastic locator at local (+16,+4)')
metric['usb_recess']=math.sqrt(30**2-metric['usb_z']**2)-metric['usb_mouth_x']
metric['battery_slot_radial_margin']=27.6-(12+20.5/2)
output=dict(version='V0.6 uniform cylinder, TWO handle PCBs',source=old['source'],sha256=old['sha256'],boards=boards,items=items,metrics=metric,wire_curve=wire,radial_checks=sorted(radial,key=lambda a:a['margin']),mount_overlaps=coll,board_component_overlaps=component_pairs,limitations=['Native PCB XY from saved V082 snapshot; physical heights partly provisional.','Battery, screen and cable envelopes need measurements.','No STL/STEP/Blender or solid CAD model created.','Blade PCB is mechanically attached to removable blade, not handle BOM; only mating interface is reserved.','No full CAD collision, structural load, RF, thermal or manufacturing tolerance validation.'])
(O/'dimensions_and_checks.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
print(json.dumps(dict(metrics=metric,radial_worst=output['radial_checks'][:8],mount_overlaps=coll,component_overlaps=component_pairs),ensure_ascii=False,indent=2))
