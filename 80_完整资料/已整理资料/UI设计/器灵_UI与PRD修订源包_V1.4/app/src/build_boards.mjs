import fs from 'node:fs';import path from 'node:path';import{fileURLToPath}from'node:url';import{createRequire}from'node:module';const require=createRequire(import.meta.url);let sharp;try{sharp=require('sharp');}catch{sharp=createRequire('/opt/codex/runtimes/codex-primary-runtime/dependencies/node/package.json')('sharp');}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),C={bg:'#080D19',text:'#F4F3ED',mint:'#72E5DB',muted:'#93A3BC'};
const meta=JSON.parse(fs.readFileSync(root+'/screen_index.json'));const get=id=>meta.find(s=>s.id===id);const esc=s=>s.replaceAll('&','&amp;');
const t=(x,y,s,z=14,c=C.text,w=400)=>`<text x="${x}" y="${y}" fill="${c}" font-size="${z}" font-weight="${w}">${esc(s)}</text>`;
const groups=[
['01','陪伴、成长与收藏',['A01','A02','A03','A04']],
['02','第一次连接到真正认识',['A07','A08','A09','A10']],
['03','登录与横屏表单',['A35','A40','A37','A37K']],
['04','联网、命名与初次问候',['A38','A39','A11','A12']],
['05','读卡到获得',['A13','A14','A15','A17']],
['06','异常有出口，权益不消失',['A16','A18','A32','A36']],
['07','记忆只读查看与删除',['A19','A20','A21','A22']],
['08','删除需确认，完成看真实结果',['A22','A23','A24','A26']],
['09','我的器灵与隐私',['A05','A06','A33','A34']],
['10','读卡器灵与拥有者分开',['A14S','A15S','A17S','A04SU']],
['11','目标一致地把特性用起来',['A04S','A25S','A03SB','A32S']],
['12','偏好记忆也仅查看与删除',['A21','A22P','A24P','A26P']],
['13','成长、装饰与记忆，分别成立',['A03U','A02N','A19N','A19S']],
['14','只留下这一条，也能完整删除',['A19S','A23','A27S','A24']]
];
for(const[num,title,ids]of groups){let b=`<svg xmlns="http://www.w3.org/2000/svg" width="1824" height="1126" viewBox="0 0 1824 1126"><rect width="1824" height="1126" fill="${C.bg}"/><g font-family="Noto Sans CJK SC, sans-serif">${t(48,49,'器灵 / SPIRIT · LANDSCAPE UI',14,C.mint,600)}${t(48,94,title,30,C.text,700)}${t(48,128,'全流程844 × 390横屏 · 左侧共用导航 · 组件与异步状态保持一致',14,C.muted)}${t(1450,49,'V1.4 · 记忆只读 / 对话仅实体',12,C.muted)}`;ids.forEach((id,i)=>{let x=48+(i%2)*884,y=166+Math.floor(i/2)*453;let svg=fs.readFileSync(root+'/screens/'+id+'.svg','utf8').replace(/^<svg[^>]*>/,'').replace(/<\/svg>$/,'');b+=`<g transform="translate(${x} ${y})">${svg}</g>`+t(x,y+417,id+' · '+get(id).title.replace(' · 横屏',''),15,C.text,600);});b+=t(48,1094,'正常界面内不放研发标注。按钮、取消、键盘、失败与返回规范见 screens.md。',12,C.muted)+t(1680,1094,num+' / 14',12,C.mint,600)+'</g></svg>';fs.writeFileSync(root+'/boards/'+num+'.svg',b);await sharp(Buffer.from(b)).png().toFile(root+'/boards/'+num+'.png');}
console.log('14 landscape boards');
