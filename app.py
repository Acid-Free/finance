import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    rows = db.execute(
        "SELECT * FROM portfolio join users on user_id = users.id WHERE user_id = ?",
        session["user_id"])

    for row in rows:
        update_share_price(row)

    user_balance = db.execute(
        "SELECT * FROM users WHERE id = ? ", session["user_id"])[0]["cash"]

    return render_template("index.html", rows=rows, user_balance=user_balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        raw_symbol = request.form.get("symbol")
        if not raw_symbol:
            return apology("must provide symbol", 400)

        lookup_result = lookup(raw_symbol)
        if not lookup_result:
            return apology("symbol is invalid", 400)

        share_count = request.form.get("shares")
        if not share_count:
            return apology("must provide shares", 400)

        share_count = int(share_count)
        if share_count < 1:
            return apology("shares must be at least 1", 400)

        # Extract lookup result
        name = lookup_result["name"]
        price = float(lookup_result["price"])
        symbol = lookup_result["symbol"]

        # Query database for balance
        row = db.execute(
            "SELECT cash FROM users WHERE id = ?", session["user_id"])
        balance = row[0]["cash"]

        # Check if user can purchase the stock
        total_cost = price * share_count

        if (total_cost > balance):
            return apology("cash balance not enough", 400)

        # Get current date time
        current_datetime = datetime.now().strftime("%m/%d/%Y: %H:%M:%S")

        # Check if portfolio entry already exists (should be the same price too, for now different priced entry are considered different)
        rows = db.execute(
            "SELECT * FROM portfolio WHERE symbol = ? AND user_id = ? AND price = ?", symbol, session["user_id"], price)
        if len(rows) == 0:
            db.execute("INSERT INTO portfolio (user_id, symbol, name, shares, price, date) VALUES (?, ?, ?, ?, ?, ?)",
                       session["user_id"], symbol, name, share_count, price, current_datetime)
        else:
            current_share_id = rows[0]["id"]
            current_share_count = rows[0]["shares"] + share_count

            db.execute("UPDATE portfolio SET shares = ?, date = ? WHERE id = ?",
                       current_share_count, current_datetime, current_share_id)

        # Decrease user account balance
        new_balance = balance - total_cost
        db.execute("UPDATE users SET cash=? WHERE id=?",
                   new_balance, session["user_id"])

        # Add transaction history entry
        db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, date) VALUES (?, ?, ?, ?, ?, ?)",
                   session["user_id"], symbol, name, share_count, price, current_datetime)

        flash_text = "Successfully purchased {0} {1} for {2}."
        flash(flash_text.format(share_count, symbol, usd(total_cost)))

        return redirect("/")
    else:
        return render_template("buy.html")


@ app.route("/history")
@ login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


@ app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id but maintain flashed messages
    flashes = session.get("_flashes")
    session.clear()
    if flashes:
        session["_flashes"] = flashes

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@ app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@ app.route("/quote", methods=["GET", "POST"])
@ login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        raw_symbol = request.form.get("symbol")
        if not raw_symbol:
            return apology("must provide symbol", 400)

        lookup_result = lookup(raw_symbol)
        if not lookup_result:
            return apology("symbol is invalid", 400)

        # Extract lookup result
        name = lookup_result["name"]
        price = lookup_result["price"]
        symbol = lookup_result["symbol"]

        return render_template("quoted.html", name=name, price=price, symbol=symbol)
    else:
        return render_template("quote.html")


@ app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    username = request.form.get("username")

    if request.method == "POST":
        if not username:
            return apology("must provide username", 403)

        username_row = db.execute("SELECT * FROM users WHERE username = ?",
                                  request.form.get("username"))

        if len(username_row) > 0:
            return apology("username already exists", 403)

        password = request.form.get("password")
        password_confirm = request.form.get("password-confirm")

        if not password:
            return apology("must provide password", 403)

        if not password_confirm:
            return apology("must provide password confirmation", 403)

        if password != password_confirm:
            return apology("must match password", 403)

        # Performed if inputs are valid
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                   username, generate_password_hash(password))

        flash("Account created successfully.")
        return redirect("/login")
    else:
        print("test1")
        return render_template("register.html")


@ app.route("/sell", methods=["GET", "POST"])
@ login_required
def sell():
    """Sell shares of stock"""
    # TODO: refactor to remove repetition in buy()
    if request.method == "POST":
        raw_symbol = request.form.get("symbol")
        if not raw_symbol:
            return apology("must provide symbol", 400)

        lookup_result = lookup(raw_symbol)
        if not lookup_result:
            return apology("symbol is invalid", 400)

        share_count = request.form.get("shares")
        if not share_count:
            return apology("must provide shares", 400)

        share_count = int(share_count)
        if share_count < 1:
            return apology("shares must be at least 1", 400)

        # Extract lookup result
        name = lookup_result["name"]
        price = float(lookup_result["price"])
        symbol = lookup_result["symbol"]

        # Check if share exists in account
        rows = db.execute(
            "SELECT * FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])
        if len(rows) == 0:
            return apology("You don't have this stock", 400)

        # Check if sufficient number of share exists
        current_share_count = rows[0]["shares"]
        if current_share_count < share_count:
            return apology("Insufficient share count", 400)

        # Get current date time
        current_datetime = datetime.now().strftime("%m/%d/%Y: %H:%M:%S")

        # Update portfolio: delete entry if share count will become 0
        new_share_count = current_share_count - share_count
        if new_share_count == 0:
            rows = db.execute(
                "DELETE FROM portfolio WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])
        else:
            rows = db.execute("UPDATE portfolio SET shares = ?, price = ? WHERE symbol = ? AND user_id = ?",
                              new_share_count, price, symbol, session["user_id"])

        # Update user account
        sell_price = price * share_count
        rows = db.execute("UPDATE users SET cash = cash + ? WHERE id = ?",
                          sell_price, session["user_id"])

        # Update transactions
        db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, date) VALUES (?, ?, ?, ?, ?, ?)",
                   session["user_id"], symbol, name, -share_count, price, current_datetime)

        flash_text = "Successfully sold {0} {1} for {2}"
        flash(flash_text.format(share_count, symbol, usd(sell_price)))

        return redirect("/")
    else:
        return render_template("sell.html")


# Updates the share price of a particular share on current user
def update_share_price(row):
    symbol = row["symbol"]
    price = float(lookup(symbol)["price"])
    db.execute("UPDATE portfolio SET price = ? WHERE symbol = ?", price, symbol)
