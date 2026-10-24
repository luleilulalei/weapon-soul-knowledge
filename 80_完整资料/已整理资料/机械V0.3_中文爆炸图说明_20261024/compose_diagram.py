from pathlib import Path
import json,base64,html
R=Path(__file__).resolve().parent;A=json.loads((R/'anchors.json').read_text());W,H=3200,2250
s=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<style>text{font-family:"PingFang SC","Heiti SC",STHeiti,"Noto Sans CJK SC",sans-serif;fill:#223944} .muted{fill:#65757b} .tag{fill:#0b706e;font-weight:600}</style>', '<rect width="3200" height="2250" fill="#f3f5f4"/>']
def text(x,y,t,size=30,color=None,weight=None,anchor=None):
 attrs=f' font-size="{size}"'+(f' fill="{color}" style="fill:{color}"'if color else'')+(f' font-weight="{weight}"'if weight else'')+(f' text-anchor="{anchor}"'if anchor else'')
 s.append(f'<text x="{x}" y="{y}"{attrs}>{html.escape(t)}</text>')
text(90,105,'器灵  /  机械 V0.3 爆炸图',64,weight=600)
text(93,163,'基于 V074H PCB · 屏幕在前，NFC 朝后 · 装配关系说明',33,'#65757b')
text(3100,100,'主体 190 × 62 × 40 mm',34,anchor='end')
text(3100,151,'结构评审稿  /  2026.10.24',27,'#65757b',anchor='end')
s.append('<path d="M90 204 H3110" stroke="#cad4d7" stroke-width="2"/>')
for x,t in [(390,'A  屏幕与按键'),(1000,'B  前壳内侧'),(1650,'C  主板与支架'),(2240,'D  背部外设'),(2840,'E  后壳内侧')]:text(x,273,t,38,weight=600,anchor='middle')
img=base64.b64encode((R/'exploded_native.png').read_bytes()).decode()
s.append(f'<image x="100" y="310" width="3000" height="1600" xlink:href="data:image/png;base64,{img}"/>')
# Caption leaders are generated from projected native object positions; component mesh is not redrawn.
def label(key,title,x,y,w,anchor_override=None):
 ax,ay=anchor_override if anchor_override else(A[key][0]+100,A[key][1]+310)
 bx=x if ax<x else x+w if ax>x+w else min(max(ax,x+16),x+w-16)
 by=y+26
 if y<ay and x<ax<x+w:by=y+52
 if y>ay and x<ax<x+w:by=y
 midx=(ax+bx)/2
 s.append(f'<path d="M{ax:.1f} {ay:.1f} L{midx:.1f} {ay:.1f} L{bx:.1f} {by:.1f}" fill="none" stroke="#497d7c" stroke-width="2.6"/>')
 s.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="5" fill="#0b706e"/>')
 s.append(f'<rect x="{x}" y="{y}" width="{w}" height="52" rx="10" fill="#fbfcfa" stroke="#bfcfcd" stroke-width="1.6"/>')
 s.append(f'<rect x="{x}" y="{y}" width="61" height="52" rx="10" fill="#0b706e"/>')
 text(x+30.5,y+36,key,27,'#ffffff',600,'middle');text(x+74,y+36,title,29)
label('A1','电源键推杆',420,635,238)
label('A2','屏幕＋外压框',465,855,266)
label('A3','屏幕后压环',465,1200,238)
label('B3','麦克风导音件',1170,875,266)
label('B2','LRA 马达＋压条',1190,1305,298)
label('C0','接口防尘盖',1700,407,238)
label('C1','剑身接口 J7',1240,580,250)
label('C2','V074H 主板',1230,760,250)
label('C3','四孔固定支架',1695,1095,266)
label('C4','ESP32-S3 · 天线朝下',1265,1200,365)
label('D1','NFC 控制板',2375,655,245)
label('D2','NFC 天线',2375,853,217)
text(2385,951,'向后壳一侧扫描 →',27,'#0b706e')
label('D4','电池＋独立托架',2370,1550,298)
# The speaker grille, speaker body and chamber follow the literal left-to-right mesh order.
s.append('<path d="M1710 1585 V1625 H2100 V1585" fill="none" stroke="#497d7c" stroke-width="2.6"/>')
text(1905,1680,'D5  格栅 → 扬声器 → 声腔',29,'#0b706e',anchor='middle')
text(1010,1860,'B1  前壳（翻面展示内部）',30,anchor='middle')
text(2840,1860,'E1  后壳 / 固定柱',30,anchor='middle')
text(2235,1070,'D3  NFC 托架',27,'#65757b',anchor='middle')
# Explicitly separate conceptual display spacing from the actual insertion trajectory.
s.append('<rect x="90" y="1940" width="3020" height="228" rx="18" fill="#e5eeec"/>')
text(125,1995,'装配顺序',33,'#0b706e',600)
text(330,1995,'支架与外设 → 固定主板 → 接排线与线束 → 安装屏幕、按键、导音件 → 合壳',33)
text(125,2052,'读图：按装配层次横向展开；前壳已翻面，后压环和扬声器另外拉开。展开距离不是实际拆卸行程。',29)
text(125,2103,'边界：电子件为尺寸包络；未绘制排线、线束和紧固件。屏幕/FPC、NFC 实物配合与整机受力仍待验证。',29)
text(125,2147,'P14 尺寸试片不参与总装。金棕色零件同样为塑料结构件。顶部防尘盖不代表功能剑身接头。',26,'#65757b')
text(95,2211,'原生模型：Spirit_V03_V074H_review.blend  ·  本图未改变已交付 STL 或 PCB',25,'#65757b')
text(3100,2211,'器灵  /  EXPLODED ASSEMBLY  01',25,'#65757b',anchor='end')
s.append('</svg>');(R/'器灵_V03_中文爆炸图.svg').write_text('\n'.join(s))
