# Airport Staff Facilities Management System

A Flask and MySQL web application for managing airport employee facilities and resources. The project is located in its own `airport_staff_facilities` folder so it does not overwrite the unrelated Lab 6 coverage exercise.

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

The application connects to the existing `airport_staff_facilities_db` database. It does not create, drop, reset, or seed database tables. Do not rerun the sample `INSERT` section from the SQL reference against an already populated database.

## Database design

The application uses the existing ten tables:

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

1. Open File Explorer and go to the `airport_staff_facilities` folder.
2. Double-click `setup.cmd`. It creates a virtual environment and installs Flask, the MySQL connector, and dotenv. It creates `.env` from `.env.example` only if `.env` does not already exist.
3. Right-click `.env`, choose **Open with → Notepad**, then enter your MySQL login. For example, set `DB_USER=root` and set `DB_PASSWORD` to the password for your MySQL account. Keep the existing database name `airport_staff_facilities_db`. Save and close Notepad.
4. Double-click `run.cmd`.
5. Open **http://127.0.0.1:5000**. Leave the command window open while using the application. Press **Ctrl+C** in that window to stop the server.

You can also run the setup from a regular Command Prompt:

```bat
cd /d "C:\Users\Vakalapudi kushal\Downloads\L6_L7_12_cloud_storage_tier-main\L6_L7_12_cloud_storage_tier-main\Lab 6\airport_staff_facilities"
setup.cmd
```

After editing `.env`, start the app with:

```bat
cd /d "C:\Users\Vakalapudi kushal\Downloads\L6_L7_12_cloud_storage_tier-main\L6_L7_12_cloud_storage_tier-main\Lab 6\airport_staff_facilities"
run.cmd
```

Confirm MySQL 8.0 is running and the ten tables exist in `airport_staff_facilities_db`. The web app connects using the `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` values from `.env`. This application will not initialize or alter the database.

## Manual setup on Windows PowerShell

Open PowerShell in this project folder:

```powershell
Set-Location "C:\Users\Vakalapudi kushal\Downloads\L6_L7_12_cloud_storage_tier-main\L6_L7_12_cloud_storage_tier-main\Lab 6\airport_staff_facilities"
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

Create your private configuration file and edit it with your actual MySQL login:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and replace `SECRET_KEY` with a long random value. `.env` is ignored by Git and must not be shared. The database user needs normal `SELECT`, `INSERT`, `UPDATE`, and `DELETE` permissions for the project tables and access to the existing stored routines if you use them separately.

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
