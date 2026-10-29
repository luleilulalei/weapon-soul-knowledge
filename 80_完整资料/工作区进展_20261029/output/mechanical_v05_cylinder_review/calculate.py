import json,sys,math,hashlib,itertools
from pathlib import Path
sys.path.insert(0,'output/layout_v074m')
from geometry import local,transform,parse_source,path_points,MM
O=Path(__file__).resolve().parent
src=Path('output/pcb_v082_dedicated_planes/after_layout.json')
D=json.loads(src.read_text())['boards'];F=json.load(open('output/pcb_v082_dedicated_planes/footprints.json'))
old=json.load(open('output/mechanical_v04/model/pcb_input.json'))
heights={c['ref']:c['height_mm'] for c in old['components']}
heights.update(J301=7.3,J401=7.3,J202=3.0,U201=1.0,Y201=1.2,L201=1.8)
poses={'main':(-4,136,6),'power':(-4,156,-8.4),'blade':(-4,191.3,6)}
boards={};items=[]
for name,b in D.items():
 dx,dy,z=poses[name];rows=parse_source(b['source'])
 outline=next(a for h,a in rows if h['type']=='POLY' and a.get('layerId')==11)
 pts=[(x*MM,y*MM) for x,y in path_points(outline['path'])]
 holes=[(p[1]*MM,p[2]*MM,p[3]*MM*2) for h,a in rows if h['type']=='FILL' and a.get('layerId')==12 for p in a.get('path',[]) if p[0]=='CIRCLE']
 freeholes=[a for h,a in rows if h['type']=='PAD' and not a.get('netName')]
 comp=[]
 for c in b['components']:
  r=c['designator'];p=dict(x=c['x']*MM,y=c['y']*MM,rotation=c['rotation'],layer=c['layer'])
  geom=local(F[c['footprint']['uuid']]);bb=list(transform(geom['court'],p).bounds)
  body=list(transform(geom['body'],p).bounds)
  h=heights.get(r,1.6 if r.startswith('U') else 1.4 if r.startswith(('C','L')) else 0.9)
  zz=(z+1.6,z+1.6+h) if p['layer']==1 else(z-h,z)
  bounds=[bb[0]+dx,bb[1]+dy,zz[0],bb[2]+dx,bb[3]+dy,zz[1]]
  rec=dict(ref=r,layer=p['layer'],body=body,court=bb,placement=p,height=h,bounds=bounds,status='datasheet max' if r in ['J301','J401'] else 'legacy nominal / conservative allocation; sample pending')
  comp.append(rec);items.append(dict(name=name+'.'+r,bounds=bounds))
 boards[name]=dict(uuid=b['uuid'],pose=poses[name],outline=pts,holes=holes,freeholes=freeholes,components=comp,thickness=1.6)
def block(n,b):items.append(dict(name=n,bounds=b));return b
block('main PCB',[-24,136,6,16,186,7.6]);block('power PCB',[-23,156,-8.4,15,204,-6.8])
block('screen provisional',[-17.9,157.85,18,17.9,196.15,19.8])
block('screen foam / lens',[-18.5,157.5,19.8,18.5,196.5,21.6])
block('NFC coil provisional',[-14,169,-25.5,14,197,-24.5])
block('NFC ferrite',[-14,169,-24.5,14,197,-24])
block('main plug conservative',[15.15,162.9,7.6,23.5,177.1,14.9])
block('power plug conservative',[14.15,182.9,-6.8,22.5,197.1,.5])
for name in ['main','power']:
 dx,dy,z=poses[name]
 for i,(x,y,d)in enumerate(boards[name]['holes']):
  x+=dx;y+=dy
  block(f'{name} support {i}',[x-2.5,y-2.5,z-3.5,x+2.5,y+2.5,z])
  if name=='main' and i==1:
   block('main locator pin (R1 corner)',[x-.95,y-.95,z,x+.95,y+.95,z+2.1])
   continue
  block(f'{name} nylon nut {i}',[x-2.3,y-2.3,z-5.1,x+2.3,y+2.3,z-3.5])
  block(f'{name} washer/head {i}',[x-2.4,y-2.4,z+1.6,x+2.4,y+2.4,z+3.5])
  block(f'{name} screw tail {i}',[x-1,y-1,z-5.9,x+1,y+1,z-5.1])
def radius_at(y):
 if y<118:return 17.6
 if y<136:return 17.6+(y-118)*12/18
 return 29.6
def margin(a):
 x0,y0,z0,x1,y1,z1=a['bounds'];rr=max(math.hypot(x,z)for x in [x0,x1]for z in[z0,z1]);return min(radius_at(y) for y in [y0,y1])-rr
radial=[dict(name=a['name'],margin=round(margin(a),3)) for a in items]
def overlap(a,b):
 return all(min(a[i+3],b[i+3])-max(a[i],b[i])>.025 for i in range(3))
coll=[]
for a in items:
 if not any(t in a['name'] for t in ['support','nylon nut','washer/head','screw tail','locator pin']):continue
 for b in items:
  if '.' not in b['name']:continue
  if overlap(a['bounds'],b['bounds']):coll.append([a['name'],b['name']])
def ref(n,r):return next(c for c in boards[n]['components']if c['ref']==r)
u=ref('main','U1');antenna_y0=136+u['body'][1];antenna_y1=antenna_y0+6.0
# An explicit routing allowance, not a manufacturer cable bend specification.
wire=[]
for i in range(101):
 t=math.pi*i/200;x=23.5+4*math.sin(t);z=6.9+4*math.cos(t)
 wire.append(math.hypot(x,z)+.5)
metrics=dict(head_outer=64,head_inner=59.2,grip_outer=40,grip_inner=35.2,wall=2.4,body_length=218,grip_usable=110,main_hole_pitch=[32,42],power_hole_pitch=[30,40],hole_diameter=2.2,board_bottom_plane_spacing=14.4,board_face_gap=12.8,main_bottom_allocation=4.0,power_top_allocation=7.3,conservative_component_gap=1.5,screen_to_main_max=3.1,pcb_center_shift=-4,power_axial_shift=20,battery_max=[19.1,69.2],battery_range=[43,112.2],battery_cavity=[20.5,74],battery_radial_gap=.7,battery_axial_total_gap=4.8,antenna_y=[antenna_y0,antenna_y1],battery_to_antenna=antenna_y0-112.2,power_to_antenna=156-antenna_y1,screen_to_antenna=157.85-antenna_y1,screen_body=[35.8,38.3,1.8],screen_center_y=177,usb_center_y=168,usb_center_z=-5.1,usb_mouth_x=ref('power','J101')['body'][2]-4,usb_pocket=[18,12,18],usb_max_boot=[17,10],harness_bend_allowance=4,wire_min_wall_gap=29.6-max(wire),minimum_screen_inner_margin=29.6-math.hypot(18.5,21.6),nfc_to_power_allocated=9.7,adapter_origin_y=191.3,adapter_board_edge_gap=5.3,adapter_insertion_assumed=2.5)
metrics['usb_radial_recess']=math.sqrt(32**2-metrics['usb_center_z']**2)-metrics['usb_mouth_x']
metrics['wire_required_outer_diameter']=2*(max(wire)+.5+2.4)
metrics['main_fixing']='3 M2 nylon screws + 1 uncapped 1.9mm locator/support at local (+16,+4); avoids R1'
metrics['main_R1_pin_clearance']=math.hypot(16-15.15660164,5.5679975-4)-.95
out=dict(version='V0.5 cylinder 2D review',date='2026-10-28',basis='saved V082 after_layout snapshot; live EDA session returned no active project',source=str(src.resolve()),sha256=hashlib.sha256(src.read_bytes()).hexdigest(),boards=boards,items=items,metrics=metrics,radial_checks=sorted(radial,key=lambda r:r['margin']),mount_component_overlaps=coll,limitations=['No solid model, STL, or STEP generated.','Conservative component envelopes; heights and assembled cable geometry are not fully verified.','Main board is shifted -4mm laterally and power shifted +20mm axially.','Screen and protected battery are inherited provisional envelopes, not measurements of user hardware.','USB boot pocket and power-button linkage require sample validation.','Antenna estimate uses 6mm from module outer tip; no RF qualification.'])
(O/'dimensions_and_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(dict(metrics=metrics,worst_radial=out['radial_checks'][:10],mount_component_overlaps=coll),ensure_ascii=False,indent=2))
