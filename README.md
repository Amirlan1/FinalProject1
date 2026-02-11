
# Stock Trading Platform - Unified FastAPI Application

## Description
This is a unified FastAPI application that includes:
- User registration and authentication system
- Stock charts (via yfinance)
- Trading platform in demo and real modes (via stooq)
- Deposit and withdrawal system

## Quick Setup

### Step 1: Extract Files

Extract the archive `stocking_complete.tar.gz`:

```bash
tar -xzf stocking_complete.tar.gz
```

Rename directories:

```bash
mv templates_package templates
mv static_package static
```

### Step 2: Install Dependencies

```bash
pip install fastapi uvicorn jinja2 yfinance argon2-cffi pandas requests python-multipart
```

### Step 3: Initialize the Database

```bash
python databasa.py
```

This will create the `db/` folder and the `users.db` database file with a user table.

### Step 4: Start the Application

```bash
python app_unified.py
```

Or:

```bash
uvicorn app_unified:app --host 127.0.0.1 --port 8000 --reload
```

The application will be available at: **http://127.0.0.1:8000**

## Project Structure

After installation, your project should look like this:

```
project/
├── app_unified.py          # Main application
├── databasa.py             # Database handling module
├── db/
│   └── users.db            # User database
├── templates/
│   ├── index.html          # Home page with charts
│   ├── graphic.html        # Extended charts page
│   ├── register.html       # Registration page
│   ├── login.html          # Login page
│   ├── profile.html        # User profile page
│   ├── stock.html          # Trading platform page
│   └── funding.html        # Deposit/withdraw page
└── static/
    ├── styles.css          # Styles
    └── app.js              # JavaScript for trading logic
```

## Routes Structure

### Public Pages (No authentication required)
- `GET /` - Home page with stock chart (AAPL by default)
- `GET /gra` - Extended charts page
- `POST /update_graph/` - Update chart for another ticker
- `GET /register` - Registration page
- `POST /register` - Register a new user
- `GET /login` - Login page
- `POST /login` - User login

### Protected Pages (Authentication required)
- `GET /profile` - User profile
- `GET /trading` - Trading platform
- `GET /funding` - Deposit/withdraw funds
- `GET /logout` - Logout

### API Endpoints

#### General
- `GET /api/health` - Check the health of the application
- `GET /api/mode` - Get current mode (demo/real)
- `POST /api/mode?mode=demo|real` - Switch mode

#### Profile
- `GET /api/profile` - Get profile data
- `POST /api/profile?username=...` - Update username

#### Market Data
- `GET /api/bars?symbol=AAPL&timeframe=1Day&limit=100` - Get historical data for a symbol

#### Account & Positions
- `GET /api/account` - Get account info
- `GET /api/positions` - Get open positions
- `GET /api/orders` - Get order history

#### Trading
- `POST /api/order?symbol=AAPL&qty=10&side=buy` - Place an order
- `POST /api/reset` - Reset the account

#### Finance (Only for REAL mode)
- `POST /api/deposit` - Deposit funds (JSON body)
- `POST /api/withdraw?amount=100` - Withdraw funds

## Usage

### 1. Registration and Login
1. Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
2. Click on "Register" in the top menu
3. Fill out the registration form
4. After registering, you will be redirected to the login page
5. Log in using your email and password

### 2. Viewing Charts
- The home page (`/`) displays the AAPL stock chart
- Enter any ticker (e.g., MSFT, TSLA, GOOGL) and click "Update Chart"
- For cryptocurrencies, use the format BTC-USD, ETH-USD

### 3. Trading Platform
1. After logging in, go to `/trading`
2. Enter a stock ticker (e.g., AAPL)
3. Click "Load" to display the chart
4. Use the "Buy 1" / "Sell 1" buttons to trade
5. Your positions and orders are displayed on the right

### 4. Trading Modes

#### DEMO Mode (default)
- Starts with $10,000 in virtual money
- Safe for testing
- Can reset the account by clicking "Reset"

#### REAL Mode
- Starts with $0
- Requires funding via `/funding`
- Only fake credit cards (starting with 9999) should be used

### 5. Funding Your Account (REAL Mode)
1. Switch to REAL mode
2. Go to `/funding`
3. Click "Generate FAKE card" to create a test card
4. Enter the amount and card details
5. Click "Deposit"

**IMPORTANT:** Only use fake cards! Real cards will NOT work.

## Implementation Details

### Security
- Passwords are hashed using Argon2
- HTTP-only cookies are used for sessions
- SQL injection is prevented by parameterized queries
- Passwords are trimmed to 256 characters

### Stock Data
- The homepage uses **yfinance** (Yahoo Finance) for stock data
- The trading platform uses **stooq** (more stable)
- Data is cached for 60 seconds to reduce load

### Trading Logic
- Demo account: starts with $10,000
- Real account: starts with $0
- Supports buy/sell functionality
- Automatically calculates the average entry price
- Tracks all operations

## Requirements for Fake Cards

For funding in REAL mode:
- The card MUST start with `9999`
- Length: exactly 16 digits
- The card MUST fail the Luhn check (intentionally invalid)

Example: `9999 1234 5678 9010`

## Troubleshooting

### "No module named 'databasa'" error
Make sure `databasa.py` is in the same directory as `app_unified.py`

### "Template not found" error
Ensure the `templates/` folder is in the same directory as `app_unified.py`

### 404 error for static files
Ensure the `static/` folder exists and contains `styles.css` and `app.js`

### Database not created
Manually run:
```bash
python databasa.py
```

### Trading platform charts not working
Make sure Plotly is included in `stock.html`:
```html
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
```

## Technologies

**Backend:**
- FastAPI - Web framework
- SQLite - Database
- Argon2 - Password hashing
- yfinance - Stock data from Yahoo Finance
- pandas - Data manipulation
- stooq - Alternative stock data source

**Frontend:**
- Jinja2 - Templating
- Chart.js - Charts on the home page
- Plotly.js - Interactive charts on the trading platform
- Vanilla JavaScript - Frontend logic
- Custom CSS - Styling

## License

This is an educational project. Do not use for real trading!

## Support

For troubleshooting, check:
1. All dependencies are installed
2. The database is initialized
3. Folder structure matches the description
4. Port 8000 is available

For debugging, run with the `--reload` flag:
```bash
uvicorn app_unified:app --reload
```
