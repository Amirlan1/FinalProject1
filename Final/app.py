from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates  # исправленный импорт
import yfinance as yf
from fastapi.responses import HTMLResponse
from datetime import datetime

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# Функция для получения данных о цене акций
async def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo")  # Получаем данные за последний месяц
    data = hist[['Close']].reset_index()
    return data.to_dict(orient='records')

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    ticker = "AAPL"  # Тикер по умолчанию
    stock_data = await get_stock_data(ticker)

    # Формируем данные для графика
    chart_data = {
        "labels": [str(item['Date']).split()[0] for item in stock_data],
        "data": [item['Close'] for item in stock_data]
    }

    return templates.TemplateResponse("index.html", {"request": request, "chart_data": chart_data, "ticker": ticker})

# Роут для обновления графика на основе выбранного тикера
@app.post("/update_graph/")
async def update_graph(request: Request, ticker: str = Form(...)):
    stock_data = await get_stock_data(ticker)

    # Формируем данные для графика
    chart_data = {
        "labels": [str(item['Date']).split()[0] for item in stock_data],
        "data": [item['Close'] for item in stock_data]
    }

    return templates.TemplateResponse("index.html", {"request": request, "chart_data": chart_data, "ticker": ticker})
