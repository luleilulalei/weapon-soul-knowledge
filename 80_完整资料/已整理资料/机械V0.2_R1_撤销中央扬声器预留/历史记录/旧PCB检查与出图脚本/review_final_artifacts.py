import json, math, shutil, base64, zipfile, datetime
from pathlib import Path
import review_manual_routes as r
from review_placement import P,check,BOARD,SPEAKER
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.units import mm
from xml.sax.saxutils import escape

OUT=Path('outputs/01a15a36-86c2-78c3-9a59-27c844dedc2e')
data=json.loads((OUT/'逐元件核查.json').read_text())
native=json.load(open('review-v072-native-check.json'))['value']
assert native['drc']==[]
errors,sh=check();assert not errors
assert not r.audit()
stamp=datetime.datetime.now().isoformat(timespec='seconds')
metrics={'checked_at':stamp,'project':'Spirit_V0.7.2_Manual_20261021','project_uuid':'e2c7376212b240cca1d4082976592cbf',
 'pcb_uuid':'5354a7bf4c630a18','components':len(P),'unique_skus_including_dnp':len(data['bom']),'fitted_components':136,'fitted_unique_skus':50,'dnp':['C114'],'pcb_native_drc':native['drc'],
 'same_side_overlap_and_through_hole_interference':errors,'geometric_copper_clearance_errors':[],
 'explicit_trace_segments':len(r.tracks),'vias':len(r.vias),'copper_layers':[1,15,16,2],
 'method':'Every trace follows explicitly chosen coordinates; no autorouter or route-search algorithm used.',
 'scope':'First routed prototype revision. Existing display pinout, NFC module availability, harnesses, thermal and signal measurements remain as documented.'}
(OUT/'检查结果.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
(OUT/'Spirit_V072.pcbdoc').write_text(native['source'])

fig,axes=plt.subplots(1,2,figsize=(9,14),facecolor='#F6F8FA')
for ax,layer in zip(axes,[1,2]):
    ax.fill(*BOARD.exterior.xy,color='#174535',alpha=.95)
    ax.fill([-17,17,17,-17],[134.5,134.5,141,141],color='#FADBD5',alpha=.6)
    if layer==1:ax.fill(*SPEAKER.exterior.xy,fc='#CFE2D2',alpha=.25)
    for t in r.tracks:
        if t['layer']!=layer:continue
        a,b=t['points'];ax.plot([a[0],b[0]],[a[1],b[1]],color='#BBDDD2',lw=max(.35,t['width']*3),alpha=.65)
    for v in r.vias:
        ax.add_patch(plt.Circle((v['x'],v['y']),v['diameter']/2,fc='#D4B56F',ec='none'))
        ax.add_patch(plt.Circle((v['x'],v['y']),v['hole']/2,fc='#123128',ec='none'))
    for ref,p in P.items():
        if p['layer']!=layer:continue
        poly=sh[ref]['body'];ax.fill(*poly.exterior.xy,fc='#19242D',ec='#E3EBE6',lw=.5,alpha=.85)
        ax.text(p['x'],p['y'],ref,color='white',fontsize=5.5,ha='center',va='center')
    for pad in r.PADALL:
        if pad['layer']not in [layer,12]:continue
        ax.fill(*pad['poly'].exterior.xy,fc='#D4B56F',ec='none')
    if layer==1:ax.text(0,80,'SPEAKER\n26 x 26 mm\nINSULATED SPACE',color='#D8EEE0',ha='center',fontsize=9)
    ax.text(0,138,'ANTENNA KEEP-OUT',ha='center',fontsize=8,color='#76291C')
    ax.set_aspect('equal');ax.set_xlim(-19,19);ax.set_ylim(33,144);ax.axis('off')
    ax.set_title('TOP' if layer==1 else 'BOTTOM (mirrored view)',fontsize=12,color='#1D3547')
    if layer==2:ax.invert_xaxis()
fig.suptitle('SPIRIT V0.7.2  |  Manual layout and routing  |  34 x 105 mm',fontsize=13,color='#1D3547',y=.97)
fig.savefig(OUT/'Spirit_V072_布局布线.png',dpi=200,bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,4,figsize=(15,13),facecolor='white')
palette={1:'#B22222',15:'#8459B6',16:'#BB8F00',2:'#176CB3'}
for ax,l in zip(axes,[1,15,16,2]):
    ax.plot(*BOARD.exterior.xy,color='#4D5660',lw=1)
    for p in r.PADALL:
        if p['layer']in[l,12]:ax.fill(*p['poly'].exterior.xy,color='#C0C6CD',alpha=.6)
    for t in r.tracks:
        if t['layer']==l:
            a,b=t['points'];ax.plot([a[0],b[0]],[a[1],b[1]],color=palette[l],lw=max(.3,t['width']*2),alpha=.8)
    for v in r.vias:ax.add_patch(plt.Circle((v['x'],v['y']),v['diameter']/2,fill=False,ec='#555F68',lw=.25))
    ax.set_xlim(-18,18);ax.set_ylim(35,142);ax.set_aspect('equal');ax.axis('off')
    ax.set_title({1:'L1 TOP',15:'L2 GND / local signals',16:'L3 3V3 / power / signals',2:'L4 BOTTOM'}[l],fontsize=10)
fig.suptitle('Explicit copper traces (poured copper omitted for clarity)',fontsize=13)
fig.savefig(OUT/'Spirit_V072_四层走线.png',dpi=180,bbox_inches='tight');plt.close(fig)

pdfmetrics.registerFont(TTFont('CNEmbedded','/System/Library/Fonts/STHeiti Light.ttc',subfontIndex=0))
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='CNTitle',fontName='CNEmbedded',fontSize=21,leading=28,textColor=colors.HexColor('#17324D'),spaceAfter=15))
styles.add(ParagraphStyle(name='CNHead',fontName='CNEmbedded',fontSize=13,leading=18,textColor=colors.HexColor('#17324D'),spaceBefore=12,spaceAfter=7))
styles.add(ParagraphStyle(name='CN',fontName='CNEmbedded',fontSize=10,leading=16,spaceAfter=7))
styles.add(ParagraphStyle(name='CNSmall',fontName='CNEmbedded',fontSize=8.5,leading=12,spaceAfter=5))
story=[]
def p(t,style='CN'):return Paragraph(escape(t).replace('\n','<br/>'),styles[style])
def add(t,style='CN'):story.append(p(t,style))
def tbl(rows,widths):
    t=Table([[p(str(x),'CNSmall')for x in row]for row in rows],colWidths=[v*mm for v in widths],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E4ECF3')),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#A5B3C0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),4),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F6F8FA')])]))
    story.append(t)
add('器灵 V0.7.2\n原理图复核与手动布局布线','CNTitle')
add('2026-10-21 · Spirit_V0.7.2_Manual_20261021')
add('已完成一版四层 PCB 手动布局布线。原工程保留，新版使用独立工程。全程未调用自动布线、外部布线器或路径搜索功能；脚本只转录已确定的线段和进行几何检查。')
tbl([['检查项目','结果'],['PCB原生DRC','0错误；含连通、间距、差分线长和网表一致性'],['独立元件几何检查','137个元件；同面重叠和跨面穿孔干涉0项'],['网络连接复核','0个未连通网络；最终铺铜以原生DRC结果为准'],['料号与明细','137个位号；默认装136件/50种料号，C114不装'],['板框与层数','34×105mm，4层；顶部天线槽与全层禁铜区'],['走线记录',f'{len(r.tracks)}条明确线段、{len(r.vias)}个过孔；EDA保存时可能合并/拆分线段']],[54,120])
add('本版主要修正','CNHead')
for text in [
 'ESP32-S3放在上端背面，天线朝板顶开槽区；USB和屏幕接口靠近主控，充电与DC-DC集中在下部。正面中央为外置扬声器保留26×26mm空间。',
 '原理图与PCB重新逐件同步：清理旧器件、更新12针FPC屏幕座，补齐屏幕电源磁珠和去耦，背光串阻R39统一为10Ω/1206。',
 'CAP1296固定地址0x28与原RFID2冲突，NFC接口改为3.3V PN532候选方案，7位地址0x24。GPIO18注释与实际IMU中断一致。',
 '修正USB定位孔铜间距、过孔孔距、局部器件间距和3.3V分割铜区；USB两段差分对均通过现有10mil长度差规则。']:add(text)
add('仍需明确的实物条件','CNHead')
add('GC9A01屏幕按“用户已有、不采购”处理；当前保留12针定义，但缺少手头屏幕完整型号/排线图，不能把驱动芯片型号当作插接兼容证明。NFC候选现货未确认，已从购买数量中排除。电池、开关与连接线必须按本报告引脚表匹配。')
story.append(PageBreak())
add('布局与布线预览','CNTitle')
add('底面图按从底面观察镜像显示；元件重叠检查使用实际封装边界与穿孔范围。图中的外置扬声器需要绝缘固定与声腔。','CNSmall')
story.append(Image(str(OUT/'Spirit_V072_布局布线.png'),width=153*mm,height=231*mm))
story.append(PageBreak())
add('电气检查重点','CNTitle')
tbl([['电路','核查结论及样机条件'],
 ['主控与总线','ESP32-S3 N16R8的PSRAM相关GPIO35/36/37保持NC。3.3V逻辑。BMI270 0x69、CAP1296 0x28、TCA9534 0x20、DRV2605L 0x5A、PN532候选0x24无重复。'],
 ['单节电池充电','BQ24075，输入限流1.18kΩ，充电设定1kΩ，典型约0.89A、上界约0.985A。电池必须有保护并带真实10kΩ NTC，额定充电能力覆盖此值。壳内充电温升需实测。'],
 ['Type-C输入','TUSB320LAI使用内部Rd，默认100mA，检测到≥1.5A电流广告才选高限流。USB检测域由TLV75533供电。需验证插拔、Rp变化和上电次序。'],
 ['3.3V与5V','TPS63802采用470nH与560kΩ/100kΩ反馈。TPS61023采用1µH与732kΩ/100kΩ反馈；220pF前馈C114默认不装。电感/MLCC按实际最低电池电压、纹波、峰值和温升验证。'],
 ['音频','MAX98357A的5V BTL输出匹配8Ω/2W扬声器，两个输出均不得接地。从低音量启动，检查5V跌落、啸叫和温升。'],
 ['LRA触觉','DRV2605L设LRA模式，额定1.2Vrms，所选马达REV02为240±10Hz，交流最大1.25Vrms、90mArms。固定后执行自动校准，并限制持续振动时间。'],
 ['USB与射频','差分线长检查通过；此结果不等于90Ω阻抗认证，打样叠层和实测波形尚需验证。天线禁铜与结构净空要延续到外壳、屏幕金属和电池装配。']
 ],[32,142])
add('屏幕连接定义','CNHead')
tbl([['J8引脚','网络'],['1 / 5 / 6 / 12','GND'],['2 / 3','LCD_LEDK / LCD_LEDA'],['4','LCD_VCC（3.3V经磁珠）'],['7 / 8 / 9 / 10 / 11','DC / CS / SCK / MOSI / RST_N'],['13 / 14','连接器固定脚接GND']],[45,129])
add('背光R39为10Ω/250mW；100mA时耗散0.1W。上电前仍需根据手头屏幕的LED串并联方式、允许电流和接触面确认。','CNSmall')
story.append(PageBreak())
add('外置器件与接线','CNTitle')
tbl([['器件','立创选型','采购结果'],
 ['LRA','LD0825BC-0169F\nC5632412','1件价￥9.16，实时页面库存18。8×2.55mm、1.2Vrms。'],
 ['扬声器','20MM-8Ω2W-JFHM\nC50387209','1件价￥4.41，实时页面库存33。直径20mm，高5.1mm。'],
 ['NFC','Grove NFC 113020006\n历史料号C445568','PN532，3.3V，25.43×20.35mm加独立天线。合适候选，商城现货未确认，暂不下单。'],
 ['GC9A01屏幕','用户已有','不购买。备查商城型号与无货/停售状态保存在工作簿。']
 ],[27,65,82])
add('库存与价格为2026-10-21页面快照，不锁库存；未下单、未付款。马达与扬声器均需另配与板座相匹配的线束。','CNSmall')
cn=json.load(open('review-v072-netlist.json'))['components']
byref={c['props']['Designator']:c for c in cn.values()}
rows=[['接口','引脚网络']]
for ref in ['J3','J110','J104','J111','J201']:
    rows.append([ref,'；'.join(f'{k}: {v.get("net") or "固定脚/NC"}'for k,v in byref[ref]['pinInfoMap'].items())])
tbl(rows,[27,147])
add('NFC使用条件','CNHead')
add('Grove NFC默认UART，需要改为I2C模式；J201线序为1SCL、2SDA、3V3、4GND，不能仅根据Grove外形或现成线色直插。PN532采用0x24七位地址，固件用轮询方式处理就绪状态。天线应贴近非金属壳面并离开电池与扬声器磁体。')
add('没有用55×40mm的MH1612S开发板替代：它超过当前34mm板宽，并且默认SPI、地址/复位接口适配未闭合。也没有用裸PN532芯片料号冒充模块。')
add('资料入口','CNHead')
for label,url in [
 ('马达商城','https://item.szlcsc.com/6552539.html'),
 ('马达原厂REV02','https://atta.szlcsc.com/upload/public/pdf/source/20231116/6E8E24E2DD0A6A3BF17BC9D10915D8C6.pdf'),
 ('扬声器商城','https://item.szlcsc.com/53008592.html'),
 ('Grove NFC原厂说明','https://wiki.seeedstudio.com/Grove_NFC/'),
 ('DRV2605L原厂手册','https://www.ti.com/lit/ds/symlink/drv2605l.pdf')]:
    story.append(Paragraph(f'{label}：<link href="{url}" color="#1A5B9A">{label}链接</link>',styles['CNSmall']))
add('交付文件','CNHead')
add('工程epro2可导入嘉立创EDA专业版。Gerber为这一版样机制造资料，未下单。采购工作簿包含51种板载料号（含不装项）、137条逐件核查及外设选型。默认采购136件/50种料号，C114为DNP。原始规则检查与布局、布线图一并保存。')
def footer(canvas,doc):
    canvas.setFont('CNEmbedded',8);canvas.setFillColor(colors.HexColor('#607080'))
    canvas.drawString(18*mm,12*mm,'器灵 V0.7.2 · 2026-10-21 · 手动布局布线样机版')
    canvas.drawRightString(192*mm,12*mm,str(doc.page))
SimpleDocTemplate(str(OUT/'Spirit_V072_设计检查报告.pdf'),pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=16*mm,bottomMargin=20*mm).build(story,onFirstPage=footer,onLaterPages=footer)
print('Generated report and routing views')
