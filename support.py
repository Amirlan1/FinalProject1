import os
from fastapi import HTTPException
import aiosmtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM", "StockingRep <stockingrep00@gmail.com>")
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))

async def send_support_email(user_email: str, username: str, subject: str, message: str):
    if len(subject) < 3:
        raise HTTPException(400, "Subject too short")
    if len(message) < 10:
        raise HTTPException(400, "Message too short")

    msg = EmailMessage()
    msg["From"] = MAIL_FROM
    msg["To"] = EMAIL_USER
    msg["Reply-To"] = user_email
    msg["Subject"] = f"[Support] {subject}"
    msg.set_content(f"""
New Support Request

Username: {username}
User Email: {user_email}

----------------------------------
{message}
----------------------------------

StockingRep System Notification
""")

    try:
        await aiosmtplib.send(
            msg,
            hostname=MAIL_SERVER,
            port=MAIL_PORT,
            start_tls=True,
            username=EMAIL_USER,
            password=EMAIL_PASSWORD
        )
    except Exception as e:
        print("Failed to send support email:", e)
        raise HTTPException(500, f"Failed to send email: {e}")
