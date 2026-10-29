import sys,json,itertools,copy
from pathlib import Path
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'layout_v074m'))
from geometry import local,transform,parse_source,MM
from shapely.geometry import Point
B=json.loads((O/'before.json').read_text())['boards']
S=json.loads((O/'footprints.json').read_text())
MOVES={
'main':{
'R201':(5.7,28.7,270),'R202':(8.8,27.2,0),'C213':(11.8,27.2,0),
'C207':(7.4,29.1,270),'C206':(7.2,31,0),'C214':(3.5,25.8,0),
'C121':(16.8,26.3,90),'C120':(8.1,21.3,180),
'U4':(-13,21,0),'C13':(-9.8,21.5,0),'C14':(-9.8,23,0),
'R8':(-14,18.2,0),'R9':(-16.5,19.4,90),'R10':(-11.6,15.6,180),
'U3':(-6.8,24.5,180),'C11':(-3.7,22.8,180),'C12':(-3.7,24.3,180),'R6':(-3.7,25.8,180),
'C7':(-1.3,20.2,270),'C8':(3.9,20.7,0),
'C15':(18.8,17.6,90),'C16':(18,14.7,270),'R26':(16.5,19.6,0),
'C5':(14,4.2,180),'R1':(14,6,180),'C4':(11.5,8,0),
'C29':(-12.6,32.2,270),'C30':(-10.9,32.2,270),'FB202':(-9.2,34.8,0),
'Q2':(-11.4,28.8,0),'R38':(-8.9,25.4,90),'R37':(-8.9,28.2,90),'R39':(-8.4,31.8,90),
'C134':(9.3,45,0),'R147':(3.7,41,0)
},
'power':{
'C101':(.8,18.5,270),'C102':(2.4,18.5,270),'R114':(4.6,18.5,0),'R115':(-1,16.5,0),
'C133':(6.3,5.7,180),'R142':(8,3.8,0),'R144':(3.6,5.6,90),'R143':(3.6,3.4,0),
'L101':(-3.9,32,270),'C108':(-8,29,270),'C107':(-7.8,26.8,180),'C129':(-11.5,28,180),
'C109':(-8.4,35.9,180),'C128':(-8.4,37.7,180),'R117':(-10.9,34.5,270),'R118':(-12.5,34.5,270),
'C113':(4,33.1,180)
},
'blade':{'C701':(-.98,8.9,270),'C706':(.9,22.1,180),'C704':(-3.2,20.2,270),'C705':(-6.1,25.5,90)}
}

def shapes(bn,moves):
 b=B[bn];out={}
 for c in b['components']:
  r=c['designator'];p={'x':c['x']*MM,'y':c['y']*MM,'rotation':c['rotation'],'layer':c['layer']}
  if r in moves:p.update(zip(['x','y','rotation'],moves[r]))
  lo=local(S[c['footprint']['uuid']]);out[r]={'p':p,**{k:transform(lo[k],p) if lo[k] is not None else None for k in ['body','court','through']}}
 return out

def audit(bn,moves):
 sh=shapes(bn,moves);issues=[]
 for r,s in itertools.combinations(sh,2):
  a,b=sh[r],sh[s]
  if a['p']['layer']==b['p']['layer']:
   d=a['court'].distance(b['court'])
   if d<.199:issues.append((r,s,'same',round(d,3)))
  else:
   for x,y in [(r,s),(s,r)]:
    if sh[x]['through'] is not None:
     d=sh[x]['through'].distance(sh[y]['court'])
     if d<.199:issues.append((x,y,'through',round(d,3)))
 return issues

if __name__=='__main__':
 for bn,m in MOVES.items():
  print(bn,'moves',len(m),'issues',audit(bn,m))
 (O/'layout_plan.json').write_text(json.dumps(MOVES,indent=2))
