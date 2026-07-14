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


#  REGISTER
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
        if user["status"] == "blocked":
            return "You are blocked by Admin  "

        if user["status"] != "active":
            return "Account not approved "

        session["user_id"] = user["id"]
        session["role"] = user["role"]

        if user["role"] == "admin":
            return redirect("/admin")
        elif user["role"] == "staff":
            return redirect("/staff")
        else:
            return redirect("/user")

    return "Invalid credentials "


@app.route("/admin")
def admin():
    conn = get_db()

    trek_count = conn.execute(
    "SELECT COUNT(*) FROM treks"
    ).fetchone()[0]

    user_count = conn.execute(
    "SELECT COUNT(*) FROM users WHERE role='user'"
    ).fetchone()[0]

    staff_count = conn.execute(
    "SELECT COUNT(*) FROM users WHERE role='staff'"
    ).fetchone()[0]

    booking_count = conn.execute(
    "SELECT COUNT(*) FROM bookings"
    ).fetchone()[0]

    
    
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
    trek_count=trek_count,
    user_count=user_count,
    staff_count=staff_count,
    booking_count=booking_count,
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

    return render_template(
        "admin_dashboard.html",
        treks=treks,
        users=users,
        bookings=bookings,
        pending_staff=pending_staff,
        staff_list=staff_list
    )

    


@app.route("/create_trek", methods=["POST"])
def create_trek():
    print(request.form)   

    name = request.form["name"]
    location = request.form["location"]
    difficulty = request.form["difficulty"]
    duration = int(request.form["duration"])   
    slots = int(request.form["slots"])         

    conn = get_db()
    conn.execute("""
        INSERT INTO treks(name, location, difficulty, duration, slots, status)
        VALUES (?, ?, ?, ?, ?, 'open')
    """, (name, location, difficulty, duration, slots))

    conn.commit()

    return redirect("/admin")




@app.route("/user")
def user_dashboard():
    user_id = session["user_id"]

    conn = get_db()

   
    treks = conn.execute(
        "SELECT * FROM treks WHERE status='open'"
    ).fetchall()

    
    bookings = conn.execute("""
        SELECT bookings.id, treks.name AS trek_name,
               bookings.booking_date, bookings.status
        FROM bookings
        JOIN treks ON bookings.trek_id = treks.id
        WHERE bookings.user_id=?
    """, (user_id,)).fetchall()
    
    user = conn.execute(
    "SELECT * FROM users WHERE id=?",
    (user_id,)
    ).fetchone()

    return render_template(
    "user_dashboard.html",
    treks=treks,
    bookings=bookings,
    user=user
)


@app.route("/book/<int:trek_id>")
def book_trek(trek_id):
    user_id = session["user_id"]

    conn = get_db()

    existing = conn.execute(
        "SELECT * FROM bookings WHERE user_id=? AND trek_id=?",
        (user_id, trek_id)
    ).fetchone()

    if existing:
        return "Already booked this trek "

    
    trek = conn.execute(
        "SELECT * FROM treks WHERE id=?",
        (trek_id,)
    ).fetchone()

    
    if trek["slots"] <= 0:
        return "No slots available "

   
    conn.execute(
        "UPDATE treks SET slots = slots - 1 WHERE id=?",
        (trek_id,)
    )

    
    conn.execute("""
        INSERT INTO bookings(user_id, trek_id, booking_date, status)
        VALUES (?, ?, ?, 'booked')
    """, (user_id, trek_id, datetime.now()))

    conn.commit()

    return redirect("/user")


#  STAFF DASHBOARD
@app.route("/staff")
def staff_dashboard():
    staff_id = session["user_id"]

    conn = get_db()

    #  Get assigned treks
    treks = conn.execute(
        "SELECT * FROM treks WHERE staff_id=?",
        (staff_id,)
    ).fetchall()

    #  Get bookings + user names for these treks
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
    print("Assign hit ")   # DEBUG

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

@app.route("/update_trek_add", methods=["POST"])
def update_trek_add():
    trek_id = request.form["trek_id"]
    slots = int(request.form["slots"])
    status = request.form["status"]

    conn = get_db()

    conn.execute(
        "UPDATE treks SET slots=?, status=? WHERE id=?",
        (slots, status, trek_id)
    )

    conn.commit()

    return redirect("/admin")

@app.route("/block_user", methods=["POST"])
def block_user():

    print("BLOCK HIT ")

    user_id = request.form["user_id"]

    conn = get_db()

    conn.execute(
        "UPDATE users SET status='blocked' WHERE id=?",
        (user_id,)
    )

    conn.commit()

    return redirect("/admin")

@app.route("/unblock_user", methods=["POST"])
def unblock_user():

    print("UNBLOCK HIT ")

    user_id = request.form["user_id"]

    conn = get_db()

    conn.execute(
        "UPDATE users SET status='active' WHERE id=?",
        (user_id,)
    )

    conn.commit()

    return redirect("/admin")

@app.route("/update_participant", methods=["POST"])
def update_participant():

    booking_id = request.form["booking_id"]
    status = request.form["status"]

    conn = get_db()

    conn.execute(
        "UPDATE bookings SET status=? WHERE id=?",
        (status, booking_id)
    )

    conn.commit()

    return redirect("/staff")


@app.route("/check_users")
def check_users():

    conn = get_db()

    users = conn.execute(
        "SELECT * FROM users"
    ).fetchall()

    for user in users:
        print(dict(user))

    return "Check terminal"


@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():

    user_id = session["user_id"]

    conn = get_db()

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")

        conn.execute(
            "UPDATE users SET name=?, email=? WHERE id=?",
            (name, email, user_id)
        )

        conn.commit()

        return redirect("/user")

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    return render_template(
        "edit_profile.html",
        user=user
    )


#  RUN
if __name__ == "__main__":
    app.run(debug=True)
