from passlib.context import CryptContext
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi import HTTPException
import aiosmtplib
from email.message import EmailMessage

BASE_DIR = Path(__file__).resolve().parent
db_folder = BASE_DIR / "db"
db_path = db_folder / "users.db"


pwd_context = CryptContext(
    schemes=["argon2"],  
    deprecated="auto"
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password) 

def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False

import os
load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM", "StockingRep <stockingrep00@gmail.com>")
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
RESET_URL = os.getenv("RESET_PASSWORD_URL", "http://localhost:8000/reset-password")

conf = ConnectionConfig(
    MAIL_USERNAME=EMAIL_USER,
    MAIL_PASSWORD=EMAIL_PASSWORD, 
    MAIL_FROM=MAIL_FROM,
    MAIL_PORT=MAIL_PORT,
    MAIL_SERVER=MAIL_SERVER,
    MAIL_STARTTLS=True,     
    MAIL_SSL_TLS=False,    
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER="./templates" 
)


async def send_reset_email(email_to: str, token: str):
    """Send password reset email via Gmail"""
    link = f"{RESET_URL}?token={token}"
    message = MessageSchema(
        subject="Password Reset - StockingRep",
        recipients=[email_to],
        body=f"""
Hello,

You requested to reset your password for StockingRep.

Please click the link below to reset your password:
{link}

This link will expire in 1 hour.

If you did not request this, please ignore this email.

Best regards,
StockingRep Team


Здравствуйте,

Вы просили сбросить ваш пароль для StockingRep.

Пожалуйста, перейдите по ссылке ниже, чтобы сбросить пароль:
{link}

Срок действия этой ссылки истечет через 1 час.

Если вы не запрашивали это, пожалуйста, проигнорируйте это электронное письмо.

С наилучшими пожеланиями,
команда StockingRep
        """,
        subtype="plain"
    )
    fm = FastMail(conf)
    await fm.send_message(message)


def generate_reset_token():
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=1)
    return token, expires_at


def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


async def forgot_password(email: str):
    conn = get_db()
    cursor = conn.cursor()
    
    email = email.strip().lower()

    cursor.execute("SELECT id FROM users WHERE LOWER(email)=?", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return {"error": "User not found"}

    token, expires_at = generate_reset_token()
    cursor.execute(
        "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user["id"], token, expires_at)
    )
    conn.commit()
    conn.close()

    try:
        await send_reset_email(email, token)
        return {"message": "Password reset link has been sent to your email"}
    except Exception as e:
        return {"error": f"Failed to send email: {str(e)}"}


async def reset_password(token: str, new_password: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, expires_at FROM password_resets WHERE token=?", (token,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"error": "Invalid token"}

    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        conn.close()
        return {"error": "Token expired"}

    hashed = hash_password(new_password)
    cursor.execute("UPDATE users SET password=? WHERE id=?", (hashed, row["user_id"]))
    cursor.execute("DELETE FROM password_resets WHERE token=?", (token,))
    conn.commit()
    conn.close()
    
    return {"message": "Password successfully changed"}