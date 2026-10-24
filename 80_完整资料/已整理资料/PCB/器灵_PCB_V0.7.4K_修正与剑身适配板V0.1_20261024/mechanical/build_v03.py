import bpy,bmesh,math,json,os,struct
from mathutils import Vector,Matrix
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT.parent
for p in [ROOT/'stl',OUT/'renders',OUT/'verification']:p.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001;scene.unit_settings.length_unit='MILLIMETERS'
exec((ROOT/'helpers_fragment.txt').read_text())
# New mechanical model, current PCB. All coordinates millimeters, front +Z.
PCB=json.loads((ROOT/'pcb_input.json').read_text());SHIFT=PCB['pcb_shift_y_mm'];SY=138.5
P={'version':'V0.3R2 V074K layout fit review','body_length':190,'maximum_width':62,'front_depth':15.5,'rear_depth':24.5,'wall':2.4,'pcb_shift_y':SHIFT,'pcb_bottom_y':107.5,'pcb_top_y':179,'pcb_thickness':1.6,'screen_center_y':SY,'screen_assumed_body':[35.8,38.3,1.8],'screen_status':'UNCONFIRMED USER PANEL; replaceable bezel and retainer','battery_center':[0,48,-8.5],'battery_max':[19.1,69.2],'nfc_antenna_assumed':[28,35,1],'nfc_controller_nominal':[25.43,20.35],'speaker_selected':[20,5.1],'lra_assumed':[8.2,2.7],'print_fit_per_side':.3,'fasteners':'PCB M2 nylon screws/washers mandatory near antenna; other fasteners per fit test','status':'FIT REVIEW; NOT ASSEMBLY OR LOAD QUALIFIED'}
(ROOT/'parameters.json').write_text(json.dumps(P,indent=2))
parts=[];dummies=[];reviewobjs=[]
def part(o):parts.append(o);return o
def proxy(o,kind='review placeholder'):
 dummies.append(o);o['validation_status']=kind;return o
def prism(n,xy,z0,z1,m=None,c=prod):
 k=len(xy);vs=[(x,y,z)for z in [z0,z1]for x,y in xy];fs=[tuple(reversed(range(k))),tuple(range(k,2*k))]+[(i,(i+1)%k,(i+1)%k+k,i+k)for i in range(k)]
 me=bpy.data.meshes.new(n);me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new(n,me);c.objects.link(o)
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
 if m:o.data.materials.append(m)
 return o
profile=[(0,17),(5,21),(14,23),(78,23),(95,23),(112,25),(125,28),(140,31),(153,31),(165,27),(180,24),(190,23)]
def shellbody(n,z0,z1,inset=0):
 pts=[(w-inset,y)for y,w in profile]
 if inset:pts[0]=(pts[0][0],inset);pts[-1]=(pts[-1][0],190-inset)
 return prism(n,pts+[(-x,y)for x,y in reversed(pts)],z0,z1)
front=part(shellbody('P01_front_shell',0,15.5));front.data.materials.append(ivory);bevel(front,1)
boolean(front,shellbody('front cavity',-2,13.1,2.4))
back=part(shellbody('P02_rear_shell',-24.5,0));back.data.materials.append(dark);bevel(back,1)
boolean(back,shellbody('rear cavity',-22.1,2,2.4))
# Six shell screws, metal nuts trapped in front bosses; no screw crosses battery body.
SHELL_HOLES=[(-17,9),(17,9),(-19.5,87),(19.5,87),(-20,181),(20,181)]
for x,y in SHELL_HOLES:
 union(front,cyl('front closure boss',3.45,15.5,(x,y,7.75)))
 union(back,cyl('rear closure boss',3.45,24.5,(x,y,-12.25)))
 boolean(front,cyl('shell screw clearance',1.4,25,(x,y,5)))
 boolean(front,cyl('M2p5 front nut recess',2.95,2.4,(x,y,14.35),verts=6))
 boolean(back,cyl('shell screw clearance',1.4,30,(x,y,-12)))
 boolean(back,cyl('shell screw head recess',2.7,2.5,(x,y,-23.3)))
# Alignment uses nonmetal dowels in the seam, separate from screws.
for x,y in [(-23.2,112),(23.2,112),(-26.4,162),(26.4,162)]:
 union(front,cyl('alignment peg',.9,1.8,(x,y,-.7),verts=32))
 boolean(back,cyl('alignment socket',1.2,2.6,(x,y,-1.15),verts=32))
# Replaceable display bezel: hard shell locates bezel, actual LCD supported with separate soft pads.
boolean(front,cyl('bezel opening',20.2,22,(0,SY,12)))
boolean(front,cube('LCD shoulder opening',(26.6,9,22),(0,SY-17.5,12)))
boolean(front,cyl('bezel flange recess',22.3,1.9,(0,SY,15.1)))
for x in [-25.3,25.3]:
 union(front,cyl('screen mounting boss',3.2,7.5,(x,SY,11.75)))
 boolean(front,cyl('screen M2 clearance',1.1,15,(x,SY,12)))
 boolean(front,cube('retainer rear insertion',(10,6,12),(x-1.5*(1 if x>0 else -1),SY,4.95)))
 boolean(front,cube('bezel ear seating pocket',(9,6.6,1.7),(x-1.5*(1 if x>0 else -1),SY,15.1)))
bezel=part(cyl('P04_replaceable_screen_bezel',21.95,1.4,(0,SY,15.0),copper))
union(bezel,cube('bezel lower flange',(28.6,9.8,1.4),(0,SY-17.5,15.0)))
boolean(front,cube('lower flange recess',(29.2,10.4,1.7),(0,SY-17.5,15.1)))
union(bezel,cube('lower shoulder skirt',(26,8,3.5),(0,SY-17.5,12.75)))
union(bezel,cyl('LCD locating skirt',19.8,3.5,(0,SY,12.75)))
for x in [-25.3,25.3]:
 union(bezel,cube('bezel ear',(8,6,1.4),(x-1.5*(1 if x>0 else -1),SY,15)))
 boolean(bezel,cyl('bezel screw',1.15,10,(x,SY,14)))
# Universal cavity deliberately larger than the assumed circular 35.8 mm body and lower shoulder.
boolean(bezel,cyl('LCD body recess',18.2,5,(0,SY,11.9)))
boolean(bezel,cube('LCD lower shoulder recess',(24,6.5,5),(0,SY-17.0,11.9)))
boolean(bezel,cyl('view aperture',16.6,12,(0,SY,15)))
boolean(bezel,cube('flex exit',(15,8,8),(0,SY-20.5,11)))
ret=part(cyl('P05_screen_rear_retainer',19.55,1.2,(0,SY,10.25),copper))
boolean(ret,cyl('retainer central opening',16.9,5,(0,SY,10.25)))
for x in [-25.3,25.3]:
 union(ret,cube('retainer ear',(9.5,5,1.2),(x-2*(1 if x>0 else -1),SY,10.25)))
 boolean(ret,cyl('retainer screw',1.15,5,(x,SY,10.25)))
boolean(ret,cube('retainer flex exit',(16,9,5),(0,SY-20,10.25)))
# Top axial interface entrance, with asymmetric key. Contact and load latch remain sample-dependent.
union(front,cube('top contact reinforcement',(26,10,13.0),(0,185,6.5)))
for o in [front,back]:
 boolean(o,cube('axial contact mouth',(23.2,22,12.4),(0,187,4.0)))
union(front,cube('polarizing rib',(1.2,5,2),(9.5,187.5,9.2)))
cap=part(cube('P11_keyed_top_dust_cap',(25.8,1.8,13),(0,191.0,5.1),copper,bev=.6))
union(cap,cube('cap spigot',(21.3,5.2,9.5),(0,187.5,5.1),copper,bev=.3))
boolean(cap,cube('key relief',(2,8,3),(9.5,188,9.2)))
# USB opening follows actual J101; decorative surrounds do not bear on the socket.
for o in [front,back]:boolean(o,cube('USB plug access',(14,12.3,7.2),(30,146.5,3.2),bev=.6))
# Power key: simple trapped plunger with guide, no exposed boot/reset.
PX,PY=-10,164.5
union(front,cyl('power plunger guide',4,7,(PX,PY,11.5)))
boolean(front,cyl('plunger bore',2.25,22,(PX,PY,8)))
button=part(cyl('P06_power_plunger',2.0,12.7,(PX,PY,10.3),copper))
union(button,cyl('plunger retaining flange',3.5,1.2,(PX,PY,7.05),copper))
union(button,cyl('power finger face',3.5,1.1,(PX,PY,16.75),copper))
# Actual PCB carrier: four M2 holes at the native coordinates; carrier fixes to rear shell.
carrier=part(cube('P03_PCB_four_hole_carrier',(42,59,2),(0,145,-7.4),copper))
boolean(carrier,cube('carrier open center',(36,51,8),(0,145,-7.4)))
# End bridge y=115.5..119.5 and170.5..174.5; component back budget >=6.4mm.
PCB_H=[(x,y+SHIFT)for x,y in PCB['holes']]
for x,y in PCB_H:
 union(carrier,cyl('PCB M2 standoff',2.6,6.6,(x,y,-3.3)))
 boolean(carrier,cyl('PCB M2 through',1.1,15,(x,y,-4)))
for x,y in [(x,y)for x in [-20,20]for y in [129,172.5]]:
 union(carrier,cyl('carrier mounting tab',3.1,2,(x,y,-7.4)))
 boolean(carrier,cyl('carrier M2p5 hole',1.4,8,(x,y,-7.4)))
 union(back,cyl('carrier rear pedestal',3.4,13.8,(x,y,-15.3)))
 boolean(back,cyl('carrier screw pilot',1.15,8,(x,y,-10.5)))
for x in [-20,20]:boolean(back,cyl('upper carrier lateral clearance',3.35,2.6,(x,172.5,-7.1)))
# Battery lower cradle, removable; protected-pack maximum from previous selected pack.
by,bz=48,-8.5
cradle=part(cyl('P07_battery_cradle',11.5,74,(0,by,bz),copper,axis='Y'))
boolean(cradle,cube('open upper half',(50,90,40),(0,by,bz+20)))
union(cradle,cube('battery base plate',(37,64,1.8),(0,47.5,-19.1)))
boolean(cradle,cyl('base plate bore',10.15,80,(0,by,bz),axis='Y'))
for y in [by-36.5,by+36.5]:union(cradle,cube('battery end fence',(23,1.6,9),(0,y,-15.5)))
for x in [-15.5,15.5]:
 for y in [25,70]:
  boolean(cradle,cyl('battery M2 hole',1.15,8,(x,y,-19)))
  union(back,cyl('battery pedestal',3.0,2.3,(x,y,-21.15)))
  boolean(back,cyl('battery pilot',.95,6,(x,y,-20.6)))
for y in [30,65]:
 for x in [-11,11]:boolean(cradle,cube('strap slit',(2.6,8,8),(x,y,-17)))
boolean(cradle,cube('battery wire exit',(12,6,8),(0,84.5,-12)))
# Side speaker chamber: sleeve facing left, away from main PCB and antenna.
speaker=part(cyl('P08_side_speaker_chamber',11.4,9.4,(-15.5,48,1),copper,axis='X'))
union(speaker,cube('speaker bolt spine',(9.4,28,5),(-15.5,48,-4)))
for y in [34,62]:union(speaker,cyl('speaker ear',3.5,9.4,(-15.5,y,-4),axis='X'))
boolean(speaker,cyl('speaker insertion pocket',10.3,6.8,(-18.3,48,1),axis='X'))
boolean(speaker,cyl('speaker back chamber',8.8,4.0,(-13.8,48,1),axis='X'))
for y in [34,62]:
 boolean(speaker,cyl('speaker screw',1.4,15,(-16,y,-4),axis='X'))
 boolean(speaker,cyl('speaker nut trap',2.95,2.2,(-12.2,y,-4),axis='X',verts=6))
for o in [front,back]:
 boolean(o,cyl('speaker opening',11.75,10,(-23,48,1),axis='X'))
 for y in [34,62]:boolean(o,cyl('speaker bolt access',1.4,12,(-23,y,-4),axis='X'))
grille=part(cyl('P09_side_speaker_grille',11.45,1.2,(-23.8,48,1),copper,axis='X'))
union(grille,cube('grille bolt bridge',(1.2,28,5),(-23.8,48,-4)))
for y in [34,62]:
 union(grille,cyl('grille bolt ear',3.5,1.2,(-23.8,y,-4),copper,axis='X'))
 boolean(grille,cyl('grille screw',1.4,5,(-23.8,y,-4),axis='X'))
for y in [-6,-3,0,3,6]:boolean(grille,cube('sound slit',(6,1.25,12),(-23.8,48+y,2),bev=.4))
speaker.location.x-=.8
boolean(back,cube('speaker inner flange relief',(1.2,35.5,7.5),(-20.7,48,-4)))
# NFC removable holder, antenna directly behind display; upper control module is separate.
nfc=part(cube('P10_rear_NFC_holder',(32,64,1.2),(0,150,-20.5),copper))
boolean(nfc,cube('antenna frame opening',(25.5,31.5,5),(0,SY,-20.5)))
for y in [117,184]:
 union(nfc,cyl('NFC mounting ear',3.4,1.2,(0,y,-20.5)))
 boolean(nfc,cyl('NFC M2 hole',1.15,5,(0,y,-20.5)))
 union(back,cyl('NFC rear pedestal',3.3,1.1,(0,y,-21.65)))
 boolean(back,cyl('NFC pilot',.95,5,(0,y,-22)))
# Module ledges; two loose nylon straps retain the provisional PCB, no invented mounting holes.
for x in [-12,12]:union(nfc,cube('NFC control module ledge',(3.5,23,3.1),(x,168,-18.45)))
for y in [161,175]:
 for x in [-14.4,14.4]:boolean(nfc,cube('NFC strap slit',(1.5,3,7),(x,y,-19)))
# LRA seat is in the front grip, short flexible wire to J110. Uses replaceable tape/foam.
MX,MY=12.5,76
union(front,cyl('LRA front mounting boss',6.0,6.1,(MX,MY,10.2)))
boolean(front,cyl('LRA fit pocket',4.35,4.2,(MX,MY,7.8)))
boolean(front,cube('LRA wire passage',(5.5,8,3),(MX,MY+5,7.3)))
lracap=part(cube('P12_LRA_retaining_bridge',(16,6,1.2),(MX,MY,5.5),copper))
for x in [MX-6.3,MX+6.3]:
 union(front,cyl('LRA cap anchor',1.5,7.0,(x,MY,9.8)))
 boolean(front,cyl('LRA cap pilot',.8,7,(x,MY,8)))
 boolean(lracap,cyl('LRA cap clearance',.9,5,(x,MY,5.5)))
boolean(lracap,cyl('LRA central relief',2.9,4,(MX,MY,5.5)))
# Microphone lateral duct, seated above top port via silicone gasket. Duct is separate.
# Position uses U5 envelope; acoustic aperture alignment remains sample-check item.
MICX,MICY=12.005,138.3
for o in [front,back]:boolean(o,cyl('microphone side port',1.1,12,(29,MICY,4.8),axis='X',verts=40))
duct=part(cube('P13_MIC_side_duct',(15.8,4,3.6),(19.9,MICY,4.8),copper,bev=.3))
boolean(duct,cyl('duct horizontal bore',1,19,(20.2,MICY,4.8),axis='X',verts=40))
boolean(duct,cyl('mic inlet',1,4.4,(MICX,MICY,3.0),verts=40))
union(duct,cube('mic foot',(4.2,4.8,1),(MICX,MICY,3.6),copper))
boolean(duct,cyl('mic inlet through foot',1,5,(MICX,MICY,3),verts=40))
# Duct anchors to front via two small self-tapping prototype screws, clear the USB.
for y in [MICY-4.6,MICY+4.6]:
 union(duct,cube('duct ear',(3.2,6,1.4),(24.8,y,6.1),copper))
 boolean(duct,cyl('duct clearance',.9,8,(24.8,y,6)))
 union(front,cyl('duct shell anchor',1.8,6.4,(24.8,y,10.1)))
 boolean(front,cyl('duct pilot',.7,7,(24.8,y,8.5)))
# Small sliding fit/fastener coupon, separate from assembly.
coupon=part(cube('P14_fit_coupon',(48,24,4),(65,25,2),copper))
for x,r in [(49,1),(58,1.1),(67,1.4),(76,1.5)]:boolean(coupon,cyl('trial hole',r,8,(x,20,2)))
for x,w in [(51,1.8),(64,2.0),(77,2.2)]:boolean(coupon,cube('board slot',(w,10,5),(x,31,3)))
# Exact board outline + actual holes. Its component solids are conservative envelopes, NOT vendor STEP.
board=proxy(prism('PCB_V074K_ACTUAL_OUTLINE',[(x,y+SHIFT)for x,y in PCB['outline']],0,1.6,blue,dum),'native outline/holes; thickness review assumption 1.6')
for x,y in PCB_H:boolean(board,cyl('PCB fixing hole',1.1,5,(x,y,.8)))
electronics=[]
for item in PCB['components']:
 r=item['ref'];x0,y0,x1,y1=item['bbox_xy'];h=item['height_mm'];l=item['placement']['layer'];z=1.6+h/2 if l==1 else -h/2
 o=proxy(cube('PCB_'+r,(x1-x0,y1-y0,h),((x0+x1)/2,(y0+y1)/2+SHIFT,z),glass if r.startswith('U') else copper if r.startswith('J') else dark,dum),item['height_status']);o['reference']=r;electronics.append(o)
# LCD placeholder includes circular face and conservative lower shoulder.
lcd=proxy(cyl('UNCONFIRMED_USER_GC9A01_SCREEN',17.9,1.8,(0,SY,12.65),glass,dum),'35.8 mm proxy from old screen, NOT user screen dimensions')
union(lcd,cube('LCD lower shoulder',(22,5,1.8),(0,SY-16.65,12.65),glass,dum))
battery=proxy(cyl('BATTERY_MAX_19p1x69p2',9.55,69.2,(0,by,bz),batteryMat,dum,axis='Y'),'prior selected protected pack max; actual pack/lead verification pending')
spk=proxy(cyl('SPEAKER_20mm_PROXY',10,5.1,(-18.6,48,1),dark,dum,axis='X'),'20mm diameter x5.1mm selected speaker envelope, sample pending')
ant=proxy(cube('NFC_ANTENNA_28x35_PROXY',(28,35,1),(0,SY,-19.3),blue,dum),'antenna dimensions provisional; rear-facing scan zone')
nfcboard=proxy(cube('NFC_CONTROL_25p43x20p35_PROXY',(25.43,20.35,3.6),(0,168,-15.0),blue,dum),'Seeed control board XY nominal; height allowance 3.6')
motor=proxy(cyl('LRA_LD0825_BODY_PROXY',4.1,2.7,(MX,MY,8.2),dark,dum),'current part proxy, fit and adhesive stack unconfirmed')
# Electrical interface cables are not made-up solids: preserve explicit service volumes.
for n,dim,pos in [('FPC_NO_FRONT_COMPONENTS',(7.25,8.4,4),(-19.875,149.9,3.6)),('J104_PLUG_SERVICE',(9.373845,11,4),(-21.3130775,139.4,-2)),('J201_PLUG_SERVICE',(8.73,8.4,4),(20.635,156.5,-2)),('J3_PLUG_SERVICE',(8.73,4.4,4),(-20.135,123.7,3.6)),('J110_PLUG_SERVICE',(8.73,4.4,4),(20.635,159.5,3.6)),('RF_REVIEW',(49,36,34),(0,101.2,3)),('BATTERY_UPPER_LEAD',(12,12,7),(0,90,-8.5))]:
 o=cube(n,dim,pos,None,reviews);o.hide_render=True;o.display_type='WIRE';reviewobjs.append(o)
# Touch electrode channels are optional nonmetallic adhesive installation areas, no conductive foil near antenna.
# Render-only friendly face, not printed; diagrams show exact manufactured meshes.
def curve(n,pts,r,material):
 cu=bpy.data.curves.new(n,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=2;sp=cu.splines.new('POLY');sp.points.add(len(pts)-1)
 for v,co in zip(sp.points,pts):v.co=(*co,1)
 o=bpy.data.objects.new(n,cu);viz.objects.link(o);o.data.materials.append(material);return o
face=[]
for x in [-6,6]:face.append(curve('display eye',[(x+2.4*math.cos(t),SY+2+2.4*math.sin(t),13.7)for t in [math.pi*i/24 for i in range(25)]],.45,cyan))
face.append(curve('display smile',[(2.5*math.cos(t),SY-4+1.4*math.sin(t),13.7)for t in [math.pi+math.pi*i/24 for i in range(25)]],.35,cyan))

# Replaceable accessory plug carrier: keyed alignment and axial hard-stop flange.
# It supports connector alignment only; blade retention/load structure is not qualified.
ADPY=181.524
adapter=part(cube('P15_adapter_alignment_carrier',(1.4,36,11.7),(-10.6,ADPY+18,3.95),copper))
union(adapter,cube('adapter right side',(1.4,36,11.7),(10.6,ADPY+18,3.95)))
# Relieve inner sides to give 0.30mm lateral clearance around 20mm PCB.
for x in [-9.5,9.5]:boolean(adapter,cube('PCB side clearance',(1.6,33,2.2),(x,ADPY+16,0.8)))
union(adapter,cube('adapter roof',(22.6,36,1.0),(0,ADPY+18,9.3)))
union(adapter,cube('hard stop flange',(26,2,12),(0,191,4)))
boolean(adapter,cube('flange circuit opening',(20.6,3,9.0),(0,191,3.2)))
boolean(adapter,cube('asymmetric key relief',(2.4,10,3),(9.6,187.5,9.0)))
for x in [-7.5,7.5]:
 union(adapter,cube('adapter fixing bridge',(5,4,1.0),(x,ADPY+18,-1.4)))
 union(adapter,cyl('adapter M2 pilot boss',2.1,1.8,(x,ADPY+18,-.9)))
 boolean(adapter,cyl('adapter M2 pilot',.85,4,(x,ADPY+18,-1.0)))
 boolean(adapter,cyl('driver access',2.3,4,(x,ADPY+18,9.3)))
adapter_board=proxy(prism('ADAPTER_ACTUAL_OUTLINE',[(-9, 181.524), (9, 181.524), (10, 182.524), (10, 212.524), (9, 213.524), (-9, 213.524), (-10, 212.524), (-10, 182.524)],0,1.6,blue,dum),'20x32 native adapter outline')
boolean(adapter_board,cyl('adapter fixing hole',1.1,5,(-7.5,199.524,.8)))
boolean(adapter_board,cyl('adapter fixing hole',1.1,5,(7.5,199.524,.8)))
proxy(cube('ADAPTER_J701',(15.24,6.24000022,2.54),(0.0,184.75400113,2.87),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_J702',(6.100191000000001,5.650026799999999,2.9),(0.0,210.1364966,3.05),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_U701',(7.0356222,7.4839322,1.6),(-0.19160489999999974,195.524,2.4000000000000004),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_U702',(2.4999187999999997,2.2000718,1.6),(-4.5,204.52403809999998,2.4000000000000004),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_U703',(3.8000177999999996,3.327907999999997,1.6),(4.5,204.409954,2.4000000000000004),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_C701',(1.4201393999999998,2.7799284,0.9),(-0.9800380999999999,190.0240508,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_C702',(1.4201394,2.7799284,0.9),(-3.1000381,190.0240508,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_R701',(1.3212063999999994,2.7701747999999995,0.9),(4.0,190.024,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_C703',(1.4201394,2.7799284,0.9),(1.2999619,190.0240508,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_R702',(1.3212064000000003,2.7701747999999995,0.9),(-7.5,204.524,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_C704',(2.7799284,1.4201394,0.9),(-3.1999492000000003,201.02403809999998,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_C705',(2.7799284,1.4201394,0.9),(-4.699949200000001,207.8240381,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_C706',(2.7799284,1.4201394,0.9),(5.0000508,207.52403809999998,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_C707',(1.420139400000001,2.7799283999999993,0.9),(7.5999619,204.5240508,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_R703',(2.7701748,1.3212064000000012,0.9),(0.0,206.124,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cube('ADAPTER_R704',(2.7701748000000004,1.3212064000000012,0.9),(3.6,200.724,2.0500000000000003),blue,dum),'native footprint envelope; actual sample pending')
proxy(cyl('ADAPTER_TAIL_1',.23,1.6,(-6.35,187.224,-.8),copper,dum),'399 0.46mm tail, nominal 1.6mm below PCB')
proxy(cyl('ADAPTER_TAIL_2',.23,1.6,(-3.81,187.224,-.8),copper,dum),'399 0.46mm tail, nominal 1.6mm below PCB')
proxy(cyl('ADAPTER_TAIL_3',.23,1.6,(-1.27,187.224,-.8),copper,dum),'399 0.46mm tail, nominal 1.6mm below PCB')
proxy(cyl('ADAPTER_TAIL_4',.23,1.6,(1.27,187.224,-.8),copper,dum),'399 0.46mm tail, nominal 1.6mm below PCB')
proxy(cyl('ADAPTER_TAIL_5',.23,1.6,(3.81,187.224,-.8),copper,dum),'399 0.46mm tail, nominal 1.6mm below PCB')
proxy(cyl('ADAPTER_TAIL_6',.23,1.6,(6.35,187.224,-.8),copper,dum),'399 0.46mm tail, nominal 1.6mm below PCB')
# Mated preview is a separate assembly: dust cap must be removed for insertion.
cap.hide_render=True;cap.hide_set(True)
# Deterministic topology QA and literal-mm STL export. Do not auto-fill arbitrary holes.
report=[]
for o in parts:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bmesh.ops.triangulate(bm,faces=list(bm.faces),ngon_method='EAR_CLIP');bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(o.data)
 entry={'part':o.name,'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'boundary_edges':sum(e.is_boundary for e in bm.edges),'volume_mm3':abs(bm.calc_volume(signed=True)),'assembly_bbox_mm':list(o.dimensions)};report.append(entry);bm.free()
 original=o.matrix_world.copy()
 # All parts placed on build plane. Both shell cavities face up; small local supports may still be required.
 if o==front:o.rotation_euler.x+=math.pi
 if o in [speaker,grille]:o.rotation_euler.y+=math.pi/2
 bpy.context.view_layer.update();vs=[o.matrix_world@Vector(v)for v in o.bound_box];o.location-=Vector(((min(v.x for v in vs)+max(v.x for v in vs))/2,(min(v.y for v in vs)+max(v.y for v in vs))/2,min(v.z for v in vs)))
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 bpy.ops.wm.stl_export(filepath=str(ROOT/'stl'/(o.name+'.stl')),export_selected_objects=True,apply_modifiers=True,global_scale=1,use_scene_unit=False)
 o.matrix_world=original
(ROOT/'mesh_validation.json').write_text(json.dumps(report,indent=2))
(ROOT/'component_placements.json').write_text(json.dumps([{'name':o.name,'center':list(o.location),'bbox':list(o.dimensions),'status':o.get('validation_status','')}for o in dummies],indent=2))
# Assembly STL is for viewing only, kept apart from individually oriented print parts.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:
 if o not in [coupon,cap]:o.select_set(True)
bpy.ops.wm.stl_export(filepath=str(OUT/'Spirit_V03_assembly_VIEW_ONLY.stl'),export_selected_objects=True,apply_modifiers=True,global_scale=1,use_scene_unit=False)
# Native CAD saves assembled meshes with transparent provenance and optional service envelopes.
scene['STATUS']='V0.3R2 V074K-based review STL; real screen/FPC/NFC/plug dimensions and physical fit not validated.'
scene['DATUM']='mm; X width, Y bottom-to-top, +Z screen. Native PCB Y shifted +27.5, Z bottom=0.'
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1200;scene.render.resolution_y=1600;scene.render.resolution_percentage=100
scene.world.color=(.3,.3,.3);scene.view_settings.view_transform='AgX'
for pos,power,size in [((120,160,280),1600000,180),((-160,120,120),1000000,130),((0,240,-180),1200000,160)]:
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,100,0))-o.location).to_track_quat('-Z','Y').to_euler();move(o,viz)
bpy.ops.object.camera_add();cam=bpy.context.object;move(cam,viz);cam.data.type='ORTHO';scene.camera=cam

def camera(pos,target,scale):cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
camera((135,-35,410),(0,96,0),220);coupon.hide_render=True;coupon.hide_set(True)
for o in reviews.objects:o.hide_set(True)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location=Vector((0,96,0));area.spaces.active.region_3d.view_distance=240;area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion();area.spaces.active.region_3d.view_perspective='ORTHO'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Spirit_V03_V074K_review.blend'))
print('TOPOLOGY',json.dumps(report),flush=True)
if os.getenv('SPIRIT_SKIP_RENDERS')=='1':
 if os.getenv('SPIRIT_VERIFY')=='1':exec((ROOT/'verify_v03.py').read_text())
 if os.getenv('SPIRIT_RENDER_FINAL')=='1':
  check=json.loads((OUT/'verification/geometry.json').read_text())
  assert not check['collisions'] and all(x['components']==1 and x['bad_edges']==0 for x in check['mesh']),check
  exec((ROOT/'render_v03.py').read_text())
 raise SystemExit
for fname,pos,target,scale in [('01_front',(135,-35,410),(0,96,0),220),('02_rear',(-135,250,-430),(0,96,-4),220)]:
 camera(pos,target,scale);scene.render.filepath=str(OUT/'renders'/f'{fname}.png');bpy.ops.render.render(write_still=True)
# Open rear: rear and detachable mounted rear contents displaced as an exploded service view.
orig={o:o.location.copy()for o in parts+dummies+face}
front.location.x=-65;bezel.location.x=-65;ret.location.x=-65;button.location.x=-65;duct.location.x=-65;lracap.location.x=-65;motor.location.x=-65;lcd.location.x=-65
for o in face:o.location.x=-65
back.location.x=75;cradle.location.x=75;nfc.location.x=75;ant.location.x=75;nfcboard.location.x=75;battery.location.x=75;speaker.location.x+=75;grille.location.x+=75
cap.location.y+=15
camera((200,15,460),(5,98,0),285);scene.render.resolution_x=1800;scene.render.resolution_y=1500;scene.render.filepath=str(OUT/'renders/03_exploded.png');bpy.ops.render.render(write_still=True)
for o,p in orig.items():o.location=p
# Back cover off, looking into real motherboard and battery arrangement.
back.hide_render=True;nfc.hide_render=True;ant.hide_render=True;nfcboard.hide_render=True;cradle.hide_render=True
camera((-120,15,-460),(0,96,-3),225);scene.render.resolution_x=1200;scene.render.resolution_y=1600;scene.render.filepath=str(OUT/'renders/04_internal.png');bpy.ops.render.render(write_still=True)
print('BUILD_COMPLETE',flush=True)
