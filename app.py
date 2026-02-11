from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import yfinance as yf
from datetime import datetime
import uvicorn
from databasa import create_users_table, get_db, create_password_resets_table
import sqlite3
from fastapi import status
import os
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pathlib import Path
from security import forgot_password, reset_password
from pydantic import BaseModel, Field
import io
import time
import threading
import requests
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
db_folder = BASE_DIR / "db"
db_path = db_folder / "users.db"

ph = PasswordHasher()
app = FastAPI()

templates = Jinja2Templates(directory="templates")

try:
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
except:
    pass

create_users_table()
create_password_resets_table()

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


class TradeReq(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    action: str = Field(..., description="open|close")
    side: str | None = Field(None, description="long|short (needed for open)")
    qty: int = Field(..., ge=1, le=1_000_000)
    leverage: float | None = Field(None, ge=1, le=50)


class DepositReq(BaseModel):
    amount: float = Field(..., gt=0, le=1_000_000)
    name: str = Field(..., min_length=2, max_length=64)
    number: str = Field(..., min_length=12, max_length=32)
    exp: str = Field(..., min_length=4, max_length=7)
    cvc: str = Field(..., min_length=3, max_length=4)

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


def liq_price(entry: float, lev: float, side: str) -> float:
    if lev <= 1:
        return 0.0 if side == "long" else entry * 2
    if side == "long":
        return max(0.0, entry * (1.0 - 1.0 / lev))
    else:
        return entry * (1.0 + 1.0 / lev)


def pos_pnl(entry: float, price: float, qty: int, side: str) -> float:
    if side == "long":
        return (price - entry) * qty
    else:
        return (entry - price) * qty


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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    
    try:
        return templates.TemplateResponse("stock.html", {"request": request})
    except:
        ticker = "AAPL"
        stock_data, err = await get_stock_data(ticker)
        chart_data = {
            "labels": [str(item['Date']).split()[0] for item in stock_data],
            "data": [item['Close'] for item in stock_data]
        }
        return templates.TemplateResponse("index.html", {"request": request, "chart_data": chart_data, "ticker": ticker})


@app.get("/gra", response_class=HTMLResponse)
async def graphic(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    
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
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def post_register(username: str = Form(...), password: str = Form(...), email: str = Form(None)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    safe_password = password[:256]  
    hashed_pass = ph.hash(safe_password)
    email = email.strip().lower()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password, email) VALUES (?, ?, ?)
        ''', (username, hashed_pass, email))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse("register.html", {
            "request": None,
            "error": "User with this email already exists"
        })
    
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
    email = email.strip().lower()
    cursor.execute(
        "SELECT id, password, username FROM users WHERE email = ?",
        (email,)
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "User not found"
        })

    user_id, hashed_pass, username = user

    try:
        ph.verify(hashed_pass, password)
    except VerifyMismatchError:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Wrong password"
        })

    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="user_id", value=str(user_id))
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("user_id")
    return response


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


@app.get("/funding", response_class=HTMLResponse)
def funding_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("funding.html", {"request": request})


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_submit(request: Request, email: str = Form(...)):
    result = await forgot_password(email)
    if "error" in result:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request, 
            "error": result["error"]
        })
    return templates.TemplateResponse("forgot_password.html", {
        "request": request, 
        "message": result["message"]
    })


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = Query(...)):
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token
    })


@app.post("/reset-password", response_class=HTMLResponse)
async def reset_password_submit(request: Request, token: str = Form(...), new_password: str = Form(...)):
    result = await reset_password(token, new_password)
    if "error" in result:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "error": result["error"]
        })
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token,
        "message": result["message"]
    })


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

            side = p.get("side", "long")
            qty = int(p["qty"])
            entry = float(p["entry"])
            lev = float(p.get("leverage", 1.0))
            margin = float(p.get("margin", 0.0))

            pnl = pos_pnl(entry, pr, qty, side)
            mv = qty * pr

            items.append({
                "symbol": sym,
                "side": side,
                "qty": qty,
                "entry_price": round(entry, 4),
                "current_price": round(pr, 4),
                "market_value": round(mv, 2),
                "leverage": lev,
                "margin": round(margin, 2),
                "unrealized_pl": round(pnl, 2),
                "liq_price": round(liq_price(entry, lev, side), 4),
            })
        return JSONResponse(items)


@app.post("/api/trade")
def api_trade(req: TradeReq):
    sym = req.symbol.strip().upper()
    act = req.action.strip().lower()
    if act not in ["open", "close"]:
        raise HTTPException(400, "action must be open or close")

    with lock:
        acc = cur_acc()
        positions = acc["positions"]

    sfix = sym_fix(sym)
    price = last_price(sfix)

    with lock:
        acc = cur_acc()
        positions = acc["positions"]

        if act == "open":
            side = (req.side or "").strip().lower()
            if side not in ["long", "short"]:
                raise HTTPException(400, "side must be long or short for open")

            lev = float(req.leverage or 1.0)
            if lev < 1:
                lev = 1.0

            if sym in positions and positions[sym].get("side") != side:
                raise HTTPException(400, "You already have opposite position on this symbol. Close it first.")

            notional = req.qty * price
            margin_need = notional / lev

            if float(acc["cash"]) < margin_need:
                raise HTTPException(400, "Not enough cash for margin")

            acc["cash"] = float(acc["cash"]) - margin_need

            if sym not in positions:
                positions[sym] = {
                    "side": side,
                    "qty": int(req.qty),
                    "entry": float(price),
                    "leverage": float(lev),
                    "margin": float(margin_need),
                }
            else:
                old = positions[sym]
                if float(old.get("leverage", 1.0)) != float(lev):
                    raise HTTPException(400, "Leverage must match existing position (close first to change).")

                oldq = int(old["qty"])
                olde = float(old["entry"])
                newq = oldq + int(req.qty)
                newe = (oldq * olde + int(req.qty) * price) / newq

                old["qty"] = newq
                old["entry"] = newe
                old["margin"] = float(old.get("margin", 0.0)) + float(margin_need)

            oid = int(acc["order_id"])
            acc["order_id"] = oid + 1
            acc["orders"].append({
                "id": oid,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "type": "trade",
                "symbol": sym,
                "action": "open",
                "side": side,
                "qty": int(req.qty),
                "price": round(float(price), 4),
                "leverage": float(lev),
                "mode": cur_mode(),
            })

            return {"ok": True}

        if sym not in positions:
            raise HTTPException(400, "No position to close for this symbol")

        p = positions[sym]
        side = p.get("side", "long")
        qty_have = int(p["qty"])
        if req.qty > qty_have:
            raise HTTPException(400, "Close qty is bigger than position qty")

        entry = float(p["entry"])
        lev = float(p.get("leverage", 1.0))
        margin_total = float(p.get("margin", 0.0))

        frac = req.qty / qty_have
        margin_release = margin_total * frac

        pnl = pos_pnl(entry, price, int(req.qty), side)

        acc["cash"] = float(acc["cash"]) + float(margin_release) + float(pnl)

        left = qty_have - int(req.qty)
        if left == 0:
            del positions[sym]
        else:
            p["qty"] = left
            p["margin"] = margin_total - margin_release

        oid = int(acc["order_id"])
        acc["order_id"] = oid + 1
        acc["orders"].append({
            "id": oid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "trade",
            "symbol": sym,
            "action": "close",
            "side": side,
            "qty": int(req.qty),
            "price": round(float(price), 4),
            "mode": cur_mode(),
        })

        return {"ok": True}


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
        state["accounts"][m] = {
            "cash": (10000.0 if m == "demo" else 0.0), 
            "positions": {}, 
            "orders": [], 
            "order_id": 1
        }
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


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
