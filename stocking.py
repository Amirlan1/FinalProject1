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
from pydantic import BaseModel, Field


BASE = Path(__file__).resolve().parent

app = FastAPI()
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

lock = threading.Lock()

state = {
    "mode": "demo", 
    "profile": {
        "username": "Trader",
    },
    "accounts": {
        "demo": {"cash": 10000.0, "positions": {}, "orders": [], "order_id": 1},
        "real": {"cash": 0.0, "positions": {}, "orders": [], "order_id": 1},
    },
}

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


def cur_mode() -> str:
    return state["mode"]


def cur_acc() -> dict:
    return state["accounts"][cur_mode()]


def last_price(symbol_fixed: str) -> float:
    df = get_df(symbol_fixed)
    if df.empty:
        raise HTTPException(404, "No data for symbol")
    return float(df["Close"].iloc[-1])


def equity_value(acc: dict) -> float:
    eq = float(acc["cash"])
    for sym, p in acc["positions"].items():
        pr = last_price(sym_fix(sym))
        eq += int(p["qty"]) * pr
    return eq


def luhn_ok(num: str) -> bool:
    s = "".join(ch for ch in num if ch.isdigit())
    if not s:
        return False
    total = 0
    rev = s[::-1]
    for i, ch in enumerate(rev):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class DepositReq(BaseModel):
    amount: float = Field(..., gt=0, le=1_000_000)
    name: str = Field(..., min_length=2, max_length=64)
    number: str = Field(..., min_length=12, max_length=32)
    exp: str = Field(..., min_length=4, max_length=7)  # MM/YY
    cvc: str = Field(..., min_length=3, max_length=4)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("stock.html", {"request": request})


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})


@app.get("/funding", response_class=HTMLResponse)
def funding_page(request: Request):
    return templates.TemplateResponse("funding.html", {"request": request})


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/mode")
def api_mode():
    return {"mode": cur_mode()}


@app.post("/api/mode")
def api_set_mode(mode: str = Query(...)):
    m = mode.strip().lower()
    if m not in ["demo", "real"]:
        raise HTTPException(400, "mode must be demo or real")
    with lock:
        state["mode"] = m
    return {"mode": m}


@app.get("/api/profile")
def api_profile():
    with lock:
        return {"username": state["profile"]["username"], "mode": cur_mode()}


@app.post("/api/profile")
def api_profile_set(username: str = Query(..., min_length=2, max_length=32)):
    with lock:
        state["profile"]["username"] = username.strip()
    return {"ok": True}

@app.get("/api/bars")
def api_bars(
    symbol: str = Query(...),
    timeframe: str = Query("1Day"),
    limit: int = Query(0, ge=0, le=20000),
):
    sym = symbol.strip().upper()
    sfix = sym_fix(sym)

    df = get_df(sfix)
    if df.empty:
        raise HTTPException(404, "No data for symbol")

    df2 = df if limit == 0 else df.tail(limit)

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
    with lock:
        acc = cur_acc()
        eq = equity_value(acc)
        return JSONResponse({
            "mode": cur_mode(),
            "cash": round(float(acc["cash"]), 2),
            "equity": round(eq, 2),
            "buying_power": round(float(acc["cash"]), 2),
        })


@app.get("/api/positions")
def api_positions():
    with lock:
        acc = cur_acc()
        items = []
        for sym, p in acc["positions"].items():
            pr = last_price(sym_fix(sym))
            qty = int(p["qty"])
            avg = float(p["avg"])
            mv = qty * pr
            upl = (pr - avg) * qty
            items.append({
                "symbol": sym,
                "qty": qty,
                "avg_entry_price": round(avg, 4),
                "current_price": round(pr, 4),
                "market_value": round(mv, 2),
                "unrealized_pl": round(upl, 2),
            })
        return JSONResponse(items)


@app.get("/api/orders")
def api_orders():
    with lock:
        acc = cur_acc()
        return JSONResponse(list(reversed(acc["orders"][-200:])))


@app.post("/api/order")
def api_order(
    symbol: str = Query(...),
    qty: int = Query(..., ge=1, le=1_000_000),
    side: str = Query(...),
):
    sym = symbol.strip().upper()
    sd = side.strip().lower()
    if sd not in ["buy", "sell"]:
        raise HTTPException(400, "side must be buy or sell")

    sfix = sym_fix(sym)
    price = last_price(sfix)
    cost = qty * price

    with lock:
        acc = cur_acc()

        if sd == "buy":
            if float(acc["cash"]) < cost:
                raise HTTPException(400, "Not enough cash")

            acc["cash"] = float(acc["cash"]) - cost

            if sym not in acc["positions"]:
                acc["positions"][sym] = {"qty": qty, "avg": price}
            else:
                oldq = int(acc["positions"][sym]["qty"])
                olda = float(acc["positions"][sym]["avg"])
                newq = oldq + qty
                newa = (oldq * olda + qty * price) / newq
                acc["positions"][sym]["qty"] = newq
                acc["positions"][sym]["avg"] = newa

        else:
            if sym not in acc["positions"] or int(acc["positions"][sym]["qty"]) < qty:
                raise HTTPException(400, "Not enough shares")

            acc["positions"][sym]["qty"] = int(acc["positions"][sym]["qty"]) - qty
            acc["cash"] = float(acc["cash"]) + cost
            if int(acc["positions"][sym]["qty"]) == 0:
                del acc["positions"][sym]

        oid = int(acc["order_id"])
        acc["order_id"] = oid + 1

        acc["orders"].append({
            "id": oid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "trade",
            "symbol": sym,
            "side": sd,
            "qty": int(qty),
            "price": round(float(price), 4),
            "notional": round(float(cost), 2),
            "mode": cur_mode(),
        })

    return {"status": "filled", "order_id": oid}


@app.post("/api/reset")
def api_reset():
    with lock:
        m = cur_mode()
        state["accounts"][m] = {"cash": (10000.0 if m == "demo" else 0.0), "positions": {}, "orders": [], "order_id": 1}
    return {"ok": True}

@app.post("/api/deposit")
def api_deposit(req: DepositReq):
    if cur_mode() != "real":
        raise HTTPException(400, "Deposit works only in REAL mode")

    num = "".join(ch for ch in req.number if ch.isdigit())

    if not num.startswith("9999"):
        raise HTTPException(400, "Use FAKE card only (must start with 9999)")
    if len(num) != 16:
        raise HTTPException(400, "FAKE card must be 16 digits")
    if luhn_ok(num):
        raise HTTPException(400, "FAKE card must be INVALID (Luhn must fail)")

    with lock:
        acc = cur_acc()
        acc["cash"] = float(acc["cash"]) + float(req.amount)

        oid = int(acc["order_id"])
        acc["order_id"] = oid + 1
        acc["orders"].append({
            "id": oid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "deposit",
            "amount": round(float(req.amount), 2),
            "mode": "real",
        })

        return {"ok": True, "cash": round(float(acc["cash"]), 2)}


@app.post("/api/withdraw")
def api_withdraw(amount: float = Query(..., gt=0, le=1_000_000)):
    if cur_mode() != "real":
        raise HTTPException(400, "Withdraw works only in REAL mode")

    with lock:
        acc = cur_acc()
        if float(acc["cash"]) < float(amount):
            raise HTTPException(400, "Not enough cash")

        acc["cash"] = float(acc["cash"]) - float(amount)

        oid = int(acc["order_id"])
        acc["order_id"] = oid + 1
        acc["orders"].append({
            "id": oid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "withdraw",
            "amount": round(float(amount), 2),
            "mode": "real",
        })

        return {"ok": True, "cash": round(float(acc["cash"]), 2)}
