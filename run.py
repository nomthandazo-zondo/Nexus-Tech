"""One command: desktop locally, interactive terminal in Codespaces."""
import os,sys,subprocess,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    os.chdir(ROOT)
    if any(importlib.util.find_spec(m) is None for m in ('requests','sklearn')):
        print('Installing Python dependencies (first run only)...',flush=True)
        subprocess.check_call([sys.executable,'-m','pip','install','-r','requirements.txt'])
    terminal='--terminal' in sys.argv or os.environ.get('CODESPACES','').lower()=='true' or (sys.platform.startswith('linux') and not os.environ.get('DISPLAY'))
    if not terminal:
        try: import tkinter
        except ImportError: terminal=True
    subprocess.check_call([sys.executable,str(ROOT/('terminal_app.py' if terminal else 'shopsmart.py'))])
if __name__=='__main__': main()
