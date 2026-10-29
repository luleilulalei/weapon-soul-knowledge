from pathlib import Path
import json,hashlib,html,zipfile,shutil,csv
O=Path('output/mechanical_v04');R=O/'model'
v=json.load(open(O/'verification/geometry.json'));st=json.load(open(O/'verification/stl_independent.json'));ops=v['operation_checks']
assert not v['collisions'] and not ops['cap_collisions'] and not any(x['collisions']for x in ops['nominal_axial_sweep'])
assert ops['wrong_orientation_stop_volume_mm3']>.02 and ops['overtravel_half_mm_stop_volume_mm3']>.02
assert all(x['components']==1 and not x['bad_edges']for x in v['mesh'])
assert len(st)==16 and all(x['connected_components']==1 and not x['boundary_or_nonmanifold_edges']and abs(x['minimum_z_mm'])<.001 for x in st)
assert hashlib.sha256((R/'Spirit_V04_V074P3B_review.blend').read_bytes()).hexdigest()==v['native_model_sha256']
manifest=json.load(open(O/'source_manifest.json'));assert hashlib.sha256(Path(manifest['pcb_snapshot']).read_bytes()).hexdigest()==manifest['sha256']
parts=[('P01','前壳','更新','板边避让、肩部加宽、对接导向与固定孔'),('P02','后壳','更新','匹配四耳主板、托架固定点与定位销'),('P03','四孔主板托架','更新','38 × 61.5 孔距；上部托架固定点移至总装 Y=162'),('P04','可换屏幕压框','沿用','实屏外形待量测，保留独立更换'),('P05','屏幕后压环','沿用','配软垫夹持，不用螺丝压玻璃'),('P06','POWER 推杆','沿用','RESET / BOOT 位于内部'),('P07','电池托架','沿用','Ø19.1 × 69.2 电池包占位，配绑带'),('P08','侧面扬声器声腔','沿用','Ø20 × 5.1 扬声器包络'),('P09','扬声器格栅','沿用','侧出声、软垫密封待试装'),('P10','背部 NFC 托架','沿用','独立天线面向后壳'),('P11','顶部防尘盖','更新','使用顶部同组固定孔；与 P15 二选一'),('P12','LRA 压条','沿用','Ø8.2 × 2.7 占位，胶层需实配'),('P13','麦克风侧向导音件','沿用','对准 U5，密封垫和声学待测'),('P14','尺寸试片','沿用','不装入整机，先核对孔径和板厚配合'),('P15','韩下六针适配板导向壳','更新','导向、防反插、肩部止挡、双螺丝固定、轴向调节槽'),('P16','0.3 mm 高度调节垫片','新增','需要时打印两件同厚垫片，实配后重查插针高度')]
with (O/'分件清单.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.writer(f);w.writerow(['编号','名称','变化','说明','STL'])
 for p,n,c,t in parts:w.writerow([p,n,c,t,next(x['file']for x in st if x['file'].startswith(p))])
readme=f'''器灵内核 · 机械 V0.4 结构试装稿
2026-10-26｜基于主板 V074P3B + 适配板 V0.2

入口
打开“结构评审.html”查看整机、爆炸图、PCB托架、六针对接和内部布局。
model/stl/ 是 16 个独立分件（毫米）；P14 是试片，P16 按需打印两件；P11 防尘盖与 P15 配件导向壳二选一。
model/Spirit_V04_V074P3B_review.blend 是可编辑的 Blender 网格装配源文件，包含电子包络与检查空间。不是 STEP 实体 CAD。
Spirit_V04_assembly_VIEW_ONLY.stl 是带 P15 的装配位置预览，不能作为整件打印；不包含电子件。

本轮完成
1. 四个 PCB 固定柱更新到原生孔中心（±19,85）和（±19,146.5），孔距 38×61.5，孔径 2.2。映射到总装为（±19,112.5）和（±19,174），主板底 Z=0、顶 Z=1.6。
2. 重做 P03 框架与 P02 支撑。主板仍使用 M2 尼龙螺丝、尼龙垫圈/螺母和塑料柱；托架的上部合壳固定点从 Y=172.5 移到 162，避开 PCB 新上孔及其螺母。
3. 顶部局部宽度由 46 增至 51；主体仍长 190、最大宽 62、前后厚 40、握持区宽 46。按板框增加 0.35 mm 装配避让，保留右侧 USB、左侧 FPC 与线束插接预留。
4. 删除旧 Mill-Max 插合结构，按当前韩下 J7 母座 / J701 公头重做 P15。两块板平行、从端部插合；外壳先导向，带非对称键、肩部止挡和两颗轴向固定螺丝。固定孔位 X=±14.3、Z=7.1，使用 M2.5 样机螺丝，塑料孔需试片/攻丝确认。P11 改用同组孔。没有把插针当作结构锁扣。
5. 按已保存的 V074P3B 原生数据更新主板 129 件和适配板 16 件的坐标、面别、板框及孔位，纳入背面 U105/电源器件、通孔焊尾和主板/适配板螺丝头、垫圈、螺母包络。保留屏幕正面、NFC背面、电池下置、扬声器侧出声、LRA与导音件布局。

接口装配基准（暂定，供实物试配）
主板顶边总装 Y=179；母座口约 Y=181.8。
适配板本地 Y=0 映射到总装 Y=184.3；板边间距 5.3，公针前端约 Y=179.3，暂定插入 2.5。两板底 Z 都为 0。
P15 鼻端 Y=177，比公针尖端前伸约 2.3。非对称键先导向；肩部限位在 Y=190。
板固定槽可沿轴调整约 ±0.6；P16 提供 0.3 高度垫片。调整后必须重新核对完整插合与针序，不能把调节范围当作已验证的容差。
上述插深、同平面安装高度和孔槽间隙是结构设计值，并非厂家整套对插认证；按连接器实物修正后再冻结。J7/J701 采用简化主体/插针/焊尾，弯脚完整形状尚未建成厂家 STEP。
J7→J701 对应为 1→5、2→6、3→3、4→4、5→1、6→2。沿用板级断电插拔与逐针确认要求。

尺寸
主体 190×62×40（长×宽×厚）。
所建模型含防尘盖、按钮等外形约 191.9×62×41.8；含 P15 时约 219×62×41.8。
这两个包络不包含尚未选定的外露紧固件头、真实引线及外接剑身/其他附件；以最终实物总装为准。

检查结果与范围
16/16 个二进制 STL 独立核验：每件封闭、单体连通、体积为正、最低点在打印平面。
静态检查 {v['pairs_checked']} 组几何对：报告干涉 0（布尔相交体积报告阈值 0.02 mm³）。安装状态结构件均单体连通。检查包含壳体、托架、电子包络、螺丝包络及所建插接空间。
防尘盖替换状态报告干涉 0；沿轴退出 1、2、3、5、8、12、16 mm 的离散位置均无报告干涉。是离散位置检查，不是连续运动/公差认证。
错误翻转方向在距最终位置 5 mm 处已被键挡住（插针尖端尚距母座口约 2.5）；超插 0.5 mm 时肩部产生实体阻挡。这只验证几何设计意图，不验证塑料件在受力下的变形或失效。
所有电子高度并非厂家 STEP 或实物逐项确认；C114 不贴装位仍保留保守空间。数字检查不覆盖真实屏幕/FPC、全部线束弯折、打印收缩、射频、声音、温升、跌落与挥动载荷。

建议试装顺序
先打印 P14，再打印 P03、P11/P15 与需要的 P16；核对 PCB 孔距、两组连接器实物和固定件。
确认后打印前后壳。先装电池托架/绑带、主板托架，再装主板；先插 FPC 与线束，再固定屏幕压框/软垫、按键、麦克风导音件及 LRA。NFC 托架装在后盖，留拆盖线长。
主板固定的建模参考为 M2 尼龙螺丝约 12 mm、Ø4.8×0.5 垫圈及 1.6 厚螺母；这是空间包络，购买前核对实际规格和有效啮合。其余固定件按孔径和实物叠厚确定，不用过长螺丝顶到电池、屏幕或 PCB。
分件虽已摆到打印平面，壳内悬空台阶、导音通道及导向壳仍需在切片中选择支撑或调整方向。
本包用于静态试装和结构评审；连接器落板高度、屏幕/FPC、线束和强度验证完成前，不作为整机定型或挥动承力验收。

来源与保留
PCB输入为 2026-10-25 保存的 V074P3B 原生回读，原生工程文件为 Spirit_V074P3B_Prototype_Review_20261025.epro2。本轮没有修改PCB或旧机械版本。
source_manifest.json 记录来源 SHA256；model/pcb_input.json 与 adapter_input.json 记录结构输入及高度来源，verification/ 保存检查结果。
'''
(O/'00_结构试装说明.txt').write_text(readme)
refs=O/'references';refs.mkdir(exist_ok=True)
for name in ['C46061744.pdf','C32713227-drawing.pdf']:shutil.copyfile(Path('output/horizontal_connector_v01')/name,refs/name)
figs=[('01_core.png','整机 · 保留现有比例','主视图采用实际网格；金棕色件同样按塑料建模。屏幕表情为渲染示意。'),('02_exploded.png','三组展开 · 前壳 / 主板 / 后壳','为便于阅读，沿横向分开展示；顶部适配组件向上移开。'),('03_board_carrier.png','四耳主板与新托架','外侧四孔匹配 38×61.5；托架与后壳的固定孔另行布置，避开 PCB 螺丝。'),('04_interface.png','当前韩下六针对接','导向壳向右移开以显示插针。模型中插深暂定 2.5，实际落板高度/插深仍待试配。'),('05_open_rear.png','后盖拆开后的内部','为看清主板、电池与声腔，隐藏后盖、NFC托架和电池托架。'),('06_head.png','顶部装配','非对称导向、止挡肩和独立固定孔。仅验证名义几何，未验证载荷。'),('07_datums.png','尺寸与坐标','PCB 外形和 XY 坐标来自最新保存的原生工程；完整参数见模型输入。')]
rows=''.join(f'<tr><td>{p}</td><td>{n}</td><td>{c}</td><td>{t}</td><td><a href="model/stl/{next(x["file"]for x in st if x["file"].startswith(p))}">STL</a></td></tr>'for p,n,c,t in parts)
sections=''.join(f'<section><h2>{t}</h2><p>{desc}</p><a href="renders/{im}"><img src="renders/{im}" alt="{t}" loading="lazy"></a></section>'for im,t,desc in figs)
page=f'''<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>器灵内核 · V0.4 结构评审</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#eef3f6;color:#173443;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{max-width:1140px;margin:auto;padding:48px 30px}}header{{padding:30px 0}}.tag{{color:#2a817e;letter-spacing:2px;font-size:13px}}h1{{font-size:42px;line-height:1.3;margin:16px 0}}h2{{font-size:25px;margin:0 0 12px}}p{{color:#4e6572}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card{{background:#fff;border:1px solid #d8e3e8;border-radius:12px;padding:20px}}strong{{display:block;font-size:28px;color:#123c4c}}section{{padding:28px;background:white;border-radius:16px;margin:24px 0}}img{{width:100%;display:block;border-radius:10px}}section:first-of-type img{{max-height:820px;object-fit:contain;background:#3d4953}}a{{color:#106e79}}nav a{{display:inline-block;margin:6px 14px 6px 0}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px 8px;border-bottom:1px solid #dbe5eb;text-align:left}}.note{{border-left:4px solid #b38b4a;padding:14px 20px;background:#fcf6ec}}details{{margin:20px 0}}pre{{white-space:pre-wrap;font:14px/1.8 inherit}}@media(max-width:700px){{main{{padding:24px 16px}}h1{{font-size:32px}}.cards{{grid-template-columns:1fr}}section{{padding:18px}}table{{font-size:12px}}}}</style><main><header><div class="tag">器灵内核 / MECHANICAL V0.4 / 2026.10.26</div><h1>让现有 PCB 装进最新结构</h1><p>适配 V074P3B 主板 + V0.2 适配板。更新四耳托架、顶部六针对接件与板边避让，保留屏幕、NFC、电池和侧出声布局。</p><nav><a href="00_结构试装说明.txt">完整试装说明</a><a href="model/Spirit_V04_V074P3B_review.blend">Blender 装配源文件</a><a href="Spirit_V04_assembly_VIEW_ONLY.stl">总装预览 STL</a><a href="分件清单.csv">分件清单</a></nav></header><div class="cards"><div class="card"><strong>38 × 61.5</strong>主板四孔中心距 / mm</div><div class="card"><strong>16 个分件</strong>独立 STL 封闭、连通检查通过</div><div class="card"><strong>190 × 62 × 40</strong>主体长 × 宽 × 厚 / mm</div></div><p class="note">结构试装稿：已建模型的静态相交、防尘盖替换状态与 7 个插拔采样位置均无报告干涉。屏幕/FPC、连接器真实落板高度、线束、打印公差与强度仍需实物验证。</p>{sections}<section><h2>分件与下载</h2><p>P11 防尘盖与 P15 配件导向壳二选一；P14 是试片，P16 在实配需要时打印两件。</p><table><tr><th>编号</th><th>名称</th><th>变化</th><th>说明</th><th>文件</th></tr>{rows}</table></section><section><h2>检查记录</h2><p>静态 {v['pairs_checked']} 组几何对，报告干涉 0，报告阈值 0.02 mm³。16 个实际二进制 STL 全部通过独立网格检查。反插与超插模型中均出现预期机械阻挡，尚未做实体载荷测试。</p><nav><a href="verification/geometry.json">装配与插拔检查</a><a href="verification/stl_independent.json">STL 独立检查</a><a href="source_manifest.json">PCB 来源记录</a><a href="references/C46061744.pdf">母座厂家图</a><a href="references/C32713227-drawing.pdf">公头厂家图</a></nav><details><summary>展开完整试装说明</summary><pre>{html.escape(readme)}</pre></details></section></main></html>'''
(O/'结构评审.html').write_text(page)
files=[O/'00_结构试装说明.txt',O/'结构评审.html',O/'分件清单.csv',O/'source_manifest.json',O/'Spirit_V04_assembly_VIEW_ONLY.stl']
files += [p for p in R.rglob('*')if p.is_file()and not p.name.endswith('.blend1')]
files += list((O/'verification').glob('*.json'))+list((O/'renders').glob('*.png'))+list(refs.glob('*.pdf'))
assert all((O/'renders'/name).is_file()for name,_,_ in figs)
checks=[{'path':str(p.relative_to(O)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in files]
(O/'交付校验.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));files.append(O/'交付校验.json')
Z=O/'器灵内核_机械V0.4_结构试装包_20261026.zip'
with zipfile.ZipFile(Z,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for p in files:z.write(p,'器灵内核_机械V0.4/'+str(p.relative_to(O)))
with zipfile.ZipFile(Z)as z:assert z.testzip()is None
print(json.dumps({'zip':str(Z),'files':len(files),'zip_bytes':Z.stat().st_size,'fit_pairs':v['pairs_checked'],'static_collisions':len(v['collisions']),'stl_files':len(st),'source_unchanged':True},ensure_ascii=False))
