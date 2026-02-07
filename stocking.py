from pathlib import Path
import io
import time
import threading
import requests
import pandas as pd

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


BASE = Path(__file__).resolve().parent

app = FastAPI()

templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

state_lock = threading.Lock()

cash = 10000.0
positions = {}   
orders = []     
order_id = 1

cache_lock = threading.Lock()
cache = {}  
CACHE_TTL = 60  

def sym_fix(symbol: str) -> str:
    s = (symbol or "").strip()
    if not s:
        raise HTTPException(400, "symbol is required")

    if "." in s:
        return s.lower()
    return f"{s.lower()}.us"


def load_stooq(symbol_fixed: str) -> pd.DataFrame:
    url = f"https://stooq.com/q/d/l/?s={symbol_fixed}&i=d"
    r = requests.get(url, timeout=20)
    r.raise_for_status()

    df = pd.read_csv(io.StringIO(r.text))
    if df.empty or "Date" not in df.columns:
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date").sort_index()

    for col in ["Open", "High", "Low", "Close"]:
        if col not in df.columns:
            return pd.DataFrame()

    if "Volume" not in df.columns:
        df["Volume"] = 0

    return df


def get_df(symbol_fixed: str) -> pd.DataFrame:
    now = time.time()
    with cache_lock:
        item = cache.get(symbol_fixed)
        if item and (now - item["ts"] < CACHE_TTL):
            return item["df"]

    df = load_stooq(symbol_fixed)

    with cache_lock:
        cache[symbol_fixed] = {"ts": now, "df": df}

    return df


def last_price(symbol_fixed: str) -> float:
    df = get_df(symbol_fixed)
    if df.empty:
        raise HTTPException(404, "No data for symbol")
    return float(df["Close"].iloc[-1])


def equity_value() -> float:
    eq = cash
    for sym, p in positions.items():
        pr = last_price(sym_fix(sym))
        eq += p["qty"] * pr
    return eq

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("stock.html", {"request": request})


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/bars")
def api_bars(
    symbol: str = Query(...),
    timeframe: str = Query("1Day"),
    limit: int = Query(200, ge=0, le=20000),
):
    sym = symbol.strip().upper()
    sfix = sym_fix(sym)

    df = get_df(sfix)
    if df.empty:
        raise HTTPException(404, "No data for symbol")

    if limit == 0:
        df2 = df
    else:
        df2 = df.tail(limit)

    bars = []
    for dt, row in df2.iterrows():
        bars.append({
            "t": dt.strftime("%Y-%m-%d"),
            "o": float(row["Open"]),
            "h": float(row["High"]),
            "l": float(row["Low"]),
            "c": float(row["Close"]),
            "v": float(row["Volume"]) if "Volume" in df2.columns else 0.0,
        })

    return JSONResponse({
        "symbol": sym,
        "symbol_fixed": sfix,
        "timeframe": timeframe,
        "count": len(bars),
        "bars": bars
    })

@app.get("/api/account")
def api_account():
    eq = equity_value()
    return JSONResponse({
        "cash": round(cash, 2),
        "equity": round(eq, 2),
        "buying_power": round(cash, 2),
    })


@app.get("/api/positions")
def api_positions():
    items = []
    for sym, p in positions.items():
        pr = last_price(sym_fix(sym))
        mv = p["qty"] * pr
        upl = (pr - p["avg"]) * p["qty"]
        items.append({
            "symbol": sym,
            "qty": int(p["qty"]),
            "avg_entry_price": round(float(p["avg"]), 4),
            "current_price": round(pr, 4),
            "market_value": round(mv, 2),
            "unrealized_pl": round(upl, 2),
        })
    return JSONResponse(items)


@app.get("/api/orders")
def api_orders():
    return JSONResponse(list(reversed(orders[-200:])))


@app.post("/api/order")
def api_order(
    symbol: str = Query(...),
    qty: int = Query(..., ge=1, le=1000000),
    side: str = Query(...),
):
    global cash, positions, orders, order_id

    sym = symbol.strip().upper()
    side2 = side.strip().lower()
    if side2 not in ["buy", "sell"]:
        raise HTTPException(400, "side must be buy or sell")

    sfix = sym_fix(sym)
    price = last_price(sfix)
    cost = qty * price

    with state_lock:
        if side2 == "buy":
            if cash < cost:
                raise HTTPException(400, "Not enough cash")

            cash -= cost

            if sym not in positions:
                positions[sym] = {"qty": qty, "avg": price}
            else:
                oldq = int(positions[sym]["qty"])
                olda = float(positions[sym]["avg"])
                newq = oldq + qty
                newa = (oldq * olda + qty * price) / newq
                positions[sym]["qty"] = newq
                positions[sym]["avg"] = newa

        else:
            if sym not in positions or int(positions[sym]["qty"]) < qty:
                raise HTTPException(400, "Not enough shares")

            positions[sym]["qty"] = int(positions[sym]["qty"]) - qty
            cash += cost
            if int(positions[sym]["qty"]) == 0:
                del positions[sym]

        oid = order_id
        order_id += 1

        orders.append({
            "id": oid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": sym,
            "side": side2,
            "qty": int(qty),
            "price": round(price, 4),
            "notional": round(cost, 2),
        })

    return JSONResponse({"status": "filled", "order_id": oid})


@app.post("/api/reset")
def api_reset():
    global cash, positions, orders, order_id
    with state_lock:
        cash = 10000.0
        positions = {}
        orders = []
        order_id = 1
    return {"ok": True}
