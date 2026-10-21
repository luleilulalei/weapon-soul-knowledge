from pathlib import Path
import math, html, json, copy
C={'bg':'#0B1020','card':'#151E32','white':'#F4F3ED','cyan':'#72E5DB','gold':'#E7BD79','muted':'#98A8BE','line':'#2C3A51','bad':'#F3A896'}
def esc(s):return html.escape(str(s))
def rect(x,y,w,h,fill,r=0,stroke=None,sw=1,opacity=1):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" opacity="{opacity}"'+(f' stroke="{stroke}" stroke-width="{sw}"' if stroke else '')+'/>'
def text(x,y,s,size=16,fill=None,weight=400,anchor='start',spacing=None):
 return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill or C["white"]}" font-weight="{weight}" text-anchor="{anchor}"'+(f' letter-spacing="{spacing}"' if spacing else '')+f'>{esc(s)}</text>'
def path(d,fill='none',stroke=None,sw=1,extra=''):return f'<path d="{d}" fill="{fill}"'+(f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"' if stroke else '')+f' {extra}/>'
def line(x1,y1,x2,y2,c,sw=1,extra=''):return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{sw}" stroke-linecap="round" {extra}/>'
def circle(x,y,r,fill,stroke=None,sw=1,extra=''):return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"'+(f' stroke="{stroke}" stroke-width="{sw}"' if stroke else '')+f' {extra}/>'
def group(s,x=0,y=0,scale=1,extra=''):return f'<g transform="translate({x} {y}) scale({scale})" {extra}>{s}</g>'
DEFS='''<defs>
<linearGradient id="sky" x2="0" y2="1"><stop stop-color="#101D35"/><stop offset=".62" stop-color="#142A3B"/><stop offset="1" stop-color="#172333"/></linearGradient>
<linearGradient id="floor" x2="0" y2="1"><stop stop-color="#233347"/><stop offset="1" stop-color="#0B1020"/></linearGradient>
<linearGradient id="armor" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#506979"/><stop offset=".35" stop-color="#263B50"/><stop offset="1" stop-color="#101B2E"/></linearGradient>
<linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#F7DC9E"/><stop offset=".5" stop-color="#9E7948"/><stop offset="1" stop-color="#54432F"/></linearGradient>
<linearGradient id="whiteBlade" x2="0" y2="1"><stop stop-color="#FFFFFF"/><stop offset=".25" stop-color="#B7FFF2"/><stop offset="1" stop-color="#5BBAB9"/></linearGradient>
<linearGradient id="mist"><stop stop-color="#72E5DB" stop-opacity="0"/><stop offset=".5" stop-color="#72E5DB" stop-opacity=".18"/><stop offset="1" stop-color="#72E5DB" stop-opacity="0"/></linearGradient>
<radialGradient id="aura"><stop stop-color="#72E5DB" stop-opacity=".25"/><stop offset="1" stop-color="#72E5DB" stop-opacity="0"/></radialGradient>
<radialGradient id="warmAura"><stop stop-color="#E7BD79" stop-opacity=".3"/><stop offset="1" stop-color="#E7BD79" stop-opacity="0"/></radialGradient>
<linearGradient id="panel"><stop stop-color="#0B1020" stop-opacity=".98"/><stop offset="1" stop-color="#0B1020" stop-opacity=".55"/></linearGradient>
<linearGradient id="topShade" x2="0" y2="1"><stop stop-color="#070D19" stop-opacity=".95"/><stop offset="1" stop-color="#070D19" stop-opacity="0"/></linearGradient>
<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3"/></filter>
<filter id="soft" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="12"/></filter>
</defs>'''
def svg(w,h,body):return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><style>text{{font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif}}</style>{DEFS}{body}</svg>'
def pill(x,y,w,s,color=None):return rect(x,y,w,26,C['card'],13,C['line'])+circle(x+12,y+13,3,color or C['cyan'])+text(x+23,y+18,s,11,color or C['muted'],500)
def btn(x,y,w,s,primary=True,h=48):return rect(x,y,w,h,C['cyan'] if primary else C['card'],14,None if primary else C['line'])+text(x+w/2,y+h/2+6,s,16,C['bg'] if primary else C['white'],700,'middle')
def eye(x,y,scale=1,emotion='calm'):
 s=circle(0,0,42,'url(#aura)')+path('M-25 0 Q-16 -8 -8 -3 L-8 4 Q-16 5 -25 0Z',C['cyan'])+path('M8 -3 Q16 -8 25 0 Q16 5 8 4Z',C['cyan'])
 return group(s,x,y,scale)
def mic(x,y):return group(path('M0 -5 V1 Q0 4 3 4 Q6 4 6 1 V-5 Q6 -8 3 -8 Q0 -8 0 -5M-3 -1 Q-3 7 3 7 Q9 7 9 -1M3 7V11M-2 11H8','none',C['muted'],1.4)+line(-5,-9,11,10,C['muted'],1.4),x,y)
def check(x,y,col=None):return circle(x,y,10,(col or C['cyan'])+'22')+path(f'M{x-4} {y} l3 3 l6 -7','none',col or C['cyan'],1.8)
def statusbar():return text(24,28,'9:41',13,C['white'],700)+path('M316 25v-3m5 3v-6m5 6v-9','none',C['white'],2)+path('M337 19q8-8 16 0m-13 3q5-5 10 0m-7 3q2-2 4 0','none',C['white'],1.7)+rect(361,16,16,9,'none',2,C['white'])+rect(363,18,11,5,C['white'],1)
def nav(active='训练'):
 s=rect(0,756,390,88,'#0F1628')+line(24,756,366,756,'#243048',.6)
 paths=[circle(12,12,9,'none','currentColor',1.65)+path('M8 10v3M16 10v3','none','currentColor',1.65),path('M6 18L17 7l1-4-4 1L3 15M5 13l6 6M3 21l3-3','none','currentColor',1.65),path('M4 4h7l1 2 1-2h7v16h-7l-1 1-1-1H4zM12 6v15','none','currentColor',1.65)]
 for i,label in enumerate(['器灵','训练','收藏']):
  x=65+i*130;c=C['cyan'] if label==active else '#93A3BC'
  if label==active:s+=rect(x-29,764,58,32,C['cyan']+'14',16)
  s+=group(paths[i],x-12,769,1,extra=f'color="{c}"')+text(x,816,label,11,c,600 if label==active else 400,'middle')
 return s+rect(145,832,100,4,'#B9C1D1',2)

def appbase(title,subtitle=None):return rect(0,0,390,844,C['bg'])+circle(340,160,160,'url(#aura)')+statusbar()+text(24,80,title,28,C['white'],700)+ (text(24,106,subtitle,12,C['muted']) if subtitle else '')
def guardian(x=490,y=208,scale=1,pose='guard'):
 s=f'<ellipse cx="0" cy="104" rx="95" ry="18" fill="#070D18" opacity=".65"/>'
 s+=path('M-43 -43 L-60 84 L-17 105 L4 83 L36 106 L63 81 L40 -45Z','#101C2F','#2C4054',1)
 s+=path('M-25 12 L-34 70 L-21 100 L-5 99 L-1 49 L5 49 L10 100 L28 100 L36 71 L24 12Z','url(#armor)','#5C6D77',1)
 s+=path('M-29 63L-7 67M9 67L31 64','none','#A6BAB7',2)
 s+=path('M-28 -49 L-45 -22 L-28 18 L-3 28 L27 17 L46 -22 L28 -49Z','url(#armor)','#70848D',1.2)
 s+=path('M-28 -45L-7 -26L0 -4L8 -26L28 -45M-26 7L0 18L26 6','none','#A8B4AC',1.2)
 s+=path('M-7 -19L0 -28L7 -19L0 -9Z',C['gold'])+circle(0,-18,17,'url(#warmAura)')
 s+=path('M-25 -77 L-17 -94 L18 -94 L27 -76 L19 -48 L0 -39 L-20 -51Z','url(#armor)','#97B4B9',1.3)
 s+=path('M-16 -74L-3 -68L-3 -62L-16 -65Z',C['cyan'])+path('M3 -68L17 -74L16 -65L3 -62Z',C['cyan'])
 s+=path('M-8 -86L0 -104L9 -87M-3 -61L0 -49L4 -61','none',C['gold'],2)
 s+=path('M-27 -48L-49 -51L-60 -26L-44 -15L-28 -25M28 -48L47 -50L63 -25L45 -13L29 -25','url(#gold)','#AB8B58',1)
 s+=path('M-48 -16L-59 21L-45 33L-25 2M48 -14L56 22L43 34L27 2','url(#armor)','#72878D',1)
 # left shield, concentric crest
 s+=group(path('M-29 -31Q0 -46 29 -31L33 8Q22 36 0 48Q-22 36-33 8Z','url(#armor)','#9CBBB8',2)+path('M-19 -23Q0 -33 19 -23L23 6Q15 26 0 35Q-15 26-23 6Z','none','#D1B97D',1)+path('M0 -23L9 0L0 22L-9 0Z','#253C48',C['cyan'],1.3)+line(-21,0,21,0,C['cyan'],1),-56,13,1)
 # right sword extends across shoulder or outward
 sword=path('M-5 32L-4 -75L0 -94L4 -75L5 32Z','url(#whiteBlade)','#B6FFF4',1)+rect(-13,31,26,5,'url(#gold)',2)+rect(-3,36,6,22,'#657C82',2)+circle(0,59,5,'url(#gold)')
 s+=group(sword,58,15,1,extra='transform-origin="58 15"') if False else f'<g transform="translate(57 10) rotate({28 if pose=="attack" else -16})">{sword}</g>'
 return group(s,x,y,scale)
def arena(w=844,h=390,enemy=True,pose='guard'):
 s=rect(0,0,w,h,'url(#sky)')+circle(468,107,175,'url(#aura)')+circle(465,111,87,'none','#597584',1,extra='opacity=".25"')+circle(465,111,75,'none','#6F9190',1,extra='opacity=".15"')
 s+=path('M0 215L90 189L177 203L252 169L331 188L402 158L485 180L572 146L646 179L735 165L844 201V390H0Z','#122336')
 # monumental side columns
 for x,y,ww,hh in [(34,67,33,184),(93,104,18,134),(727,70,32,181),(790,40,42,224),(655,112,18,126)]:
  s+=path(f'M{x} {y+hh}V{y+14}L{x+ww/2} {y}L{x+ww} {y+14}V{y+hh}Z','#172A3B','#314758',1)+line(x+ww*.45,y+22,x+ww*.45,y+hh-10,'#577174',1)
  s+=line(x+8,y+42,x+ww-7,y+42,'#9E9B70',1)
 s+=path('M0 245L844 245V390H0Z','url(#floor)')
 for xx in [-400,-80,190,420,650,920,1240]:s+=line(422,236,xx,390,'#425161',1,extra='opacity=".6"')
 for yy in [254,274,309,365]:s+=path(f'M0 {yy}Q422 {yy-19}844 {yy}','none','#405063',1,extra='opacity=".55"')
 s+=f'<ellipse cx="470" cy="294" rx="223" ry="43" fill="#203448" stroke="#52676C" stroke-width="1"/>'
 s+=f'<ellipse cx="470" cy="293" rx="194" ry="33" fill="none" stroke="#72E5DB" stroke-opacity=".24" stroke-width="1"/>'
 for i in range(18):
  xx=35+((i*173)%772);yy=47+((i*43)%199);s+=circle(xx,yy,1 if i%2 else 1.6,C['gold'] if i%3==0 else C['cyan'],extra='opacity=".35"')
 s+=rect(0,0,w,92,'url(#topShade)')+rect(0,309,w,81,'url(#topShade)')
 if enemy:s+=guardian(490,204,1.04,pose)
 return s

def hearts(x,y,n=3,total=3,color=None):
 s=''
 for i in range(total):s+=path(f'M{x+i*25} {y}l9-6l9 6l-3 11l-6 4l-6-4Z',color or C['cyan'] if i<n else '#29384B')
 return s

def gamehud(title='守门者',phase='反击',own=3,foe=3,skill='蓄势斩',sub='雾光 · 训练剑',paused=False):
 s=eye(37,33,.48)+text(63,26,sub,12,C['white'],600)+hearts(65,40,own)
 s+=text(422,26,title,14,C['white'],600,'middle')+text(422,46,phase,11,C['muted'],400,'middle')
 s+=text(644,27,'守门者',12,C['white'],600)+hearts(644,41,foe,color=C['gold'])
 s+=rect(780,18,44,44,'#101A2BCC',13,C['line'])+line(797,31,797,48,C['white'],2.8)+line(807,31,807,48,C['white'],2.8)
 s+=mic(28,361)+text(46,366,'硬件麦克风已关',10,C['muted'])+pill(650,340,174,skill,C['gold'])
 return s

def command(title,sub,kicker='现在',accent=None):
 a=accent or C['cyan'];return rect(24,106,284,176,'url(#panel)',20)+rect(24,130,3,29,a,1.5)+text(43,136,kicker,12,a,600)+text(43,179,title,34,C['white'],700)+text(43,209,sub,13,C['muted'])
def timeline(x,y,w,label,frac=.5,c=None):
 return text(x,y,label,11,C['muted'])+rect(x,y+12,w,5,'#2D3E51',2.5)+rect(x,y+12,w*frac,5,c or C['cyan'],2.5)+circle(x+w*frac,y+14.5,4,c or C['cyan'])

def arc_arrow(cx,cy,kind='right',color=None):
 col=color or C['cyan'];d=f'M{cx-128} {cy+20} Q{cx} {cy-98} {cx+138} {cy+2}'
 if kind=='left':d=f'M{cx+128} {cy+20} Q{cx} {cy-98} {cx-138} {cy+2}'
 s=path(d,'none',col,25,extra='opacity=".1" filter="url(#glow)"')+path(d,'none',col,9,extra='opacity=".2"')+path(d,'none',col,2.5)
 ax=cx+138 if kind=='right' else cx-138
 s+=path(f'M{ax-16 if kind=="right" else ax+16} {cy-16}L{ax} {cy+2}L{ax-23 if kind=="right" else ax+23} {cy+5}','none',col,3)
 return s

def core_release():
 s=arena(pose='attack')+gamehud(phase='格挡成功 · 反击窗口',foe=3)
 s+=circle(490,207,140,'url(#warmAura)')+arc_arrow(489,199,'right',C['gold'])
 s+=path('M353 221Q450 112 635 185Q476 174 388 246Z','url(#mist)')
 s+=command('向你的右侧','从你的左侧 → 右侧挥斩','蓄力就绪 · 现在释放',C['gold'])
 s+=line(49,242,252,242,C['gold'],2.5)+path('M239 234L252 242L239 250','none',C['gold'],2.5)+circle(49,242,5,C['gold'])
 s+=rect(325,308,299,48,'#0B1020CC',14,C['line'])+timeline(343,325,262,'释放窗口',.66,C['gold'])
 return s
