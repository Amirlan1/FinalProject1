from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dotenv import load_dotenv
from pathlib import Path
import os
import requests

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


# --- env ---
env_path = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=env_path)

KEY = os.getenv("ALPACA_KEY")
SECRET = os.getenv("ALPACA_SECRET")
PAPER = os.getenv("ALPACA_PAPER", "1") == "1"
DATA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")

if not KEY or not SECRET:
    raise RuntimeError("No keys. Check .env near stocking.py: ALPACA_KEY / ALPACA_SECRET")

# --- clients ---
trade = TradingClient(api_key=KEY, secret_key=SECRET, paper=PAPER)  # paper=True -> paper trading :contentReference[oaicite:12]{index=12}

# --- app ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")


def api_fail(code: int, msg: str):
    raise HTTPException(status_code=code, detail=msg)


@app.get("/", response_class=HTMLResponse)
def page(request: Request):
    return templates.TemplateResponse("stock.html", {"request": request})


@app.get("/api/account")
def account():
    try:
        a = trade.get_account()
        return {
            "cash": str(a.cash),
            "buying_power": str(a.buying_power),
            "portfolio_value": str(a.portfolio_value),
            "status": str(a.status)
        }
    except Exception as e:
        api_fail(500, "Account error: " + str(e))


@app.get("/api/positions")
def positions():
    try:
        ps = trade.get_all_positions()
        out = []
        for p in ps:
            out.append({
                "symbol": p.symbol,
                "qty": str(p.qty),
                "avg_entry_price": str(p.avg_entry_price),
                "market_value": str(p.market_value),
                "unrealized_pl": str(p.unrealized_pl),
            })
        return out
    except Exception as e:
        api_fail(500, "Positions error: " + str(e))


@app.post("/api/order")
def place_order(
    symbol: str = Query(..., min_length=1, max_length=10),
    qty: int = Query(..., ge=1, le=100000),
    side: str = Query(...),  # buy / sell
):
    sym = symbol.strip().upper()
    sd = side.strip().lower()

    if sd not in ["buy", "sell"]:
        api_fail(400, "side must be buy or sell")

    try:
        req = MarketOrderRequest(
            symbol=sym,
            qty=qty,
            side=OrderSide.BUY if sd == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        o = trade.submit_order(req)
        return {"id": o.id, "symbol": sym, "qty": qty, "side": sd, "status": str(o.status)}
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Unauthorized" in msg:
            api_fail(401, "Trading 401 Unauthorized. Check paper keys and paper mode.")
        api_fail(500, "Order error: " + msg[:200])


@app.get("/api/bars")
def bars(
    symbol: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(200, ge=1, le=2000),
    timeframe: str = Query("1Day")  # 1Day / 1Hour
):
    sym = symbol.strip().upper()

    tf = timeframe
    if tf not in ["1Day", "1Hour"]:
        api_fail(400, "timeframe must be 1Day or 1Hour")

    headers = {
        "APCA-API-KEY-ID": KEY,
        "APCA-API-SECRET-KEY": SECRET
    }  # Market Data auth headers :contentReference[oaicite:13]{index=13}

    url = f"{DATA_BASE}/v2/stocks/bars"
    params = {"symbols": sym, "timeframe": tf, "limit": limit}

    r = requests.get(url, headers=headers, params=params, timeout=20)

    if r.status_code == 401:
        api_fail(401, "Market Data 401 Unauthorized. Check keys or DATA_BASE domain.")
    if not r.ok:
        api_fail(r.status_code, f"Market Data error {r.status_code}: {r.text[:200]}")

    data = r.json()
    bars = data.get("bars", {}).get(sym, [])

    out = []
    for b in bars:
        out.append({
            "time": b["t"],
            "close": b["c"]
        })
    return out
