"""Interactive ShopSmart interface for headless terminals."""
from getpass import getpass
from shopsmart import Engine, Accounts, DB, STORES, CFG
import requests

def main():
    DB.parent.mkdir(exist_ok=True)
    accounts=Accounts(DB.parent/'accounts.db')
    print('\nSHOPSMART AI | One Basket, Multiple Stores, Better Living\nDemo prices in ZAR; no real payments or deliveries.')
    try:
        while True:
            action=input('\n1 Login | 2 Register | 0 Exit: ').strip()
            if action=='0': return
            if action=='2':
                try:
                    name=input('Full name: '); email=input('Email: '); password=getpass('Password (8+ characters): ')
                    if password!=getpass('Confirm password: '): print('Passwords do not match.'); continue
                    accounts.register(name,email,password); print('Account created. Please log in.')
                except ValueError as e: print(e)
                continue
            if action!='1': continue
            user=accounts.login(input('Email: '),getpass('Password: '))
            if not user: print('Invalid credentials.'); continue
            engine=Engine(user[0])
            try: session(engine,user[1])
            finally: engine.conn.close()
    except (EOFError,KeyboardInterrupt): print('\nGoodbye.')
    finally: accounts.db.close()

def session(engine,name):
    history=[]; dark=True
    print(f'\nWelcome, {name}! Type help for examples, /menu for shortcuts, /logout to sign out.')
    while True:
        text=input('\nYou > ').strip()
        if not text: continue
        if text=='/logout': return
        if text=='/theme':
            dark=not dark; print('\033[0m' if dark else '\033[36m',end=''); print('Terminal text theme switched.'); continue
        if text=='/menu':
            print('Stores: '+', '.join(STORES)+'\nCommands: /catalog, /cart, /checkout, /track, /optimise, /feedback, /theme, /logout\nUse /add PRODUCT_ID or /remove PRODUCT_ID for exact catalog selections.') ; continue
        if text.startswith('/add ') or text.startswith('/remove '):
            parts=text.split(); pid=parts[1]
            if len(parts)>3 or (len(parts)==3 and (not parts[2].isdigit() or not 1<=int(parts[2])<=99)):
                print('Use /add PRODUCT_ID [quantity] or /remove PRODUCT_ID [quantity].'); continue
            q=int(parts[2]) if len(parts)==3 else None
            answer=engine.add(pid,q or 1) if parts[0]=='/add' else engine.remove(pid,q)
        else:
            text={'/catalog':'browse','/cart':'show cart','/checkout':'checkout','/track':'track orders','/optimise':'optimise basket'}.get(text,text)
            if text=='/feedback': text='suggestion: '+input('Suggestion: ')
            answer=engine.local(text)
            if answer is None:
                try:
                    requests.get(CFG['ollama_url'].rstrip('/')+'/api/tags',timeout=1).raise_for_status()
                    answer=engine.ollama(text,history)
                except (requests.RequestException,ValueError,KeyError):
                    answer='Free-form AI is unavailable. I can still compare prices, browse products, handle baskets, budgets and demo orders. Type help for examples.'
        print('\nShopSmart AI > '+answer)
        history.extend([{'role':'user','content':text},{'role':'assistant','content':answer}]); history=history[-10:]

if __name__=='__main__': main()
