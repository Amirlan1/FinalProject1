from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
db_folder = BASE_DIR / "db"
db_folder.mkdir(exist_ok=True)
db_path = db_folder / "users.db"

_current_snapshot = None


class StateSnapshot:
    def __init__(self):
        self.before = None
        self.after = None
        self.user_id = None


def init_state_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_states_auto (
            user_id INTEGER PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()


def load_state_from_db(user_id: int):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT state_json FROM user_states_auto WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        try:
            return json.loads(row[0])
        except:
            pass
    
    return {
        "mode": "demo",
        "profile": {"username": "Trader"},
        "accounts": {
            "demo": {"cash": 10000.0, "positions": {}, "orders": [], "order_id": 1},
            "real": {"cash": 0.0, "positions": {}, "orders": [], "order_id": 1},
        }
    }


def save_state_to_db(user_id: int, state):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    state_json = json.dumps(state)
    
    cursor.execute("""
        INSERT OR REPLACE INTO user_states_auto (user_id, state_json, updated_at)
        VALUES (?, ?, datetime('now'))
    """, (user_id, state_json))
    
    conn.commit()
    conn.close()


def merge_state_to_global(state_dict, global_state):
    if not state_dict:
        return
    
    global_state["mode"] = state_dict.get("mode", "demo")
    
    if "accounts" in state_dict:
        for mode in ["demo", "real"]:
            if mode in state_dict["accounts"]:
                global_state["accounts"][mode] = state_dict["accounts"][mode]


class AutoSaveMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = request.cookies.get("user_id")
        
        if user_id and request.url.path.startswith("/api/"):
            try:
                user_id = int(user_id)
                
                from app import state, lock
                
                with lock:
                    saved_state = load_state_from_db(user_id)
                    merge_state_to_global(saved_state, state)
                
                snapshot_before = json.dumps(state)
                
                response = await call_next(request)
                
                with lock:
                    snapshot_after = json.dumps(state)
                    
                    if snapshot_before != snapshot_after:
                        save_state_to_db(user_id, state)
                
                return response
                
            except Exception:
                return await call_next(request)
        
        return await call_next(request)


def inject_state_loader():
    try:
        import app
        
        original_post_login = app.post_login
        original_post_register = app.post_register
        
        def patched_post_login(request, email, password):
            response = original_post_login(request, email, password)
            
            if hasattr(response, 'status_code') and response.status_code == 302:
                user_id = response.cookies.get('user_id')
                if user_id:
                    try:
                        user_id = int(user_id)
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1 FROM user_states_auto WHERE user_id=?", (user_id,))
                        if not cursor.fetchone():
                            default_state = load_state_from_db(user_id)
                            save_state_to_db(user_id, default_state)
                        conn.close()
                    except:
                        pass
            
            return response
        
        def patched_post_register(username, password, email):
            response = original_post_register(username, password, email)
            
            if hasattr(response, 'status_code') and response.status_code == 302:
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email=? ORDER BY id DESC LIMIT 1", (email.strip().lower(),))
                    row = cursor.fetchone()
                    if row:
                        user_id = row[0]
                        default_state = load_state_from_db(user_id)
                        save_state_to_db(user_id, default_state)
                    conn.close()
                except:
                    pass
            
            return response
        
        app.post_login = patched_post_login
        app.post_register = patched_post_register
        
    except Exception:
        pass


def setup_auto_save(app):
    init_state_db()
    
    app.add_middleware(AutoSaveMiddleware)
    
    inject_state_loader()
