# ShopSmart AI — direct launch

Run `python run.py` from this folder. On Windows this opens the original Tkinter desktop. In GitHub Codespaces or headless Linux it opens the interactive terminal application directly; no forwarded port, no VNC, no sudo. Use `python run.py --terminal` on any platform to choose the terminal interface. First run installs Python dependencies using pip (internet required). Python 3.11–3.13 recommended; Windows desktop requires Python with Tk support. If pip fails, use a supported Python environment and retry.

Register an account then log in. Password typing is hidden. Try `compare milk`, `add 2 milk`, `show cart`, `recommend groceries for R300`, `optimise basket`, `confirm optimise`, `checkout`, `confirm checkout`, `track orders`, `suggestion: more products`. Type `/menu` for terminal shortcuts and `/logout` to sign out. Ctrl+C exits.

Ollama is optional and is not installed or launched automatically. To enable free-form AI, install Ollama separately, start `ollama serve` and pull the model specified in config.json (`ollama pull llama3.2:3b`). Built-in shopping commands work without it. The prototype uses 200 demonstration catalog records; not live prices, stock, payments or tracking. Local SQLite data stays in the data folder; do not commit customer databases.

Tests: `python -m unittest -v test_project`. Model evaluation: `python intent.py`.
