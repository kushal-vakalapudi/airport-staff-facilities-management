import csv
import io
import logging
import os
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from functools import wraps
from secrets import token_urlsafe

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from mysql.connector import Error as MySQLError

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or os.urandom(32)
app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STAFF_FIELDS = [
    ("Name", "Name", "text", True),
    ("Department", "Department", "text", True),
    ("Designation", "Designation", "text", True),
    ("Email", "Email", "email", True),
    ("Phone", "Phone", "text", False),
    ("Shift", "Shift", "select:Morning|Evening|Night|Rotational", True),
    ("StaffStatus", "Status", "select:ACTIVE|INACTIVE", True),
]
@app.template_filter("singular")
def singular(value):
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


@app.template_filter("display")
def display_value(value):
    if value is None:
        return "—"
    if isinstance(value, timedelta):
        total_minutes = int(value.total_seconds() // 60)
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return value


@app.template_filter("input_value")
def input_value(value, kind):
    if value is None:
        return ""
    if kind == "time" and isinstance(value, timedelta):
        total_minutes = int(value.total_seconds() // 60)
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    if kind == "date" and isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value)


FACILITY_FIELDS = [
    ("FacilityName", "Facility name", "text", True),
    ("FacilityType", "Facility type", "select:LOUNGE|REST_AREA|CHANGING_ROOM|RECREATION_ROOM|MEDICAL_ROOM|TRAINING_ROOM|CAFETERIA", True),
    ("Location", "Location", "text", True),
    ("Capacity", "Capacity", "number", True),
    ("AvailabilityStatus", "Availability", "select:AVAILABLE|UNAVAILABLE", True),
]

MODULES = {
    "staff": {
        "title": "Staff",
        "icon": "people",
        "table": "STAFF",
        "pk": "StaffID",
        "fields": STAFF_FIELDS,
        "columns": [("StaffID", "ID"), ("Name", "Name"), ("Department", "Department"), ("Designation", "Designation"), ("Email", "Email"), ("Shift", "Shift"), ("StaffStatus", "Status")],
        "query": "SELECT StaffID, Name, Department, Designation, Email, Phone, Shift, StaffStatus FROM STAFF ORDER BY StaffID DESC",
        "search": ["Name", "Department", "Email"],
    },
    "facilities": {
        "title": "Facilities",
        "icon": "building",
        "table": "STAFF_FACILITY",
        "pk": "FacilityID",
        "fields": FACILITY_FIELDS,
        "columns": [("FacilityID", "ID"), ("FacilityName", "Facility"), ("FacilityType", "Type"), ("Location", "Location"), ("Capacity", "Capacity"), ("AvailabilityStatus", "Availability")],
        "query": "SELECT FacilityID, FacilityName, FacilityType, Location, Capacity, AvailabilityStatus FROM STAFF_FACILITY ORDER BY FacilityID DESC",
        "search": ["FacilityName", "Location", "FacilityType"],
    },
    "access": {
        "title": "Facility access",
        "icon": "door-open",
        "table": "FACILITY_ACCESS",
        "pk": "AccessID",
        "fields": [
            ("StaffID", "Staff member", "ref:staff", True),
            ("FacilityID", "Facility", "ref:facility", True),
            ("AccessDate", "Access date", "date", True),
            ("AccessTime", "Access time", "time", True),
        ],
        "columns": [("AccessID", "ID"), ("StaffName", "Staff"), ("FacilityName", "Facility"), ("AccessDate", "Date"), ("AccessTime", "Time")],
        "query": "SELECT a.AccessID, a.StaffID, a.FacilityID, s.Name AS StaffName, f.FacilityName, a.AccessDate, a.AccessTime FROM FACILITY_ACCESS a JOIN STAFF s ON s.StaffID=a.StaffID JOIN STAFF_FACILITY f ON f.FacilityID=a.FacilityID ORDER BY a.AccessDate DESC, a.AccessTime DESC",
        "search": ["StaffName", "FacilityName"],
    },
    "bookings": {
        "title": "Bookings",
        "icon": "calendar-check",
        "table": "FACILITY_BOOKING",
        "pk": "BookingID",
        "fields": [
            ("StaffID", "Staff member", "ref:staff", True),
            ("FacilityID", "Facility", "ref:facility", True),
            ("BookingDate", "Booking date", "date", True),
            ("StartTime", "Start time", "time", True),
            ("EndTime", "End time", "time", True),
            ("BookingStatus", "Status", "select:PENDING|CONFIRMED", True),
        ],
        "columns": [("BookingID", "ID"), ("StaffName", "Staff"), ("FacilityName", "Facility"), ("BookingDate", "Date"), ("StartTime", "Start"), ("EndTime", "End"), ("BookingStatus", "Status")],
        "query": "SELECT b.BookingID, b.StaffID, b.FacilityID, s.Name AS StaffName, f.FacilityName, b.BookingDate, b.StartTime, b.EndTime, b.BookingStatus, CASE WHEN (b.BookingDate<CURRENT_DATE() OR (b.BookingDate=CURRENT_DATE() AND b.EndTime<CURRENT_TIME())) THEN 1 ELSE 0 END AS IsCompletable FROM FACILITY_BOOKING b JOIN STAFF s ON s.StaffID=b.StaffID JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID ORDER BY b.BookingDate DESC, b.StartTime",
        "search": ["StaffName", "FacilityName", "BookingStatus"],
    },
    "parking": {
        "title": "Staff parking",
        "icon": "car-front",
        "table": "STAFF_PARKING",
        "pk": "ParkingID",
        "fields": [
            ("StaffID", "Staff member", "ref:staff", True),
            ("VehicleNumber", "Vehicle number", "text", True),
            ("VehicleType", "Vehicle type", "text", True),
            ("ParkingArea", "Parking area", "text", True),
            ("ParkingSlot", "Parking slot", "text", True),
            ("ValidFrom", "Valid from", "date", True),
            ("ValidUntil", "Valid until", "date", False),
        ],
        "columns": [("ParkingID", "ID"), ("StaffName", "Staff"), ("VehicleNumber", "Vehicle"), ("VehicleType", "Type"), ("ParkingArea", "Area"), ("ParkingSlot", "Slot"), ("ValidFrom", "From"), ("ValidUntil", "Until"), ("AllocationStatus", "Status")],
        "query": "SELECT p.ParkingID, p.StaffID, s.Name AS StaffName, p.VehicleNumber, p.VehicleType, p.ParkingArea, p.ParkingSlot, p.ValidFrom, p.ValidUntil, p.AllocationStatus FROM STAFF_PARKING p JOIN STAFF s ON s.StaffID=p.StaffID ORDER BY p.ParkingID DESC",
        "search": ["StaffName", "VehicleNumber", "ParkingArea", "ParkingSlot"],
    },
    "lockers": {
        "title": "Lockers",
        "icon": "lock",
        "table": "LOCKER",
        "pk": "LockerID",
        "fields": [
            ("LockerNumber", "Locker number", "text", True),
            ("Location", "Location", "text", True),
            ("LockerType", "Locker type", "select:STANDARD|LARGE|SECURE", True),
        ],
        "columns": [("LockerID", "ID"), ("LockerNumber", "Locker"), ("Location", "Location"), ("LockerType", "Type"), ("Status", "Status")],
        "query": "SELECT LockerID, LockerNumber, Location, LockerType, Status FROM LOCKER ORDER BY Location, LockerNumber",
        "search": ["LockerNumber", "Location", "LockerType", "Status"],
    },
    "locker-allocations": {
        "title": "Locker allocations",
        "icon": "key",
        "table": "LOCKER_ALLOCATION",
        "pk": "AllocationID",
        "fields": [
            ("LockerID", "Available locker", "ref:locker", True),
            ("StaffID", "Staff member", "ref:staff", True),
            ("AllocationDate", "Allocation date", "date", True),
        ],
        "columns": [("AllocationID", "ID"), ("LockerNumber", "Locker"), ("StaffName", "Staff"), ("AllocationDate", "Allocated"), ("ReturnDate", "Returned"), ("Status", "Status")],
        "query": "SELECT a.AllocationID, a.LockerID, a.StaffID, l.LockerNumber, s.Name AS StaffName, a.AllocationDate, a.ReturnDate, a.Status FROM LOCKER_ALLOCATION a JOIN LOCKER l ON l.LockerID=a.LockerID JOIN STAFF s ON s.StaffID=a.StaffID ORDER BY a.AllocationID DESC",
        "search": ["LockerNumber", "StaffName", "Status"],
    },
    "training-rooms": {
        "title": "Training rooms",
        "icon": "easel",
        "table": "TRAINING_ROOM",
        "pk": "TrainingRoomID",
        "fields": [
            ("FacilityID", "Linked facility", "ref:training-facility", True),
            ("RoomNumber", "Room number", "text", True),
            ("Capacity", "Capacity", "number", True),
            ("EquipmentAvailable", "Equipment", "text", False),
        ],
        "columns": [("TrainingRoomID", "ID"), ("RoomNumber", "Room"), ("FacilityName", "Facility"), ("Location", "Location"), ("Capacity", "Capacity"), ("EquipmentAvailable", "Equipment")],
        "query": "SELECT t.TrainingRoomID, t.FacilityID, t.RoomNumber, f.FacilityName, f.Location, t.Capacity, t.EquipmentAvailable FROM TRAINING_ROOM t JOIN STAFF_FACILITY f ON f.FacilityID=t.FacilityID ORDER BY t.RoomNumber",
        "search": ["RoomNumber", "FacilityName", "Location"],
    },
    "cafeterias": {
        "title": "Cafeterias",
        "icon": "cup-hot",
        "table": "CAFETERIA",
        "pk": "CafeteriaID",
        "fields": [
            ("FacilityID", "Linked facility", "ref:cafeteria-facility", True),
            ("CafeteriaName", "Cafeteria name", "text", True),
            ("Location", "Location", "text", True),
            ("Capacity", "Capacity", "number", True),
        ],
        "columns": [("CafeteriaID", "ID"), ("CafeteriaName", "Cafeteria"), ("FacilityName", "Facility"), ("Location", "Location"), ("Capacity", "Capacity")],
        "query": "SELECT c.CafeteriaID, c.FacilityID, c.CafeteriaName, f.FacilityName, c.Location, c.Capacity FROM CAFETERIA c JOIN STAFF_FACILITY f ON f.FacilityID=c.FacilityID ORDER BY c.CafeteriaName",
        "search": ["CafeteriaName", "FacilityName", "Location"],
    },
    "meals": {
        "title": "Meal schedules",
        "icon": "calendar2-week",
        "table": "MEAL_SCHEDULE",
        "pk": "MealID",
        "fields": [
            ("CafeteriaID", "Cafeteria", "ref:cafeteria", True),
            ("MealType", "Meal type", "select:BREAKFAST|LUNCH|SNACKS|DINNER", True),
            ("MealDate", "Meal date", "date", True),
            ("StartTime", "Start time", "time", True),
            ("EndTime", "End time", "time", True),
        ],
        "columns": [("MealID", "ID"), ("CafeteriaName", "Cafeteria"), ("MealType", "Meal"), ("MealDate", "Date"), ("StartTime", "Start"), ("EndTime", "End")],
        "query": "SELECT m.MealID, m.CafeteriaID, c.CafeteriaName, m.MealType, m.MealDate, m.StartTime, m.EndTime FROM MEAL_SCHEDULE m JOIN CAFETERIA c ON c.CafeteriaID=m.CafeteriaID ORDER BY m.MealDate DESC, m.StartTime",
        "search": ["CafeteriaName", "MealType"],
    },
}

REFERENCE_QUERIES = {
    "staff": ("SELECT StaffID AS id, CONCAT(Name, ' · ', Department) AS label FROM STAFF ORDER BY Name",),
    "facility": ("SELECT FacilityID AS id, FacilityName AS label FROM STAFF_FACILITY ORDER BY FacilityName",),
    "locker": ("SELECT LockerID AS id, CONCAT(LockerNumber, ' — ', Location) AS label FROM LOCKER WHERE Status='AVAILABLE' ORDER BY Location, LockerNumber",),
    "training-facility": ("SELECT FacilityID AS id, FacilityName AS label FROM STAFF_FACILITY WHERE FacilityType='TRAINING_ROOM' ORDER BY FacilityName",),
    "cafeteria-facility": ("SELECT FacilityID AS id, FacilityName AS label FROM STAFF_FACILITY WHERE FacilityType='CAFETERIA' ORDER BY FacilityName",),
    "cafeteria": ("SELECT CafeteriaID AS id, CafeteriaName AS label FROM CAFETERIA ORDER BY CafeteriaName",),
}


@contextmanager
def db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "airport_staff_facilities_db"),
        connection_timeout=5,
    )
    try:
        yield connection
    finally:
        connection.close()


def fetch_all(sql, params=()):
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()


def insert_locker_allocation(values):
    with db_connection() as connection:
        cursor = connection.cursor()
        try:
            connection.start_transaction()
            cursor.execute(
                "SELECT Status FROM LOCKER WHERE LockerID=%s FOR UPDATE",
                (values["LockerID"],),
            )
            locker = cursor.fetchone()
            if not locker:
                raise ValueError("The selected locker does not exist.")
            if locker[0] != "AVAILABLE":
                raise ValueError("That locker is no longer available.")
            cursor.execute(
                """INSERT INTO LOCKER_ALLOCATION (LockerID, StaffID, AllocationDate)
                   VALUES (%s, %s, %s)""",
                (values["LockerID"], values["StaffID"], values["AllocationDate"]),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def fetch_one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def run_write(sql, params=()):
    with db_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            connection.commit()
            return cursor.rowcount
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def database_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except MySQLError as exc:
            logger.exception("Database operation failed")
            message = database_message(exc)
            if request.method == "GET":
                return render_template("errors/database.html", message=message), 503
            flash(message, "danger")
            return redirect(request.referrer or url_for("dashboard"))
    return wrapped


def database_message(exc):
    message = str(exc).lower()
    if "duplicate entry" in message:
        return "That value is already in use. Check unique fields such as staff email, locker number, and room number."
    if "booking conflict" in message:
        return "This time conflicts with an existing confirmed booking for the selected facility."
    if "locker is not available" in message:
        return "That locker is no longer available. Refresh the list and choose another one."
    if "foreign key constraint fails" in message:
        return "The selected related record does not exist or is still in use."
    if "check constraint" in message or "data too long" in message or "incorrect" in message:
        return "Some values are invalid or outside the database rules. Review the form and try again."
    if "access denied" in message:
        return "MySQL rejected the credentials. Check DB_USER and DB_PASSWORD in your .env file."
    if "unknown database" in message:
        return "The configured database was not found. Verify DB_NAME; this app will not create or reset it."
    return "Could not complete the database operation. Check that MySQL is running and the schema is ready."


def parse_form(fields):
    values = {}
    for key, label, kind, required in fields:
        value = request.form.get(key, "").strip()
        if required and not value:
            raise ValueError(f"{label} is required.")
        if not value:
            values[key] = None
            continue
        if kind == "number":
            try:
                number = int(value)
            except ValueError as exc:
                raise ValueError(f"{label} must be a whole number.") from exc
            if number <= 0:
                raise ValueError(f"{label} must be greater than zero.")
            values[key] = number
        elif kind == "email":
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                raise ValueError("Enter a valid email address.")
            values[key] = value
        elif kind == "date":
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{label} must be a valid date.") from exc
            values[key] = value
        elif kind == "time":
            try:
                datetime.strptime(value, "%H:%M")
            except ValueError as exc:
                raise ValueError(f"{label} must be a valid time.") from exc
            values[key] = value
        elif kind.startswith("select:"):
            if value not in kind.split(":", 1)[1].split("|"):
                raise ValueError(f"Choose a valid {label.lower()}.")
            values[key] = value
        elif kind.startswith("ref:"):
            try:
                values[key] = int(value)
            except ValueError as exc:
                raise ValueError(f"Choose a valid {label.lower()}.") from exc
        else:
            values[key] = value
    if "StartTime" in values and "EndTime" in values and values["StartTime"] >= values["EndTime"]:
        raise ValueError("End time must be later than start time.")
    if values.get("ValidUntil") and values.get("ValidFrom") and values["ValidUntil"] < values["ValidFrom"]:
        raise ValueError("Valid until cannot be before valid from.")
    return values


def reference_options(fields):
    options = {}
    for _, _, kind, _ in fields:
        if kind.startswith("ref:"):
            ref_name = kind.split(":", 1)[1]
            options[ref_name] = fetch_all(*REFERENCE_QUERIES[ref_name])
    return options


@app.context_processor
def inject_navigation():
    from flask import session

    if "csrf_token" not in session:
        session["csrf_token"] = token_urlsafe(32)
    return {"navigation": MODULES, "current_year": date.today().year, "csrf_token": session["csrf_token"]}


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        from flask import session

        submitted = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not submitted or submitted != expected:
            abort(400)


@app.get("/")
@database_errors
def dashboard():
    stats = fetch_one(
        """SELECT
            (SELECT COUNT(*) FROM STAFF) AS total_staff,
            (SELECT COUNT(*) FROM STAFF WHERE StaffStatus='ACTIVE') AS active_staff,
            (SELECT COUNT(*) FROM STAFF_FACILITY) AS total_facilities,
            (SELECT COUNT(*) FROM STAFF_FACILITY WHERE AvailabilityStatus='AVAILABLE') AS available_facilities,
            (SELECT COUNT(*) FROM FACILITY_BOOKING) AS total_bookings,
            (SELECT COUNT(*) FROM FACILITY_BOOKING WHERE BookingStatus='CONFIRMED') AS confirmed_bookings,
            (SELECT COUNT(*) FROM LOCKER WHERE Status='AVAILABLE') AS available_lockers,
            (SELECT COUNT(*) FROM LOCKER WHERE Status='ALLOCATED') AS allocated_lockers,
            (SELECT COUNT(*) FROM STAFF_PARKING WHERE AllocationStatus='ACTIVE') AS active_parking,
            (SELECT COUNT(*) FROM MEAL_SCHEDULE) AS meal_schedules"""
    )
    staff = fetch_all("SELECT Department AS label, COUNT(*) AS value FROM STAFF GROUP BY Department ORDER BY value DESC")
    facility = fetch_all("SELECT FacilityType AS label, COUNT(*) AS value FROM STAFF_FACILITY GROUP BY FacilityType ORDER BY value DESC")
    booking = fetch_all("SELECT BookingStatus AS label, COUNT(*) AS value FROM FACILITY_BOOKING GROUP BY BookingStatus ORDER BY BookingStatus")
    access = fetch_all("SELECT f.FacilityName AS label, COUNT(a.AccessID) AS value FROM STAFF_FACILITY f LEFT JOIN FACILITY_ACCESS a ON a.FacilityID=f.FacilityID GROUP BY f.FacilityID, f.FacilityName ORDER BY value DESC LIMIT 8")
    recent_bookings = fetch_all("SELECT b.BookingID, s.Name AS StaffName, f.FacilityName, b.BookingDate, b.StartTime, b.BookingStatus FROM FACILITY_BOOKING b JOIN STAFF s ON s.StaffID=b.StaffID JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID ORDER BY b.BookingDate DESC, b.StartTime DESC LIMIT 6")
    return render_template("dashboard.html", stats=stats, today=date.today().strftime("%A, %d %B %Y"), charts={
        "staff": staff, "facility": facility, "booking": booking, "access": access,
    }, recent_bookings=recent_bookings)


@app.get("/<slug>")
@database_errors
def module_page(slug):
    if slug not in MODULES:
        abort(404)
    module = MODULES[slug]
    search = request.args.get("q", "").strip()
    params = ()
    sql = module["query"]
    if search:
        clauses = [f"{column} LIKE %s" for column in module["search"]]
        sql = f"SELECT * FROM ({sql.rstrip(';')}) AS results WHERE " + " OR ".join(clauses)
        params = tuple(f"%{search}%" for _ in clauses)
    rows = fetch_all(sql, params)
    options = reference_options(module["fields"])
    return render_template("module.html", slug=slug, module=module, rows=rows, options=options, search=search)


@app.get("/staff/<int:staff_id>")
@database_errors
def staff_detail(staff_id):
    staff = fetch_one("SELECT * FROM STAFF WHERE StaffID=%s", (staff_id,))
    if not staff:
        abort(404)
    history = [
        {
            "title": "Facility bookings",
            "columns": ["Facility", "Date", "Start", "End", "Status"],
            "rows": fetch_all(
                """SELECT f.FacilityName AS Facility, b.BookingDate AS Date,
                          b.StartTime AS Start, b.EndTime AS End, b.BookingStatus AS Status
                   FROM FACILITY_BOOKING b JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID
                   WHERE b.StaffID=%s ORDER BY b.BookingDate DESC, b.StartTime DESC""",
                (staff_id,),
            ),
        },
        {
            "title": "Facility access history",
            "columns": ["Facility", "Date", "Time"],
            "rows": fetch_all(
                """SELECT f.FacilityName AS Facility, a.AccessDate AS Date, a.AccessTime AS Time
                   FROM FACILITY_ACCESS a JOIN STAFF_FACILITY f ON f.FacilityID=a.FacilityID
                   WHERE a.StaffID=%s ORDER BY a.AccessDate DESC, a.AccessTime DESC""",
                (staff_id,),
            ),
        },
        {
            "title": "Parking records",
            "columns": ["Vehicle", "Area", "Slot", "From", "Until", "Status"],
            "rows": fetch_all(
                """SELECT VehicleNumber AS Vehicle, ParkingArea AS Area, ParkingSlot AS Slot,
                          ValidFrom AS `From`, ValidUntil AS Until, AllocationStatus AS Status
                   FROM STAFF_PARKING WHERE StaffID=%s ORDER BY ValidFrom DESC""",
                (staff_id,),
            ),
        },
        {
            "title": "Locker allocations",
            "columns": ["Locker", "Location", "Allocated", "Returned", "Status"],
            "rows": fetch_all(
                """SELECT l.LockerNumber AS Locker, l.Location AS Location,
                          a.AllocationDate AS Allocated, a.ReturnDate AS Returned, a.Status AS Status
                   FROM LOCKER_ALLOCATION a JOIN LOCKER l ON l.LockerID=a.LockerID
                   WHERE a.StaffID=%s ORDER BY a.AllocationDate DESC""",
                (staff_id,),
            ),
        },
    ]
    return render_template("detail.html", title=staff["Name"], subtitle=f"Staff ID {staff_id}", record=staff, detail_type="staff", history=history)


@app.get("/facilities/<int:facility_id>")
@database_errors
def facility_detail(facility_id):
    facility = fetch_one("SELECT * FROM STAFF_FACILITY WHERE FacilityID=%s", (facility_id,))
    if not facility:
        abort(404)
    history = [
        {
            "title": "Facility bookings",
            "columns": ["Staff", "Date", "Start", "End", "Status"],
            "rows": fetch_all(
                """SELECT s.Name AS Staff, b.BookingDate AS Date, b.StartTime AS Start,
                          b.EndTime AS End, b.BookingStatus AS Status
                   FROM FACILITY_BOOKING b JOIN STAFF s ON s.StaffID=b.StaffID
                   WHERE b.FacilityID=%s ORDER BY b.BookingDate DESC, b.StartTime DESC""",
                (facility_id,),
            ),
        },
        {
            "title": "Access history",
            "columns": ["Staff", "Department", "Date", "Time"],
            "rows": fetch_all(
                """SELECT s.Name AS Staff, s.Department AS Department,
                          a.AccessDate AS Date, a.AccessTime AS Time
                   FROM FACILITY_ACCESS a JOIN STAFF s ON s.StaffID=a.StaffID
                   WHERE a.FacilityID=%s ORDER BY a.AccessDate DESC, a.AccessTime DESC""",
                (facility_id,),
            ),
        },
    ]
    return render_template("detail.html", title=facility["FacilityName"], subtitle=f"Facility ID {facility_id}", record=facility, detail_type="facility", history=history)


@app.post("/<slug>/add")
@database_errors
def add_record(slug):
    if slug not in MODULES:
        abort(404)
    module = MODULES[slug]
    try:
        values = parse_form(module["fields"])
        if slug == "bookings":
            insert_booking(values)
        elif slug == "locker-allocations":
            insert_locker_allocation(values)
        else:
            columns = list(values)
            placeholders = ", ".join(["%s"] * len(columns))
            run_write(
                f"INSERT INTO {module['table']} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
        flash(f"{module['title'].rstrip('s')} added successfully.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    except MySQLError:
        raise
    return redirect(url_for("module_page", slug=slug))


def insert_booking(values):
    with db_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            connection.start_transaction()
            cursor.execute(
                "SELECT FacilityID, AvailabilityStatus FROM STAFF_FACILITY WHERE FacilityID=%s FOR UPDATE",
                (values["FacilityID"],),
            )
            facility = cursor.fetchone()
            if not facility:
                raise ValueError("The selected facility does not exist.")
            if facility["AvailabilityStatus"] != "AVAILABLE":
                raise ValueError("The selected facility is currently unavailable.")
            if values["BookingStatus"] == "CONFIRMED":
                cursor.execute(
                    """SELECT BookingID FROM FACILITY_BOOKING
                       WHERE FacilityID=%s AND BookingDate=%s AND BookingStatus='CONFIRMED'
                         AND StartTime < %s AND EndTime > %s
                       FOR UPDATE""",
                    (values["FacilityID"], values["BookingDate"], values["EndTime"], values["StartTime"]),
                )
                if cursor.fetchone():
                    raise ValueError("This time conflicts with an existing confirmed booking.")
            columns = list(values)
            cursor.execute(
                f"INSERT INTO FACILITY_BOOKING ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})",
                tuple(values[column] for column in columns),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


@app.get("/<slug>/<int:record_id>/edit")
@database_errors
def edit_record(slug, record_id):
    if slug not in MODULES or slug in {"access", "bookings", "locker-allocations"}:
        abort(404)
    module = MODULES[slug]
    row = fetch_one(f"SELECT * FROM {module['table']} WHERE {module['pk']}=%s", (record_id,))
    if row is None:
        flash("That record no longer exists.", "warning")
        return redirect(url_for("module_page", slug=slug))
    return render_template("edit.html", slug=slug, module=module, row=row, options=reference_options(module["fields"]))


@app.post("/<slug>/<int:record_id>/edit")
@database_errors
def update_record(slug, record_id):
    if slug not in MODULES or slug in {"access", "bookings", "locker-allocations"}:
        abort(404)
    module = MODULES[slug]
    try:
        values = parse_form(module["fields"])
        assignments = ", ".join(f"{column}=%s" for column in values)
        run_write(
            f"UPDATE {module['table']} SET {assignments} WHERE {module['pk']}=%s",
            tuple(values.values()) + (record_id,),
        )
        flash("Record updated successfully.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("edit_record", slug=slug, record_id=record_id))
    return redirect(url_for("module_page", slug=slug))


@app.post("/<slug>/<int:record_id>/action/<action>")
@database_errors
def record_action(slug, record_id, action):
    allowed = {
        ("staff", "deactivate"): ("UPDATE STAFF SET StaffStatus='INACTIVE' WHERE StaffID=%s", "Staff member deactivated."),
        ("bookings", "cancel"): ("UPDATE FACILITY_BOOKING SET BookingStatus='CANCELLED' WHERE BookingID=%s AND BookingStatus IN ('PENDING','CONFIRMED')", "Booking cancelled."),
        ("bookings", "complete"): ("UPDATE FACILITY_BOOKING SET BookingStatus='COMPLETED' WHERE BookingID=%s AND BookingStatus='CONFIRMED' AND (BookingDate<CURRENT_DATE() OR (BookingDate=CURRENT_DATE() AND EndTime<CURRENT_TIME()))", "Booking marked completed."),
        ("parking", "release"): ("UPDATE STAFF_PARKING SET AllocationStatus='RELEASED', ValidUntil=COALESCE(ValidUntil,GREATEST(ValidFrom,CURRENT_DATE())) WHERE ParkingID=%s AND AllocationStatus='ACTIVE'", "Parking allocation released."),
        ("locker-allocations", "return"): ("UPDATE LOCKER_ALLOCATION SET Status='RETURNED', ReturnDate=CURRENT_DATE() WHERE AllocationID=%s AND Status='ACTIVE'", "Locker returned."),
        ("lockers", "unavailable"): ("UPDATE LOCKER SET Status='UNAVAILABLE' WHERE LockerID=%s AND Status='AVAILABLE'", "Locker marked unavailable."),
        ("lockers", "available"): ("UPDATE LOCKER SET Status='AVAILABLE' WHERE LockerID=%s AND Status='UNAVAILABLE'", "Locker marked available."),
        ("meals", "delete"): ("DELETE FROM MEAL_SCHEDULE WHERE MealID=%s", "Meal schedule deleted."),
    }
    entry = allowed.get((slug, action))
    if not entry:
        abort(404)
    affected = run_write(entry[0], (record_id,))
    if affected:
        flash(entry[1], "success")
    else:
        flash("No change was made. This record may no longer be eligible for that action.", "warning")
    return redirect(url_for("module_page", slug=slug))


REPORTS = [
    ("Staff by department", "SELECT Department AS `Department`, COUNT(*) AS `Staff` FROM STAFF GROUP BY Department ORDER BY COUNT(*) DESC"),
    ("Staff by shift", "SELECT Shift AS `Shift`, COUNT(*) AS `Staff` FROM STAFF GROUP BY Shift ORDER BY Shift"),
    ("Facilities by type", "SELECT FacilityType AS `Facility type`, COUNT(*) AS `Facilities` FROM STAFF_FACILITY GROUP BY FacilityType ORDER BY FacilityType"),
    ("Facility access counts", "SELECT f.FacilityName AS `Facility`, COUNT(a.AccessID) AS `Access events` FROM STAFF_FACILITY f LEFT JOIN FACILITY_ACCESS a ON a.FacilityID=f.FacilityID GROUP BY f.FacilityID, f.FacilityName ORDER BY COUNT(a.AccessID) DESC"),
    ("Bookings by status", "SELECT BookingStatus AS `Status`, COUNT(*) AS `Bookings` FROM FACILITY_BOOKING GROUP BY BookingStatus ORDER BY BookingStatus"),
    ("Staff booking history", "SELECT s.Name AS `Staff`, f.FacilityName AS `Facility`, b.BookingDate AS `Date`, b.StartTime AS `Start`, b.EndTime AS `End`, b.BookingStatus AS `Status` FROM FACILITY_BOOKING b JOIN STAFF s ON s.StaffID=b.StaffID JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID ORDER BY b.BookingDate DESC"),
    ("Locker inventory and allocation history", "SELECT l.LockerNumber AS `Locker`, l.Location AS `Location`, l.Status AS `Locker status`, s.Name AS `Staff`, a.AllocationDate AS `Allocated`, a.ReturnDate AS `Returned`, a.Status AS `Allocation status` FROM LOCKER l LEFT JOIN LOCKER_ALLOCATION a ON a.LockerID=l.LockerID LEFT JOIN STAFF s ON s.StaffID=a.StaffID ORDER BY l.Location, l.LockerNumber"),
    ("Active parking by area", "SELECT ParkingArea AS `Area`, COUNT(*) AS `Active allocations` FROM STAFF_PARKING WHERE AllocationStatus='ACTIVE' GROUP BY ParkingArea ORDER BY COUNT(*) DESC"),
    ("Cafeteria meal schedules", "SELECT c.CafeteriaName AS `Cafeteria`, m.MealType AS `Meal`, m.MealDate AS `Date`, m.StartTime AS `Start`, m.EndTime AS `End` FROM MEAL_SCHEDULE m JOIN CAFETERIA c ON c.CafeteriaID=m.CafeteriaID ORDER BY m.MealDate DESC, m.StartTime"),
    ("Booking utilization by facility", "SELECT f.FacilityName AS `Facility`, COUNT(b.BookingID) AS `Bookings`, SUM(CASE WHEN b.BookingStatus='CONFIRMED' THEN 1 ELSE 0 END) AS `Confirmed` FROM STAFF_FACILITY f LEFT JOIN FACILITY_BOOKING b ON b.FacilityID=f.FacilityID GROUP BY f.FacilityID, f.FacilityName ORDER BY COUNT(b.BookingID) DESC"),
    ("Staff with no bookings", "SELECT s.StaffID AS `Staff ID`, s.Name AS `Staff`, s.Department AS `Department` FROM STAFF s WHERE NOT EXISTS (SELECT 1 FROM FACILITY_BOOKING b WHERE b.StaffID=s.StaffID) ORDER BY s.Name"),
    ("Facilities without access events", "SELECT f.FacilityID AS `Facility ID`, f.FacilityName AS `Facility`, f.Location AS `Location` FROM STAFF_FACILITY f WHERE NOT EXISTS (SELECT 1 FROM FACILITY_ACCESS a WHERE a.FacilityID=f.FacilityID) ORDER BY f.FacilityName"),
    ("Staff with multiple active lockers", "SELECT s.StaffID AS `Staff ID`, s.Name AS `Staff`, COUNT(*) AS `Active lockers` FROM LOCKER_ALLOCATION a JOIN STAFF s ON s.StaffID=a.StaffID WHERE a.Status='ACTIVE' GROUP BY s.StaffID, s.Name HAVING COUNT(*)>1 ORDER BY COUNT(*) DESC"),
    ("Potential allocation conflicts", "SELECT 'Locker' AS `Resource`, l.LockerNumber AS `Item`, COUNT(*) AS `Active allocations` FROM LOCKER_ALLOCATION a JOIN LOCKER l ON l.LockerID=a.LockerID WHERE a.Status='ACTIVE' GROUP BY l.LockerID, l.LockerNumber HAVING COUNT(*)>1 UNION ALL SELECT 'Parking slot', CONCAT(ParkingArea, ' / ', ParkingSlot), COUNT(*) FROM STAFF_PARKING WHERE AllocationStatus='ACTIVE' GROUP BY ParkingArea, ParkingSlot HAVING COUNT(*)>1"),
]


@app.get("/reports")
@database_errors
def reports():
    report_data = []
    for title, sql in REPORTS:
        rows = fetch_all(sql)
        report_data.append({"title": title, "columns": list(rows[0].keys()) if rows else [], "rows": rows})
    return render_template("reports.html", reports=report_data)


@app.get("/export/<slug>.csv")
@database_errors
def export_csv(slug):
    if slug not in MODULES:
        abort(404)
    module = MODULES[slug]
    rows = fetch_all(module["query"])
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        writer = csv.writer(output)
        writer.writerow([label for _, label in module["columns"]])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={slug}.csv"},
    )


@app.errorhandler(404)
def not_found(_error):
    return render_template("errors/404.html"), 404


@app.errorhandler(400)
def bad_request(_error):
    return render_template("errors/400.html"), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=app.config["DEBUG"])
