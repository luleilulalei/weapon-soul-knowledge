from pathlib import Path
import json,re,base64,copy,math
ROOT=Path(__file__).resolve().parent
OLD=ROOT/'source'
(ROOT/'screens').mkdir(exist_ok=True)
(ROOT/'boards').mkdir(exist_ok=True)
# Reuse the reviewed visual primitives without rerunning the earlier export.
foundation=(OLD/'primitives.py').read_text()
exec(compile(foundation,'reviewed_visual_primitives','exec'))
ROOT=Path(__file__).resolve().parent
BG=base64.b64encode((ROOT/'assets/training_arena.jpg').read_bytes()).decode()
source=json.loads((OLD/'screens.json').read_text())
source_by={s['id']:s for s in source}
new={}
def rail(active='训练'):
 s=rect(0,0,80,390,'#0F172A')+line(80,20,80,370,'#28364D',.8)+circle(40,40,21,'#1C293E','#34445B')+group(path('M8 7a4 4 0 108 0 4 4 0 10-8 0M4 21v-2a8 8 0 0116 0v2','none','#BCC7D7',1.65),29,28,22/24)
 shapes=[circle(12,12,9,'none','currentColor',1.65)+path('M8 10v3M16 10v3','none','currentColor',1.65),path('M6 18L17 7l1-4-4 1L3 15M5 13l6 6M3 21l3-3','none','currentColor',1.65),path('M4 4h7l1 2 1-2h7v16h-7l-1 1-1-1H4zM12 6v15','none','currentColor',1.65)]
 for i,label in enumerate(['器灵','训练','收藏']):
  y=136+i*74;c=C['cyan'] if label==active else '#93A3BC'
  if label==active:s+=rect(12,y-24,56,62,C['cyan']+'14',18)
  s+=group(shapes[i],28,y-12,1,extra=f'color="{c}"')+text(40,y+29,label,11,c,600 if label==active else 400,'middle')
 s+=text(40,371,'SPIRIT',8,'#93A3BC',600,'middle','1.4')
 return s

def base():return rect(0,0,844,390,C['bg'])+circle(770,50,170,'url(#aura)')+rail()
def store_screen(id,body):
 d=copy.deepcopy(source_by[id]);d.update(width=844,height=390);name=Path(d['file']).name;(ROOT/'screens'/name).write_text(svg(844,390,body));d['body']=body;new[id]=d

def hall(progress='rhythm'):
 s=base()+text(104,47,'训练场',28,C['white'],700)+text(104,72,'握住熟悉的节奏，再向前一步。',12,C['muted'])+pill(632,29,188,'雾光 · 训练剑已连接')
 s+=rect(104,95,360,263,C['card'],22,C['line'])+'<defs><clipPath id="hallClip"><rect x="104" y="95" width="360" height="263" rx="22"/></clipPath></defs>'
 s+='<g clip-path="url(#hallClip)">'+f'<image href="data:image/jpeg;base64,{BG}" x="73" y="89" width="426" height="240"/>'+rect(104,230,360,128,'#0B1020',opacity=.82)+'</g>'
 tag,title,desc=('下一场挑战','守门者','看清来袭，格挡后再反击。') if progress=='rhythm' else (('第一次练剑','初次持剑','先认识方向，让动作清楚起来。') if progress=='new' else ('下一场练习','节拍','把左斩和右斩，连成完整一组。'))
 s+=text(127,122,tag,11,C['gold'],600)+text(128,278,title,28,C['white'],700)+text(128,306,desc,12,C['muted'])+text(128,338,'我陪你，把这一式练稳。',11,C['muted'])+circle(427,309,19,C['cyan'])+path('M423 302l8 7l-8 7','none',C['bg'],2)
 s+=text(486,81,'循序练习',14,C['white'],600)+text(820,80,'动作教学',12,C['cyan'],500,'end')
 items=[('01','辨向','6 次方向提示'),('02','节拍','左斩 → 右斩'),('03','守门者','格挡后反击，完成 3 次命中')]
 stats={'new':['可开始','辨向通关后开放','节拍通关后开放'],'direction':['已通过','可开始','节拍通关后开放'],'rhythm':['已通过','已通过','可挑战']}[progress]
 for i,(num,title,desc) in enumerate(items):
  y=95+i*91;locked='开放' in stats[i]
  s+=rect(484,y,336,81,C['card'],17,C['line'])+text(503,y+45,num,26,C['gold'] if not locked else '#526475',500)+text(552,y+31,title,17,C['white'] if not locked else C['muted'],600)+text(552,y+56,desc,10,C['muted'])+text(800,y+31,stats[i],10,C['cyan'] if stats[i] in ['可开始','可挑战'] else C['muted'],500,'end')
 return s

def result(id):
 fail=id in ['G16','G16D','G16G'];guardian=id in ['G16G','G22'];first=id=='G17';repeat=id=='G17R';direction=id=='G16D'
 s=base()+rect(104,25,264,340,'#111A2B',22,C['line'])
 label=('守门者' if guardian else ('辨向' if direction else '节拍'))+' · '+('本局已结束' if fail else ('首次通关' if first else ('本局胜利' if guardian else '再次通关')))
 s+=text(236,56,label,12,C['muted'],500,'middle')+circle(236,140,92,'url(#aura)' if fail else 'url(#warmAura)')
 if fail:
  score='0 / 3' if guardian else ('3 / 6' if direction else '2 / 4');cap='剩余生命' if guardian else ('有效动作' if direction else '完整组合')
  s+=text(236,150,score,49,C['white'],500,'middle')+text(236,183,cap,13,C['muted'],500,'middle')
  if guardian:s+=hearts(202,215,0)
  else:
   n=6 if direction else 4;good=3 if direction else 2;start=236-(n-1)*17
   for i in range(n):
    accepted=(i in ([0,2,4] if direction else [0,2]));s+=circle(start+i*34,219,10,C['cyan']+'20' if accepted else C['bad']+'16',C['cyan'] if accepted else '#795353')+text(start+i*34,223,'✓' if accepted else '×',11,C['cyan'] if accepted else C['bad'],500,'middle')
  s+=text(236,272,'这一局，差一点',24,C['white'],700,'middle')+text(236,302,'通关需要 4 次有效动作' if direction else ('三次防御未完成，本局结束' if guardian else '通关需要 3 组完整成功'),11,C['muted'],400,'middle')+text(236,338,'不用更快，也不用更用力。',11,C['muted'],400,'middle')
  s+=text(392,53,'这次先调整一件事',14,C['gold'],600)+rect(392,74,428,114,C['card'],17,C['line'])
  sentence='等“现在格挡”亮起，再持势。' if guardian else ('先看清“你的左 / 右”，再动作。' if direction else '第二段，等提示亮起再右斩。')
  reason='主要原因：两次格挡过早' if guardian else ('主要原因：两次方向错误' if direction else '第 2、4 组：右斩过早')
  s+=text(414,114,sentence,19,C['white'],600)+text(414,147,reason,12,C['muted'])+text(414,172,'先回起始姿态，再跟随下一次提示。',11,C['muted'])
  s+=btn(392,207,428,'重新准备，再试一次',True,48)+btn(392,269,428,'先练这一组动作' if not guardian else '回看格挡动作',False,44)+text(606,351,'回训练场休息',13,C['muted'],500,'middle')
 else:
  s+=circle(236,137,63,'none',C['gold'],1.2,extra='opacity=".65"')+circle(236,137,76,'none',C['gold'],1,extra='opacity=".22"')+path('M214 138l15 16l33-39','none',C['gold'],4)
  s+=text(236,254,'这一式，稳了',26,C['white'],700,'middle')+text(236,292,'3 次反击' if guardian else '3 / 4 组',23,C['white'],600,'middle')+text(236,323,'三次反击，都把握住了。' if guardian else '完整组合，已经连起来了。',11,C['muted'],400,'middle')
  s+=text(392,53,'新的节奏，接着练。' if first else '完成本局，按自己的节奏继续。',17,C['white'],600)
  s+=rect(392,74,428,103,C['card'],18,C['gold']+'65')+circle(439,125,34,'url(#warmAura)')+path('M422 144L452 104M420 132L433 145M436 104L450 119','none',C['gold'],2.5)
  s+=text(483,100,'新剑技已解锁' if first else ('本局表现' if guardian else '已拥有'),11,C['gold'],600)+text(483,127,'有效反击' if guardian else '蓄势斩',22,C['white'],700)+text(483,153,'正确格挡后反击 · 每次只结算一次' if guardian else '抬起蓄力 · 等待就绪 · 向下挥斩',11,C['muted'])
  s+=btn(392,195,428,'换一种剑技，再挑战' if guardian else '继续 · 挑战守门者',True,48)+(btn(392,254,428,'回训练场休息',False,44) if guardian else btn(392,254,206,'再练一次节拍',False,44)+btn(610,254,210,'回训练场休息',False,44))
  s+=line(392,317,820,317,C['line'])+text(392,343,'先放下剑，再选择下一步。',12,C['muted'])
 return s

store_screen('G01',hall())
store_screen('G17',result('G17'))
print('Prepared first landscape samples G01 and G17.')
# Keep previously reviewed full-screen battle and tutorial layouts at their native dimensions.
for d in source:
 if d['width']!=844:continue
 raw=(OLD/d['file']).read_text();body=raw.split('</defs>',1)[1].rsplit('</svg>',1)[0]
 body=body.replace('把手机横屏放稳','把手机放稳').replace('手机已横屏放稳','手机已放稳').replace('横屏放稳，8 秒后准备','放稳手机，8 秒后准备')
 if d['id']=='G12':
  body=body.replace('保持架势','举剑蓄力').replace('先等就绪，再向右挥斩','抬起剑，保持舒适姿态').replace('尚未就绪，请勿释放','尚未就绪，请保持姿态')
  body+=line(267,268,267,233,C['gold'],2)+path('M260 241L267 233L274 241','none',C['gold'],2)
 if d['id']=='G20T':body=body.replace('下一次在金色窗口结束前右斩','下一次在金色窗口内向下挥斩')
 store_screen(d['id'],body)

def arena_scene():
 return rect(0,0,844,390,C['bg'])+f'<image href="data:image/jpeg;base64,{BG}" x="0" y="-30" width="844" height="475" preserveAspectRatio="xMidYMid slice"/>'+rect(0,0,844,390,'#0B1020',opacity=.18)+rect(0,0,844,100,'url(#topShade)')+rect(0,307,844,83,'#0B1020',opacity=.55)
b=arena_scene()+gamehud(title='训练对抗',phase='格挡成功 · 反击窗口',foe=3)
b+=circle(425,207,140,'url(#warmAura)')+path('M437 95Q429 179 439 281','none',C['gold'],24,extra='opacity=".18" filter="url(#glow)"')+path('M437 95Q429 179 439 281','none',C['gold'],4)+path('M421 261L439 281L455 260','none',C['gold'],3)
b+=command('向下挥斩','从高位向下，完成一次挥斩','蓄力就绪 · 现在释放',C['gold'])+line(253,232,253,266,C['gold'],2.5)+path('M245 257L253 266L261 257','none',C['gold'],2.5)+text(43,249,'就绪后，一次下挥即可',12,C['gold'],500)
b+=rect(325,308,299,48,'#0B1020CC',14,C['line'])+timeline(343,325,262,'剩余释放时间',.66,C['gold'])+line(601,342,586,342,C['gold'],1.5)+path('M591 338L586 342L591 346','none',C['gold'],1.5)+line(343,337,343,350,C['gold'],1.3)
store_screen('G13',b)
oldfile=ROOT/new['G13']['file'];new['G13']['file']='screens/G13_守门者_向下释放.svg';new['G13']['title']='守门者_向下释放';oldfile.rename(ROOT/new['G13']['file'])
print('Native landscape scenes adapted, including lift-charge/downward-release candidate.')

def prepare(id):
 blocked=id=='G02B';mode='辨向' if id=='G02D' else ('节拍' if id=='G02R' else '守门者');skill={'G02S':'基础斩','G02C':'回锋'}.get(id,'蓄势斩')
 s=base()+text(104,47,'充电时，先歇一歇' if blocked else '开始前，准备好',27,C['white'],700)+text(104,72,'挥剑训练暂不可开始' if blocked else '本次挑战 · '+mode,12,C['muted'])
 s+=rect(104,95,288,81,C['card'],18,C['line'])+eye(143,134,.62)+text(180,124,'雾光',20,C['white'],700)+text(180,148,'训练剑 · 当前器灵',11,C['muted'])+text(180,165,'手机与器灵已连接',10,C['cyan'])
 s+=text(104,205,'设备检查',16,C['white'],600)+text(392,204,'已更新',11,C['muted'],400,'end')
 labels=['剑身已识别，当前可用','正在充电 · 挥剑已禁用' if blocked else '未充电 · 未入座','当前可查看器灵与设备状态' if blocked else '未发现设备风险提示']
 for i,label in enumerate(labels):
  y=230+i*32
  s+=(circle(114,y,10,C['gold']+'22')+line(110,y,118,y,C['gold'],2)) if blocked and i==1 else check(114,y)
  s+=text(134,y+5,label,12,C['gold'] if blocked and i==1 else C['white'])
 s+=rect(104,320,288,45,'#241F25',12)+text(119,339,'感觉不安全，就停下并放下剑。',10,C['gold'],600)+text(119,355,'无需为了避免失败继续动作。',10,C['muted'])
 s+=text(416,45,'本局使用剑技' if id in ['G02D','G02R'] else '本局反击剑技',14,C['white'],600)
 if id in ['G02D','G02R']:
  s+=rect(416,64,404,45,C['card'],13,C['line'])+text(618,93,'基础斩 · 左 / 右辨向' if id=='G02D' else '回锋 · 左斩接右斩',15,C['cyan'],600,'middle')
 else:
  for i,label in enumerate(['基础斩','回锋','蓄势斩']):
   x=416+i*138;sel=label==skill;s+=rect(x,64,128,45,C['cyan']+'18' if sel else C['card'],13,C['cyan'] if sel else C['line'])+text(x+64,93,label,15,C['cyan'] if sel else C['muted'],600,'middle')
 for y,title,desc in [(147,'手机已经放稳','面向屏幕，回到可看清提示的位置'),(207,'周围有充足空间','确认挥动范围没有人或障碍物')]:
  s+=rect(416,y-12,20,20,C['cyan'],6)+path(f'M421 {y-2}l3 3l7-8','none',C['bg'],1.8)+text(449,y+3,title,16,C['white'],600)+text(449,y+26,desc,12,C['muted'])
 s+=btn(416,274,404,'返回器灵主页' if blocked else '放稳手机，8 秒后准备',True,48)+text(618,349,'结束充电、离座后再重新进入训练' if blocked else '倒计时后先校准，本页不开始计分',11,C['muted'],400,'middle')
 return s

for id in ['G02','G02B','G02D','G02R','G02S','G02C']:store_screen(id,prepare(id))
for id in ['G16','G16D','G16G','G17','G17R','G22']:store_screen(id,result(id))
store_screen('G01N',hall('new'));store_screen('G01D',hall('direction'))
# No user-facing diagram or stage asks for a rotation: the application is now landscape throughout.
for id,d in new.items():
 d['body']=d['body'].replace('把手机横屏放稳','把手机放稳').replace('手机已横屏放稳','手机已放稳').replace('横屏放稳，8 秒后准备','放稳手机，8 秒后准备')
 (ROOT/d['file']).write_text(svg(844,390,d['body']))
# Reflow all real hit areas instead of scaling the old portrait coordinates.
portrait_ids={s['id'] for s in source if s['width']==390}
def area(z,x,y,w,h):z.update(x=x,y=y,w=w,h=h);return z
def rail_targets():
 return [dict(x=18,y=18,w=44,h=44,target='A05',label='个人主页'),dict(x=12,y=112,w=56,h=62,target='A01',label='器灵',contextTarget={'key':'progress','targets':{'new':'A01N','direction':'A01N','rhythm':'A01'}}),dict(x=12,y=186,w=56,h=62,target='G01',label='训练',contextTarget={'key':'progress','targets':{'new':'G01N','direction':'G01D','rhythm':'G01'}}),dict(x=12,y=260,w=56,h=62,target='A03',label='收藏',contextTarget={'key':'progress','targets':{'new':'A03N','direction':'A03N','rhythm':'A03'}})]
for id in portrait_ids:
 d=new[id];hot=[]
 for oldhot in d['hotspots']:
  z=copy.deepcopy(oldhot)
  if z['label'] in ['器灵','训练','收藏']:continue
  if id in ['G01','G01N','G01D']:
   if oldhot['y']==171:area(z,104,95,360,263)
   elif oldhot['y']==436:area(z,744,56,76,35)
   elif oldhot['y'] in [474,550,626]:area(z,484,95+91*([474,550,626].index(oldhot['y'])),336,81)
  elif id.startswith('G02'):
   if oldhot['y']==685:area(z,416,274,404,48);z['label']=z['label'].replace('进入横屏倒计时','放稳手机后准备倒计时')
   elif oldhot['y']==266:area(z,416+138*([24,136,248].index(oldhot['x'])),64,128,45)
  elif id in ['G16','G16D','G16G']:
   if oldhot['y']==593:area(z,392,207,428,48)
   elif oldhot['y']==652:area(z,392,269,428,44)
   else:area(z,392,330,428,37)
  elif id in ['G17','G17R','G22']:
   if oldhot['y']==556:area(z,392,195,428,48)
   elif oldhot['y']==615:area(z,392,254,428 if id=='G22' else 206,44)
   else:area(z,392,326,428,44)
  hot.append(z)
 
 if id in ['G17','G17R']:
  hot.append(dict(x=610,y=254,w=210,h=44,target='G01',label='回训练场休息',contextTarget={'key':'progress','targets':{'new':'G01N','direction':'G01D','rhythm':'G01'}}))
 d['hotspots']=hot+rail_targets()
# Normalize event descriptions only where the candidate charge-release direction changed.
for d in new.values():
 for z in d['events']:
  if d['id'] in ['G12','G13','G20','G20T']:z['label']=z['label'].replace('右斩','向下挥斩')
 for z in d['hotspots']:z['label']=z['label'].replace('横屏','')
assert set(new)==set(source_by),(set(source_by)-set(new))
metadata=[{k:v for k,v in new[s['id']].items() if k!='body'} for s in source]
(ROOT/'screens.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
context=json.loads((OLD/'context.json').read_text())
context['interactionScope']={'gameConversation':False,'dialogueSurface':'physical_hardware_only','hardwareMicrophoneStatus':'read_only','postLevelMemoryDecision':False,'memoryAutoSaveSpecified':False}
(ROOT/'context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2))
(ROOT/'manifest.json').write_text(json.dumps({'screen_count':len(metadata),'width':844,'height':390,'revision':'v1.4','interaction_scope':{'game_conversation':False,'post_level_memory_decision':False,'memory_auto_save_specified':False,'dialogue_surface':'physical_hardware_only'},'shared_navigation':{'rail_width':80,'content_x':104,'centers':[[40,136],[40,210],[40,284]]},'screens':[{'id':d['id'],'title':d['title'],'file':d['file']} for d in metadata]},ensure_ascii=False,indent=2))

NOTES={
'G01':('训练入口，横屏常驻','左侧导航与 App 共用；场景入口和关卡列表各有清楚目标。'),
'G01N':('第一次玩，没有虚构进度','只开放辨向；通过后依次进入节拍和守门者。'),
'G02':('手机放稳，仍需回站位','横屏不替代安全准备；倒计时和开始点设备复核保留。'),
'G02B':('充电阻断，返回器灵主页','不是把按钮置灰后无路可走；停止挥剑要求。'),
'G16':('失败，先纠正一件事','重试回准备；已有技能保留，不诱导更猛烈动作。'),
'G17':('结果与下一步优先','技能解锁只发生一次；下一步只有继续、再练或休息。'),
'G03':('近屏设置 → 放稳 → 回站位','8 秒为可调默认建议，倒计时本身不开始计分。'),
'G04':('先看懂玩家视角','“你的左 / 右”不因画面敌人朝向而翻转。'),
'G05':('轮到玩家，等待实体输入','成功不是触屏按钮；画外模拟事件不伪装真实识别。'),
'G06':('已知错向，给单项纠正','有证据才说方向错；未知输入另有 G06U。'),
'G07':('验证后，进入原选关卡','校准成功只是一组模拟样例，不代表识别性能达标。'),
'G08':('辨向运行截面','六次提示完整循环由规则描述；原型明确模拟余下过程。'),
'G09':('完整组合才算一组','首段正确、次段失败不算完整组，不继承到下一组。'),
'G10':('敌人防御与来袭预告','防御期挥斩不扣生命；来袭方向和要求格挡分开。'),
'G11':('窗口打开，再格挡','成功后进入所选技能轨道，失败不同时庆祝成功。'),
'G12':('抬起 / 举剑蓄力','按早期表达统一动作候选；姿态、安全阈值仍需实测。'),
'G13':('就绪后，向下挥斩','仅改蓄势释放候选；基础斩与回锋左右方向不变。'),
'G20':('提前释放，取消这一式','不补基础斩命中；超时另有明确 G20T 状态。'),
'G14':('暂停冻结，保留已确认进度','触屏入口不等于远距即时暂停已解决。'),
'G15':('恢复也先回站位','旧组合 / 蓄力清空，验证后按原快照恢复，不回血。'),
'G18':('断连，先停止推进','按钮只去检查中；结果未知就保持待核对。'),
'G19':('已核对中断，准备新开','已连接不等于已确认本局终态，也不自动续战。'),
'G16G':('守门者普通失败','生命耗尽与节拍组数分开，回看格挡不直接开攻击。'),
'G22':('胜利后，可再练也可休息','本局表现不暗示重复授予；新开仍走准备。')}
def board(name,num,title,sub,ids):
 w=1840;h=190+math.ceil(len(ids)/2)*494+45
 b=rect(0,0,w,h,'#080D18')+text(40,52,'器灵  /  LANDSCAPE GAME UI',13,C['gold'],500,spacing='2')+text(40,99,title,34,C['white'],700)+text(40,130,sub,13,C['muted'])+text(w-40,58,num,36,'#304155',500,'end')+line(40,151,w-40,151,C['line'])
 for i,id in enumerate(ids):
  x=40+(i%2)*912;y=183+(i//2)*494;d=new[id]
  b+=f'<svg x="{x}" y="{y}" width="844" height="390" viewBox="0 0 844 390" overflow="hidden">{d["body"]}</svg>'+rect(x,y,844,390,'none',0,'#3A475D')+text(x,y+420,id+'  '+NOTES[id][0],17,C['white'],600)+text(x,y+448,NOTES[id][1],11,C['muted'])
 b+=text(40,h-23,'全横屏 844 × 390 · 共享组件的状态样张，非新增独立开发页 · 动作识别、窗口、安全与灯效时序仍待实测',11,C['muted'])
 (ROOT/'boards'/f'{name}.svg').write_text(svg(w,h,b))
board('01_横屏大厅准备与结果','01','放稳手机，进入同一个训练世界。','全部界面原生横向重排 · 80 px 共享导航 · 大厅 / 准备 / 失败 / 结算各自保持清楚的下一步',['G01','G02','G16','G17','G01N','G02B'])
board('02_准备与方向教学','02','不再旋转手机，也不省略准备。','设置 → 手机放稳 → 回到站位 → 演示 → 验证 · 保留完整安全路径',['G03','G04','G05','G06','G07','G08'])
board('03_攻防与向下释放','03','该等、该挡、该出手，一眼读懂。','抬起蓄力 → 就绪 → 向下挥斩的细化候选，与实体灯效表达统一',['G09','G10','G11','G12','G13','G20'])
board('04_暂停恢复与正常结束','04','停下来，也能有序回来。','暂停保留本局已确认快照；中断先核对；胜负与主动退出分别处理',['G14','G15','G18','G19','G16G','G22'])
print(f'Exported {len(new)} landscape state samples, every state 844×390; four review boards.')
