import bpy, math, json, os, bmesh
from mathutils import Vector, Matrix
ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.dirname(ROOT)
os.makedirs(ROOT+'/stl',exist_ok=True); os.makedirs(OUT+'/renders',exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=.001; scene.unit_settings.length_unit='MILLIMETERS'
P={'body_length':190,'body_max_width':60,'body_depth':49,'front_depth':19,'rear_depth':30,'wall':2.4,'screen_diameter':35.6,'screen_thickness':1.6,'screen_window':33.2,'screen_y':140,'screen_body_height':38.1,'screen_fpc_length':47.5,'screen_fpc_trial_radius':6.7,'screen_fpc_tip_width':5.5,'screen_fpc_tip_thickness':.3,'pcb_width':34,'pcb_length':105,'pcb_thickness':1.6,'battery_diameter':19.1,'battery_length':69.2,'battery_center_y':96,'battery_center_z':-15,'battery_installation_diameter':22,'battery_installation_length':72,'fit_gap':.3,'screw_clearance':2.8,'nut_af':5.2}
paramfile=ROOT+'/parameters.json'
if os.path.exists(paramfile): P.update(json.load(open(paramfile)))
# User withdrew the central speaker arrangement; reject legacy parameters explicitly.
for key in list(P):
 if key.startswith('pcb_top_keepout_'): del P[key]
P['speaker_mount_status']='WITHDRAWN: new position and acoustic path pending PCB/mechanical co-design'
json.dump(P,open(paramfile,'w'),indent=2)
parts=[]; dummies=[]
def coll(name):
 c=bpy.data.collections.new(name); scene.collection.children.link(c); return c
prod=coll('01_PRINTED_PARTS_mm'); dum=coll('02_UNPRINTED_DUMMY_COMPONENTS'); reviews=coll('03_REVIEW_VOLUMES_NOT_FIT_APPROVAL'); viz=coll('04_RENDER_ONLY')
def move(o,c):
 for cc in list(o.users_collection): cc.objects.unlink(o)
 c.objects.link(o)
def mat(n,c,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=(*c,1); bs.inputs['Metallic'].default_value=metal; bs.inputs['Roughness'].default_value=.3; return m
ivory=mat('Warm ceramic | printed polymer',(0.65,.64,.57)); dark=mat('Graphite polymer',(.055,.07,.08)); copper=mat('Ochre polymer, NOT metal',(.36,.23,.095)); blue=mat('Dummy PCB',(.02,.18,.20)); batteryMat=mat('Battery dummy',(.22,.27,.31)); glass=mat('Display black',(.005,.015,.025)); cyan=mat('Expression cyan',(.02,.6,.85));
cyan.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(.01,.5,1,1); cyan.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=2

def finish(o,n,m=None,c=prod):
 o.name=n; move(o,c)
 if m: o.data.materials.clear(); o.data.materials.append(m)
 return o

def cube(n,dim,pos,m=None,c=prod,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos); o=bpy.context.object; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bev:
  mod=o.modifiers.new('Rounded edges','BEVEL'); mod.width=bev; mod.segments=3; bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier=mod.name)
 return finish(o,n,m,c)
def cyl(n,r,depth,pos,m=None,c=prod,axis='Z',verts=96):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=pos); o=bpy.context.object
 if axis=='Y': o.rotation_euler.x=math.pi/2
 if axis=='X': o.rotation_euler.y=math.pi/2
 bpy.ops.object.transform_apply(location=False,rotation=True,scale=True); return finish(o,n,m,c)
def boolean(a,b,op='DIFFERENCE'):
 bpy.context.view_layer.objects.active=a; mod=a.modifiers.new(op,'BOOLEAN'); mod.operation=op; mod.solver='EXACT'; mod.object=b; bpy.ops.object.modifier_apply(modifier=mod.name); bpy.data.objects.remove(b,do_unlink=True)
def union(a,b): boolean(a,b,'UNION')
def bevel(o,w=.55):
 bpy.context.view_layer.objects.active=o; mod=o.modifiers.new('Edge relief','BEVEL'); mod.width=w; mod.segments=3; mod.affect='EDGES'; bpy.ops.object.modifier_apply(modifier=mod.name)
def body(n,z0,z1,inset=0):
 profile=[(0,16),(4,20),(12,23),(32,26.4),(58,26.4),(82,26.4),(105,26.4),(120,28),(134,30),(148,29),(160,26),(171,19),(180,17),(190,16)]
 # Width/length scaling is independent of component positions: user must revalidate after changing.
 pts=[(w*P['body_max_width']/60-inset,y*P['body_length']/190) for y,w in profile]
 if inset: pts[0]=(pts[0][0],inset); pts[-1]=(pts[-1][0],P['body_length']-inset)
 xy=pts+[(-x,y) for x,y in reversed(pts)]; N=len(xy)
 vs=[(x,y,z) for z in (z0,z1) for x,y in xy]
 fs=[tuple(reversed(range(N))),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
 mesh=bpy.data.meshes.new(n); mesh.from_pydata(vs,[],fs); mesh.update(); o=bpy.data.objects.new(n,mesh); prod.objects.link(o)
 # Recalculate normals before exact booleans.
 bm=bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(mesh); bm.free(); return o
half=P['front_depth']; rear=P['rear_depth']; wall=P['wall']; sy=P['screen_y']; sr=P['screen_diameter']/2
front=body('P01_front_sculpted_shell',0,half); bevel(front,1.2); boolean(front,body('cavity',-2,half-wall,wall))
back=body('P02_rear_panel',-rear,0); bevel(back,1.2); boolean(back,body('cavity',-rear+wall,2,wall))
front.data.materials.append(ivory); back.data.materials.append(dark)
# Continuous reinforced screen seat and rim, fully fused to front shell.
rim=cyl('seat',sr+3.6,5,(0,sy,half-2)); boolean(rim,cyl('aperture',P['screen_window']/2,12,(0,sy,half-2))); union(front,rim)
# HOTHMI bare panel: conservative circular+lower-tab cavity from maker 2D drawing.
# Undimensioned outline transitions are approximations; no vendor STEP is claimed.
# Single extruded circle+shoulder cutter avoids coincident sequential pocket faces.
r=18.2;w=10.0;ang=math.atan2(-math.sqrt(r*r-w*w),w)
xy=[(r*math.cos(ang+(math.pi-2*ang)*i/96),sy+r*math.sin(ang+(math.pi-2*ang)*i/96)) for i in range(97)]
xy.extend([(-w,sy-23),(w,sy-23)]);nn=len(xy)
vs=[(x,y,z) for z in (9.9,18.3) for x,y in xy]
fs=[tuple(reversed(range(nn))),tuple(range(nn,2*nn))]+[(i,(i+1)%nn,(i+1)%nn+nn,i+nn) for i in range(nn)]
me=bpy.data.meshes.new('panel cavity profile');me.from_pydata(vs,[],fs);me.update()
cut=bpy.data.objects.new('unified bare panel cavity',me);prod.objects.link(cut)
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
boolean(front,cut)
boolean(front,cyl('window',P['screen_window']/2,30,(0,sy,half)))
boolean(front,cube('FPC straight chip roof relief',(20.4,16,4),(0,112.6,16),bev=.3))
boolean(front,cyl('retainer insertion rebate',22.0,10.1,(0,sy,11)))
# Four through-shell screws; front nut cavities accessible from inside before closure.
for x,y in [(-12,12),(12,12),(-19,172),(19,172)]:
 union(front,cyl('front boss',4.2,18.0,(x,y,8.9)))
 union(back,cyl('back boss',4.2,rear-2,(x,y,-(rear-2)/2)))
 boolean(front,cyl('clearance',P['screw_clearance']/2,10,(x,y,1)))
 boolean(front,cyl('M2.5 nut pocket',P['nut_af']/math.sqrt(3),3,(x,y,1.4),verts=6))
 boolean(back,cyl('clearance',P['screw_clearance']/2,50,(x,y,0)))
 boolean(back,cyl('head counterbore',2.65,3,(x,y,-rear+1)))
# Removable board-carrier ledges attach to inner front walls, using clip-free screws/nuts.
for x in (-20.5,20.5):
 for y in (64,104):
  union(front,cube('carrier ledge',(4.2,8,17),(x,y,8.5)))
  boolean(front,cyl('carrier screw',1.4,12,(x,y,5)))
  boolean(front,cyl('carrier nut',P['nut_af']/math.sqrt(3),3,(x,y,1),verts=6))
# Screen retainer screw bosses outside panel diameter.
for x in (-22.6,22.6):
 union(front,cyl('retainer boss',3.5,2.0,(x,sy,16.95)))
 boolean(front,cyl('retainer screw',1.4,10,(x,sy,13)))
 boolean(front,cyl('retainer nut',P['nut_af']/math.sqrt(3),2.8,(x,sy,16.5),verts=6))
# Functional openings are service apertures, no connector mounting datum implied.
boolean(back,cube('USB service opening',(24,20,10),(25,136,-8),bev=1))
boolean(back,cube('hard-off switch access',(24,18,12),(-25,136,-8),bev=.5))
boolean(front,cyl('single MIC port',1,12,(12,110,18)))
# Blunt crown socket: empty axis-Y concept interface, no live blade rating.
for shell in (front,back):
 cutter=cyl('crown socket',13.3,25.2,(0,182.5,0),axis='Y'); cutter.rotation_euler.y=math.pi/96
 boolean(shell,cutter)
# Fused bottom eyelet, hole axis Z; deliberately not strength-certified.
eye=cyl('bag eye',8,6,(0,-5,5)); boolean(eye,cyl('eye hole',4,12,(0,-5,5))); union(front,eye)
# Grip touch-electrode shallow pockets behind the outer polymer wall.
for x in (-11,11): boolean(front,cube('grip electrode pocket',(9,48,.9),(x,78,half-wall+.25),bev=2))
for x in (-10,10): boolean(front,cube('rim foil recess',(9,7,1.1),(x,162,16.95),bev=.4))
# Trim unioned boss overrun back to exact seam; avoids coplanar Boolean face fragments.
boolean(front,cube('seam trim',(150,300,20),(0,90,-10)))
# Carrier open frame. No board holes are invented; component edge clearance must be reviewed after routing.
carrier=cube('P03_removable_PCB_carrier',(39,109,2),(0,88.5,-1))
boolean(carrier,cube('open center',(31,101,8),(0,88.5,-1)))
for x in (-20.5,20.5):
 for y in (64,104):
  union(carrier,cube('tab',(6,8,2),(x,y,-1)))
  boolean(carrier,cyl('fastener',1.4,8,(x,y,-1)))
# Loose edge guides do not clamp components or specify hole locations.
for x in (-17.9,17.9): union(carrier,cube('edge guide',(.8,101,3),(x,88.5,1.5)))
carrier.data.materials.append(copper)
# Protected cylindrical pack: open insulating trough with end walls and strap guides.
# Bore20.3 gives0.6 radial gap around maker MAX19.1; not a compression fit.
by=P['battery_center_y']; bz=P['battery_center_z']
batt=cube('P04_18650_open_cradle',(31,76,2),(0,by,-25.95))
trough=cyl('lower cradle arc',11,74,(0,by,bz),axis='Y')
boolean(trough,cyl('pack bore',10.15,78,(0,by,bz),axis='Y'))
boolean(trough,cube('open upper half',(40,90,30),(0,by,0)))
union(batt,trough)
# End stops are outside the actual protected-pack max body, not on its terminals.
for yy in (by-36.5,by+36.0):
 end=cube('end stop',(22,1.5,9),(0,yy,-21.0)); union(batt,end)
# Factory-wire exit at upper end; channel does not require soldering the cell.
boolean(batt,cube('upper factory lead relief',(12,12,8),(0,by+38,-18),bev=.5))
# Side NTC window and insulated lead corridor; actual attachment is nonmetallic tape/sleeve.
boolean(batt,cube('NTC side pocket',(4,8.4,6.4),(11.3,96,-15),bev=.2))
boolean(batt,cube('NTC insulated lead slot',(4,20,4),(12,108,-15),bev=.4))
# Two loose textile straps pass through slots beside the pack. Do not tighten onto insulation.
for xx in (-13.3,13.3):
 for yy in (78,114): boolean(batt,cube('strap passage',(3.0,9,5),(xx,yy,-25.3),bev=.35))
# Through bolts to rear shell, outside cell+NTC body. Real metal nuts seat on the printed tabs.
for xx in (-18,18):
 for yy in (76,110):
  union(batt,cube('rear mounting tab',(7,8,2),(xx,yy,-25.95)))
  boolean(batt,cyl('cradle screw',1.4,8,(xx,yy,-25.95)))
  boolean(back,cyl('rear cradle screw',1.4,12,(xx,yy,-rear+3)))
for ax in (-8,8):
 anchor=cube('factory lead soft-tie anchor',(4,6,6),(ax,134,-20))
 boolean(anchor,cube('tie loop passage',(2.2,8,3),(ax,134,-20)))
 union(batt,anchor)
batt.data.materials.append(copper)
# Rear frame plus compliant perimeter pads; no direct screw load on glass.
ret=cyl('P05_FPC_bare_panel_retainer',20.8,2,(0,sy,14.9))
boolean(ret,cyl('open panel back',15.8,8,(0,sy,14.9)))
for xx in (-22.6,22.6):
 union(ret,cube('retainer ear',(7,6,2),(xx,sy,14.9)))
 boolean(ret,cyl('ear clearance',1.4,8,(xx,sy,14.9)))
boolean(ret,cube('FPC neck and chip exit',(19,15,8),(0,sy-20,15.0)))
ret.data.materials.append(copper)
# Blank plug closes crown hole. This is a loose mock interface, not a latch or blade adapter.
cap=cyl('P06_crown_blank_plug',13,10,(0,187,0),axis='Y'); union(cap,cyl('cap flange',15,3,(0,192,0),axis='Y')); cap.data.materials.append(copper)
# 2026-10-21: central speaker nest, duct and rear air cavity withdrawn by user.
# No substitute mounting location has been approved or verified in this correction.
# Motor seat is mechanically located on rear panel; adhesive/foam stack is included in pocket depth.
mx,my,mz=17,148,-24.2
motorseat=cyl('P11_LRA_rear_seat',7.4,5.4,(mx,my,-24.5))
# Shared printed foot mounts using2 realM2.5 bolts; no soldering or printed threads.
for yy in (138.5,159):
 union(motorseat,cube('motor mount tab',(8,8,1.8),(mx,yy,-26.3)))
 union(motorseat,cube('motor tab bridge',(5,7,1.8),(mx,(yy+my)/2,-26.3)))
 boolean(motorseat,cyl('motor seat bolt',1.4,10,(mx,yy,-26.3)))
 boolean(back,cyl('motor rear bolt',1.4,12,(mx,yy,-28)))
anchor=cube('motor lead soft-tie anchor',(3,6,3),(10.5,153,-25.5))
boolean(anchor,cube('motor tie passage',(6,3,1.2),(10.5,153,-25.5)))
union(motorseat,anchor)
union(motorseat,cube('short FPC supported solder tail shelf',(9,7,1.2),(8.5,my,-26.6)))
boolean(motorseat,cyl("final LRA body clearance after anchor",4.3,4.3,(mx,my,-23.85)))
boolean(motorseat,cube("LRA short FPC tail exit",(11,5.4,3.2),(mx-7,my,-24.4),bev=.2))
# Removable positive axial stop; nominal0.35mm gap above maximum motor/foam stack.
# Two shared mounting screws and solid spacers prevent tightening onto the motor.
for yy in (138.5,159):
 union(motorseat,cyl('cap spacer',3,3.7,(mx,yy,-23.55)))
 boolean(motorseat,cyl('spacer through bolt',1.4,12,(mx,yy,-24)))
motorcap=cube('P12_LRA_removable_axial_stop',(9,28.5,1.2),(mx,148.75,-21.1),copper)
boolean(motorcap,cyl('motor center no pressure opening',2.3,5,(mx,my,-21.1)))
for yy in (138.5,159): boolean(motorcap,cyl('cap screw clearance',1.4,7,(mx,yy,-21.1)))
motorseat.data.materials.append(copper)
# Hole-only coupon: measured fit must be confirmed before any assembly printing.
coupon=cube('P08_M2p5_fit_coupon',(56,20,4),(70,30,2),bev=.5)
for i,d in enumerate((2.6,2.8,3.0,3.2)):
 boolean(coupon,cyl('hole',d/2,9,(50+i*9,30,2)))
boolean(coupon,cyl('nut trap',P['nut_af']/math.sqrt(3),3,(90,30,3),verts=6)); coupon.data.materials.append(ivory)
slotcoupon=cube('P09_PCB_slot_sliding_fit_coupon',(70,25,6),(75,70,3),ivory,prod,.3)
for x,w in [(50,1.8),(60,2.2),(70,2.6)]: boolean(slotcoupon,cube('PCB thickness trial',(w,17,6),(x,70,5)))
boolean(slotcoupon,cube('10mm peg trial pocket',(10.6,10.6,5),(90,70,4.5)))
peg=cube('P10_10mm_sliding_test_peg',(10,10,6),(105,70,3),copper)
parts=[front,back,carrier,batt,ret,cap,motorseat,motorcap,coupon,slotcoupon,peg]
# Non-printing electronics proxies. Explicit names distinguish every placeholder from a selected component.
def dummybox(n,d,p,m=blue):
 o=cube('DUMMY_'+n,d,p,m,dum,.3); dummies.append(o); return o
def dummycyl(n,r,h,p,m=blue):
 o=cyl('DUMMY_'+n,r,h,p,m,dum); dummies.append(o); return o
pcb=dummybox('PCB_34x105_LEGACY_ENVELOPE_NOT_CURRENT_LAYOUT',(P['pcb_width'],P['pcb_length'],P['pcb_thickness']),(0,88.5,P['pcb_thickness']/2))
topbudget=dummybox('PCB_top_allowance_CENTRAL_SPEAKER_CONSTRAINT_REMOVED',(30,101,4),(0,88.5,3.6))
boolean(topbudget,cube('FPC loop and connector local component keepout',(16,35,12),(0,117.5,7.6)))
dummybox('PCB_bottom_allowance_NOT_placement',(30,101,3),(0,88.5,-1.5))
pack=dummycyl('Keeppower_400T_MAKER_MAX_19p1x69p2',P['battery_diameter']/2,P['battery_length'],(0,by,bz),batteryMat)
pack.rotation_euler.x=math.pi/2; bpy.context.view_layer.objects.active=pack; bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
# Maker drawing reconstruction: nominal35.6 diameter plus lower shoulder to38.1 totalheight.
module=dummycyl('HOTHMI_MAX_BODY_CONSERVATIVE_2D_ENVELOPE',sr+.1,P['screen_thickness']+.2,(0,sy,17.1),glass)
union(module,cube('approximated lower metal shoulder',(18.0,8.4,1.8),(0,sy-16.2,17.1)))
# Two compliant rear perimeter pads: sample compression and permitted contact area unverified.
for px in (-16.8,16.8):
 dummybox('rear_perimeter_pad_0p3_MAX_BODY_TRIAL',(1.2,4,.3),(px,sy,16.05),dark)
for px in (-17.2,17.2): dummybox('front_perimeter_pad_0p3_MAX_BODY_TRIAL',(.6,3,.3),(px,sy,18.15),dark)
# Flex length47.5 from lower body edge. Illustrative smooth180-degree loop; radius6.7
# is an engineering candidate, NOT maker-approved minimum. First10mm stays straight.
fz=16.6; fy=sy-20.4; rr=P['screen_fpc_trial_radius']; pts=[(fy,fz,0,1),(fy-10,fz,0,1)]
for i in range(1,65):
 t=math.pi*i/64; pts.append((fy-10-rr*math.sin(t),fz-rr+rr*math.cos(t),-math.sin(t),math.cos(t)))
end_y=fy-10+(P['screen_fpc_length']-10-math.pi*rr); pts.append((end_y,fz-2*rr,0,-1))
verts=[]
for yy,zz,ny,nz in pts:
 verts.extend([(-2.8,yy-ny*.175,zz-nz*.175),(2.8,yy-ny*.175,zz-nz*.175),(-2.8,yy+ny*.175,zz+nz*.175),(2.8,yy+ny*.175,zz+nz*.175)])
faces=[(0,2,3,1)]
for j in range(len(pts)-1):
 a=4*j;b=a+4;faces.extend([(a,b,b+1,a+1),(a+2,a+3,b+3,b+2),(a,a+2,b+2,b),(a+1,b+1,b+3,a+3)])
n=4*(len(pts)-1);faces.append((n,n+1,n+3,n+2))
me=bpy.data.meshes.new('FPC trial loop');me.from_pydata(verts,[],faces);me.update()
flex=bpy.data.objects.new('DUMMY_FPC47p5_ROUTE_ASSUMPTION_R6p7',me);dum.objects.link(flex);flex.data.materials.append(copper);dummies.append(flex)
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
dummycyl('LEADER_LD0832BC0195F_BODY_MAX8p1x3p35',4.05,3.35,(mx,my,-24.175),dark)
dummycyl('LRA_bottom_adhesive_NOMINAL0p15',3.5,.15,(mx,my,-25.925),dark)
dummycyl('LRA_top_foam_NOMINAL0p3',3.5,.3,(mx,my,-22.35),dark)
dummybox('LRA_short_FPC_solder_tail_MAX_LENGTH10p6',(6.55,4.7,.15),(9.675,my,-25.8),copper)
dummybox('SEMITEC103AT2_MAX_4x3p7x2p4',(2.4,4,3.7),(10.75,96,bz),blue)
dummybox('NFC_module_UNSELECTED',(20,20,3),(0,160,-16),blue)
dummybox('NFC_antenna_UNSELECTED',(28,35,1),(0,156,-19.5),copper)
dummybox('MIC_carrier_UNVERIFIED',(8,8,4),(12,110,14),blue)
# Installed harness trial envelope is a review requirement, not a verified plug model.
# Bare-board component keepout beneath rear PH socket; board shape itself is unchanged.
# FPC socket and service route require the explicitly cut bare-board keepout.
for ch,x,y in [('CS1',-11,70),('CS2',11,70),('CS3',-11,91),('CS4',11,91)]:
 dummybox(ch+'_grip_foil_UNPRINTED',(8,18,.2),(x,y,17.2),copper)
for ch,x in [('CS5',-10),('CS6',10)]:
 dummybox(ch+'_rim_foil_UNPRINTED',(8,6,.2),(x,162,17.4),copper)
# Review volumes hidden from beauty renders, visible in Blender wire view.
review_specs=[('RF_15mm_ANTENNA_REVIEW',(48,40,33),(0,39,1.5)),('FPC_CHIP_REGION_NO_BEND_UNDIMENSIONED',(15,10,2),(0,114.7,16.6)),('FPC_SOCKET_LAYOUT_REACH_CONSTRAINT',(13,9,4),(0,end_y,3.6)),('FPC_LATCH_TOOL_AFTER_CARRIER_REMOVAL',(14,16,10),(0,end_y,8.6)),('wire_corridor',(5,68,5),(18,94,-8)),('local_header_10mm_TBD',(10,12,10),(-10,100,6.6)),('USB_service_NOT_VALIDATED',(14,18,8),(25,136,-8)),('hard_off_switch_NOT_VALIDATED',(12,16,10),(-25,136,-8)),('user_button_NO_FINAL_MOUNT',(8,8,6),(0,97,12)),('battery_factory_wire_EXIT_UNVERIFIED',(10,18,7),(0,140.2,-15)),('NTC_side_allowance',(3.5,8,6),(11.3,96,-15)),('LRA_tail_UV_AND_LEAD_REVIEW',(6.5,5,2.7),(9.675,my,-24.4)),('LRA_soldered_flexible_wire_EXIT',(6,6,3),(3.5,my,-24.3))]
for n,d,p in review_specs:
 o=cube(n,d,p,None,reviews); o.display_type='WIRE'; o.hide_render=True; o['status']='Review volume; selected-body geometry does not validate harness, thermal attachment or service motion.'
# Routed service envelope follows the flex instead of a misleading large solid cuboid.
sv=[]
for yy,zz,ny,nz in pts:
 sv.extend([(-4.5,yy-ny,zz-nz),(4.5,yy-ny,zz-nz),(-4.5,yy+ny,zz+nz),(4.5,yy+ny,zz+nz)])
sm=bpy.data.meshes.new('FPC routed service envelope');sm.from_pydata(sv,[],faces);sm.update()
so=bpy.data.objects.new('FPC_ROUTED_SERVICE_RADIUS_UNVERIFIED',sm);reviews.objects.link(so);so.display_type='WIRE';so.hide_render=True
bm=bmesh.new();bm.from_mesh(sm);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(sm);bm.free()
# Expression: only render curves, not included in manufacturing STL.
def curve(n,pts,r,material):
 cu=bpy.data.curves.new(n,'CURVE'); cu.dimensions='3D'; cu.bevel_depth=r; cu.bevel_resolution=3; sp=cu.splines.new('POLY'); sp.points.add(len(pts)-1)
 for v,co in zip(sp.points,pts): v.co=(*co,1)
 o=bpy.data.objects.new(n,cu); viz.objects.link(o); o.data.materials.append(material); return o
for xx in (-6,6): curve('Render eye',[(xx+3*math.cos(t),sy+2+3*math.sin(t),19.2) for t in [math.pi*i/32 for i in range(33)]],.55,cyan)
curve('Render smile',[(2.1*math.cos(t),sy-4+2*math.sin(t),19.2) for t in [math.pi+math.pi*i/32 for i in range(33)]],.4,cyan)
# Export individual solids in build orientation. All STL coordinates are literal mm.
report=[]
for o in parts:
 bm=bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001); bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=3); bmesh.ops.triangulate(bm,faces=list(bm.faces),ngon_method='EAR_CLIP'); bmesh.ops.dissolve_degenerate(bm,dist=.00001,edges=list(bm.edges)); bmesh.ops.triangulate(bm,faces=list(bm.faces),ngon_method='EAR_CLIP'); bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(o.data)
 report.append({'part':o.name,'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'volume_mm3':abs(bm.calc_volume(signed=True)),'assembly_bbox_mm':list(o.dimensions)})
 bm.free(); original=o.matrix_world.copy()
 # Rear outer surface is down, cavity up; front split surface down. Cap axis vertical for printing.
 if o==back: pass # Rear outside down, cavity up
 if o==cap: o.rotation_euler.x=math.pi/2
 bpy.context.view_layer.update(); minz=min((o.matrix_world@Vector(v)).z for v in o.bound_box); o.location.z-=minz
 # Center buildplate X/Y regardless of assembly origin.
 bounds=[o.matrix_world@Vector(v) for v in o.bound_box]; o.location.x-=(min(v.x for v in bounds)+max(v.x for v in bounds))/2; o.location.y-=(min(v.y for v in bounds)+max(v.y for v in bounds))/2
 bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o
 bpy.ops.wm.stl_export(filepath=ROOT+'/stl/'+o.name+'.stl',export_selected_objects=True,apply_modifiers=True,global_scale=1.0,use_scene_unit=False)
 o.matrix_world=original
json.dump(report,open(ROOT+'/mesh_validation.json','w'),indent=2)
json.dump([{'name':o.name,'center_xyz_mm':list(o.location),'bbox_mm':list(o.dimensions),'status':'See object name: manufacturer maximum, nominal CAD, or explicitly unselected proxy. No physical fit test.'} for o in dummies],open(ROOT+'/component_placements.json','w'),indent=2)
# Rendering setup: orthographic studio, actual CAD geometry only.
scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.use_denoising=False; scene.render.resolution_x=1100; scene.render.resolution_y=1400; scene.render.resolution_percentage=100
scene.world.color=(.2,.2,.2); scene.view_settings.view_transform='AgX'
for pos,power,size in [((120,150,280),1800000,180),((-140,100,160),1200000,140),((0,230,-80),1000000,100)]:
 bpy.ops.object.light_add(type='AREA',location=pos); l=bpy.context.object; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; l.rotation_euler=(Vector((0,90,0))-l.location).to_track_quat('-Z','Y').to_euler(); move(l,viz)
bpy.ops.object.camera_add(location=(230,-90,430)); cam=bpy.context.object; move(cam,viz); cam.data.type='ORTHO'; cam.data.ortho_scale=245; scene.camera=cam

def camera(pos,target,scale):
 cam.location=pos; cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.ortho_scale=scale
coupon.hide_render=True; slotcoupon.hide_render=True; peg.hide_render=True
for o in reviews.objects: o.hide_set(True)
# Native file saves assembled objects with measurements and unprinted proxies separated.
scene['STATUS']='V0.2-R1: CENTRAL SPEAKER ARRANGEMENT WITHDRAWN 2026-10-21. Incomplete assembly; speaker not located. Old verification does not apply.'
scene['USER_OVERRIDE']='No 26x26 central PCB speaker keepout. Shorter PCB and matching mounting holes required; MCU face is not a user-fixed constraint.'
scene['ASSEMBLY_AXIS']='X width, Y length, +Z front. mm. Seam Z=0.'
camera((170,-80,440),(0,91,0),225)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_location=Vector((0,91,0)); area.spaces.active.region_3d.view_distance=260; area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion(); area.spaces.active.region_3d.view_perspective='ORTHO'
for o in (coupon,slotcoupon,peg): o.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=ROOT+'/Spirit_EVT_mechanical_v02_r1.blend')
if os.environ.get('SPIRIT_SKIP_RENDERS')=='1':
 print('COMPLETE',json.dumps(report)); raise SystemExit
camera((170,-80,440),(0,91,0),225); scene.render.filepath=OUT+'/renders/01_assembly.png'; bpy.ops.render.render(write_still=True)
# Exploded is a render-only state; do not overwrite assembly master.
orig={o:o.location.copy() for o in list(parts)+dummies+list(viz.objects) if o.type in ('MESH','CURVE')}
front.location.z+=55; ret.location.z+=32; back.location.z-=55; batt.location.z-=25; cap.location.y+=22
motorseat.location.x+=44; motorseat.location.z-=15; motorcap.location.x+=44; motorcap.location.z+=18
for o in dummies:
 if 'HOTHMI' in o.name or 'FPC47p5' in o.name or 'perimeter_pad' in o.name: o.location.z+=36
 if 'Keeppower' in o.name: o.location.z-=22
 if 'LRA_' in o.name or 'LD0832' in o.name: o.location.x+=44
 if 'XHXDZ' in o.name: o.location.x-=42
for o in viz.objects:
 if o.type=='CURVE': o.location.z+=55
camera((270,-100,340),(0,92,0),290); scene.render.filepath=OUT+'/renders/02_exploded.png'; bpy.ops.render.render(write_still=True)
for o,loc in orig.items(): o.location=loc
# Open-back assembly, no fake transparency: remove back and show actual cavity and dummies.
back.hide_render=True; batt.hide_render=True; motorseat.hide_render=True; motorcap.hide_render=True
for o in viz.objects:
 if o.type=='CURVE': o.hide_render=True
camera((-100,-70,-460),(0,94,-7),255); scene.render.filepath=OUT+'/renders/03_open_back_cutaway.png'; bpy.ops.render.render(write_still=True)
back.hide_render=False; batt.hide_render=False; motorseat.hide_render=False; motorcap.hide_render=False
# Front/back shell internal face render.
for o in dummies+[carrier,batt,ret,cap,motorseat,motorcap]: o.hide_render=True
front.location.x=-40; back.location.x=40; back.rotation_euler.y=math.pi
camera((0,95,-500),(0,95,0),235); scene.render.resolution_x=1500; scene.render.resolution_y=1400; scene.render.filepath=OUT+'/renders/04_shell_cavities.png'; bpy.ops.render.render(write_still=True)
print('COMPLETE',json.dumps(report))
