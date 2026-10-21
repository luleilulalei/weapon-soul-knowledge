from pathlib import Path
import json,sys
from html import escape
from face_primitives import eyes,icon,text,DEFS,C,MIC
P=Path(__file__).resolve().parent.parent
states=json.loads((P/'source/base_states.json').read_text())+json.loads((P/'source/extension_states.json').read_text())
changes={
'D07':dict(wave=''),
'D42':dict(label='关断已确认',sub='仅短提示后熄屏',note='条件样张：真实安全关断且可短显后，熄屏。'),
'X-D16':dict(label='关断已确认',sub='仅短提示后熄屏',note='真实安全信号＋短显能力均成立才显示；随后熄屏。'),
'D18':dict(sub='独立触摸区可回应'), 'D19':dict(sub='感受到轻触'),
'D21':dict(label='等待许可',sub='请通过硬件语音确认'),
'D25':dict(label='查阅记忆',sub='请在硬件侧说明'),
'D26':dict(label='等待删除确认',sub='请通过语音或 App 确认'),
'X-D01':dict(title='设备等待外部输入',mood='calm',label='等待输入',sub='',note='既有控制能力保留，实体键方案待定；此处不显示菜单。'),
'X-D02':dict(title='关麦意图待确认',mood='calm',label='关麦待确认',sub='采音尚未改变',note='外部控制请求的状态反馈，不是屏幕可选项。'),
'X-D03':dict(title='开麦意图待确认',mood='calm',label='开麦待确认',sub='仍保持关闭',note='获批非语音确认与权限有效后，才发送请求。'),
'X-D04':dict(title='深眠意图待确认',mood='drowsy',label='深眠待确认',sub='尚未执行',note='确认方式由实体输入方案决定，不能点按屏幕。'),
'X-D05':dict(title='关机意图待确认',mood='calm',label='关机待确认',sub='先别拆装',note='保留关机能力；确认与完成仍是不同事实。'),
'X-D06':dict(title='等待独立输入',mood='calm',label='等待确认',sub='',note='来源须是经批准的独立非语音输入，具体按法未定。'),
'X-D07':dict(title='确认处理中',mood='think',label='确认中',sub='仍保持关闭',note='确认来源与权限尚需批准；无屏幕操作目标。'),
'X-D08':dict(title='已取消控制意图',label='已取消',sub='状态未改变',note='退出或超时不执行操作；已发请求需另核对。')}
for s in states:
 s.update(changes.get(s['id'],{}));s['display_only']=True
 for k in ['prev','next','active','item','hint']:s.pop(k,None)
 if s['id'].startswith('X-'):s['kind']='status'
 s['note']=s['note'].replace('触摸表情','独立触摸区触发的表情')

def face(d):
 off=d['mic']=='off'; mi,ml=MIC[d['mic']]
 o='<circle cx="120" cy="120" r="119" fill="url(#screen)"/>'
 o+=icon(mi,64,30,14,C['gold'] if off else C['cyan'])+text(132,42,ml,10.5,C['gold'] if off else C['muted'])
 o+=eyes(d['mood'])
 if d.get('badge'):
  o+=icon(d['badge'],106 if d['mood']=='none' else 111,87 if d['mood']=='none' else 57,28 if d['mood']=='none' else 18,C.get(d.get('accent','cyan'),C['cyan']))
 if d.get('wave'):
  for i,h in enumerate([4,9,16,22,12,18,8,4]):o+=f'<path d="M{87+i*9} {162-h/2}v{h}" stroke="#72E5DB" stroke-width="3" stroke-linecap="round"/>'
 if d.get('dots'):
  for i in range(3):o+=f'<circle cx="{110+i*10}" cy="161" r="2" fill="#72E5DB" opacity="{.4+.25*i}"/>'
 if d.get('ticks'):o+=text(120,168,'·  ·  ·',13,C['cyan'])
 if d.get('pulse'):o+='<circle cx="120" cy="117" r="85" fill="none" stroke="#72E5DB" opacity=".3"/>'
 if d.get('label'):o+=text(120,190 if d.get('wave') else 183,d['label'],18 if len(d['label'])<8 else 16,C['white'],500)
 if d.get('sub'):o+=text(120,207,d['sub'],10.5 if len(d['sub'])>11 else 12,C['muted'])
 return o

def svg(w,h,o):return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{DEFS}{o}</svg>'
def save(name,w,h,o): (P/'boards'/f'{name}.svg').write_text(svg(w,h,o))
def lines(x,y,ss,size=19,color=None):return ''.join(text(x,y+i*(size+14),s,size,color or C['muted'],400,'start') for i,s in enumerate(ss))
def header(n,title,sub,w=1920):return f'<rect width="{w}" height="2400" fill="#0B1020"/>'+text(80,65,'器灵 / SPIRIT    ·    DISPLAY ONLY R2',18,C['cyan'],500,'start')+text(80,125,title,40,C['white'],600,'start')+text(80,169,sub,19,C['muted'],400,'start')+text(w-80,66,n,18,C['gold'],500,'end')
by={s['id']:s for s in states}
# First board: separation of hardware inputs from the passive display.
o=header('01','圆屏是器灵的表情，不是操作面板。','无触屏按钮 · 无滚动列表 · 无屏幕导航    /    所有操作发生在屏幕之外')
o+=f'<g transform="translate(172,300) scale(1.3)">{face(by["D01"])}</g>'
o+=text(330,665,'非触摸圆屏',24,C['white'],500)
o+='<rect x="220" y="730" width="75" height="56" rx="10" fill="#344B59" stroke="#E7BD79" stroke-width="2"/><rect x="350" y="730" width="110" height="56" rx="16" fill="#243E43" stroke="#72E5DB" stroke-width="2" stroke-dasharray="6 6"/>'
o+=text(258,830,'实体键',18,C['gold'])+text(405,830,'独立触摸区',18,C['cyan'])
o+=text(330,890,'仅表示输入分离，不代表外观与位置',16,C['muted'])
for y,t,ls in [(355,'01  非触摸圆屏',['显示表情、采音事实、简短状态与动作反馈。','没有任何点按、长按或滑动命中区域。']),(565,'02  实体按键',['实体输入与圆屏物理分离；位置未定。','保留既有控制需求；键序与防误触规则待验证。']),(735,'03  独立触摸区',['位于屏幕之外的壳体区域；此分区不代表外观。','触摸只触发表情等获批反馈，不等于屏幕操作。'])]:
 o+=text(650,y,t,26,C['white'],500,'start')+lines(650,y+45,ls)
o+=text(80,1060,'复杂操作交给 App；持剑时不用低头找按钮。',30,C['white'],500,'start')
o+=lines(80,1110,['配网、账户与权限、记忆查看/删除（不可修改）、参数设置：沿用 App 对应能力。','保留语音、实体键、独立触摸、动作识别与入离座等输入；圆屏只是这些事件的反馈端。','只有硬件侧可与器灵对话；游戏端不提供对话，也不询问闯关记忆是否保留。'])
save('01_圆屏与输入物理分离',1920,1280,o)
# Remaining boards keep every existing ID while removing control affordances.
groups=[('02_表情与对话','眼睛负责回应，状态负责说清事实。',states[:12]),('03_离线隐私与记忆','记忆支持查看与删除，已有内容不可修改。',states[12:28]),('04_电源与恢复','电源结果真实可见，安全不靠动画猜测。',states[28:44]),('05_异常与补充分支','未知就是未知，不提前展示成功。',states[44:50]),('06_外部控制状态反馈','控制来自屏幕外，这里只呈现一个当前状态。',states[50:58]),('07_真实结果与安全完成','请求、成功、安全完成，各有自己的证据。',states[58:])]
for name,title,arr in groups:
 rows=(len(arr)+3)//4;h=230+rows*405+80;o=header(name[:2],title,'240 × 240 状态画布    /    下方说明属于设计图板，不进入设备屏幕')
 for i,d in enumerate(arr):
  x=80+(i%4)*450;y=220+(i//4)*405
  o+=f'<g transform="translate({x+65},{y}) scale(1.15)">{face(d)}</g>'
  o+=text(x+202,y+311,d['id']+'  '+d['title'],18,C['white'],500)
  note=d['note'];parts=[note[j:j+23] for j in range(0,len(note),23)];parts=[p for p in parts if p not in ['。','；']]
  for j,p in enumerate(parts[:2]):o+=text(x+202,y+344+j*25,p,15,C['muted'])
 o+=text(80,h-28,'仅显示反馈 · 非触摸屏 · 输入方案与实机可读性仍待验证',17,C['gold'],400,'start')
 save(name,1920,h,o)
for d in states:(P/'screens'/f'{d["id"]}.svg').write_text(svg(240,240,face(d)))
(P/'states.json').write_text(json.dumps(states,ensure_ascii=False,indent=2))
(P/'scope_rules.json').write_text((P/'source/scope_rules.json').read_text())
# Local review controls are deliberately outside the noninteractive display.
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>器灵 · 非触摸圆屏评审</title><style>*{box-sizing:border-box}body{margin:0;background:#0b1020;color:#f4f3ed;font:17px system-ui,'Noto Sans CJK SC',sans-serif}header{padding:32px 6vw;border-bottom:1px solid #293849}h1{font-size:34px}p{line-height:1.8;color:#93a7b5}main{display:grid;grid-template-columns:1fr 1fr;gap:70px;padding:45px 6vw}.hardware{width:360px;height:580px;margin:auto;position:relative;padding:35px}.display{width:286px;height:286px;pointer-events:none;user-select:none;touch-action:none}.display img{width:100%;height:100%;pointer-events:none}.key{position:absolute;left:45px;top:400px;width:60px;height:40px;border:2px solid #e7bd79;border-radius:10px}.touch{width:150px;margin:100px 0 0 120px;padding:18px 0;border:1px dashed #72e5db;border-radius:18px;text-align:center;color:#72e5db;font-size:14px}aside{border-left:1px solid #293849;padding-left:40px}label{display:block;color:#e7bd79;margin-bottom:12px}select,button{font:inherit;padding:12px;background:#152638;color:#fff;border:1px solid #577080;border-radius:6px;margin:8px 8px 8px 0}select{width:100%}.caption{text-align:center}.note{min-height:80px}small{color:#93a7b5}@media(max-width:800px){main{grid-template-columns:1fr}aside{border-left:0;padding:0}}</style><header><small>器灵 / SPIRIT · V1.4 / R2 修订评审原型</small><h1>圆屏只显示。操作在屏幕外。</h1><p>左侧是非触摸圆屏与输入区域示意；右侧是设计评审模拟器，不属于设备界面。不连接设备、不采音。</p></header><main><section><div class="hardware"><div class="display" aria-label="非触摸圆屏，仅显示"><img id="face" alt="器灵当前状态"></div><div class="key" aria-label="实体键分区示意"></div><div class="touch">独立壳体触摸区<br>分区不代表外观</div></div><p class="caption">圆屏点按、长按、滑动均不触发事件</p></section><aside><label for="state">屏幕外 · 评审模拟控制</label><select id="state"></select><div><button id="prev">上一状态</button><button id="next">下一状态</button><button id="black">模拟断电黑屏</button></div><h2 id="title"></h2><p class="note" id="note"></p><p id="voice"></p><hr><p>App 支持记忆查看与删除，不提供修改。器灵对话仅在硬件侧，游戏端没有对话或闯关记忆保留选择。此页切换仅为展示已有状态，不代表实体键方案已批准，也不会执行开麦、关机等真实操作。</p><small>实体按键与独立触摸区的图形也不绑定点击事件；它们的位置、尺寸、手势与阈值仍待确认。</small></aside></main><script>const states=__STATES__;let index=0;const sel=document.getElementById('state');states.forEach((s,i)=>sel.add(new Option(s.id+' '+s.title,i)));function show(i){index=(i+states.length)%states.length;let s=states[index];sel.value=index;document.getElementById('face').src='screens/'+s.id+'.svg';document.getElementById('title').textContent=s.title;document.getElementById('note').textContent=s.note;document.getElementById('voice').textContent='声音反馈说明：'+(s.voice||'由当前状态规则决定');}sel.onchange=()=>show(+sel.value);document.getElementById('prev').onclick=()=>show(index-1);document.getElementById('next').onclick=()=>show(index+1);document.getElementById('black').onclick=()=>{document.getElementById('face').src='screens/power_off_illustration.svg';document.getElementById('title').textContent='断电后显示示意';document.getElementById('note').textContent='纯黑屏只演示断电后没有显示能力，不证明安全关断成功；实际关断须硬件信号确认。选择任一状态可恢复评审。';document.getElementById('voice').textContent='无自动成功转换，无真实设备动作。';};show(0);window.__review={get index(){return index},states};</script></html>'''
(P/'index.html').write_text(html.replace('__STATES__',json.dumps(states,ensure_ascii=False)))
(P/'screens/power_off_illustration.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><circle cx="120" cy="120" r="119" fill="#000"/></svg>')
print('Generated',len(states),'display-only states, 7 boards and review prototype')
