from run import call,O
import json,sys
plans=json.loads((O/'silkscreen_plan.json').read_text());boards=json.loads((O/'after_layout.json').read_text())['boards']
for name in sys.argv[1:] or ['main','power','blade']:
 uuid=boards[name]['uuid'];guard='if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='+json.dumps(uuid)+')throw Error("Wrong board");'
 call('await __v081Open('+json.dumps(uuid)+');'+guard+'return true;')
 labels=plans[name]['labels']
 for n in range(0,len(labels),20):
  code=guard
  for p in labels[n:n+20]:
   prop={k:p[k] for k in ['rotation','fontSize','layer','mirror']};prop.update(x=p['x']/.0254,y=p['y']/.0254,lineWidth=4,primitiveLock=False)
   if p['kind']=='ATTR':prop.update(valueVisible=True,keyVisible=False)
   cls='Attribute' if p['kind']=='ATTR' else 'String'
   code+='if(!await eda.pcb_Primitive'+cls+'.modify('+json.dumps(p['id'])+','+json.dumps(prop)+'))throw Error("Label update failed");'
  code+='await new Promise(r=>setTimeout(r,2500));return true;';call(code);print(name,'labels',min(n+20,len(labels)),'/',len(labels),flush=True)
 code=guard
 for pid,p in plans[name]['texts'].items():code+='if(!await eda.pcb_PrimitiveString.modify('+json.dumps(pid)+','+json.dumps(p)+'))throw Error("Version update failed");'
 code+='await new Promise(r=>setTimeout(r,3000));if(!await eda.pcb_Document.save())throw Error("Save failed");return {source:await eda.sys_FileManager.getDocumentSource(),drc:await eda.pcb_Drc.check(true,false,true)};'
 d=call(code);(O/(name+'_silkscreen_check.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));print(name,'DRC',[(v['name'],v.get('count'))for v in d['drc']],flush=True)
