import csv
import io
import logging
import os
import re
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from secrets import token_urlsafe

import mysql.connector
from pymongo import MongoClient
from pymongo.errors import PyMongoError
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
import sql_queries

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or os.urandom(32)
app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
mongo_client = None
activity_file_lock = threading.Lock()

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
        "query": sql_queries.MODULE_QUERIES["staff"],
        "search": ["Name", "Department", "Email"],
    },
    "facilities": {
        "title": "Facilities",
        "icon": "building",
        "table": "STAFF_FACILITY",
        "pk": "FacilityID",
        "fields": FACILITY_FIELDS,
        "columns": [("FacilityID", "ID"), ("FacilityName", "Facility"), ("FacilityType", "Type"), ("Location", "Location"), ("Capacity", "Capacity"), ("AvailabilityStatus", "Availability")],
        "query": sql_queries.MODULE_QUERIES["facilities"],
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
        "query": sql_queries.MODULE_QUERIES["access"],
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
        "query": sql_queries.MODULE_QUERIES["bookings"],
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
        "query": sql_queries.MODULE_QUERIES["parking"],
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
        "query": sql_queries.MODULE_QUERIES["lockers"],
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
        "query": sql_queries.MODULE_QUERIES["locker-allocations"],
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
        "query": sql_queries.MODULE_QUERIES["training-rooms"],
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
        "query": sql_queries.MODULE_QUERIES["cafeterias"],
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
        "query": sql_queries.MODULE_QUERIES["meals"],
        "search": ["CafeteriaName", "MealType"],
    },
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
                sql_queries.LOCKER_STATUS_FOR_UPDATE,
                (values["LockerID"],),
            )
            locker = cursor.fetchone()
            if not locker:
                raise ValueError("The selected locker does not exist.")
            if locker[0] != "AVAILABLE":
                raise ValueError("That locker is no longer available.")
            cursor.execute(
                sql_queries.LOCKER_ALLOCATION_INSERT,
                (values["LockerID"], values["StaffID"], values["AllocationDate"]),
            )
            allocation_id = cursor.lastrowid
            connection.commit()
            return allocation_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def fetch_one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def mongo_activity_collection():
    global mongo_client

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return None
    if mongo_client is None:
        mongo_client = MongoClient(uri, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
    mongo_client.admin.command("ping")
    database = os.getenv("MONGODB_DATABASE", "airport_staff_facilities")
    collection = os.getenv("MONGODB_COLLECTION", "activity_logs")
    return mongo_client[database][collection]


def mongo_records_collection():
    global mongo_client

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return None
    if mongo_client is None:
        mongo_client = MongoClient(uri, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
    mongo_client.admin.command("ping")
    database = os.getenv("MONGODB_DATABASE", "airport_staff_facilities")
    collection = os.getenv("MONGODB_RECORDS_COLLECTION", "management_records")
    return mongo_client[database][collection]


def mongo_record_value(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        sign = "-" if total_seconds < 0 else ""
        hours, remainder = divmod(abs(total_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
    if isinstance(value, Decimal):
        return str(value)
    return value


def sync_mongo_record(slug, record_id, deleted=False):
    if not os.getenv("MONGODB_URI", "").strip():
        return "MongoDB is not configured, so this record could not be mirrored; the MySQL change was saved."
    try:
        collection = mongo_records_collection()
        document_id = f"{slug}:{record_id}"
        if deleted:
            collection.delete_one({"_id": document_id})
            return None
        module = MODULES[slug]
        row = fetch_one(
            sql_queries.record_by_id_statement(module["table"], module["pk"]),
            (record_id,),
        )
        if row is None:
            collection.delete_one({"_id": document_id})
            return None
        document = {
            "_id": document_id,
            "module": slug,
            "table": module["table"],
            "record_id": record_id,
            "synced_at": datetime.now(timezone.utc),
        }
        document.update({key: mongo_record_value(value) for key, value in row.items()})
        collection.replace_one({"_id": document_id}, document, upsert=True)
    except (MySQLError, PyMongoError, TypeError, ValueError):
        logger.exception("Could not mirror the %s record to MongoDB", slug)
        return "The MySQL change was saved, but MongoDB could not mirror the record. Check MONGODB_URI and the MongoDB connection."
    return None


def activity_log_file():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "activity_audit.log")


def append_activity_file(event):
    line = "\t".join((
        event["created_at"].isoformat(),
        str(event["operation"]).replace("\t", " "),
        str(event["module"]).replace("\t", " "),
        str(event["record_id"] if event["record_id"] is not None else ""),
    ))
    with activity_file_lock:
        with open(activity_log_file(), "a", encoding="utf-8", newline="") as activity_file:
            if activity_file.tell() == 0:
                activity_file.write("timestamp_utc\toperation\tmodule\trecord_id\n")
            activity_file.write(line + "\n")


def read_activity_file(limit):
    path = activity_log_file()
    if not os.path.exists(path):
        return []
    with activity_file_lock:
        with open(path, encoding="utf-8") as activity_file:
            lines = activity_file.readlines()[-1000:]
    events = []
    for line in lines:
        line = line.rstrip("\r\n")
        if not line or line.startswith("timestamp_utc\t"):
            continue
        created_at, operation, module, record_id = line.split("\t", 3)
        events.append({
            "created_at": datetime.fromisoformat(created_at),
            "operation": operation,
            "module": module,
            "record_id": int(record_id) if record_id else None,
        })
    return sorted(events, key=lambda event: event["created_at"], reverse=True)[:limit]


def record_activity(operation, module, record_id):
    event = {
        "operation": operation,
        "module": module,
        "record_id": record_id,
        "created_at": datetime.now(timezone.utc),
    }
    warnings = []
    try:
        append_activity_file(event)
    except OSError:
        logger.exception("Could not append activity event to the local audit file")
        warnings.append("The MySQL change was saved, but the local activity audit file could not be written.")
    try:
        collection = mongo_activity_collection()
        if collection is not None:
            collection.insert_one(event)
    except PyMongoError:
        logger.exception("Could not write activity event to MongoDB")
        warnings.append("The MySQL change and local audit file were saved, but MongoDB could not record the activity. Check MONGODB_URI and the Atlas connection.")
    return " ".join(warnings) or None


def record_successful_change(operation, slug, record_id, deleted=False, related_records=()):
    warnings = []
    warning = sync_mongo_record(slug, record_id, deleted=deleted)
    if warning:
        warnings.append(warning)
    for related_slug, related_id in related_records:
        warning = sync_mongo_record(related_slug, related_id)
        if warning:
            warnings.append(warning)
    warning = record_activity(operation, MODULES[slug]["title"], record_id)
    if warning:
        warnings.append(warning)
    return " ".join(dict.fromkeys(warnings)) or None


def fetch_recent_activity(limit=8):
    if not os.getenv("MONGODB_URI", "").strip():
        try:
            return read_activity_file(limit), "File log (MongoDB not configured)"
        except (OSError, ValueError):
            logger.exception("Could not read the local activity audit file")
            return [], "File log unavailable"
    try:
        collection = mongo_activity_collection()
        events = list(
            collection.find(
                {},
                {"_id": 0, "operation": 1, "module": 1, "record_id": 1, "created_at": 1},
            )
            .sort("created_at", -1)
            .limit(limit)
        )
    except PyMongoError:
        logger.exception("Could not read activity events from MongoDB")
        try:
            return read_activity_file(limit), "File log (MongoDB unavailable)"
        except (OSError, ValueError):
            logger.exception("Could not read the local activity audit file")
            return [], "MongoDB and file log unavailable"
    return events, "Connected"


def run_write(sql, params=(), return_id=False):
    with db_connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            connection.commit()
            return cursor.lastrowid if return_id else cursor.rowcount
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
            options[ref_name] = fetch_all(sql_queries.REFERENCE_QUERIES[ref_name])
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
    stats = fetch_one(sql_queries.DASHBOARD_STATS)
    staff = fetch_all(sql_queries.DASHBOARD_STAFF)
    facility = fetch_all(sql_queries.DASHBOARD_FACILITIES)
    booking = fetch_all(sql_queries.DASHBOARD_BOOKINGS)
    access = fetch_all(sql_queries.DASHBOARD_ACCESS)
    recent_bookings = fetch_all(sql_queries.DASHBOARD_RECENT_BOOKINGS)
    recent_activity, mongo_status = fetch_recent_activity(5)
    return render_template("dashboard.html", stats=stats, today=date.today().strftime("%A, %d %B %Y"), charts={
        "staff": staff, "facility": facility, "booking": booking, "access": access,
    }, recent_bookings=recent_bookings, recent_activity=recent_activity, mongo_status=mongo_status)


@app.get("/activity")
def activity_page():
    events, mongo_status = fetch_recent_activity(50)
    return render_template("activity.html", events=events, mongo_status=mongo_status)


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
        sql = sql_queries.search_statement(sql, module["search"])
        params = tuple(f"%{search}%" for _ in module["search"])
    rows = fetch_all(sql, params)
    options = reference_options(module["fields"])
    return render_template("module.html", slug=slug, module=module, rows=rows, options=options, search=search)


@app.get("/staff/<int:staff_id>")
@database_errors
def staff_detail(staff_id):
    staff = fetch_one(sql_queries.STAFF_BY_ID, (staff_id,))
    if not staff:
        abort(404)
    history = [
        {
            "title": "Facility bookings",
            "columns": ["Facility", "Date", "Start", "End", "Status"],
            "rows": fetch_all(
                sql_queries.STAFF_BOOKING_HISTORY,
                (staff_id,),
            ),
        },
        {
            "title": "Facility access history",
            "columns": ["Facility", "Date", "Time"],
            "rows": fetch_all(
                sql_queries.STAFF_ACCESS_HISTORY,
                (staff_id,),
            ),
        },
        {
            "title": "Parking records",
            "columns": ["Vehicle", "Area", "Slot", "From", "Until", "Status"],
            "rows": fetch_all(
                sql_queries.STAFF_PARKING_HISTORY,
                (staff_id,),
            ),
        },
        {
            "title": "Locker allocations",
            "columns": ["Locker", "Location", "Allocated", "Returned", "Status"],
            "rows": fetch_all(
                sql_queries.STAFF_LOCKER_HISTORY,
                (staff_id,),
            ),
        },
    ]
    return render_template("detail.html", title=staff["Name"], subtitle=f"Staff ID {staff_id}", record=staff, detail_type="staff", history=history)


@app.get("/facilities/<int:facility_id>")
@database_errors
def facility_detail(facility_id):
    facility = fetch_one(sql_queries.FACILITY_BY_ID, (facility_id,))
    if not facility:
        abort(404)
    history = [
        {
            "title": "Facility bookings",
            "columns": ["Staff", "Date", "Start", "End", "Status"],
            "rows": fetch_all(
                sql_queries.FACILITY_BOOKING_HISTORY,
                (facility_id,),
            ),
        },
        {
            "title": "Access history",
            "columns": ["Staff", "Department", "Date", "Time"],
            "rows": fetch_all(
                sql_queries.FACILITY_ACCESS_HISTORY,
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
            record_id = insert_booking(values)
        elif slug == "locker-allocations":
            record_id = insert_locker_allocation(values)
        else:
            columns = list(values)
            record_id = run_write(
                sql_queries.insert_statement(module["table"], columns),
                tuple(values[column] for column in columns),
                return_id=True,
            )
        flash(f"{module['title'].rstrip('s')} added successfully.", "success")
        related_records = ()
        if slug == "locker-allocations":
            related_records = (("lockers", values["LockerID"]),)
        warning = record_successful_change(
            "created",
            slug,
            record_id,
            related_records=related_records,
        )
        if warning:
            flash(warning, "warning")
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
                sql_queries.BOOKING_FACILITY_FOR_UPDATE,
                (values["FacilityID"],),
            )
            facility = cursor.fetchone()
            if not facility:
                raise ValueError("The selected facility does not exist.")
            if facility["AvailabilityStatus"] != "AVAILABLE":
                raise ValueError("The selected facility is currently unavailable.")
            if values["BookingStatus"] == "CONFIRMED":
                cursor.execute(
                    sql_queries.BOOKING_CONFLICT_CHECK,
                    (values["FacilityID"], values["BookingDate"], values["EndTime"], values["StartTime"]),
                )
                if cursor.fetchone():
                    raise ValueError("This time conflicts with an existing confirmed booking.")
            columns = list(values)
            cursor.execute(
                sql_queries.insert_statement("FACILITY_BOOKING", columns),
                tuple(values[column] for column in columns),
            )
            booking_id = cursor.lastrowid
            connection.commit()
            return booking_id
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
    row = fetch_one(
        sql_queries.record_by_id_statement(module["table"], module["pk"]),
        (record_id,),
    )
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
        affected = run_write(
            sql_queries.update_statement(module["table"], list(values), module["pk"]),
            tuple(values.values()) + (record_id,),
        )
        if affected:
            flash("Record updated successfully.", "success")
            warning = record_successful_change("updated", slug, record_id)
            if warning:
                flash(warning, "warning")
        else:
            flash("No change was made to this record.", "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("edit_record", slug=slug, record_id=record_id))
    return redirect(url_for("module_page", slug=slug))


@app.post("/<slug>/<int:record_id>/action/<action>")
@database_errors
def record_action(slug, record_id, action):
    allowed = {
        ("staff", "deactivate"): (sql_queries.ACTION_QUERIES[("staff", "deactivate")], "Staff member deactivated."),
        ("bookings", "cancel"): (sql_queries.ACTION_QUERIES[("bookings", "cancel")], "Booking cancelled."),
        ("bookings", "complete"): (sql_queries.ACTION_QUERIES[("bookings", "complete")], "Booking marked completed."),
        ("parking", "release"): (sql_queries.ACTION_QUERIES[("parking", "release")], "Parking allocation released."),
        ("locker-allocations", "return"): (sql_queries.ACTION_QUERIES[("locker-allocations", "return")], "Locker returned."),
        ("lockers", "unavailable"): (sql_queries.ACTION_QUERIES[("lockers", "unavailable")], "Locker marked unavailable."),
        ("lockers", "available"): (sql_queries.ACTION_QUERIES[("lockers", "available")], "Locker marked available."),
        ("meals", "delete"): (sql_queries.ACTION_QUERIES[("meals", "delete")], "Meal schedule deleted."),
    }
    entry = allowed.get((slug, action))
    if not entry:
        abort(404)
    related_records = ()
    if slug == "locker-allocations" and action == "return":
        allocation = fetch_one(
            sql_queries.record_by_id_statement(
                MODULES[slug]["table"],
                MODULES[slug]["pk"],
            ),
            (record_id,),
        )
        if allocation:
            related_records = (("lockers", allocation["LockerID"]),)
    affected = run_write(entry[0], (record_id,))
    if affected:
        flash(entry[1], "success")
        operation = "deleted" if action == "delete" else action
        warning = record_successful_change(
            operation,
            slug,
            record_id,
            deleted=action == "delete",
            related_records=related_records,
        )
        if warning:
            flash(warning, "warning")
    else:
        flash("No change was made. This record may no longer be eligible for that action.", "warning")
    return redirect(url_for("module_page", slug=slug))


@app.get("/reports")
@database_errors
def reports():
    report_data = []
    for title, query in sql_queries.REPORTS:
        rows = fetch_all(query)
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
