from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
import yfinance as yf
from fastapi.responses import HTMLResponse
from datetime import datetime
import uvicorn
from databasa import create_users_table, get_db
import sqlite3
from fastapi import status
import os
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
db_folder = BASE_DIR / "db"
db_path = db_folder / "users.db"


ph = PasswordHasher()
app = FastAPI()

templates = Jinja2Templates(directory="templates")



async def get_stock_data(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo", interval="1d", actions=False, auto_adjust=False)
    except Exception as e:
        return [], f"yfinance error: {e}"

    if hist is None or hist.empty:
        return [], "No data from Yahoo. Try ticker like AAPL / MSFT / TSLA (crypto: BTC-USD)."

    hist = hist.reset_index()

    out = []
    for i in range(len(hist)):
        d = hist.loc[i, "Date"]
        c = hist.loc[i, "Close"]
        out.append({
            "Date": d.strftime("%Y-%m-%d"),
            "Close": float(c)
        })

    return out, None


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    ticker = "AAPL"
    stock_data, err = await get_stock_data(ticker)
    chart_data = {
        "labels": [str(item['Date']).split()[0] for item in stock_data],
        "data": [item['Close'] for item in stock_data]
    }
    return templates.TemplateResponse("index.html", {"request": request, "chart_data": chart_data, "ticker": ticker})

@app.get("/gra", response_class=HTMLResponse)
async def home(request: Request):
    ticker = "AAPL"
    stock_data, err = await get_stock_data(ticker)
    chart_data = {
        "labels": [str(item['Date']).split()[0] for item in stock_data],
        "data": [item['Close'] for item in stock_data]
    }
    return templates.TemplateResponse("graphic.html", {"request": request, "chart_data": chart_data, "ticker": ticker})


@app.post("/update_graph/")
async def update_graph(request: Request, ticker: str = Form(...)):
    stock_data = await get_stock_data(ticker)
    chart_data = {
        "labels": [str(item['Date']).split()[0] for item in stock_data],
        "data": [item['Close'] for item in stock_data]
    }
    return templates.TemplateResponse("index.html", {"request": request, "chart_data": chart_data, "ticker": ticker})




@app.get("/register")
def get_register(request: Request):
    return templates.TemplateResponse("register.html", {
        "request": request
    })
@app.post("/register")
def post_register(username: str = Form(...), password: str = Form(...), email: str = Form(None)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    safe_password = password[:256]  
    hashed_pass = ph.hash(safe_password)
    cursor.execute('''
        INSERT INTO users (username, password, email) VALUES (?, ?, ?)
    ''', (username, hashed_pass, email))
    conn.commit()
    conn.close()
    
    return RedirectResponse("/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})




@app.post("/login")
def post_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password, username FROM users WHERE email = ?",
        (email,)
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "No such user"

    user_id, hashed_pass, username = user

    try:
        ph.verify(hashed_pass, password)
    except VerifyMismatchError:
        return "Wrong password"

    response = RedirectResponse("/profile", status_code=302)
    response.set_cookie(key="user_id", value=str(user_id))
    return response



def get_current_user(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email FROM users WHERE id = ?",
        (user_id,)
    )
    user = cursor.fetchone()
    conn.close()
    return user



@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login")

    user_id, username, email = user

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "username": username,
            "email": email
        }
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
