from engine import *
import importlib,sys,collections
name=sys.argv[1];b=importlib.import_module(name).b;es=b.audit();filt=sys.argv[2:]
print(name,'errors',len(es))
if not filt:
 c=collections.Counter()
 for e in es:
  for n in set([e.get('an'),e.get('bn')]):
   if n:c[n]+=1
 print(c)
else:
 for e in es:
  if not any(v in str(e)for v in filt):continue
  print(e)
  for k in ['a','b']:
   a=e.get(k,'')
   if a.startswith('T'):i=int(a.split()[0][1:]);print(' ',i,b.tracks[i])
