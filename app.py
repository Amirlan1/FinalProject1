from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
import yfinance as yf
from fastapi.responses import HTMLResponse
from datetime import datetime
import uvicorn  # импортируем uvicorn прямо в файл

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


# 🔹 Этот блок добавляем в конец файла
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
