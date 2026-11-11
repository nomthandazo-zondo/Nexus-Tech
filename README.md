# ShopSmart AI — Final-Year Academic Project

Team: **Sandile, Hlengiwe, Trevor, Lefa**. Built for the VUT Web Development 3.2 assignment (AIWEY3A).

## Run in VS Code (Windows)
1. Install **PHP 8.1+** or XAMPP. Check `php -v` in VS Code Terminal. If not found, add the PHP installation folder to PATH or use the full path to `php.exe`.
2. Extract the ZIP. In VS Code choose **File > Open Folder** and open `ShopSmart_AI_VSCode`.
3. Open **Terminal > New Terminal**. Run `php -S localhost:8000`.
4. Open **http://localhost:8000/index.php** in your browser. **Do not use Live Server**: PHP APIs will not run.
5. Browse retailers, add products, open Smart Checkout, place a **demo** order, copy its ID, and use Track Order. Press **Advance Demo Status** to demonstrate fulfilment. Try chatbot prompts: `compare milk prices`, `stock for eggs`, `top sales`.

Alternative XAMPP: copy folder to `C:\xampp\htdocs\ShopSmart_AI_VSCode`, start Apache, open `http://localhost/ShopSmart_AI_VSCode/index.php`.

## Files
- `index.php`, `about.php`, `contact.php`: required pages.
- `shell.php`, `style.css`, `app.js`: responsive UI and interactions.
- `config.php`, `api.php`: PHP catalogue, orders, tracking and rule-based data-aware chatbot.
- `data/products.csv`: **120 fictional price/stock/sales records**, 20 product categories/items × six stores.
- `data/orders.json`: demo orders persisted locally; writable by PHP.
- `data/consultations.csv`: consultation template, with **pending** interviews clearly labelled.
- `docs/PROJECT_REPORT.md`, `docs/TEST_PLAN.md`, `docs/ARCHITECTURE.md`: submission documents.
- `.vscode`: VS Code settings and tasks.

## Demonstration limitations
**All prices, stock, discounts, sales, retailer fulfilment and delivery are simulated.** This is not a retailer-integrated system. No payment is collected; no real order is sent. Chatbot is a transparent, deterministic retrieval/rule-based assistant, **not a hosted generative LLM**. The prototype does not implement authentication or production privacy/security controls. Local JSON order storage is appropriate only for single-user demonstration. Protect the `data/` directory when deploying; preferably move storage outside the web root. Avoid deploying publicly without server-side authentication, rate limiting, database transactions, HTTPS, CSRF protection, and data protection review.

## Troubleshooting
- Blank page? Open browser developer console and confirm PHP server is running.
- Catalogue unavailable? Open `http://localhost:8000/api.php?action=catalog`.
- Order saving fails? Give PHP write permission to `data/orders.json`.
- PHP missing? Install PHP or XAMPP; no Python dependencies required.
