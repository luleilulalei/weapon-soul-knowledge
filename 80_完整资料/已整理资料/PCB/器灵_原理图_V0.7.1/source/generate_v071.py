from pathlib import Path
import copy,json,re,uuid,shutil,csv
from sexpr_utils import children,head,prop,setprop,Q
B=Path(__file__).resolve().parent.parent;OLD=B/'source/baseline_v07';OUT=B/'project'
if OUT.exists():shutil.rmtree(OUT)
shutil.copytree(OLD/'project',OUT)
design=json.loads((OLD/'combined_design.json').read_text());cs=design['components'];before=copy.deepcopy(cs);by={c['ref']:c for c in cs}
rows=json.loads((OLD/'catalog_mapping.json').read_text());mr={r['Reference']:r for r in rows}
cs.remove(by['JP1']);rows.remove(mr['JP1']);del by['JP1'];del mr['JP1']
for ref in ['Q1','R11']:
 by[ref]['pins']={k:('+3V3' if v=='MIC_FEED' else v) for k,v in by[ref]['pins'].items()}
 by[ref]['notes']='V0.7.1移除台架JP1，将原MIC_FEED并入+3V3：Q1源极与R11上拉直接接主逻辑电源。保留Q1开关及U9/U10时钟/数据断电隔离。关麦仍需验证实际电压、电流及信号反灌，不以删除跳线替代隐私测试。';mr[ref]['Risk_Notes']=by[ref]['notes']
old='ASSUMPTION: JP1 closed AND Q1 ON; MIC bus isolated when off';new='ASSUMPTION: Q1 ON; source directly on +3V3; MIC bus isolated when off'
for k,v in by['#FLG07'].items():
 if isinstance(v,str):by['#FLG07'][k]=v.replace(old,new)
for k,v in mr['#FLG07'].items():
 if isinstance(v,str):mr['#FLG07'][k]=v.replace(old,new)
# Remove exactly JP1 instance, its two wires/two labels and old localstatus text.
p=OUT/'07_Microphone_Power.kicad_sch';s=p.read_text();removeids={'3ea0cbbd-5849-58b1-926b-e0f673d11445','197a68ea-f710-5c7d-90ee-cb025e9cb7eb','0d955d7a-f355-56c6-ae5b-e91dc14d7f98','cff00363-c5b9-531e-8287-4646d7581b48','cfbc3190-522c-5451-acac-ad08d10f3100','1c719ac6-e578-5f7b-a422-0dc9b1929ffd'}
removed=[]
for a,b in reversed(children(s)):
 v=s[a:b]
 if any('(uuid '+Q(u)+')' in v for u in removeids):removed.append(v);s=s[:a]+s[b:]
 elif re.match(r'\(symbol\s+\(lib_id',v) and prop(v,'Reference') in ['Q1','R11']:
  ref=prop(v,'Reference');s=s[:a]+setprop(setprop(v,'Design_Notes',by[ref]['notes']),'Catalog_Notes',mr[ref]['Risk_Notes'])+s[b:]
assert len(removed)==6,len(removed)
s=s.replace('"MIC_FEED"','"+3V3"').replace('JP1 闭合且 Q1 导通才有 MIC_3V3。','Q1源极直接接+3V3，导通后才有MIC_3V3。').replace('JP1 是台架隔离跳线，不是产品用户开关。','台架跳线已移除；Q1、U9、U10继续保留。').replace('JP1: 1=+3V3; 2=MIC_FEED; ','Q1源极/R11上拉：+3V3直供。')
s=s.replace('V0.3','V0.7.1')
p.write_text(s)
p=OUT/'20_ERC_Power_Assumptions.kicad_sch';s=p.read_text().replace('V0.3','V0.7.1').replace(old,new).replace('#FLG07 MIC_3V3：JP1 闭合且 Q1 导通；','#FLG07 MIC_3V3：Q1导通，源极直供+3V3；');p.write_text(s)
p=OUT/'Spirit.kicad_sch';s=p.read_text().replace('V0.7','V0.7.1');note='V0.7.1：仅移除JP1并直供Q1源极；保留Q1与U9/U10，屏/LRA/I2C附件/充电电气不变。';s=s[:s.rfind(')')]+f'(text {Q(note)} (at 22.86 306 0) (effects (font (face "Noto Sans CJK SC") (size 1.4 1.4)) (justify left top)) (uuid "1a0eb705-2dd8-4e1f-a356-c7162d03af60"))\n)\n';p.write_text(s)
(B/'source/combined_design.json').write_text(json.dumps(design,ensure_ascii=False,indent=2)+'\n');(B/'catalog_mapping.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
with (B/'BOM_JLC_映射_V0.7.1.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0])+['Assembly_Location']);w.writeheader()
 for r in rows:
  if not r['Reference'].startswith('#'):w.writerow({**r,'Assembly_Location':'ENCLOSURE_OFFBOARD_NOT_PCB' if by[r['Reference']].get('offboard') else 'PCB_OR_HARNESS_CANDIDATE'})
ob={c['ref']:c for c in before};new={c['ref']:c for c in cs};ledger={'revision':'V0.7.1','scope':'Only delete JP1 and merge MIC_FEED into +3V3, Q1/R11 direct feed; U9/U10 retained.','removed_components':{k:ob[k] for k in ob.keys()-new.keys()},'added_components':{k:new[k] for k in new.keys()-ob.keys()},'changed_components':{k:{'before':ob[k],'after':new[k]} for k in ob.keys()&new.keys() if ob[k]!=new[k]},'changed_sheets':[p.name for p in OUT.glob('*.kicad_sch') if p.read_bytes()!=(OLD/'project'/p.name).read_bytes()]};(B/'source/intended_diff_v071.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n');print('Generated',len(cs)-8,'nonvirtual components')
