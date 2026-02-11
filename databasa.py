import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_folder = BASE_DIR / "db"
db_folder.mkdir(exist_ok=True)
db_path = db_folder / "users.db"


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_users_table():
    """Create users table if not exists"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def create_password_resets_table():
    """Create password_resets table if not exists"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

import sqlite3

def ensure_consent_columns():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cur.fetchall()]

    if "privacy_version" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN privacy_version TEXT")

    if "privacy_accepted_at" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN privacy_accepted_at TEXT")

    conn.commit()
    conn.close()

import sqlite3
import json

def ensure_user_mode_column():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cur.fetchall()]
    if "mode" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN mode TEXT DEFAULT 'demo'")
    conn.commit()
    conn.close()

def create_accounts_table():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        user_id INTEGER NOT NULL,
        mode TEXT NOT NULL,                 -- 'demo' | 'real'
        cash REAL NOT NULL DEFAULT 0,
        positions_json TEXT NOT NULL DEFAULT '{}',
        orders_json TEXT NOT NULL DEFAULT '[]',
        order_id INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, mode),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    conn.close()

def ensure_user_accounts(user_id: int):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # demo row
    cur.execute("SELECT 1 FROM accounts WHERE user_id=? AND mode='demo'", (user_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO accounts(user_id, mode, cash, positions_json, orders_json, order_id) VALUES(?,?,?,?,?,?)",
            (user_id, "demo", 10000.0, "{}", "[]", 1)
        )

    # real row
    cur.execute("SELECT 1 FROM accounts WHERE user_id=? AND mode='real'", (user_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO accounts(user_id, mode, cash, positions_json, orders_json, order_id) VALUES(?,?,?,?,?,?)",
            (user_id, "real", 0.0, "{}", "[]", 1)
        )

    conn.commit()
    conn.close()