"""ShopSmart AI: offline desktop shopping prototype with optional local Ollama."""
import csv, json, re, sqlite3, threading, queue, difflib, uuid, datetime
from pathlib import Path
try:
 import tkinter as tk
 from tkinter import ttk, messagebox
except ImportError:
 tk = ttk = messagebox = None
import requests
from auth import Accounts
from advanced import Advanced, quote, signature

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
DB=ROOT/'data'/'shopsmart.db'
STORES=['Shoprite','SPAR','Woolworths','Boxer','Pick n Pay','Checkers']
ALIAS={'pnp':'Pick n Pay','pick n pay':'Pick n Pay','picknpay':'Pick n Pay','pick and pay':'Pick n Pay','woolies':'Woolworths','woolworth':'Woolworths','spar':'SPAR','shoprite':'Shoprite','boxer':'Boxer','checkers':'Checkers'}

class Engine:
 def __init__(self, user_id):
  self.db_path=DB.parent / f"customer_{int(user_id)}.db"
  self.conn=sqlite3.connect(self.db_path,check_same_thread=False)
  self.conn.executescript('''CREATE TABLE IF NOT EXISTS cart (product_id TEXT PRIMARY KEY, qty INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, created TEXT, status TEXT, total REAL, details TEXT); CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, message TEXT);''')
  self.conn.commit()
  with (ROOT/'data'/'products_source_200.csv').open(encoding='utf-8-sig',newline='') as f:
   self.products=list(csv.DictReader(f))
  # The supplied 200-record CSV is the ONLY product catalog.
  for p in self.products:
   p['price_zar']=p['price']
   p['size']=''  # Size, when available, is already part of the product name.
  if len(self.products)!=200:raise ValueError('Expected 200 product records in products_source_200.csv')
  self.byid={p['id']:p for p in self.products}
  self.names=sorted({p['name'] for p in self.products})
  self.advanced=Advanced(self)
 def find(self,phrase):
  """Resolve IDs, full product names, partial names and common misspellings."""
  s=phrase.lower().strip()
  for p in self.products:
   if p['id'].lower()==s or re.search(r'(?<!\w)'+re.escape(p['id'].lower())+r'(?!\w)',s):return p['name']
  for n in sorted(self.names,key=len,reverse=True):
   if n.lower() in s:return n
  cleaned=re.sub(r'\b(add|remove|delete|buy|put|some|the|please|i|want|need|a|an|of|to|my|cart|basket|price|compare|find|show|me|cheapest|how|much|is|for|from|at|store|units|unit|pack|packs|item|items|can|you|would|like|give|get|and|in|do|have)\b',' ',s)
  for a in sorted(ALIAS,key=len,reverse=True):cleaned=re.sub(r'(?<!\w)'+re.escape(a)+r'(?!\w)',' ',cleaned)
  cleaned=re.sub(r'\b(?:r\s*)?\d+(?:\.\d+)?\b',' ',cleaned)
  cleaned=re.sub(r'[^a-z ]',' ',cleaned)
  cleaned=' '.join(cleaned.split())
  if not cleaned:return None
  # Prefer whole-word and word-prefix matches over guessing an unrelated product.
  tokens=cleaned.split()
  ranked=[]
  for name in self.names:
   target=name.lower();target_tokens=re.findall(r'[a-z]+',target)
   token_score=sum(max((difflib.SequenceMatcher(None,t,w).ratio() for w in target_tokens),default=0) for t in tokens)/len(tokens)
   exact=sum(1 for t in tokens if t in target_tokens)
   score=max(difflib.SequenceMatcher(None,cleaned,target).ratio(),token_score*.91)+exact*.06
   ranked.append((score,name))
  score,name=max(ranked)
  return name if score>=.65 else None
 def store(self,s):
  for a,store in sorted(ALIAS.items(),key=lambda x:-len(x[0])):
   if re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',s.lower()):return store
  return None
 def matches(self,name,store=None):
  return sorted([p for p in self.products if p['name']==name and (not store or p['store']==store)],key=lambda p:(int(p['stock'])<=0,float(p['price_zar'])))
 def browse(self,term='',store=None):
  out=[p for p in self.products if (not term or term.lower() in (p['name']+' '+p['category']).lower()) and (not store or p['store']==store)]
  return out[:35]
 def cart(self):
  rows=self.conn.execute('SELECT product_id,qty FROM cart').fetchall()
  return [(self.byid[pid],qty) for pid,qty in rows if pid in self.byid]
 def add(self,pid,qty=1):
  if pid not in self.byid:return 'Unknown product ID.'
  qty=max(1,min(99,int(qty)));p=self.byid[pid]
  old=self.conn.execute('SELECT qty FROM cart WHERE product_id=?',(pid,)).fetchone()
  new=(old[0] if old else 0)+qty
  if new>int(p['stock']):return 'Not enough demonstration stock for that quantity.'
  self.conn.execute('INSERT INTO cart VALUES (?,?) ON CONFLICT(product_id) DO UPDATE SET qty=excluded.qty',(pid,new));self.conn.commit()
  return f'Added {qty} × {p["name"]} from {p["store"]} at R{p["price_zar"]} each.'
 def remove(self,pid,qty=None):
  old=self.conn.execute('SELECT qty FROM cart WHERE product_id=?',(pid,)).fetchone()
  if not old:return 'That product is not in your basket.'
  if qty is None or qty>=old[0]:self.conn.execute('DELETE FROM cart WHERE product_id=?',(pid,))
  else:self.conn.execute('UPDATE cart SET qty=? WHERE product_id=?',(old[0]-qty,pid))
  self.conn.commit();return 'Updated basket.'
 def cart_text(self):
  items=self.cart()
  if not items:return 'Your basket is empty. Try: add 2 milk.'
  lines=[f'{p["id"]} | {qty} × {p["name"]} | {p["store"]} | R{qty*float(p["price_zar"]):.2f}' for p,qty in items]
  total=sum(q*float(p['price_zar']) for p,q in items)
  return 'YOUR MULTI-STORE BASKET\n'+'\n'.join(lines)+f'\nTotal (demo product prices only): R{total:.2f}\nDelivery and fees not included.'
 def checkout(self):
  items=self.cart()
  if not items:return 'Your basket is empty.'
  if any(q>int(p['stock']) for p,q in items):return 'Insufficient demonstration stock.'
  summary,total_cents=quote(items);total=total_cents/100
  oid='SS-'+uuid.uuid4().hex[:8].upper()
  details=json.dumps([{'id':p['id'],'name':p['name'],'store':p['store'],'qty':q,'price':p['price_zar']} for p,q in items])
  receipt=ROOT/'data'/'receipts'/f'{oid}.txt';receipt.parent.mkdir(exist_ok=True)
  with self.conn:
   self.conn.execute('INSERT INTO orders VALUES (?,?,?,?,?)',(oid,datetime.datetime.now().isoformat(timespec='seconds'),'Demo order created',total,details))
   self.conn.execute('DELETE FROM cart')
  text=f'DEMO order {oid} — no real payment\n'+summary+'\n'+ '\n'.join(f'{q} × {p["name"]} / {p["store"]}' for p,q in items)
  try:receipt.write_text(text,encoding='utf8')
  except OSError:return text+'\nReceipt file could not be saved; order is recorded.'
  return text+'\nReceipt: '+str(receipt)
 def track(self,oid=''):
  if oid:
   r=self.conn.execute('SELECT order_id,created,status,total FROM orders WHERE order_id=?',(oid.upper(),)).fetchone()
   return f'{r[0]} | {r[2]} | R{r[3]:.2f} | {r[1]}' if r else 'Order ID not found in this local demo.'
  rows=self.conn.execute('SELECT order_id,created,status,total FROM orders ORDER BY created DESC LIMIT 8').fetchall()
  return '\n'.join(f'{r[0]} | {r[2]} | R{r[3]:.2f}' for r in rows) if rows else 'No demonstration orders yet.'
 def feedback(self,s):
  if not s.strip():return 'Please write a suggestion.'
  self.conn.execute('INSERT INTO feedback(created,message) VALUES (?,?)',(datetime.datetime.now().isoformat(timespec='seconds'),s.strip()))
  self.conn.commit();return 'Thank you! Your suggestion was saved locally for the developers in your local customer database.'
 def compare(self,name):
  rows=self.matches(name)
  if not rows:return 'I could not identify that product. Try browsing the catalog.'
  return 'DEMO PRICE COMPARISON — '+name+'\n'+'\n'.join(f'{p["store"]}: R{p["price_zar"]} ({p["size"]}) [{p["id"]}]' for p in rows)+'\nIllustrative prices, not live quotes.'
 def budget(self,amount):
  if amount<=0:return 'Please enter a positive budget.'
  essentials=['Maize Meal 5kg','Rice 2kg','Bread White 700g','Milk 2L','Eggs 18 Pack','Chicken 1kg','Potatoes 2kg','Onions 1kg','Baked Beans 410g','Pasta 500g','Bananas 1kg','Cooking Oil 2L']
  options=[self.matches(n)[0] for n in essentials if self.matches(n)]
  chosen=[];remaining=amount
  for p in options:
   price=float(p['price_zar'])
   if price<=remaining+1e-8:chosen.append(p);remaining-=price
  if not chosen:return f'R{amount:.2f} is below the cheapest suggested essential in this demo. Try browsing individual items.'
  return f'DEMO BUDGET BASKET (R{amount:.2f})\n'+'\n'.join(f'{p["name"]} — {p["store"]} R{p["price_zar"]} [{p["id"]}]' for p in chosen)+f'\nEstimated total: R{amount-remaining:.2f}; remaining R{remaining:.2f}.\nThese are examples, not nutritional plans or live prices. Ask to add an item.'
 def local(self,s):
  return self.advanced.act(s)
 def legacy_local(self,s):
  raw=s.strip();low=raw.lower()
  if not raw:return 'Please type a message.'
  if re.search(r'\b(hi|hello|hey|howzit|heyy|helo|hii)\b',low) and len(low.split())<6:return 'Hi! 👋 Welcome to ShopSmart AI. I can compare prices, find groceries, recommend a basket for your budget, and manage demo orders. What are you shopping for?'
  if re.search(r'\b(thank|thanks|thx)\b',low):return 'You’re welcome! What else can I help you find?'
  if re.search(r'\b(help|what can you do|features)\b',low):return 'Try: compare milk; add 2 milk from Boxer; show cart; remove milk; groceries under R300; browse dairy; place demo order; track orders; suggest: please add more products.'
  if re.search(r'\b(clear|empty)\b.*\b(cart|basket)\b',low):
   self.conn.execute('DELETE FROM cart');self.conn.commit();return 'Basket cleared.'
  if re.search(r'\b(cart|basket)\b',low) and re.search(r'\b(show|view|what|total|check|display)\b',low):return self.cart_text()
  if re.search(r'\b(checkout|place order|order now|buy basket)\b',low):return self.checkout()
  if re.search(r'\b(track|orders|order status)\b',low):
   m=re.search(r'SS-[A-Z0-9]{8}',raw,re.I);return self.track(m.group(0) if m else '')
  if re.match(r'^(feedback|suggestion|suggest|developer feedback)\s*:',low):return self.feedback(raw.split(':',1)[1])
  if re.search(r'\b(budget|under|afford|recommend|suggest groceries|meal plan)\b',low):
   m=re.search(r'(?:R\s*)?(\d+(?:\.\d{1,2})?)',raw,re.I)
   if m:return self.budget(float(m.group(1)))
   return 'What is your budget in rand? For example: recommend groceries for R350.'
  if re.search(r'\b(remove|delete|take out)\b',low):
   name=self.find(raw)
   if not name:return 'Which product should I remove? You can also select a row in the basket.'
   entries=[(p,q) for p,q in self.cart() if p['name']==name]
   store=self.store(raw)
   if store:entries=[(p,q) for p,q in entries if p['store']==store]
   if len(entries)>1:return 'Several stores have this item in your basket. Specify the store or select the basket row.'
   if not entries:return 'That product is not in your basket.'
   m=re.search(r'\b(?:remove|delete)\s+(\d+)\b',low)
   return self.remove(entries[0][0]['id'],int(m.group(1)) if m else None)
  if re.search(r'\b(add|put|buy|get me|i need|i want|i would like|can you add)\b',low):
   name=self.find(raw)
   if not name:return 'I could not identify the product. Try browsing or asking for a comparison.'
   matches=self.matches(name,self.store(raw))
   if not matches:return 'No matching item found for that store.'
   m=re.search(r'\b(?:add|put|buy|get me|need|want)\s+(\d+)\b',low)
   return self.add(matches[0]['id'],int(m.group(1)) if m else 1)
  if re.search(r'\b(compare|price|prices|cheapest|cost|how much)\b',low):
   name=self.find(raw)
   return self.compare(name) if name else 'Which product should I compare? Example: compare rice.'
  if re.search(r'\b(browse|list|show|search|find|looking for)\b',low):
   store=self.store(raw);name=self.find(raw)
   term=name if name else next((c for c in ['Dairy','Produce','Staples','Meat','Household','Bakery','Breakfast','Personal care','Frozen','Beverages'] if c.lower() in low),'')
   rows=self.browse(term,store)
   if not rows:return 'No products found. Try another category or name.'
   return 'DEMO CATALOG\n'+'\n'.join(f'{p["id"]} | {p["name"]} | {p["store"]} | R{p["price_zar"]}' for p in rows)+'\nShowing up to 35 results.'
  return None
 def ollama(self,s,history):
  # Ground the language model in a small, relevant catalog slice; never let it invent an executed action.
  name=self.find(s);store=self.store(s)
  matches=self.matches(name,store) if name else []
  catalog='\n'.join(f'{p["id"]} {p["name"]} {p["store"]} R{p["price_zar"]}' for p in matches[:8]) or 'No product matched this message.'
  system=('You are ShopSmart AI, a friendly South African desktop grocery shopping assistant. Slogan: One Basket, Multiple Stores, Better Living. '
   'Understand informal English, typos, and imperfect grammar. Be concise (1-4 sentences). '
   'The catalog is the 200-row products_source_200.csv, containing demo data, NOT live prices. Do not invent product prices, stock, order status, retailer integrations or completed actions. '
   'For shopping actions instruct users to say: add 2 milk; remove milk; compare rice; browse dairy; show cart; recommend groceries for R300; place demo order; track orders; suggestion: text. '
   'If asked about real orders/payments, explain this is a local prototype. Relevant verified demo catalog:\n'+catalog)
  messages=[{'role':'system','content':system}]+history[-6:]+[{'role':'user','content':s}]
  r=requests.post(CFG['ollama_url'].rstrip('/')+'/api/chat',json={'model':CFG['model'],'messages':messages,'stream':False,'options':{'temperature':0.25,'num_predict':130,'num_ctx':2048}},timeout=CFG.get('timeout_seconds',35))
  r.raise_for_status();return r.json()['message']['content'].strip()

class App:
 def __init__(self,root,user,on_logout,dark=True):
  self.user=user;self.on_logout=on_logout;self.active=True;self.root=root;root.title('ShopSmart AI | One Basket, Multiple Stores, Better Living');root.geometry('1180x760');root.minsize(850,570)
  self.engine=Engine(user[0]);self.dark=dark;self.history=[];self.q=queue.Queue();self.busy=False
  self.theme();self.layout();self.write('ShopSmart AI','Welcome! 🛒 Shop across six stores using demonstration catalog data. Try “compare milk”, “add 2 rice”, or “recommend groceries for R400”.');self.root.after(120,self.poll)
 def theme(self):
  self.bg='#101827' if self.dark else '#f3f7fb';self.panel='#1b293b' if self.dark else '#ffffff';self.fg='#eef5ff' if self.dark else '#182a3b';self.muted='#a6b8cb' if self.dark else '#536477';self.accent='#1cb99b';self.root.configure(bg=self.bg)
  style=ttk.Style();style.theme_use('clam');style.configure('Treeview',background=self.panel,fieldbackground=self.panel,foreground=self.fg,rowheight=27,borderwidth=0);style.configure('Treeview.Heading',background=self.accent,foreground='#071b22',font=('Segoe UI',10,'bold'));style.map('Treeview',background=[('selected','#137f7b')],foreground=[('selected','#ffffff')]);style.configure('TCombobox',padding=5)
 def button(self,parent,text,command,secondary=False):
  return tk.Button(parent,text=text,command=command,bg=self.panel if secondary else self.accent,fg=self.fg if secondary else '#092b2a',activebackground='#0e927b',activeforeground='white',font=('Segoe UI',10,'bold'),relief='flat',cursor='hand2',padx=12,pady=8)
 def layout(self):
  top=tk.Frame(self.root,bg=self.bg);top.pack(fill='x',padx=18,pady=(14,8))
  tk.Label(top,text='🛒 ShopSmart AI',font=('Segoe UI',23,'bold'),fg=self.accent,bg=self.bg).pack(side='left')
  tk.Label(top,text='One Basket, Multiple Stores, Better Living',font=('Segoe UI',10),fg=self.muted,bg=self.bg).pack(side='left',padx=18)
  self.button(top,'Logout',self.logout,True).pack(side='right')
  self.button(top,'☀ / ☾ Theme',self.toggle,True).pack(side='right')
  tk.Label(top,text=self.user[1],bg=self.bg,fg=self.fg).pack(side='right',padx=8)
  main=tk.PanedWindow(self.root,orient='horizontal',sashwidth=6,bg=self.bg,bd=0);main.pack(fill='both',expand=True,padx=18,pady=8)
  left=tk.Frame(main,bg=self.panel);right=tk.Frame(main,bg=self.panel);main.add(left,minsize=420,stretch='always');main.add(right,minsize=320)
  tk.Label(left,text='AI SHOPPING CHAT',font=('Segoe UI',11,'bold'),bg=self.panel,fg=self.fg).pack(anchor='w',padx=12,pady=10)
  self.chat=tk.Text(left,wrap='word',state='disabled',bg=self.panel,fg=self.fg,font=('Segoe UI',11),relief='flat',padx=12,pady=10,selectbackground='#137f7b');self.chat.pack(fill='both',expand=True)
  self.chat.tag_config('user',foreground=self.accent,font=('Segoe UI',11,'bold'));self.chat.tag_config('bot',foreground=self.fg,font=('Segoe UI',11,'bold'))
  entryrow=tk.Frame(left,bg=self.panel);entryrow.pack(fill='x',padx=10,pady=10)
  self.entry=tk.Entry(entryrow,bg=self.bg,fg=self.fg,insertbackground=self.fg,relief='flat',font=('Segoe UI',11));self.entry.pack(side='left',fill='x',expand=True,ipady=12);self.entry.bind('<Return>',lambda e:self.send())
  self.button(entryrow,'Send ➤',self.send).pack(side='right',padx=(8,0))
  self.status=tk.Label(left,text='Ready • Ollama optional; built-in shopping commands always work',fg=self.muted,bg=self.panel,font=('Segoe UI',9));self.status.pack(anchor='w',padx=12,pady=(0,8))
  tk.Label(right,text='PRODUCT CATALOG',font=('Segoe UI',11,'bold'),bg=self.panel,fg=self.fg).pack(anchor='w',padx=12,pady=10)
  filterrow=tk.Frame(right,bg=self.panel);filterrow.pack(fill='x',padx=10)
  self.search=tk.Entry(filterrow,font=('Segoe UI',10));self.search.pack(side='left',fill='x',expand=True);self.search.bind('<KeyRelease>',lambda e:self.refresh_catalog())
  self.store_var=tk.StringVar(value='All stores');storebox=ttk.Combobox(right,textvariable=self.store_var,values=['All stores']+STORES,state='readonly');storebox.pack(fill='x',padx=10,pady=7);storebox.bind('<<ComboboxSelected>>',lambda e:self.refresh_catalog())
  self.catalog=ttk.Treeview(right,columns=('name','store','price'),show='headings',height=9,selectmode='browse')
  for key,title,width in [('name','Product',160),('store','Store',100),('price','Price',75)]:self.catalog.heading(key,text=title);self.catalog.column(key,width=width,anchor='w')
  self.catalog.pack(fill='both',expand=True,padx=10,pady=5);self.catalog.bind('<Double-1>',lambda e:self.add_selected())
  actions=tk.Frame(right,bg=self.panel);actions.pack(fill='x',padx=10,pady=5)
  self.button(actions,'Add selected',self.add_selected).pack(side='left',padx=(0,5));self.button(actions,'Compare',self.compare_selected,True).pack(side='left')
  tk.Label(right,text='YOUR BASKET',font=('Segoe UI',11,'bold'),bg=self.panel,fg=self.fg).pack(anchor='w',padx=12,pady=(12,4))
  self.basket=ttk.Treeview(right,columns=('name','qty','price'),show='headings',height=5)
  for key,title,width in [('name','Product / Store',200),('qty','Qty',45),('price','Subtotal',90)]:self.basket.heading(key,text=title);self.basket.column(key,width=width)
  self.basket.pack(fill='both',expand=True,padx=10,pady=5)
  self.total=tk.Label(right,text='Total: R0.00',bg=self.panel,fg=self.accent,font=('Segoe UI',13,'bold'));self.total.pack(anchor='e',padx=12)
  cartactions=tk.Frame(right,bg=self.panel);cartactions.pack(fill='x',padx=10,pady=10)
  self.button(cartactions,'Remove selected',self.remove_selected,True).pack(side='left');self.button(cartactions,'Demo checkout',self.checkout).pack(side='right')
  bottom=tk.Frame(self.root,bg=self.bg);bottom.pack(fill='x',padx=18,pady=(0,10))
  for label,cmd in [('View cart','show cart'),('Budget R300','recommend groceries for R300'),('Track orders','track orders'),('Optimise','optimise basket'),('Help','help')]:self.button(bottom,label,lambda s=cmd:self.ask(s),True).pack(side='left',padx=(0,7))
  self.button(bottom,'Send developer suggestion',self.feedback_dialog).pack(side='right')
  self.refresh_catalog();self.refresh_cart();self.entry.focus_set()
 def logout(self):
  if self.busy:
   return messagebox.showinfo('Please wait','Wait for the current AI response before logging out.')
  self.active=False;self.engine.conn.close()
  for w in self.root.winfo_children():w.destroy()
  self.on_logout(self.dark)
 def toggle(self):
  self.dark=not self.dark;self.theme()
  for w in self.root.winfo_children():w.destroy()
  self.layout()
 def write(self,who,msg):
  self.chat.configure(state='normal');self.chat.insert('end',who+'\n','user' if who=='You' else 'bot');self.chat.insert('end',msg+'\n\n');self.chat.configure(state='disabled');self.chat.see('end')
 def ask(self,s):self.entry.delete(0,'end');self.entry.insert(0,s);self.send()
 def send(self):
  if self.busy:return
  s=self.entry.get().strip()
  if not s:return
  self.entry.delete(0,'end');self.write('You',s)
  answer=self.engine.local(s)
  if answer is not None:self.write('ShopSmart AI',answer);self.refresh_cart();return
  self.busy=True;self.status.config(text='Thinking with Ollama…');history=list(self.history)
  def worker():
   try:reply=self.engine.ollama(s,history)
   except Exception:reply=('I can help with shopping even without Ollama. Try “compare milk”, “add 2 bread”, “browse dairy”, or “recommend groceries for R300”. To enable free-form AI conversation, start Ollama and download the configured model.')
   self.q.put((s,reply))
  threading.Thread(target=worker,daemon=True).start()
 def poll(self):
  if not self.active:return
  try:
   while True:
    s,reply=self.q.get_nowait();self.write('ShopSmart AI',reply);self.history.extend([{'role':'user','content':s},{'role':'assistant','content':reply}]);self.history=self.history[-10:];self.busy=False;self.status.config(text='Ready')
  except queue.Empty:pass
  self.root.after(120,self.poll)
 def refresh_catalog(self):
  for x in self.catalog.get_children():self.catalog.delete(x)
  term=self.search.get().strip();store=self.store_var.get();store=None if store=='All stores' else store
  for p in self.engine.browse(term,store):self.catalog.insert('', 'end',iid=p['id'],values=(p['name']+' '+p['size'],p['store'],'R'+p['price_zar']))
 def refresh_cart(self):
  for x in self.basket.get_children():self.basket.delete(x)
  total=0
  for p,q in self.engine.cart():
   sub=q*float(p['price_zar']);total+=sub;self.basket.insert('','end',iid=p['id'],values=(p['name']+' / '+p['store'],q,f'R{sub:.2f}'))
  self.total.config(text=f'Total: R{total:.2f}')
 def add_selected(self):
  sel=self.catalog.selection()
  if not sel:return messagebox.showinfo('Select a product','Select a product from the catalog first.')
  self.write('ShopSmart AI',self.engine.add(sel[0]));self.refresh_cart()
 def compare_selected(self):
  sel=self.catalog.selection()
  if sel:self.write('ShopSmart AI',self.engine.compare(self.engine.byid[sel[0]]['name']))
 def remove_selected(self):
  sel=self.basket.selection()
  if sel:self.write('ShopSmart AI',self.engine.remove(sel[0]));self.refresh_cart()
 def checkout(self):
  if not self.engine.cart():return messagebox.showinfo('Empty basket','Add items first.')
  preview=self.engine.advanced.checkout_preview()
  if messagebox.askyesno('Demo checkout',preview):
   self.write('ShopSmart AI',self.engine.advanced.confirm('checkout'));self.refresh_cart()
 def feedback_dialog(self):
  win=tk.Toplevel(self.root);win.title('Send a suggestion');win.geometry('440x250');win.configure(bg=self.bg)
  tk.Label(win,text='Suggestion for ShopSmart developers',bg=self.bg,fg=self.fg,font=('Segoe UI',12,'bold')).pack(pady=12)
  field=tk.Text(win,height=5,width=42);field.pack(padx=12,pady=8)
  def save():
   self.write('ShopSmart AI',self.engine.feedback(field.get('1.0','end').strip()));win.destroy()
  self.button(win,'Save suggestion',save).pack(pady=8)

class Login:
 def __init__(self,root,dark=True):
  self.root=root;self.dark=dark;self.signup=False;self.accounts=Accounts(DB.parent/'accounts.db');self.render()
 def render(self):
  for w in self.root.winfo_children():w.destroy()
  r=self.root;r.title('ShopSmart AI | Account access');r.minsize(470,530);r.geometry('620x610')
  bg='#101827' if self.dark else '#f3f7fb';panel='#1b293b' if self.dark else '#ffffff';fg='#eef5ff' if self.dark else '#182a3b';accent='#1cb99b'
  r.configure(bg=bg)
  tk.Button(r,text='Light / Dark',command=self.toggle,bg=panel,fg=fg,relief='flat').pack(anchor='ne',padx=16,pady=10)
  card=tk.Frame(r,bg=panel,padx=42,pady=28);card.pack(expand=True,padx=25,pady=15)
  tk.Label(card,text='ShopSmart AI',font=('Segoe UI',28,'bold'),bg=panel,fg=accent).pack()
  tk.Label(card,text='One Basket, Multiple Stores, Better Living',bg=panel,fg=fg,font=('Segoe UI',10)).pack(pady=(0,20))
  tk.Label(card,text='Create your account' if self.signup else 'Welcome back',font=('Segoe UI',18,'bold'),bg=panel,fg=fg).pack(pady=(0,10))
  self.fields={}
  for label in (['Full name','Email address','Password','Confirm password'] if self.signup else ['Email address','Password']):
   tk.Label(card,text=label,bg=panel,fg=fg).pack(anchor='w')
   e=tk.Entry(card,width=36,font=('Segoe UI',12),show='*' if 'password' in label.lower() else '',bg=bg,fg=fg,insertbackground=fg,relief='flat');e.pack(fill='x',ipady=7,pady=(3,9));self.fields[label]=e
  self.status=tk.Label(card,text='',bg=panel,fg='#e58b77',wraplength=340);self.status.pack()
  tk.Button(card,text='Create account' if self.signup else 'Log in',command=self.submit,bg=accent,fg='#092b2a',relief='flat',font=('Segoe UI',11,'bold'),pady=9).pack(fill='x',pady=5)
  tk.Button(card,text='Already have an account? Log in' if self.signup else 'New customer? Create account',command=self.switch,bg=panel,fg=accent,relief='flat').pack(pady=6)
  for e in self.fields.values():e.bind('<Return>',lambda event:self.submit())
  next(iter(self.fields.values())).focus_set()
 def toggle(self):
  self.dark=not self.dark;self.render()
 def switch(self):
  self.signup=not self.signup;self.render()
 def submit(self):
  values={k:e.get() for k,e in self.fields.items()};email=values['Email address'];password=values['Password']
  if self.signup:
   if password!=values['Confirm password']:
    self.status.config(text='Passwords do not match.');return
   try:self.accounts.register(values['Full name'],email,password)
   except ValueError as e:self.status.config(text=str(e));return
   self.signup=False;self.render();self.fields['Email address'].insert(0,email);self.status.config(text='Account created. Please log in.');return
  user=self.accounts.login(email,password)
  if not user:self.status.config(text='Incorrect email or password.');return
  self.accounts.db.close()
  for w in self.root.winfo_children():w.destroy()
  App(self.root,user,lambda dark:Login(self.root,dark),self.dark)

if __name__=='__main__':
 DB.parent.mkdir(exist_ok=True)
 root=tk.Tk();Login(root);root.mainloop()
