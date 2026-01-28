from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
import yfinance as yf
from fastapi.responses import HTMLResponse
from datetime import datetime
import uvicorn
from databasa import create_users_table, get_db
from passlib.context import CryptContext
from security import hash_password
import sqlite3
import os

db_folder = r"C:\Users\user\Documents\GitHub\FinalProject1"
os.makedirs(db_folder, exist_ok=True)
db_path = os.path.join(db_folder, "users.db")

app = FastAPI()

templates = Jinja2Templates(directory="templates")

async def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo")
    data = hist[['Close']].reset_index()
    return data.to_dict(orient='records')

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    ticker = "AAPL"
    stock_data = await get_stock_data(ticker)
    chart_data = {
        "labels": [str(item['Date']).split()[0] for item in stock_data],
        "data": [item['Close'] for item in stock_data]
    }
    return templates.TemplateResponse("index.html", {"request": request, "chart_data": chart_data, "ticker": ticker})

@app.post("/update_graph/")
async def update_graph(request: Request, ticker: str = Form(...)):
    stock_data = await get_stock_data(ticker)
    chart_data = {
        "labels": [str(item['Date']).split()[0] for item in stock_data],
        "data": [item['Close'] for item in stock_data]
    }
    return templates.TemplateResponse("index.html", {"request": request, "chart_data": chart_data, "ticker": ticker})

@app.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )






@app.post("/register")
def post_register(username: str = Form(...), password: str = Form(...), email: str = Form(None)):
    print("Добавляем пользователя в базу:", db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # хешируем пароль
    hashed_pass = hash_password(password)

    cursor.execute('''
        INSERT INTO users (username, password, email) VALUES (?, ?, ?)
    ''', (username, hashed_pass, email))
    conn.commit()
    cursor.execute('SELECT * FROM users')
    all_users = cursor.fetchall()
    print("Все пользователи в базе:", all_users)

    conn.close()
    return f"Пользователь {username} успешно зарегистрирован!"


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
