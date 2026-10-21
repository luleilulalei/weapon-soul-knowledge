import json,math
from review_geometry import *
P={}
def at(ref,x,y,r=0,l=2):P[ref]={'x':x,'y':y,'rotation':r,'layer':l}
at('U1',0,124.6,180)
at('J8',0,129,180,1)
at('J101',11.9,113,90,1)
at('J1',-11.8,119,-90,1)
at('J2',-11.8,104,-90,1)
at('J3',11.8,97,90,1)
at('J4',-11.8,63.5,-90,1)
at('J6',11.8,63.5,90,1)
at('J7',0,56.5,0,1)
at('J110',11.8,57,90,1)
at('J104',0,41,180)
at('J111',11.2,49,90,1)
at('J201',-3,42,0,1)
# MCU supply and reset on opposite face; no components in antenna region.
for ref,x,y,r in [('C1',11.5,130,90),('C2',11.5,127,90),('C3',11.5,124,90),('C4',7.5,124,0),('R1',5,120,90),('C5',7,120,90),('R2',-7,120,90),('R3',-7,116,90),('C6',-5,116,90),('R4',-11.5,130,90),('R5',-11.5,127,90),('R307',-11.5,60,90),('R308',-8.8,60,90),('R312',-8.8,56.5,90)]:at(ref,x,y,r,1)
for ref,x,y in [('SW1',-12,87),('SW2',12,87),('SW3',12,81)]:at(ref,x,y,0,2)
# Screen interface resistors placed at source end above MCU pad fanout.
for ref,x,y,r in [('R32',-3,119,90),('R33',-1,119,90),('R34',1,119,90),('R35',3,119,90),('R36',-7.5,124,0),('C29',-3,125,0),('C30',0,125,0),('FB202',3.5,125,0),('R39',6.2,130,90),('Q2',-7.8,129,0),('R37',-7.8,132,0),('R38',-4.2,132,0)]:at(ref,x,y,r,1)
# USB control cluster close to connector, charger at lower end.
at('U101',8,112.5,90,2)
at('R103',11.5,116.8,90,2);at('R104',13.5,116.8,90,2)
at('F101',7.4,119.7,0,1)
at('C101',7.4,116.7,0,1);at('C102',4.2,116.7,0,1)
at('U106',9,107,0,1);at('U107',2.5,107,0,1);at('U108',-3,107,0,1)
at('C122',2.5,110,0,1);at('C123',7,109,90,1);at('C124',-3,110,0,1)
at('C127',2.5,104,0,1);at('R137',9,104,0,1);at('R138',5,107,90,1)
at('Q104',11.5,101.5,0,2);at('R105',14,104,90,2);at('R106',14,101,90,2);at('R107',14,98,90,2)
at('U102',0,49,0,2)
for ref,x,y,r in [('C103',-3.5,47.8,90),('C104',-5.5,47.8,90),('C105',3.5,48.5,90),('C106',5.5,48.5,90),('R108',-3,52,0),('R109',-5.8,52,0),('R110',3,52,90),('R111',0,45.5,90),('R112',3,45.5,90),('R113',5.5,45.5,90),('R114',-4,55,0),('R115',-1,55,0)]:at(ref,x,y,r)
at('U103',-6,60,0);at('L101',-6,65.3,0)
for ref,x,y,r in [('C107',-10.5,60,90),('C129',-13.2,60,90),('C108',-9.5,57,0),('C109',-1.8,61,90),('C128',.8,61,90),('R116',-7,56.6,90),('R117',-3,57.5,90),('R118',-.8,57.5,90)]:at(ref,x,y,r)
at('U104',7.5,60,0);at('L102',7.5,64.5,180)
for ref,x,y,r in [('C111',12,60,90),('C112',12,57,0),('C113',3.5,63,90),('R119',6,55,0),('R120',6,57,0),('R121',4,59,90),('R122',2,58,90),('C114',4,56,0)]:at(ref,x,y,r)
at('Q102',-11,45,0);at('Q103',-11,49,0)
for ref,x,y,r in [('R123',-14,45,90),('R124',-14,49,90),('R125',-14,52,90),('R126',-8,48,90),('C115',-11,53,0)]:at(ref,x,y,r)
at('U7',-7,74,0)
for ref,x,y,r in [('C23',-10.8,76,90),('R18',-4,78.5,0),('R19',-10.8,72,90),('R22',-4,70,0)]:at(ref,x,y,r)
at('U105',8,74,90)
for ref,x,y,r in [('C119',11.5,73.5,90),('C121',11.5,77,90),('C120',5,71,90),('R135',8,70,0),('R136',8,68,0)]:at(ref,x,y,r)
at('U2',0,83,0)
for ref,x,y,r in [('C7',-3,82,90),('C8',3,82,90),('C9',0,86,0)]:at(ref,x,y,r)
at('U4',7,92,0)
for ref,x,y,r in [('C13',10.8,92,90),('C14',13,92,90),('R8',3.5,92,90),('R9',3.5,95,90),('R10',1.2,92,90)]:at(ref,x,y,r)
at('U5',12,106.5,0,1)
for ref,x,y,r in [('C15',12,103.5,0),('C16',12,109.5,0),('R15',5.8,102,90),('R26',5.8,99,90)]:at(ref,x,y,r,1)
at('U3',-6,101,90)
for ref,x,y,r in [('C11',-2.5,100,90),('C12',-.3,100,90),('R6',-2.5,104,0)]:at(ref,x,y,r)
for i,ref in enumerate(['R129','R130','R131','R132','R133','R134']):at(ref,-11.8,98+i*2,0)
# Review iteration: clear connector through-hole tails and preserve assembly margins.
at('J101',11.9,109.5,90,1);at('U101',8,109,90,2)
at('R103',5.5,113.5,0,2);at('R104',5.5,111.5,0,2)
at('U5',-12,96.8,0,1);at('C15',-8,97,0,1);at('C16',-8,94.5,0,1)
at('R15',-4,98,90,1);at('R26',-4,95,90,1)
at('F101',5.5,115.5,0,1);at('C101',6,112.5,0,1);at('C102',3,112.5,0,1)
at('R39',8.5,130,90,1);at('R38',-4.2,122,0,1)
at('R111',0,45.8,90);at('R112',3,45.8,90)
at('R22',-3.7,69.5,0);at('C119',12.5,73.5,90)
at('U106',7,105,0,1);at('R105',5.5,105.7,0,2);at('R112',7.5,45,90)
at('R137',9.5,102.5,0,1)
# Align inductor terminals with switching pins and bring ceramic caps into the local loops.
at('L101',-.5,60,90)
at('C109',-5.5,63.7,0);at('C128',-5.5,66,0)
at('R117',-8.8,64,90);at('R118',-11,64,90)
at('C107',-10.5,58,90);at('C129',-13.2,58,90)
at('C108',-6,56,0);at('R116',-8.2,56,90)
at('U104',7.5,60,180);at('L102',7.5,64.5,0)
at('C111',3.5,62,90);at('C112',3.5,59,0);at('C113',12,59,0)
at('R121',6,56,90);at('R122',4,56,90);at('C114',8.5,56,90)
at('R119',-.5,54.5,0);at('R120',-.5,52.5,0)
at('R115',-3.5,56.2,0)
at('L101',-.5,60,-90);at('L102',7.5,64.5,180)
at('C103',-3.5,47.8,-90);at('C104',-5.5,47.8,-90);at('R111',-6.8,43,90)
at('J201',-11,44,-90,1)
at('U101',5.5,109,90);at('C123',7.2,102,90,1)
for ref,x,y in [('R129',-10.5,107),('R130',-13.5,106),('R131',-10.5,105),('R132',-13.5,104),('R133',-10.5,103),('R134',-13.5,102)]:at(ref,x,y,0)
assert set(P)==set(COMPS),(set(COMPS)-set(P),set(P)-set(COMPS))

def check():
 errors=[];sh={r:shapes(r,**p)for r,p in P.items()}
 for r,p in P.items():
  if r!='U1' and not BOARD.buffer(.01).covers(sh[r]['courtyard']):errors.append(['edge',r,list(sh[r]['courtyard'].bounds)])
  if r!='U1' and sh[r]['courtyard'].intersects(box(-17,134.5,17,141)):errors.append(['antenna',r])
  if p['layer']==1 and sh[r]['body'].intersection(SPEAKER).area>.001:errors.append(['speaker',r])
 for i,r in enumerate(P):
  for s in list(P)[i+1:]:
   if P[r]['layer']==P[s]['layer']:
    if sh[r]['courtyard'].intersection(sh[s]['courtyard']).area>.0001:errors.append(['overlap',r,s,round(sh[r]['courtyard'].intersection(sh[s]['courtyard']).area,3)])
   else:
    for a,b in [(r,s),(s,r)]:
     if sh[a]['through'] and sh[a]['through'].intersects(sh[b]['courtyard']):errors.append(['through',a,b])
 return errors,sh

def draw(sh):
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(10,16))
 for ax,layer in zip(axes,[1,2]):
  ax.plot(*BOARD.exterior.xy,color='black');ax.fill(*SPEAKER.exterior.xy,color='#eeeeee')
  ax.fill([-17,17,17,-17],[134.5,134.5,141,141],color='#ffcccc',alpha=.5)
  for r,p in P.items():
   if p['layer']!=layer:continue
   shape=sh[r]['courtyard'];ax.fill(*shape.exterior.xy,alpha=.3,color='#0078a0');ax.plot(*sh[r]['body'].exterior.xy,lw=.5,color='black')
   ax.text(p['x'],p['y'],r,ha='center',va='center',fontsize=7)
   for num,poly,b in LOCAL[r]['pads']:
    q=transform(poly,**p);ax.fill(*q.exterior.xy,color='#c89222',alpha=.9)
  ax.set_aspect('equal');ax.set_ylim(33,145);ax.set_xlim(-19,19);ax.set_title('TOP' if layer==1 else 'BOTTOM (same coordinate view)');ax.grid(alpha=.1)
 fig.tight_layout();fig.savefig('output/Spirit_V072_placement.png',dpi=170);plt.close(fig)
P['C108']['y']=56.1
if __name__=='__main__':
 errors,sh=check();print(json.dumps(errors,ensure_ascii=False,indent=2));json.dump(P,open('review-v072-placement.json','w'),indent=2);json.dump({'errors':errors,'components':len(P)},open('review-v072-placement-check.json','w'),indent=2);draw(sh)
