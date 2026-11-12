# Airport Staff Facilities Management System

A Flask web application using MySQL for airport employee facility records and MongoDB to mirror frontend changes and store an activity log.

## What it manages

- Staff records and active/inactive status
- Staff detail pages with booking, access, parking, and locker history
- Staff facilities, their types, capacities, and availability
- Facility detail pages with booking and access history
- Simulated/manual facility access events (not airport hardware)
- Facility bookings, including overlap protection for confirmed bookings
- Staff parking allocations and release history
- Locker inventory, allocations, and returns
- Training-room details linked to an existing training facility
- Cafeteria records and meal schedules
- Dashboard, charts, operational reports, and CSV exports
- Recent activity history stored in MongoDB and a local plain-text audit file

MySQL remains the source of truth for the existing `airport_staff_facilities_db` records. All SQL statements and parameterized query builders are centralized in [`sql_queries.py`](./sql_queries.py); `app.py` imports and executes them directly with the MySQL connector. No separate database API is used. The app does not create, drop, reset, or seed MySQL tables. When `MONGODB_URI` is configured, the embedded PyMongo driver mirrors each successful add, edit, and supported action to the `management_records` MongoDB collection, and writes a separate event to `activity_logs`. Mirrored records contain the changed MySQL row, so fields such as staff contact details are also copied; configure MongoDB access accordingly. Existing MySQL records are mirrored when they are next changed in the app, not by a bulk import. MongoDB creates its configured database and collections when the first successful write occurs. Do not rerun the sample `INSERT` section from the SQL reference against an already populated database.

Whether or not MongoDB is configured, every successful create, update, and delete/action is appended to the plain-text `activity_audit.log` file in the project folder. This lets you inspect the audit trail without installing MongoDB. If `MONGODB_URI` is blank, the Activity log page clearly identifies that it is showing the local file and not a live MongoDB connection. When a real MongoDB URI is configured, events are written to both the local audit file and the MongoDB collection.

## Database design

The existing ten MySQL tables and their relationships are unchanged. With a real MongoDB connection, the app adds a `management_records` collection in the `airport_staff_facilities` database. Each document has a stable `_id` (`module:record_id`), module/table metadata, a `synced_at` timestamp, and the current columns from that MySQL row. Additions and edits are upserted; a deleted meal schedule is removed from this collection. Locker allocations and returns also mirror the affected locker status. The separate `activity_logs` collection stores the operation, module, record ID, and timestamp. Use **MongoDB Compass** to browse the `airport_staff_facilities` database and open `management_records`; use the **Activity log** page or dashboard to review event history. Without MongoDB, MySQL behavior remains available and audit events go to `activity_audit.log`; the app displays a warning after a change that could not be mirrored.

To present the SQL implementation, open `sql_queries.py`. It contains the `SELECT` statements, `INSERT` and `UPDATE` builders, action `UPDATE`/`DELETE` statements, and report queries. `app.py` contains the Flask routes and calls the named statements from that module.

| Table | Purpose |
|---|---|
| `STAFF` | Employee name, department, designation, contact, shift, and status |
| `STAFF_FACILITY` | Staff lounge, rest area, training room, cafeteria, and other facility details |
| `FACILITY_ACCESS` | Manually recorded facility access date/time by staff member |
| `FACILITY_BOOKING` | Facility reservation dates, times, and statuses |
| `STAFF_PARKING` | Staff vehicle and parking slot allocations |
| `LOCKER` | Locker number, location, type, and availability |
| `LOCKER_ALLOCATION` | Staff-to-locker allocation and return history |
| `TRAINING_ROOM` | Training-room details linked to a facility |
| `CAFETERIA` | Cafeteria details linked to a facility |
| `MEAL_SCHEDULE` | Cafeteria meal type and date/time schedule |

Foreign-key relationships follow the existing schema: access/bookings/parking reference staff and facilities; locker allocations reference lockers and staff; training rooms/cafeterias reference facilities; meal schedules reference cafeterias.

## Setup on Windows CMD

The easiest way is to use the included command scripts:

1. Open File Explorer and go to the folder containing `app.py`.
2. Double-click `setup.cmd`. It creates a virtual environment and installs Flask, the MySQL connector, PyMongo, and dotenv. It creates `.env` from `.env.example` only if `.env` does not already exist.
3. Make sure MySQL 8.0 is running and the existing ten tables are present in `airport_staff_facilities_db`.
4. To show frontend changes in MongoDB Compass, set `MONGODB_URI` in `.env` to the same connection string you use in Compass. In MongoDB Atlas, copy the connection string from **Connect → Drivers** (replace its username, password, and cluster placeholders). For a local MongoDB server, use `mongodb://localhost:27017`. Set your Atlas IP access and database user in Atlas if required. Leave the URI blank only if you want to use MySQL and the local audit file without MongoDB.
5. Edit `.env` with your MySQL login (`DB_USER`, `DB_PASSWORD`) and keep `DB_NAME=airport_staff_facilities_db`. Save and close it.
6. Double-click `run.cmd`, then open **http://127.0.0.1:5000**. Leave the command window open while using the application. Press **Ctrl+C** in that window to stop the server.

You can also run the setup from a regular Command Prompt:

```bat
cd /d "C:\path\to\airport-staff-facilities-management-main"
setup.cmd
```

After editing `.env`, start the app with:

```bat
cd /d "C:\path\to\airport-staff-facilities-management-main"
run.cmd
```

The web app connects directly to MySQL using the settings `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME`. MongoDB uses the embedded PyMongo driver with `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_COLLECTION`, and `MONGODB_RECORDS_COLLECTION`. A MongoDB outage does not block MySQL record changes; the page displays a warning and successful changes remain in the plain-text audit file. In Compass, connect using the same URI, then open database `airport_staff_facilities` and collection `management_records`.

## Manual setup on Windows PowerShell

Open PowerShell in this project folder:

```powershell
Set-Location "C:\path\to\airport-staff-facilities-management-main"
```

The application will not initialize or alter the database.

Create and activate a virtual environment, then install dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks environment activation, run this once for the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Create your private configuration file and edit it with your actual MySQL login and, if enabled, MongoDB URI:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and replace `SECRET_KEY` with a long random value. Set `MONGODB_URI` to your Atlas or local MongoDB connection string; this is where you put the connection string for the app. Use the same URI in MongoDB Compass to inspect the data. The defaults create/use database `airport_staff_facilities`, records collection `management_records`, and activity collection `activity_logs`. `.env` is ignored by Git and must not be shared. The MySQL user needs normal `SELECT`, `INSERT`, `UPDATE`, and `DELETE` permissions for the project tables.

Start the web application:

```powershell
python app.py
```

Open **http://127.0.0.1:5000**. Stop the local development server with **Ctrl+C** in PowerShell.

## Using the application

1. Review the live dashboard and database charts.
2. Use the sidebar to browse the ten management modules.
3. Use **Add** forms to insert records; references in dropdowns come from the database.
4. Edit supported records with the pencil action. Deactivate staff rather than deleting them.
5. Confirmed bookings are checked while holding a lock on the facility row, and the existing MySQL booking triggers remain in place. Trigger conflicts are presented as readable messages.
6. Allocate available lockers from **Locker allocations**. Return actions update the allocation; the existing trigger updates the locker status.
7. Release parking using its action; this retains the record and sets its end date.
8. Use **Reports** for live summaries and **Export CSV** on a module to download its current records.
9. Use **Activity log** to review successful data changes. In MongoDB Compass, browse `airport_staff_facilities.management_records` to see current documents for records changed through the app; `activity_logs` shows the event history. With no MongoDB configured, open `activity_audit.log` in the project folder to show the plain-text event entries.

To open the audit file from Command Prompt after making changes:

```bat
notepad activity_audit.log
```

## Validation and tests

The application uses parameterized values for database operations, validates required inputs and date/time ordering, reports database errors without exposing SQL traces, uses POST for changes, applies CSRF tokens, and commits or rolls back write transactions.

Run Python syntax validation from the project directory:

```powershell
python -m py_compile app.py
```

With valid `.env` credentials and the existing schema, start the app and verify:

- Dashboard statistics, charts, and recent bookings load.
- Each module lists database rows and its CSV export downloads.
- Staff/facility records can be added and edited; staff can be deactivated.
- A confirmed booking can be created, while an overlapping confirmed booking is rejected.
- A free locker can be allocated and returned; its `LOCKER.Status` changes through the existing triggers.
- Parking allocations can be registered and released.
- Meal schedules can be added, edited, and deleted.
- Reports reflect inserts and updates made through the interface.

The MySQL service may be running while the account credentials or table setup are still unknown. A live database connection can only be verified after entering valid credentials in `.env`; do not test by resetting or deleting existing records.

## Security and project limitations

- This is a local university demonstration app, not an authenticated production administration system. It intentionally does not create a login or claim role-based access control.
- Facility-access records are simulated/manual; there is no hardware integration.
- External Bootstrap, Bootstrap Icons, Google Fonts, and Chart.js assets are loaded from CDNs; internet access is needed for those visual assets. Core server-side pages do not rely on JavaScript for data changes.
- Keep the Flask debug server on localhost and do not expose it to a public network.
- Booking date/time and database constraint behavior ultimately depend on the existing schema and triggers. Verify they match the SQL reference before demonstrating.

## Screenshots for the DBMS report: Front End Development

Capture your own screenshots after running the application with your MySQL data:

1. Dashboard with live KPI cards, charts, and recent bookings.
2. Staff list and the add-staff form.
3. Facilities list and facility availability/capacity.
4. Facility access history and simulated event form.
5. Bookings page showing a successful booking and a rejected overlap message.
6. Parking allocation list with active/released status.
7. Locker inventory and locker allocation/return workflow.
8. Training-room details.
9. Cafeteria and meal schedule pages.
10. Reports page with several generated summaries.

Screenshots are not included or fabricated in this source project.
