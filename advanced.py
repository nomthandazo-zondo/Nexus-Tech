import re,json,uuid,datetime,itertools
from collections import defaultdict
from decimal import Decimal
from intent import train
FEE=1200 # cents per store; hypothetical consolidation fee

def cents(p): return int(Decimal(p['price_zar'])*100)
def money(n): return f'R{n/100:.2f}'
def signature(items): return tuple(sorted((p['id'],q) for p,q in items))
def quote(items):
 subt=defaultdict(int)
 for p,q in items: subt[p['store']]+=cents(p)*q
 return '\n'.join([*(f'{s}: {money(v)} + {money(FEE)} collection' for s,v in sorted(subt.items())),f'Product subtotal: {money(sum(subt.values()))}',f'Demo collection fees: {money(FEE*len(subt))}',f'Unified total: {money(sum(subt.values())+FEE*len(subt))}']),sum(subt.values())+FEE*len(subt)
def optimise(engine):
 items=engine.cart(); demand=defaultdict(int)
 for p,q in items: demand[p['name']]+=q
 stores=sorted({p['store'] for p in engine.products}); best=None
 for n in range(1,len(stores)+1):
  for subset in itertools.combinations(stores,n):
   plan=[]
   for name,q in demand.items():
    for p in sorted((p for p in engine.matches(name) if p['store'] in subset),key=cents):
     take=min(q,int(p['stock']))
     if take:plan.append((p,take));q-=take
     if not q:break
    if q:break
   else:
    cost=quote(plan)[1]
    if best is None or cost<best[0]:best=(cost,plan)
 return best

class Advanced:
 def __init__(self,engine):
  self.e=engine;self.model=train()[0];self.pending=None;self.last=None
 def checkout_preview(self):
  items=self.e.cart()
  if not items:return 'Your basket is empty.'
  self.pending=('checkout',signature(items),None)
  return 'DEMO CHECKOUT — no real payment\n'+quote(items)[0]+'\nType confirm checkout to place the demo order, or cancel.'
 def confirm(self,kind):
  p=self.pending;self.pending=None
  if not p or p[0]!=kind:return 'Please request a new '+kind+' preview first.'
  if signature(self.e.cart())!=p[1]:return 'Basket changed. Request a new preview.'
  if kind=='optimise':
   with self.e.conn:
    self.e.conn.execute('DELETE FROM cart');self.e.conn.executemany('INSERT INTO cart VALUES (?,?)',signature(p[2]))
   return 'Optimised basket applied.\n'+quote(self.e.cart())[0]
  return self.e.checkout()
 def act(self,s):
  e=self.e; low=s.lower().strip().rstrip('.!')
  if low=='confirm checkout':return self.confirm('checkout')
  if low in ('confirm optimise','confirm optimize'):return self.confirm('optimise')
  if low=='cancel':self.pending=None;return 'Pending action cancelled.'
  if self.pending:self.pending=None
  if re.fullmatch(r"(?:clear|empty) (?:my )?(?:cart|basket)",low):
   self.e.conn.execute("DELETE FROM cart");self.e.conn.commit();return "Basket cleared."
  if re.search(r'\b(?:optimise|optimize|consolidate)\b',low):intent='optimise'
  elif re.search(r'\b(?:checkout|check out|place order|order now|buy basket)\b',low):intent='checkout'
  else:
   probs=self.model.predict_proba([s])[0];i=probs.argmax();intent=self.model.classes_[i] if probs[i]>=.32 else 'other'
  if intent=='optimise':
   items=e.cart()
   if not items:return 'Add products first.'
   best=optimise(e)
   if not best:return 'No feasible basket in demo stock.'
   self.pending=('optimise',signature(items),best[1]);return 'Proposed basket (same product names and quantities):\n'+'\n'.join(f'{q} × {p["name"]} — {p["store"]}' for p,q in best[1])+'\n'+quote(best[1])[0]+f'\nSavings: {money(quote(items)[1]-best[0])}\nType confirm optimise to apply.'
  if intent=='checkout':return self.checkout_preview()
  # Explicit verbs have priority over statistical predictions. Never infer a mutation from a question or negation.
  if re.match(r'^(?:please )?(?:add|addd|put|buy|get me|i need|i want|i would like|grab|pop|throw|include|remove|remov|delete|take out|take away|drop)\b',low) or re.match(r'^can (?:you|i) (?:add|have|remove)\b',low):
   if re.search(r"\b(?:no|not|never|don't|dont|without|instead)\b",low):return 'Please specify the positive shopping action you want.'
   removing=bool(re.search(r'\b(remove|remov|delete|take out|take away|drop)\b',low)); parts=re.split(r'\s+(?:and|then)\s+|,\s*',s); replies=[]
   for part in parts:
    if re.search(r'\b(remove|delete|checkout|clear)\b',part,re.I) and not removing:return 'Please send different action types separately.'
    name=e.find(re.sub(r'\baddd\b','add',re.sub(r'\bremov\b','remove',part,flags=re.I),flags=re.I))
    if not name and re.search(r'\b(it|that|same)\b',part,re.I):name=self.last
    if not name:replies.append('Could not identify: '+part);continue
    self.last=name
    m=re.search(r'\b(\d+)\s+(?=[a-z])',part,re.I);words={'one':1,'two':2,'three':3,'four':4,'five':5}; w=re.search(r'\b(one|two|three|four|five)\b',part,re.I)
    qty=int(m.group(1)) if m else words[w.group(1).lower()] if w else 1
    if not 1<=qty<=99:replies.append('Quantity must be 1–99.');continue
    store=e.store(part);rows=e.matches(name,store)
    if removing:
     rows=[p for p,q in e.cart() if p['name']==name and (not store or p['store']==store)]
     replies.append(e.remove(rows[0]['id'],qty if m or w else None) if len(rows)==1 else 'Specify a unique product/store in your basket.')
    else:
     old=dict(signature(e.cart()));rows=[p for p in rows if int(p['stock'])-old.get(p['id'],0)>=qty];replies.append(e.add(rows[0]['id'],qty) if rows else 'Insufficient demo stock for '+name)
   return '\n'.join(replies)
  if intent in ('add','remove'):return 'Please confirm your intended action with add or remove followed by product and quantity.'
  if intent=='cart':return e.cart_text()
  if intent=='track':
   m=re.search(r'SS-[A-Z0-9]{8}',s,re.I);return e.track(m.group(0) if m else '')
  if intent=='compare':
   name=e.find(s) or (self.last if re.search(r'\b(it|that)\b',low) else None)
   if name:self.last=name;return e.compare(name)
  if intent=='budget':
   m=re.search(r'\bR\s*(\d+(?:\.\d+)?)',s,re.I);return e.budget(float(m.group(1))) if m else 'What is your budget in rand?'
  # Legacy read-only commands remain available; unsafe mutations are blocked.
  if re.search(r'\b(add|buy|put|remove|delete|clear|empty|checkout|order now|place order|i want|i need|get me)\b',low):return 'Please state a specific shopping action. No changes made.'
  if re.search(r"\b(?:hi|hello|hey|howzit|thanks|thank|help)\b",low):return e.legacy_local(s)
  if re.match(r"^(?:feedback|suggestion|suggest|developer feedback)\s*:",low):return e.feedback(s.split(":",1)[1])
  if intent=="browse" or re.match(r"^(?:browse|list|show|search|find)\b",low):
   name=e.find(s); term=name or next((c for c in {p["category"] for p in e.products} if c.lower() in low),"")
   return "DEMO CATALOG\n"+"\n".join(f'{p["id"]} | {p["name"]} | {p["store"]} | R{p["price_zar"]}' for p in e.browse(term,e.store(s)))
  return None
