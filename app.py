from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secretkey"

# ---------------- DB ---------------- #

def get_db():
    conn = sqlite3.connect("db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        status TEXT
    )
    ''')

    # TREKS
    cur.execute('''
    CREATE TABLE IF NOT EXISTS treks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        location TEXT,
        difficulty TEXT,
        duration INTEGER,
        slots INTEGER,
        staff_id INTEGER,
        status TEXT,
        start_date TEXT,
        end_date TEXT
    )
    ''')

    # BOOKINGS
    cur.execute('''
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        trek_id INTEGER,
        booking_date TEXT,
        status TEXT
    )
    ''')

    conn.commit()

    # DEFAULT ADMIN
    cur.execute("SELECT * FROM users WHERE role='admin'")
    if not cur.fetchone():
        cur.execute('''
        INSERT INTO users(name,email,password,role,status)
        VALUES('Admin','admin@gmail.com','admin123','admin','active')
        ''')
        conn.commit()


init_db()

# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    return render_template("login.html")


# ✅ REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        status = "pending" if role == "staff" else "active"

        conn = get_db()
        conn.execute(
            "INSERT INTO users(name,email,password,role,status) VALUES(?,?,?,?,?)",
            (name, email, password, role, status)
        )
        conn.commit()

        return redirect("/")

    return render_template("register.html")


# ✅ LOGIN
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, password)
    ).fetchone()

    if user:
        if user["status"] != "active":
            return "Account not approved ❌"

        session["user_id"] = user["id"]
        session["role"] = user["role"]

        if user["role"] == "admin":
            return redirect("/admin")
        elif user["role"] == "staff":
            return redirect("/staff")
        else:
            return redirect("/user")

    return "Invalid credentials ❌"


# ✅ ADMIN DASHBOARD
@app.route("/admin")
def admin():
    conn = get_db()

    # ✅ JOIN treks with staff users table
    treks = conn.execute("""
        SELECT treks.*,
               users.name AS staff_name
        FROM treks
        LEFT JOIN users ON treks.staff_id = users.id
    """).fetchall()

    users = conn.execute("SELECT * FROM users").fetchall()

    pending_staff = conn.execute(
        "SELECT * FROM users WHERE role='staff' AND status='pending'"
    ).fetchall()

    staff_list = conn.execute(
        "SELECT * FROM users WHERE role='staff' AND status='active'"
    ).fetchall()

    bookings = conn.execute("""
        SELECT bookings.id,
               users.name AS user_name,
               treks.name AS trek_name,
               bookings.booking_date,
               bookings.status
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN treks ON bookings.trek_id = treks.id
    """).fetchall()

    return render_template(
        "admin_dashboard.html",
        treks=treks,
        users=users,
        bookings=bookings,
        pending_staff=pending_staff,
        staff_list=staff_list
    )

    return render_template(
        "admin_dashboard.html",
        treks=treks,
        users=users,
        bookings=bookings,
        pending_staff=pending_staff,
        staff_list=staff_list
    )

# ✅ CREATE TREK
@app.route("/create_trek", methods=["POST"])
def create_trek():
    print(request.form)   # ✅ debug

    name = request.form["name"]
    location = request.form["location"]
    difficulty = request.form["difficulty"]
    duration = int(request.form["duration"])   # ✅ important
    slots = int(request.form["slots"])         # ✅ important

    conn = get_db()
    conn.execute("""
        INSERT INTO treks(name, location, difficulty, duration, slots, status)
        VALUES (?, ?, ?, ?, ?, 'open')
    """, (name, location, difficulty, duration, slots))

    conn.commit()

    return redirect("/admin")



# ✅ USER DASHBOARD
@app.route("/user")
def user_dashboard():
    user_id = session["user_id"]

    conn = get_db()

    # ✅ Available treks
    treks = conn.execute(
        "SELECT * FROM treks WHERE status='open'"
    ).fetchall()

    # ✅ ONLY this user's bookings
    bookings = conn.execute("""
        SELECT bookings.id, treks.name AS trek_name,
               bookings.booking_date, bookings.status
        FROM bookings
        JOIN treks ON bookings.trek_id = treks.id
        WHERE bookings.user_id=?
    """, (user_id,)).fetchall()

    return render_template("user_dashboard.html",
                           treks=treks,
                           bookings=bookings)

# ✅ BOOK TREK
@app.route("/book/<int:trek_id>")
def book_trek(trek_id):
    user_id = session["user_id"]

    conn = get_db()

    # ✅ CHECK IF ALREADY BOOKED
    existing = conn.execute(
        "SELECT * FROM bookings WHERE user_id=? AND trek_id=?",
        (user_id, trek_id)
    ).fetchone()

    if existing:
        return "Already booked this trek ❌"

    # ✅ GET TREK DETAILS
    trek = conn.execute(
        "SELECT * FROM treks WHERE id=?",
        (trek_id,)
    ).fetchone()

    # ✅ CHECK SLOT AVAILABILITY
    if trek["slots"] <= 0:
        return "No slots available ❌"

    # ✅ REDUCE SLOT
    conn.execute(
        "UPDATE treks SET slots = slots - 1 WHERE id=?",
        (trek_id,)
    )

    # ✅ INSERT BOOKING
    conn.execute("""
        INSERT INTO bookings(user_id, trek_id, booking_date, status)
        VALUES (?, ?, ?, 'booked')
    """, (user_id, trek_id, datetime.now()))

    conn.commit()

    return redirect("/user")


# ✅ STAFF DASHBOARD
@app.route("/staff")
def staff_dashboard():
    staff_id = session["user_id"]

    conn = get_db()

    # ✅ Get assigned treks
    treks = conn.execute(
        "SELECT * FROM treks WHERE staff_id=?",
        (staff_id,)
    ).fetchall()

    # ✅ Get bookings + user names for these treks
    bookings = conn.execute("""
        SELECT bookings.id,
               users.name AS user_name,
               treks.name AS trek_name,
               bookings.booking_date,
               bookings.status
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN treks ON bookings.trek_id = treks.id
        WHERE treks.staff_id=?
    """, (staff_id,)).fetchall()

    return render_template("staff_dashboard.html",
                           treks=treks,
                           bookings=bookings)

@app.route("/approve_staff/<int:staff_id>")
def approve_staff(staff_id):
    conn = get_db()

    conn.execute(
        "UPDATE users SET status='active' WHERE id=?",
        (staff_id,)
    )
    conn.commit()

    return redirect("/admin")

@app.route("/assign_staff", methods=["POST"])
@app.route("/assign_staff", methods=["POST"])
@app.route("/assign_staff", methods=["POST"])
def assign_staff():
    print("Assign hit ✅")   # DEBUG

    trek_id = request.form["trek_id"]
    staff_id = request.form["staff_id"]

    conn = get_db()
    conn.execute(
        "UPDATE treks SET staff_id=? WHERE id=?",
        (staff_id, trek_id)
    )
    conn.commit()

    return redirect("/admin")

@app.route("/update_trek", methods=["POST"])
def update_trek():
    trek_id = request.form["trek_id"]
    slots = int(request.form["slots"])
    status = request.form["status"]

    conn = get_db()

    conn.execute(
        "UPDATE treks SET slots=?, status=? WHERE id=?",
        (slots, status, trek_id)
    )

    conn.commit()

    return redirect("/staff")

# ✅ RUN
if __name__ == "__main__":
    app.run(debug=True)