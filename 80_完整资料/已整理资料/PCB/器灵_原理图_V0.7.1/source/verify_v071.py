from pathlib import Path
import json,xml.etree.ElementTree as ET
B=Path(__file__).resolve().parent.parent
old={c['ref']:c for c in json.loads((B/'source/baseline_v07/combined_design.json').read_text())['components']}
new={c['ref']:c for c in json.loads((B/'source/combined_design.json').read_text())['components']}
add=set(new)-set(old);remove=set(old)-set(new);changed={r for r in new.keys()&old.keys() if new[r]!=old[r]}
assert not add and remove=={'JP1'},(add,remove)
assert changed=={'Q1','R11','#FLG07'},changed
xml=ET.parse(B/'validation/Spirit.xml').getroot();comps={c.get('ref'):c for c in xml.findall('./components/comp')};physical={r:c for r,c in new.items() if not r.startswith('#')}
assert set(comps)==set(physical)
nodes={};netnodes={}
for n in xml.findall('./nets/net'):
 name=n.get('name');netnodes[name]=set()
 for node in n.findall('node'):
  k=node.get('ref'),node.get('pin');assert k not in nodes;nodes[k]=name;netnodes[name].add(k)
for ref,c in physical.items():
 assert comps[ref].findtext('value')==c['value'],(ref,'value')
 assert (comps[ref].findtext('footprint') or '')==c.get('footprint',''),(ref,'footprint')
 for pin,expected in c['pins'].items():
  actual=nodes.get((ref,pin),'')
  assert (actual==expected if expected is not None else actual=='' or actual.startswith('unconnected-')),(ref,pin,expected,actual)
assert 'MIC_FEED' not in netnodes
assert nodes['Q1','2']==nodes['R11','1']=='+3V3'
for r in ['U9','U10','U5','U105','M1','J8','DS1','R117','R118','U103','LS1']:assert new[r]==old[r],r
assert {'M1','LS1','DS1'}=={r for r,c in physical.items() if c.get('offboard')}
assert sorted(r for r,c in physical.items() if c.get('dnp'))==['C110','C114']
for ref,c in physical.items():
 fp=c.get('footprint')
 if fp:
  ns,name=fp.split(':');assert (B/'project/candidate_footprints'/f'{ns}.pretty'/f'{name}.kicad_mod').exists(),(ref,fp)
erc=json.loads((B/'validation/erc.json').read_text());assert not [v for s in erc['sheets'] for v in s['violations']]
changed_sheets=[]
for p in (B/'project').glob('*.kicad_sch'):
 baseline=(B/'source/baseline_v07/project'/p.name).read_text()
 if p.read_text()!=baseline:changed_sheets.append(p.name)
assert set(changed_sheets)=={'Spirit.kicad_sch','07_Microphone_Power.kicad_sch','20_ERC_Power_Assumptions.kicad_sch'},changed_sheets
report={'result':'PASS','revision':'V0.7.1','physical_or_logical_entries':len(physical),'offboard_components':['M1','LS1','DS1'],'pcb_or_harness_candidate_entries':len(physical)-3,'virtual_ERC_flags':len(new)-len(physical),'pins':sum(len(c['pins']) for c in physical.values()),'connected_pins':sum(v is not None for c in physical.values() for v in c['pins'].values()),'intentional_NC':sum(v is None for c in physical.values() for v in c['pins'].values()),'added_refs':sorted(add),'removed_refs':sorted(remove),'changed_refs':sorted(changed),'exported_pin_nets_match_source':True,'assigned_footprint_files_present':True,'ERC_violations':0,'changed_sheets':changed_sheets,'all_other_electrical_pinmaps_unchanged':True,'scope':'Structural checks only. No PCB routing/assembled test/final native JLC qualification.'}
(B/'validation/validation_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
