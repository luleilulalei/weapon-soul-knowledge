import re,json
Q=lambda s:json.dumps(str(s),ensure_ascii=False)
def spans(s):
 out=[];depth=0;start=None;instr=False;esc=False
 for i,c in enumerate(s):
  if instr:
   if esc:esc=False
   elif c=='\\':esc=True
   elif c=='"':instr=False
  elif c=='"':instr=True
  elif c=='(':
   if depth==0:start=i
   depth+=1
  elif c==')':
   depth-=1
   if depth==0:out.append((start,i+1))
 return out

def children(s):
 a=s.index('(');z=s.rfind(')');inner=s[a+1:z];return [(x+a+1,y+a+1) for x,y in spans(inner)]
def head(s):return re.match(r'\(\s*([^\s()]+)',s).group(1)
def prop(s,key):
 m=re.search(r'\(property '+re.escape(Q(key))+r' ("(?:\\.|[^"\\])*")',s)
 return json.loads(m.group(1)) if m else ''
def setprop(s,key,value):
 value=Q(value)
 pat=r'(\(property '+re.escape(Q(key))+r' )"(?:\\.|[^"\\])*"'
 if re.search(pat,s):return re.sub(pat,lambda m:m[1]+value,s)
 return s[:-1]+'\n(property '+Q(key)+' '+value+' (at 0 0 0) (effects (font (size 1 1)) hide))\n)'
def symbol_name(s):return json.loads(re.match(r'\(symbol\s+("(?:\\.|[^"\\])*")',s)[1])
def rename(s,new):
 old=symbol_name(s);short=old.split(':')[-1]
 s=s.replace('(symbol '+Q(old),'(symbol '+Q(new),1)
 s=re.sub(r'\(symbol '+re.escape(Q(short))[0:-1]+r'(_\d+_\d+)"',lambda m:'(symbol '+Q(new.split(':')[-1]+m[1]),s)
 return s

def signature(s):
 s=rename(s,'MODEL')
 for a,b in reversed(children(s)):
  if head(s[a:b])=='property':s=s[:a]+s[b:]
 return re.sub(r'\s+',' ',s).strip()

