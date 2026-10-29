from pathlib import Path
import json,hashlib,zipfile,shutil,html
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import unquote,urlparse
from engine import parse_source,Board,LineString,Point,MM
O=Path(__file__).resolve().parent;D=O/'delivery';pv=json.loads((O/'project_verification.json').read_text());mv=json.loads((O/'manufacturing_connectivity.json').read_text())
assert all(not v['errors']for v in pv.values())
assert all(not v['uncovered_pad_via_anchors']and not v['cross_net_copper_islands']and not v['split_nets']for v in mv.values())
original='修改前_当前V080E完整备份.epro2';final='V081_最终复核完成.epro2'
for f in [original,final]:
 z=zipfile.ZipFile(O/f);assert z.testzip()is None;shutil.copy2(O/f,D/f)
assert hashlib.sha256((D/original).read_bytes()).hexdigest()=='49f539b081d475914c4f7a96e79c7de5d0e9947a67981b0d8647b6b7e727c021'
z=zipfile.ZipFile(D/final);embedded=parse_source(z.read(next(n for n in z.namelist()if n.endswith('.epru'))).decode());docs={};current=None
for header,body in embedded:
 if header['type']=='DOCHEAD':current=body['uuid'];docs[current]=[]
 if current is not None:docs[current].append((header,body))
types={'LINE','VIA','POUR','COMPONENT','PAD','PAD_NET','ATTR','STRING','FILL','POLY','REGION'};backup_checks={}
def shape(rs):
 result={}
 for h,a in rs:
  if h['type']not in types:continue
  a=a.copy()
  if h['type']=='COMPONENT':a['angle']=a['angle']%360
  result[(h['type'],h.get('id'))]=a
 return result
for name,v in pv.items():
 snap=json.loads((O/(name+'_final_snapshot.json')).read_text());actual=shape(parse_source(snap['source']));saved=shape(docs[v['uuid']]);redundant=[];model=Board(name)
 for k in list(saved.keys()-actual.keys()):
  a=saved[k];assert k[0]=='LINE',k
  g=LineString([(a['startX']*MM,a['startY']*MM),(a['endX']*MM,a['endY']*MM)]);assert g.length<.003,(name,k,g.length)
  pg=g.buffer(a['width']*MM/2);covers=any(p['net']==a['netName']and p['layer']in[a['layerId'],12]and p['poly'].buffer(.0001).covers(pg)for p in model.pads.values())
  for kk,aa in actual.items():
   if kk[0]=='LINE'and aa.get('netName')==a['netName']and aa.get('layerId')==a['layerId']:
    gg=LineString([(aa['startX']*MM,aa['startY']*MM),(aa['endX']*MM,aa['endY']*MM)]).buffer(aa['width']*MM/2+.0001);covers=covers or gg.covers(pg)
   if kk[0]=='VIA'and aa.get('netName')==a['netName']:
    # Tiny stale line fragments produced by native save/reload may be wholly inside an unchanged via land.
    x=aa.get('centerX',aa.get('x'));y=aa.get('centerY',aa.get('y'));d=aa.get('diameter',aa.get('viaDiameter'))
    if x is not None and y is not None and d is not None:covers=covers or Point(x*MM,y*MM).buffer(d*MM/2+.0001).covers(pg)
  assert covers,(name,k,'uncovered extra copper');redundant.append(k[1]);saved.pop(k)
 assert saved==actual,name+' backup differs from final snapshot'
 backup_checks[name]={'physical_content_matches':True,'angle_normalized':True,'redundant_sub_3micron_segments_inside_same_net_pad_via_or_track':redundant}
(D/'backup_verification.json').write_text(json.dumps(backup_checks,ensure_ascii=False,indent=2))
for f in ['project_verification.json','manufacturing_connectivity.json','bottom_silk_correction.json']:shutil.copy2(O/f,D/f)
names={'main':'主板','power':'电源板','blade':'小刀板'};sizes={'main':'40 × 50 mm · 4 层','power':'38 × 48 mm · 4 层','blade':'20 × 32 mm · 2 层'}
rows=''.join(f'<tr><td>{names[n]}</td><td>{sizes[n]}</td><td>{v["component_count"]}</td><td>{v["relocated_components"]}</td><td>0</td><td>0 / 0</td></tr>'for n,v in pv.items())
modules=[
 ('NFC · WS1850T','重排 L201、C206–C209、C213、C214、R201、R202，使发射匹配、接收支路和晶体负载电容更便于短距离连接；补齐芯片与匹配电容的接地回路。','射频及晶体连接在底面完成；天线接口 J202 的位置保留。'),
 ('屏幕 / 背光','整理 MCU 源端串阻与 FPC 引出通道，调整 Q2、C29、C30、R37–R39、FB202 附近布局。','SPI 主通路 10mil，细间距连接器处 5mil 引出；屏幕供电、复位和背光均已连通。'),
 ('功放 · MAX98357A','调整 U4、C13/C14 和控制电阻，使供电电容、扬声器输出与功放引脚靠近。','I²S 与控制线路完成；扬声器输出主段 20mil，细引脚处保留短引出。'),
 ('MIC / PDM','整理 C15、C16、R26，靠近麦克风的供电和时钟连接点。','PDM 时钟、数据、电源及接地全部完成，麦克风器件位置保留。'),
 ('触摸 / IMU / 马达 / 配件','调整 CAP1296 及其周边和局部去耦，整理 I²C、复位、触摸与配件接口的通道。','完成传感器、马达驱动、配件供电、按键与调试测试点连接。'),
 ('电源板','调整 TPS63802、TPS61023 周边电感、电容和反馈网络，整理 BQ24075 充电与开关控制区域；解决 R113 周边器件间的占位重叠。','主电流路径采用 20/30mil 及铺铜；供电、充电、开关、Type-C 与板间接口完成。'),
 ('USB','完成保护器件、接口和板间连接线路，补偿电源板 D+ 的长度。','主板及电源板均通过现有 USB 对内长度差 ≤10mil 的原生检查。'),
 ('小刀板','调整去耦位置并旋转 R703，让电平转换器到 LED 接口的走向更直接。','MCU、I²C、调试、电平转换、负载开关和 LED 供电全部连通；过孔最小外径/孔径为 0.5/0.3mm。'),
 ('丝印','重新安排随布局移动的元件编号、测试点标识和版本号；依据底面 Gerber 实图修正原有镜像方向。','版本统一为 V081；元件编号位于实际装配面，底面文字从实物背面可正常阅读。')]
module_rows=''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>'for x in row)+'</tr>'for row in modules)
figures=''.join(f'<article><h3>{names[n]} <small>{sizes[n]}</small></h3><div class="pair">'+''.join(f'<figure><a href="{n}_{side}.png"><img src="{n}_{side}.png" alt="{names[n]}{label}生产文件预览"></a><figcaption>{label}</figcaption></figure>'for side,label in [('top','顶面'),('bottom','底面（从背面观察）')])+'</div></article>'for n in names)
gerbers=' · '.join(f'<a href="{n}_V081_Gerber.zip">{names[n]} Gerber</a>'for n in names)
date=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>器灵 V081｜布局与布线完成记录</title><style>
body{{margin:0;background:#eef2ef;color:#18342b;font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{max-width:1120px;margin:auto;padding:40px 24px 70px}}h1{{font-size:34px;margin:6px 0 16px}}h2{{font-size:24px;margin:38px 0 16px}}h3{{font-size:20px;margin:0 0 16px}}small,.sub{{color:#61776b;font-weight:400}}a{{color:#146d52;text-decoration:none;border-bottom:1px solid #9dbdad}}.hero,article,.box{{background:white;border-radius:16px;padding:26px;margin:20px 0;box-shadow:0 5px 25px #163e2610}}.badge{{display:inline-block;background:#d6eddf;color:#165d3c;padding:6px 14px;border-radius:20px;font-weight:600}}table{{width:100%;border-collapse:collapse;font-size:15px}}td,th{{padding:13px 12px;text-align:left;border-bottom:1px solid #dbe4de;vertical-align:top}}th{{background:#e5eee8}}.scroll{{overflow-x:auto}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}figure{{margin:0}}img{{width:100%;border-radius:10px;display:block}}figcaption{{text-align:center;padding-top:8px;color:#61776b}}.module td:first-child{{min-width:120px;font-weight:600}}.fine{{font-size:14px;color:#61776b}}@media(max-width:700px){{main{{padding:24px 12px}}.hero,article,.box{{padding:18px}}h1{{font-size:28px}}.pair{{gap:8px}}td,th{{padding:10px 8px}}}}</style><main>
<div class="hero"><span class="badge">三板布线完成 · 原生 DRC 0 错误</span><h1>器灵 V081<br>布局与布线完成记录</h1><p>先保存了修改前的完整工程，再逐模块调整布局、手工指定线路走向并完成三块 PCB。保存重开后通过立创原生检查，并对导出的 Gerber 铜层独立检查连通性。</p><p><a href="{final}">打开最终工程备份</a> · <a href="{original}">修改前 V080E 完整备份</a></p><p>{gerbers}</p><p class="fine">完成记录：{date}。原在线工程名称保留，板上版本标识为 V081。</p></div>
<h2>检查结果</h2><div class="box scroll"><table><thead><tr><th>PCB</th><th>尺寸 / 层数</th><th>元件数</th><th>调整位置或朝向</th><th>原生 DRC 错误</th><th>Gerber 断网 / 短接</th></tr></thead><tbody>{rows}</tbody></table><p>信号线仅用 <b>5mil 与 10mil</b>：5mil 用于引脚引出和局部细间距区域，普通通路采用 10mil。电源、地和扬声器等承载电流的主通路采用 20/30mil，并结合铺铜及过孔连接。</p><p>核对结果：元件清单与型号、引脚网络、测试点网络、板框、安装孔、天线禁布区和原有制造规则均保持一致；元件占位无重叠。主板与电源板的内层包含局部走线，地铜已验证连通，并非完全无分割的整面地层。</p><p class="fine"><a href="project_verification.json">原生工程核对记录</a> · <a href="manufacturing_connectivity.json">生产铜层连通核对记录</a></p></div>
<h2>逐模块调整</h2><div class="box scroll"><table class="module"><thead><tr><th>模块</th><th>布局处理</th><th>完成结果</th></tr></thead><tbody>{module_rows}</tbody></table></div>
<h2>生产文件预览</h2><p class="sub">图像由本包 Gerber 的铜层、阻焊开窗、丝印和钻孔生成，为裸板示意。底面已按实物背面视角翻转；点击图片可放大。</p>{figures}
<div class="box"><p>本轮已完成布局、布线与文件连通验证。NFC 天线匹配和读卡距离、音频底噪、电源温升等性能仍需首板实测；现有 USB 等长检查不等同于阻抗场求解。生产文件尚未提交下单。</p><p class="fine">工程修改使用 easyeda-api-skill 与官方 lceda-pro 工作流；未使用自动布线。完整文件校验值见 SHA256SUMS.txt。</p></div></main></html>'''
(D/'V081_完成记录.html').write_text(page)
class Links(HTMLParser):
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ['src','href']and not urlparse(v).scheme:assert(D/unquote(v)).exists(),v
Links().feed(page)
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(D.iterdir())if p.is_file()and p.name!='SHA256SUMS.txt'}
(D/'SHA256SUMS.txt').write_text('\n'.join(v['sha256']+'  '+n for n,v in manifest.items())+'\n');(O/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
bundle=O/'器灵_V081_布局布线完成_交付包.zip'
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED)as z:
 for p in sorted(D.iterdir()):
  if p.is_file():z.write(p,'器灵_V081/'+p.name)
assert zipfile.ZipFile(bundle).testzip()is None
print('delivery complete',len(manifest)+1,'files',bundle.stat().st_size,'bytes')
