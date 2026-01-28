import sqlite3
def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_users_table():
    conn=get_db()
    cursor=conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
                   id INTEGER PRIMARY KEY AUTOINCREMENT
                   username TEXT UNIQUE NOT NULL
                   email TEXT UNIQUE NOT NULL
                   password TEXT UNIQUE NOT NULL
                    )                
                   """)
    conn.commit()
    conn.close()