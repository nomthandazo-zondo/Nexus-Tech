import sqlite3, hashlib, secrets, hmac, re
from pathlib import Path

class Accounts:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, salt BLOB NOT NULL, password_hash BLOB NOT NULL)')
        self.db.commit()
    def register(self, name, email, password):
        name, email = name.strip(), email.strip().lower()
        if not name or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Enter your name and a valid email address.')
        if len(password) < 8 or len(password) > 256:
            raise ValueError('Password must contain 8–256 characters.')
        salt = secrets.token_bytes(32)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
        try:
            self.db.execute('INSERT INTO users(name,email,salt,password_hash) VALUES (?,?,?,?)', (name,email,salt,digest))
            self.db.commit()
        except sqlite3.IntegrityError:
            self.db.rollback()
            raise ValueError('An account with this email already exists.')
    def login(self, email, password):
        row = self.db.execute('SELECT id,name,salt,password_hash FROM users WHERE email=?', (email.strip().lower(),)).fetchone()
        if row and len(password)<=256 and hmac.compare_digest(row[3], hashlib.pbkdf2_hmac('sha256',password.encode(),row[2],600000)):
            return row[:2]
        return None
