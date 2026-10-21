from pathlib import Path
import json,base64,html
R=Path(__file__).parent
screens=[]
for group in ['app','game']:
 p=R/group/'screens.json'
 if not p.exists():continue
 data=json.loads(p.read_text());data=data.get('screens',data) if isinstance(data,dict) else data
 if isinstance(data,dict):data=[dict(id=k,**v) for k,v in data.items()]
 for s in data:
  s=dict(s);s['group']=group;s['title']=s.get('title',s.get('name',s['id']));s['width']=s.get('width',s.get('w',390));s['height']=s.get('height',s.get('h',844))
  f=Path(s.get('file',s.get('svg','')))
  candidates=[f,R/f,R/group/f,R/group/'screens'/f,R/group/'screens'/(str(f)+'.svg')]
  f=next((p for p in candidates if p.is_file()),None)
  if f is None:raise ValueError(s)
  # Each SVG is a separate image document; IDs cannot collide across screens.
  s['src']='data:image/svg+xml;base64,'+base64.b64encode(f.read_bytes()).decode();s.pop('file',None)
  screens.append(s)
import re
screens.sort(key=lambda s:(0 if s['group']=='app' else 1,int(re.search(r'\d+',s['id']).group()),s['id']))
ids={s['id'] for s in screens}
# Shared app navigation is connected only when explicit cross-module targets exist.
for s in screens:
 for h in s.get('hotspots',[])+s.get('events',[]):
  if h.get('target') and h.get('target') not in ids:raise ValueError(f"Broken destination {s['id']} -> {h}")
  for target in h.get('contextTarget',{}).get('targets',{}).values():
   if target not in ids:raise ValueError(f"Broken contextual destination {target}")
assert len(ids)==len(screens)
(R/'output/screens_manifest.json').write_text(json.dumps([{k:v for k,v in s.items() if k!='src'} for s in screens],ensure_ascii=False,indent=2))
DATA=json.dumps(screens,ensure_ascii=False).replace('</','<\\/')
app_context=json.loads((R/'app/context.json').read_text()) if (R/'app/context.json').exists() else {}
# Cross-module confirmed training results update the home demonstration consistently.
app_context.setdefault('defaults',{})['memoryFixture']='existing'
app_context.setdefault('enterContext',{}).setdefault('A12',{})['memoryFixture']='empty'
app_context.setdefault('enterContext',{}).setdefault('G17',{}).update({'journeyState':'existing','progress':'rhythm'})
app_context.setdefault('aliases',{}).update({'G01':{'key':'progress','targets':{'new':'G01N','direction':'G01D','rhythm':'G01'}},'G01N':{'key':'progress','targets':{'new':'G01N','direction':'G01D','rhythm':'G01'}}})
APP_CONTEXT=json.dumps(app_context,ensure_ascii=False).replace('</','<\\/')
GAME_DEFAULTS=json.dumps(json.loads((R/'game/context.json').read_text()).get('defaults',{}),ensure_ascii=False)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>器灵 高保真交互原型</title>
<style>*{box-sizing:border-box}body{margin:0;background:#080c17;color:#f4f3ed;font:15px system-ui,"Noto Sans CJK SC",sans-serif}header{padding:20px 28px;border-bottom:1px solid #26334b;display:flex;justify-content:space-between;gap:20px;align-items:center}h1{font-size:22px;margin:0 0 6px}p{color:#a9b6cb;margin:0;line-height:1.7}button,select{font:inherit;cursor:pointer;background:#151e32;color:#f4f3ed;border:1px solid #34435f;border-radius:12px;padding:11px 14px}button:hover,button:focus-visible{border-color:#72e5db;outline:2px solid #72e5db}main{display:grid;grid-template-columns:260px minmax(0,1fr) 260px;gap:24px;padding:24px}aside{min-width:0}aside h2{font-size:15px;color:#e7bd79;margin:20px 0 10px}aside button{display:block;text-align:left;width:100%;margin:8px 0}aside button.active{background:#203c43;border-color:#72e5db}.stage{display:flex;align-items:flex-start;justify-content:center;min-width:0}.phone{position:relative;box-shadow:0 24px 80px #0009;border-radius:22px;overflow:hidden;background:#0b1020;width:100%;max-height:none}.phone img{width:100%;height:auto;display:block}.hit{position:absolute;border:0;padding:0;background:transparent;border-radius:10px;min-width:0}.hit:hover{background:#72e5db20;outline:2px solid #72e5db}.hit:focus-visible{background:#72e5db20;outline:3px solid #e7bd79}.hints .hit{outline:1px dashed #72e5db;background:#72e5db0c}.note{border:1px solid #34435f;padding:16px;border-radius:16px;margin:0 0 20px;background:#10182a}.badge{font-size:12px;letter-spacing:1px;color:#72e5db}.status{color:#e7bd79;font-size:13px;margin:12px 0}#list{max-height:70vh;overflow:auto}#screenTitle{font-size:19px;line-height:1.4}label{display:block;color:#a9b6cb;margin:15px 0}a{color:#72e5db} @media(max-width:1050px){main{grid-template-columns:190px minmax(0,1fr)}.right{grid-column:1/-1}.phone{max-width:844px!important}header{display:block}}@media(max-width:650px){main{display:flex;flex-direction:column;padding:14px}.left{order:2}.stage{order:0}.right{order:1}#list{max-height:220px}.phone{width:100%!important}header{padding:16px}}</style>
<header><div><div class="badge">SPIRIT · LANDSCAPE UI V1.4</div><h1>器灵 V1.4 全横屏交互原型</h1><p>点击画面中的按钮走流程。示例数据仅用于设计演示，不连接设备与账户。</p></div><button id="reset">重置演示</button></header>
<main><aside class="left"><button id="back">← 上一步</button><label><input id="hints" type="checkbox"> 显示可点击区域</label><h2>独立样张索引</h2><p>直接选样张会重置演示状态；走流程请点击画面内按钮。</p><select id="group"><option value="all">全部页面</option><option value="app">器灵与收藏</option><option value="game">训练与游戏</option></select><div id="list"></div></aside><section class="stage"><div id="phone" class="phone"><img id="screen" alt=""><div id="hits"></div></div></section><aside class="right"><div class="note"><div class="badge" id="screenId"></div><h2 id="screenTitle"></h2><p id="notes"></p></div><h2>模拟事件</h2><p>下面的控件在真实 App 中不存在，用来演示动作识别、网络或处理结果。</p><div id="events"></div><div class="status" id="status" role="status"></div><div class="note"><p>本原型检查操作与信息层级。IMU识别、实时战斗、真实兑换、保存和删除尚未实现；模拟成功不代表已通过实机测试。</p></div></aside></main>
<script>const screens=__DATA__;const byId=Object.fromEntries(screens.map(s=>[s.id,s]));const appState=__APP_CONTEXT__;const defaults={...__GAME_DEFAULTS__,...(appState.defaults||{})};let historyStack=[],current=null,context={...defaults};const $=id=>document.getElementById(id);const start=screens.find(s=>s.id==='A01')?.id||screens[0].id;
function resolve(id){if(id==='A19'&&context.preferenceMemoryState==='deleted')return 'A26P';if(id==='A19'&&context.preferenceMemoryState==='pending')return 'A27P';if(id==='A21'&&context.preferenceMemoryState==='deleted')return 'A26P';if(id==='A21'&&context.preferenceMemoryState==='pending')return 'A23P';if(id==='A03'&&context.decorationState==='none')return context.progress==='rhythm'?'A03U':'A03N';if(id==='A26'&&context.memoryFixture==='empty')return 'A19N';if(id==='A02B'&&context.memoryFixture==='empty')return 'A02N';for(let i=0;i<6;i++){const a=(appState.aliases||{})[id];const next=a&&a.targets[context[a.key]];if(!next||next===id)break;id=next}return id}
function restorePrevious(fallback){if(historyStack.length){const prev=historyStack.pop(),fresh={...context};context=prev.context;for(const k of [...Object.keys(appState.defaults||{}),'progress'])context[k]=fresh[k];go(prev.id,false)}else if(fallback)go(fallback,false)}
function activate(h){if(h.disabled)return;if(h.behavior==='back'){restorePrevious(h.fallback_target||h.target);return}const old={...context};Object.assign(context,(appState.eventContext||{})[current+'|'+h.label]||{});if(h.setContext)Object.assign(context,h.setContext);if(context.memoryState==='singleSaved')context.memoryFixture='single';const target=h.contextTarget?h.contextTarget.targets[context[h.contextTarget.key]]:h.target;if(target){if(current)historyStack.push({id:current,context:old});go(target,false)}else $('status').textContent=typeof h.action==='string'?h.action:'此操作需要系统或设备支持，原型不执行真实操作。'}
function go(id,record=true,direct=false){if(!direct)id=resolve(id);if(!byId[id])return;if(current&&record&&current!==id)historyStack.push({id:current,context:{...context}});current=id;Object.assign(context,(appState.enterContext||{})[id]||{});if(id==='A24'&&context.memoryFixture!=='existing'){context.memoryFixture='empty';context.memoryState='none';context.eventMemoryState='none'}const s=byId[id];$('screen').src=s.src;$('screen').alt=s.title;$('phone').style.maxWidth=s.width+'px';$('screenId').textContent=s.id+' · '+(s.group==='app'?'APP':'GAME');$('screenTitle').textContent=s.title;$('notes').textContent=s.note||s.description||'画面按钮演示页面跳转；使用左侧索引查看其他状态。';$('hits').replaceChildren();for(const h of s.hotspots||[]){const b=document.createElement('button');b.className='hit';b.setAttribute('aria-label',h.label||'进入下一页');b.title=h.label||'';Object.assign(b.style,{left:(h.x/s.width*100)+'%',top:(h.y/s.height*100)+'%',width:((h.w||h.width)/s.width*100)+'%',height:((h.h||h.height)/s.height*100)+'%'});b.disabled=!!h.disabled;b.onclick=()=>activate(h);$('hits').append(b)}$('events').replaceChildren();for(const e of s.events||[]){const b=document.createElement('button');b.textContent=e.label;b.onclick=()=>{activate(e);$('status').textContent='已模拟：'+e.label};$('events').append(b)}$('status').textContent='';renderList();}
function renderList(){const g=$('group').value;$('list').replaceChildren();for(const s of screens.filter(s=>g==='all'||s.group===g)){const b=document.createElement('button');b.textContent=s.id+' '+s.title;b.className=s.id===current?'active':'';b.onclick=()=>{historyStack=[];context={...defaults};if(['A01N','G01N'].includes(s.id))context.progress='new';if(s.id==='G01D')context.progress='direction';go(s.id,false,true)};$('list').append(b)}}$('back').onclick=()=>restorePrevious();$('reset').onclick=()=>{historyStack=[];context={...defaults};go(start,false,true)};$('hints').onchange=e=>$('phone').classList.toggle('hints',e.target.checked);$('group').onchange=renderList;go(start,false);
</script></html>'''.replace('__DATA__',DATA).replace('__APP_CONTEXT__',APP_CONTEXT).replace('__GAME_DEFAULTS__',GAME_DEFAULTS)
(R/'output/器灵_V1.4_全横屏可点击原型.html').write_text(page)
print('built',len(screens),'screens',len(page),'characters')
