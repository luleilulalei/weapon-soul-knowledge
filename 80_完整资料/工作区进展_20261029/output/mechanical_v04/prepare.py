from pathlib import Path
import json,sys,shutil,hashlib
sys.path.insert(0,'output/layout_v074m')
from geometry import *
O=Path('output/mechanical_v04');R=O/'model';S=Path('output/layout_v074k/mechanical')
D=json.load(open('output/pcb_pour_v074p3b/final.json'));old=json.load(open(S/'pcb_input.json'));prev={c['ref']:c for c in old['components']}
allb={}
for name,b in D['boards'].items():
 rows=parse_source(b['pcb']['source']);ol=next(a for h,a in rows if h['type']=='POLY'and a.get('layerId')==11)
 outline=[(x*MM,y*MM)for x,y in path_points(ol['path'])]
 if outline[0]==outline[-1]:outline=outline[:-1]
 holes=[(p[1]*MM,p[2]*MM)for h,a in rows if h['type']=='FILL'and a.get('layerId')==12 for p in a['path']if p[0]=='CIRCLE']
 comps=[];tails=[]
 for c in b['pcb']['components']:
  r=c['designator'];p=dict(x=c['x']*MM,y=c['y']*MM,rotation=c['rotation'],layer=c['layer']);l=local(b['sources'][c['footprint']['uuid']]);bounds=list(transform(l['court'],p).bounds)
  base=prev.get(r,dict(ref=r,height_mm=2.9 if r=='J702'else 1.6 if r.startswith('U')else 1.2 if r.startswith('C')else.9,height_status='conservative height allowance; sample/STEP pending'))
  comps.append({**base,'ref':r,'placement':p,'bbox_xy':bounds,'body_bbox_xy':list(transform(l['body'],p).bounds)})
  for q in b['pads'][r]:
   if q['layer']==12:tails.append(dict(ref=r,pad=q['padNumber'],x=q['x']*MM,y=q['y']*MM))
 allb[name]=dict(source='V074P3B saved native readback; 2026-10-25',pcb_shift_y_mm=27.5,pcb_thickness_mm=1.6,outline=outline,holes=holes,components=comps,through_tails=tails)
main=allb['Spirit_JLC'];ad=allb['Spirit_Blade_Adapter_V01']
next(c for c in main['components']if c['ref']=='J7').update(height_mm=4.3,height_status='Hanxia drawing nominal front height 4.0 mm; 0.3 mm envelope allowance; board seating datum/sample pending')
(R/'pcb_input.json').write_text(json.dumps(main,ensure_ascii=False,indent=2));(R/'adapter_input.json').write_text(json.dumps(ad,ensure_ascii=False,indent=2));shutil.copyfile(S/'helpers_fragment.txt',R/'helpers_fragment.txt')
s=(S/'build_v03.py').read_text().replace('V074K','V074P3B').replace('V0.3R2','V0.4').replace('Spirit_V03','Spirit_V04')
s=s.replace('(112,25)','(112,26)').replace('(180,24),(190,23)','(180,26.5),(190,25.5)')
s=s.replace('(-23.2,112),(23.2,112)','(-23.2,121),(23.2,121)')
s=s.replace("(42,59,2),(0,145,-7.4)","(42,65.5,2),(0,143.25,-7.4)").replace("(36,51,8),(0,145,-7.4)","(36,57.5,8),(0,143.25,-7.4)")
s=s.replace("(26,10,13.0),(0,185,6.5)","(34,14,13.0),(0,183,6.5)")
s=s.replace("# USB opening follows", """# Axial retention screws load the polymer shoulder independently of the contacts.
for x in [-14.3,14.3]:
 union(front,cyl('top M2p5 receiver boss',2.8,14,(x,183,7.1),axis='Y'))
 boolean(front,cyl('top M2p5 pilot',1.05,9,(x,186,7.1),axis='Y'))
# USB opening follows""")
start=s.index('# Replaceable accessory plug carrier:');end=s.index('# Deterministic topology QA')
s=s[:start]+'''# V04 Hanxia parallel-board accessory interface. Nominal engagement is adjustable.
AD=json.loads((ROOT/'adapter_input.json').read_text())
ADPY=184.3 # 2.5 mm assumed pin insertion, NOT verified connector mating datum.
adapter=part(cube('P15_Hanxia_keyed_adapter_carrier',(1.4,42,11.7),(-10.6,198,3.95),copper))
union(adapter,cube('adapter right side',(1.4,42,11.7),(10.6,198,3.95)))
for x in [-9.5,9.5]:boolean(adapter,cube('PCB edge relief',(1.6,36,2.2),(x,ADPY+16,.8)))
union(adapter,cube('adapter roof',(22.6,42,1.0),(0,198,9.3)))
union(adapter,cube('axial stop shoulder',(34,2,15),(0,191,3.4)))
boolean(adapter,cube('shoulder circuit opening',(20.6,3,10.2),(0,191,3.2)))
boolean(adapter,cube('asymmetric key relief',(2.4,14,3),(9.6,184,9.0)))
# Rear recesses accept nylon M2 nuts; elongated mounting holes allow +/-0.6 mm tuning.
for x in [-7.5,7.5]:
 union(adapter,cube('adapter fixing bridge',(5,5.6,1.6),(x,ADPY+18,-1.1)))
 union(adapter,cyl('adapter slotted support',2.2,1.8,(x,ADPY+18,-.9)))
 boolean(adapter,cube('M2 axial tuning slot',(2.2,3.4,6),(x,ADPY+18,-.8),bev=.35))
 boolean(adapter,cyl('driver access',2.4,4,(x,ADPY+18,9.3)))
for x in [-14.3,14.3]:
 boolean(adapter,cyl('shoulder M2p5 clearance',1.4,5,(x,191,7.1),axis='Y'))
# Two print shims adjust the PCB seating height if the connector samples require it.
shim=part(cube('P16_adapter_height_shim_0p3',(5,5.6,.3),(65,50,.15),copper))
boolean(shim,cube('shim M2 slot',(2.2,3.4,2),(65,50,.15),bev=.3))
shim.hide_render=True;shim.hide_set(True)
adapter_board=proxy(prism('ADAPTER_V02_ACTUAL_OUTLINE',[(x,y+ADPY)for x,y in AD['outline']],0,1.6,blue,dum),'native V02 outline; board 1.6 mm')
for x,y in AD['holes']:boolean(adapter_board,cyl('adapter fixing hole',1.1,5,(x,y+ADPY,.8)))
for item in AD['components']:
 r=item['ref']
 if r=='J701':continue
 x0,y0,x1,y1=item['bbox_xy'];h=item['height_mm'];p=item['placement'];z=1.6+h/2 if p['layer']==1 else -h/2
 proxy(cube('ADAPTER_'+r,(x1-x0,y1-y0,h),((x0+x1)/2,(y0+y1)/2+ADPY,z),blue,dum),item['height_status'])
# Connector mating bodies are separated from footprint envelopes to model pin insertion.
bpy.data.objects.remove(bpy.data.objects['PCB_J7'],do_unlink=True)
dummies[:]=[o for o in dum.objects if o.type=='MESH']
female=proxy(cube('PCB_J7',(6.7,6.35,4.3),(0,178.625,3.6),dark,dum),'drawing body + width/height allowance; 1.6 mm seating plane assumed')
for x in [-2,0,2]:
 for z in [2.6,4.6]:boolean(female,cube('female mating pocket',(.9,3.5,.9),(x,180.4,z)))
male=proxy(cube('ADAPTER_J701',(6.1,2,4.3),(0,ADPY,3.6),dark,dum),'Hanxia nominal body plus allowance; mating datum assumed')
for x in [-2,0,2]:
 for z in [2.6,4.6]:proxy(cube('ADAPTER_MATING_PIN',(0.5,4,.5),(x,ADPY-3,z),copper,dum),'nominal 0.5 mm pin; 2.5 mm assumed insertion')
# Actual through-hole XY with conservative solder-tail envelope under both boards.
for data,shift,prefix in [(PCB,SHIFT,'PCB'),(AD,ADPY,'ADAPTER')]:
 for tail in data['through_tails']:
  if tail['ref'] not in ['J7','J701','J101']:continue
  proxy(cyl(prefix+'_TAIL_'+tail['ref']+'_'+tail['pad'],.5,1.9,(tail['x'],tail['y']+shift,-.95),copper,dum),'tail/solder allowance 1.9 mm below board; verify sample/cut length')
# Accessory harness outlet and full J2/FPC insertion corridors.
for n,dim,pos in [('J2_PLUG_SERVICE',(8.5,10.5,4),(-20.25,138.5,3.6)),('ADAPTER_J702_PLUG_SERVICE',(7,8,4),(0,ADPY+35.5,3.6))]:
 o=cube(n,dim,pos,None,reviews);o.hide_render=True;o.display_type='WIRE';reviewobjs.append(o)
cap.hide_render=True;cap.hide_set(True)
''' +s[end:]
s=s.replace('if o not in [coupon,cap]:o.select_set(True)','if o not in [coupon,cap,shim]:o.select_set(True)')
s=s.replace("'status':'FIT REVIEW; NOT ASSEMBLY OR LOAD QUALIFIED'", "'hole_pitch':[38,61.5],'main_pcb_holes_global':[[-19,112.5],[19,112.5],[-19,174],[19,174]],'adapter_shift_y':184.3,'connector_insertion_assumed':2.5,'connector_axial_adjustment':0.6,'status':'FIT REVIEW; NOT ASSEMBLY OR LOAD QUALIFIED'")
(R/'build_v04.py').write_text(s)
vr=(S/'verify_v03.py').read_text().replace('V074K','V074P3B').replace('Spirit_V03','Spirit_V04').replace("('P14','P11')","('P14','P11','P16')")
vr=vr.replace("'J110_PLUG_SERVICE']","'J110_PLUG_SERVICE','J2_PLUG_SERVICE','ADAPTER_J702_PLUG_SERVICE']")
vr=vr.replace("and 'ACTUAL_OUTLINE' not in a.name", "and not(a.name=='PCB_J2' and service.name=='J2_PLUG_SERVICE') and not(a.name=='ADAPTER_J702'and service.name=='ADAPTER_J702_PLUG_SERVICE') and 'ACTUAL_OUTLINE' not in a.name")
# Test components on both sides of mother/adapter boards against every printed part.
(R/'verify_v04.py').write_text(vr)
manifest={'pcb_snapshot':'output/pcb_pour_v074p3b/final.json','sha256':hashlib.sha256(Path('output/pcb_pour_v074p3b/final.json').read_bytes()).hexdigest(),'board_component_counts':{k:len(v['components'])for k,v in allb.items()},'read_only_inputs':True,'date':'2026-10-26'}
(O/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(manifest)
