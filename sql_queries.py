"""Parameterized MySQL statements used by the application."""

MODULE_QUERIES = {
    "staff": "SELECT StaffID, Name, Department, Designation, Email, Phone, Shift, StaffStatus FROM STAFF ORDER BY StaffID DESC",
    "facilities": "SELECT FacilityID, FacilityName, FacilityType, Location, Capacity, AvailabilityStatus FROM STAFF_FACILITY ORDER BY FacilityID DESC",
    "access": "SELECT a.AccessID, a.StaffID, a.FacilityID, s.Name AS StaffName, f.FacilityName, a.AccessDate, a.AccessTime FROM FACILITY_ACCESS a JOIN STAFF s ON s.StaffID=a.StaffID JOIN STAFF_FACILITY f ON f.FacilityID=a.FacilityID ORDER BY a.AccessDate DESC, a.AccessTime DESC",
    "bookings": "SELECT b.BookingID, b.StaffID, b.FacilityID, s.Name AS StaffName, f.FacilityName, b.BookingDate, b.StartTime, b.EndTime, b.BookingStatus, CASE WHEN (b.BookingDate<CURRENT_DATE() OR (b.BookingDate=CURRENT_DATE() AND b.EndTime<CURRENT_TIME())) THEN 1 ELSE 0 END AS IsCompletable FROM FACILITY_BOOKING b JOIN STAFF s ON s.StaffID=b.StaffID JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID ORDER BY b.BookingDate DESC, b.StartTime",
    "parking": "SELECT p.ParkingID, p.StaffID, s.Name AS StaffName, p.VehicleNumber, p.VehicleType, p.ParkingArea, p.ParkingSlot, p.ValidFrom, p.ValidUntil, p.AllocationStatus FROM STAFF_PARKING p JOIN STAFF s ON s.StaffID=p.StaffID ORDER BY p.ParkingID DESC",
    "lockers": "SELECT LockerID, LockerNumber, Location, LockerType, Status FROM LOCKER ORDER BY Location, LockerNumber",
    "locker-allocations": "SELECT a.AllocationID, a.LockerID, a.StaffID, l.LockerNumber, s.Name AS StaffName, a.AllocationDate, a.ReturnDate, a.Status FROM LOCKER_ALLOCATION a JOIN LOCKER l ON l.LockerID=a.LockerID JOIN STAFF s ON s.StaffID=a.StaffID ORDER BY a.AllocationID DESC",
    "training-rooms": "SELECT t.TrainingRoomID, t.FacilityID, t.RoomNumber, f.FacilityName, f.Location, t.Capacity, t.EquipmentAvailable FROM TRAINING_ROOM t JOIN STAFF_FACILITY f ON f.FacilityID=t.FacilityID ORDER BY t.RoomNumber",
    "cafeterias": "SELECT c.CafeteriaID, c.FacilityID, c.CafeteriaName, f.FacilityName, c.Location, c.Capacity FROM CAFETERIA c JOIN STAFF_FACILITY f ON f.FacilityID=c.FacilityID ORDER BY c.CafeteriaName",
    "meals": "SELECT m.MealID, m.CafeteriaID, c.CafeteriaName, m.MealType, m.MealDate, m.StartTime, m.EndTime FROM MEAL_SCHEDULE m JOIN CAFETERIA c ON c.CafeteriaID=m.CafeteriaID ORDER BY m.MealDate DESC, m.StartTime",
}

REFERENCE_QUERIES = {
    "staff": "SELECT StaffID AS id, CONCAT(Name, ' · ', Department) AS label FROM STAFF ORDER BY Name",
    "facility": "SELECT FacilityID AS id, FacilityName AS label FROM STAFF_FACILITY ORDER BY FacilityName",
    "locker": "SELECT LockerID AS id, CONCAT(LockerNumber, ' — ', Location) AS label FROM LOCKER WHERE Status='AVAILABLE' ORDER BY Location, LockerNumber",
    "training-facility": "SELECT FacilityID AS id, FacilityName AS label FROM STAFF_FACILITY WHERE FacilityType='TRAINING_ROOM' ORDER BY FacilityName",
    "cafeteria-facility": "SELECT FacilityID AS id, FacilityName AS label FROM STAFF_FACILITY WHERE FacilityType='CAFETERIA' ORDER BY FacilityName",
    "cafeteria": "SELECT CafeteriaID AS id, CafeteriaName AS label FROM CAFETERIA ORDER BY CafeteriaName",
}

DASHBOARD_STATS = """SELECT
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
DASHBOARD_STAFF = "SELECT Department AS label, COUNT(*) AS value FROM STAFF GROUP BY Department ORDER BY value DESC"
DASHBOARD_FACILITIES = "SELECT FacilityType AS label, COUNT(*) AS value FROM STAFF_FACILITY GROUP BY FacilityType ORDER BY value DESC"
DASHBOARD_BOOKINGS = "SELECT BookingStatus AS label, COUNT(*) AS value FROM FACILITY_BOOKING GROUP BY BookingStatus ORDER BY BookingStatus"
DASHBOARD_ACCESS = "SELECT f.FacilityName AS label, COUNT(a.AccessID) AS value FROM STAFF_FACILITY f LEFT JOIN FACILITY_ACCESS a ON a.FacilityID=f.FacilityID GROUP BY f.FacilityID, f.FacilityName ORDER BY value DESC LIMIT 8"
DASHBOARD_RECENT_BOOKINGS = "SELECT b.BookingID, s.Name AS StaffName, f.FacilityName, b.BookingDate, b.StartTime, b.BookingStatus FROM FACILITY_BOOKING b JOIN STAFF s ON s.StaffID=b.StaffID JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID ORDER BY b.BookingDate DESC, b.StartTime DESC LIMIT 6"

STAFF_BY_ID = "SELECT * FROM STAFF WHERE StaffID=%s"
FACILITY_BY_ID = "SELECT * FROM STAFF_FACILITY WHERE FacilityID=%s"
STAFF_BOOKING_HISTORY = """SELECT f.FacilityName AS Facility, b.BookingDate AS Date,
    b.StartTime AS Start, b.EndTime AS End, b.BookingStatus AS Status
    FROM FACILITY_BOOKING b JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID
    WHERE b.StaffID=%s ORDER BY b.BookingDate DESC, b.StartTime DESC"""
STAFF_ACCESS_HISTORY = """SELECT f.FacilityName AS Facility, a.AccessDate AS Date, a.AccessTime AS Time
    FROM FACILITY_ACCESS a JOIN STAFF_FACILITY f ON f.FacilityID=a.FacilityID
    WHERE a.StaffID=%s ORDER BY a.AccessDate DESC, a.AccessTime DESC"""
STAFF_PARKING_HISTORY = """SELECT VehicleNumber AS Vehicle, ParkingArea AS Area, ParkingSlot AS Slot,
    ValidFrom AS `From`, ValidUntil AS Until, AllocationStatus AS Status
    FROM STAFF_PARKING WHERE StaffID=%s ORDER BY ValidFrom DESC"""
STAFF_LOCKER_HISTORY = """SELECT l.LockerNumber AS Locker, l.Location AS Location,
    a.AllocationDate AS Allocated, a.ReturnDate AS Returned, a.Status AS Status
    FROM LOCKER_ALLOCATION a JOIN LOCKER l ON l.LockerID=a.LockerID
    WHERE a.StaffID=%s ORDER BY a.AllocationDate DESC"""
FACILITY_BOOKING_HISTORY = """SELECT s.Name AS Staff, f.FacilityName AS Facility, b.BookingDate AS Date,
    b.StartTime AS Start, b.EndTime AS End, b.BookingStatus AS Status
    FROM FACILITY_BOOKING b JOIN STAFF s ON s.StaffID=b.StaffID
    JOIN STAFF_FACILITY f ON f.FacilityID=b.FacilityID
    WHERE b.FacilityID=%s ORDER BY b.BookingDate DESC, b.StartTime DESC"""
FACILITY_ACCESS_HISTORY = """SELECT s.Name AS Staff, s.Department AS Department,
    a.AccessDate AS Date, a.AccessTime AS Time
    FROM FACILITY_ACCESS a JOIN STAFF s ON s.StaffID=a.StaffID
    WHERE a.FacilityID=%s ORDER BY a.AccessDate DESC, a.AccessTime DESC"""

LOCKER_STATUS_FOR_UPDATE = "SELECT Status FROM LOCKER WHERE LockerID=%s FOR UPDATE"
LOCKER_ALLOCATION_INSERT = """INSERT INTO LOCKER_ALLOCATION (LockerID, StaffID, AllocationDate)
    VALUES (%s, %s, %s)"""
BOOKING_FACILITY_FOR_UPDATE = "SELECT FacilityID, AvailabilityStatus FROM STAFF_FACILITY WHERE FacilityID=%s FOR UPDATE"
BOOKING_CONFLICT_CHECK = """SELECT BookingID FROM FACILITY_BOOKING
    WHERE FacilityID=%s AND BookingDate=%s AND BookingStatus='CONFIRMED'
    AND StartTime < %s AND EndTime > %s
    FOR UPDATE"""

ACTION_QUERIES = {
    ("staff", "deactivate"): "UPDATE STAFF SET StaffStatus='INACTIVE' WHERE StaffID=%s",
    ("bookings", "cancel"): "UPDATE FACILITY_BOOKING SET BookingStatus='CANCELLED' WHERE BookingID=%s AND BookingStatus IN ('PENDING','CONFIRMED')",
    ("bookings", "complete"): "UPDATE FACILITY_BOOKING SET BookingStatus='COMPLETED' WHERE BookingID=%s AND BookingStatus='CONFIRMED' AND (BookingDate<CURRENT_DATE() OR (BookingDate=CURRENT_DATE() AND EndTime<CURRENT_TIME()))",
    ("parking", "release"): "UPDATE STAFF_PARKING SET AllocationStatus='RELEASED', ValidUntil=COALESCE(ValidUntil,GREATEST(ValidFrom,CURRENT_DATE())) WHERE ParkingID=%s AND AllocationStatus='ACTIVE'",
    ("locker-allocations", "return"): "UPDATE LOCKER_ALLOCATION SET Status='RETURNED', ReturnDate=CURRENT_DATE() WHERE AllocationID=%s AND Status='ACTIVE'",
    ("lockers", "unavailable"): "UPDATE LOCKER SET Status='UNAVAILABLE' WHERE LockerID=%s AND Status='AVAILABLE'",
    ("lockers", "available"): "UPDATE LOCKER SET Status='AVAILABLE' WHERE LockerID=%s AND Status='UNAVAILABLE'",
    ("meals", "delete"): "DELETE FROM MEAL_SCHEDULE WHERE MealID=%s",
}

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


def insert_statement(table, columns):
    placeholders = ", ".join(["%s"] * len(columns))
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"


def update_statement(table, columns, primary_key):
    assignments = ", ".join(f"{column}=%s" for column in columns)
    return f"UPDATE {table} SET {assignments} WHERE {primary_key}=%s"


def record_by_id_statement(table, primary_key):
    return f"SELECT * FROM {table} WHERE {primary_key}=%s"


def search_statement(query, columns):
    clauses = [f"{column} LIKE %s" for column in columns]
    return f"SELECT * FROM ({query.rstrip(';')}) AS results WHERE " + " OR ".join(clauses)
