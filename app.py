from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import secrets
import re
import geonamescache
from datetime import datetime

app = Flask(__name__)

app.secret_key = secrets.token_hex(32)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'silerdawncoachesdb'

mysql = MySQL(app)


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    msg = None
    if 'dismiss' in request.args:
        msg = None

    if request.method == "POST":
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        email = request.form.get("email")
        phone = request.form.get("phone")
        city = request.form.get("city")
        addressOne = request.form.get("address1")
        addressTwo = request.form.get("address2")
        postCode = request.form.get("postcode")
        notes = request.form.get("notes")

        # Regex validation
        validEmail = re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)
        validPost = re.match(r'^([A-Z]{1,2}[0-9][0-9A-Z]? ?[0-9][A-Z]{2})$', postCode)

        # Get list of valid cities
        gc = geonamescache.GeonamesCache()
        cities = gc.get_cities()
        cityNames = [cityData['name'] for cityData in cities.values()]

        if city in cityNames:
            validCity = True
        else:
            validCity = False

        # Check required fields and validation
        if fname.isalpha() and lname.isalpha() and email and validEmail and validPost and len(phone) <= 20 and validCity:
            try:
                query = """INSERT INTO customer 
                            (`First Name`, `Surname`, `Email`, `Address Line 1`,
                            `Address Line 2`, `City`, `Postcode`, `Phone Number`, `Special Notes`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(query, (fname, lname, email, addressOne, addressTwo, city, postCode, phone, notes))
                mysql.connection.commit()
                msg = "Customer Added!"
            except Exception as e:
                print(e)
                msg = "Customer could not be added"
        elif not fname.isalpha() or not lname.isalpha():
            msg = "Enter a valid name"
        elif not validEmail:
            msg = "Enter a valid email"
        elif len(phone) > 20:
            msg = "Enter a valid phone number"
        elif not validCity:
            msg = "Enter a valid city name"
        elif not validPost:
            msg = "Enter a valid PostCode"

    return render_template('index.html', title="Home", msg=msg)


@app.route("/admin", methods=['GET', 'POST'])
def admin():
    msg = None
    if 'dismiss' in request.args:
        msg = None
        
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "goober" and password == "root":
            return redirect(url_for('access'))
        else:
            msg = "Incorrect Credential"
            print(msg)
    return render_template("admin_tab.html", title="Admin Login",msg=msg)

@app.route("/trip", methods=['GET', 'POST'])
def trip():
    msg = None
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()


        cursor.execute(f'SELECT DestinationID, Destination FROM destination;')
        destinations = cursor.fetchall()
        
        cursor.execute(f'SELECT * FROM driver;')
        driver = cursor.fetchall()

        cursor.execute(f'SELECT * FROM coach;')
        coach = cursor.fetchall()

        return render_template("new_trip.html",
                                title="New Trip",
                                tables=tables,
                                destinations=destinations, 
                                driver=driver, 
                                coach=coach)
    finally:
        cursor.close()

@app.route("/newTrip", methods=['GET', 'POST'])
def newTrip():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    destination = request.form.get('destination')
    driver = request.form.get('driver')
    date = request.form.get('date')
    coach = request.form.get('coach')
    
    try:
        date = datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
        query = "INSERT INTO trip (DestinationID, DriverID, Date, CoachID) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (destination, driver, date, coach))

        mysql.connection.commit()
        msg = "Trip Added"
    except:
        print("Error")

    return redirect(url_for('booking'))


@app.route("/access", methods=['GET', 'POST'])
def access():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        # Retrieve stored adminAction
        adminAction = session.get('adminAction')
        
        if adminAction == "trip":
            cursor.execute(f'SELECT DestinationID, Destination FROM destination;')
            destinations = cursor.fetchall()
            
            cursor.execute(f'SELECT * FROM driver;')
            driver = cursor.fetchall()

            cursor.execute(f'SELECT * FROM coach;')
            coach = cursor.fetchall()

            return render_template("access_tab.html",
                                    title="Admin | Edit",
                                    tables=tables,
                                    adminAction=adminAction, 
                                    destinations=destinations, 
                                    driver=driver, 
                                    coach=coach)
        
        if adminAction == "finance":
            cursor.execute("SELECT * FROM silerdawncoachesdb.destination")
            financeArray = cursor.fetchall()

            finaceTrip = session.get('finaceTrip')
            finData = session.get('finData')
            total_seats_booked = session.get('total_seats_booked')
            percentage_seats_booked = session.get('percentage_seats_booked')
            total_revenue = session.get('total_revenue')

            return render_template("access_tab.html",
                                   title="Admin | Edit",
                                   tables=tables,
                                   adminAction=adminAction, 
                                   financeArray=financeArray,
                                   finaceTrip=finaceTrip,
                                   finData=finData,
                                   total_seats_booked=total_seats_booked,
                                   percentage_seats_booked=percentage_seats_booked,
                                   total_revenue=total_revenue)

        if request.method == "POST":
            tableForm = request.form.get("tableSelect")
            action = request.form.get("doWhat")

            if not tableForm or not action:
                return render_template("access_tab.html", title="Admin | Edit", tables=tables, msg="Select a table and action.")

            # Store in session safely
            session['tableForm'] = tableForm
            session['action'] = action

            # Check if table exists before querying
            validTables = [t['Tables_in_silerdawncoachesdb'] for t in tables]
            if tableForm not in validTables:
                return render_template("access_tab.html", title="Admin | Edit", tables=tables, msg="Invalid table selection.")

            # Add action logic
            if action == "add":
                cursor.execute(f'SHOW COLUMNS FROM `{tableForm}`')
                attributes = cursor.fetchall()[1:]
                return render_template("access_tab.html", title="Admin | Edit", tables=tables, action=action, attributes=attributes, tableForm=tableForm, adminAction=adminAction)

            elif action == "remove":
                cursor.execute(f"SELECT * FROM `{tableForm}`")
                displayData = cursor.fetchall()
                return render_template("access_tab.html", title="Admin | Edit", tables=tables, action=action, tableList=tableForm, displayData=displayData, amountOfData=len(displayData), adminAction=adminAction)

        return render_template("access_tab.html", title="Admin | Edit", tables=tables, adminAction=adminAction)

    finally:
        cursor.close()

@app.route("/addTrip", methods=['GET', 'POST'])
def addTrip():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    destination = request.form.get('destination')
    driver = request.form.get('driver')
    date = request.form.get('date')
    coach = request.form.get('coach')

    
    try:
        date = datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
        query = "INSERT INTO trip (DestinationID, DriverID, Date, CoachID) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (destination, driver, date, coach))

        mysql.connection.commit()
    except:
        print(destination, driver, date, coach)

    return redirect(url_for('access'))

@app.route("/action", methods=['GET', 'POST'])
def action():
    adminAction = request.form.get('adminAction')
    if adminAction:
        session['adminAction'] = adminAction

    return redirect(url_for('access'))


@app.route('/add', methods=['GET', 'POST'])
def add():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    tableForm = session.pop('tableForm')
    action = session.pop('action')
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    cursor.execute(f'SHOW COLUMNS FROM `{tableForm}`')
    attributes = cursor.fetchall()
    columnNames = [col['Field'] for col in attributes]

    if request.method == "POST":
        records = []
        for col in columnNames:
            record = request.form.get(col)
            print(col, record)
            records.append(record)
        placeholders = ', '.join(['%s'] * len(columnNames))
        columns = ', '.join([f"`{col}`" for col in columnNames])
        query = f"INSERT INTO `{tableForm}` ({columns}) VALUES ({placeholders})"
        cursor.execute(query, records)
        mysql.connection.commit()

    return render_template("access_tab.html",
                           title="Admin | Edit",
                           tables=tables,
                           action=action,
                           attributes=attributes,
                           tableForm=tableForm)


@app.route('/delete', methods=['GET', 'POST'])
def delete():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    idRemove = request.args.get('id')
    print("Remove ID:", idRemove)
    tableForm = session.pop('tableForm')
    action = session.pop('action')
    cursor.execute(f'SHOW COLUMNS FROM `{tableForm}`')
    columnList = cursor.fetchall()
    query = f"SELECT * FROM `{tableForm}`"
    cursor.execute(query)
    displayData = cursor.fetchall()
    columnNames = [col['Field'] for col in columnList]
    query = f"DELETE FROM {tableForm} WHERE {columnNames[0]} = %s"
    cursor.execute(query, (idRemove,))
    mysql.connection.commit()

    return render_template("access_tab.html",
                           title="Admin | Edit",
                           tables=tables,
                           action=action,
                           tableList=tableForm,
                           displayData=displayData,
                           amountOfData=len(displayData))

@app.route('/finance', methods=['GET', 'POST'])
def finance():
    if request.method == "POST":
        finaceTrip = request.form.get("finaceTrip")
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Fetch destination details
        cursor.execute('''
            SELECT * FROM silerdawncoachesdb.destination WHERE DestinationID = %s;
        ''', (finaceTrip,))
        destinationInfo = cursor.fetchone()

        if destinationInfo:
            name = destinationInfo['Destination']
            costs = destinationInfo['Cost']
            days = destinationInfo['Days']
            hotel = destinationInfo['Hotel']

            session['finaceTrip'] = finaceTrip

            # Fetch trip details for the selected destination
            cursor.execute('''
                SELECT TripID, Date, CoachID FROM trip WHERE DestinationID = %s;
            ''', (finaceTrip,))
            tripDest = cursor.fetchall()

            finData = []
            total_seats_booked = 0
            total_revenue = 0

            for trip in tripDest:
                tripID = trip['TripID']
                tripDate = trip['Date']
                coachID = trip['CoachID']

                # Fetch booking details for each trip
                cursor.execute('''
                    SELECT booking.BookingID, booking.`Booking Date`, customer.`First Name`, customer.Surname, booking.`Number of people`, booking.`Special Request`
                    FROM booking
                    JOIN customer ON booking.CustomerID = customer.CustomerID
                    WHERE booking.TripID = %s;
                ''', (tripID,))
                bookings = cursor.fetchall()

                seats_booked = sum([booking['Number of people'] for booking in bookings])
                revenue = seats_booked * costs
                total_seats_booked += seats_booked
                total_revenue += revenue

                # Fetch total seats for the coach
                cursor.execute('''
                    SELECT Seats FROM coach WHERE CoachID = %s;
                ''', (coachID,))
                total_seats = cursor.fetchone()['Seats']
                percentage_seats_booked = (seats_booked / total_seats) * 100 if total_seats else 0

                finData.append({
                    'Trip Date': tripDate,
                    'Bookings': bookings,
                    'Trip Name': name,
                    'Cost Per Seat': costs,
                    'Days': days,
                    'Hotel': hotel,
                    'Seats Booked': seats_booked,
                    'Revenue': revenue,
                    'Total Seats': total_seats,
                    'Percentage Seats Booked': percentage_seats_booked
                })

            session['finData'] = finData
            session['total_seats_booked'] = total_seats_booked
            session['total_revenue'] = total_revenue

        return redirect("/access")


    
@app.route("/getDateBooking", methods=['GET', 'POST'])
def getDateBooking():
    if request.method == "GET":
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        trip = request.args.get('trip')
        
        # Get all available dates for the selected trip
        cursor.execute("SELECT Date, TripID FROM trip WHERE DestinationID = %s", (trip,))
        bookingSelectedInfo = cursor.fetchall()

        # Get the destination name
        cursor.execute("SELECT Destination FROM destination WHERE DestinationID = %s", (trip,))
        destinationBooking = cursor.fetchone()

        # Get total seats for the coach assigned to the trip
        cursor.execute("""
            SELECT coach.Seats, trip.TripID FROM coach 
            INNER JOIN trip ON coach.CoachID = trip.CoachID 
            WHERE trip.DestinationID = %s
        """, (trip,))
        result = cursor.fetchone()
        
        if not result:
            session['available_seats'] = 0
            return redirect(url_for('booking'))

        total_seats = result['Seats']
        trip_id = result['TripID']

        # Get booked seats only for the specific trip
        cursor.execute(
            "SELECT COALESCE(SUM(`Number of people`), 0) AS booked_seats FROM booking WHERE TripID = %s",
            (trip_id,)
        )
        booked_result = cursor.fetchone()
        booked_seats = booked_result['booked_seats']

        available_seats = total_seats - booked_seats

        session['destinationBooking'] = destinationBooking
        session['bookingDates'] = bookingSelectedInfo
        session['available_seats'] = max(0, available_seats)

        return redirect(url_for('booking'))


@app.route('/booking', methods=['GET', 'POST'])
def booking():
    trip = None
    msg = None
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch destinations and customer names
    cursor.execute("""SELECT DISTINCT destination.DestinationID, destination.Destination
                    FROM destination
                    INNER JOIN trip ON trip.DestinationID = destination.DestinationID;
                   """)
    destinations = cursor.fetchall()

    cursor.execute("SELECT CustomerID, `First Name`, Surname FROM customer")
    names = cursor.fetchall()
    cursor.execute("SELECT Date FROM trip")
    date = cursor.fetchall()

    destinationBooking = session.get('destinationBooking')
    bookingDates = session.get('bookingDates')
    available_seats = session.get('available_seats', '')

    if request.method == "POST":
        trip = request.form.get("trip")
        dateForm = request.form.get("date")
        nameID = request.form.get("name")
        selectedSeats = int(request.form.get("seats"))
        notes = request.form.get("notes")

        # Ensure a trip exists for this destination and date
        cursor.execute("SELECT TripID, CoachID FROM trip WHERE DestinationID = %s AND Date = %s", (trip, dateForm))
        tripResult = cursor.fetchone()

        if tripResult:
            tripID = tripResult['TripID']
            coachID = tripResult['CoachID']

            # Get total seats of the coach
            cursor.execute("SELECT Seats FROM coach WHERE CoachID = %s", (coachID,))
            coachResult = cursor.fetchone()
            if not coachResult:
                msg = "Error: Coach not found."
                return render_template('booking_tab.html', **locals())

            total_seats = coachResult['Seats']

            # Get currently booked seats
            cursor.execute(
                "SELECT COALESCE(SUM(`Number of people`), 0) AS booked_seats FROM booking WHERE TripID = %s",
                (tripID,)
            )
            booked_seats = cursor.fetchone()['booked_seats']

            remaining_seats = total_seats - booked_seats

            if selectedSeats > remaining_seats:
                msg = "Not enough seats available!"
            else:
                query = """INSERT INTO booking
                            (`Booking Date`, `CustomerID`, `TripID`, `Number of People`, `Special Request`)
                            VALUES (%s, %s, %s, %s, %s)"""
                cursor.execute(query, (dateForm, nameID, tripID, selectedSeats, notes))
                mysql.connection.commit()
                msg = "Booking Added!"
        else:
            msg = "Trip does not exist for the selected destination and date."

    return render_template('booking_tab.html',
                           destinations=destinations,
                           names=names,
                           date=date,
                           seats=available_seats,
                           msg=msg,
                           trip=trip,
                           bookingDates=bookingDates,
                           destinationBooking=destinationBooking)



@app.route('/get_trip_by_date/<path:trip_date>', methods=['GET', 'POST'])
def get_trip_by_date(trip_date):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT DISTINCT destination.DestinationID
        FROM destination
        INNER JOIN trip ON trip.DestinationID = destination.DestinationID
        WHERE trip.Date = %s
    """, (trip_date,))
    trip = cursor.fetchone()
    if trip:
        return {'tripId': trip['DestinationID']}
    return {'tripId': None}


@app.route('/get_trip/<trip_date>', methods=['GET', 'POST'])
def get_trip(trip_date):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT DISTINCT destination.DestinationID, destination.Destination
        FROM destination
        INNER JOIN trip ON trip.DestinationID = destination.DestinationID
        WHERE trip.Date = %s
    """, (trip_date,))
    trips = cursor.fetchall()
    return {'trips': trips}


@app.route('/get_seats/<trip_id>', methods=['GET', 'POST'])
def get_seats(trip_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Get total seats for the coach assigned to the trip
    cursor.execute(
        "SELECT coach.Seats FROM coach "
        "INNER JOIN trip ON coach.CoachID = trip.CoachID "
        "WHERE trip.DestinationID = %s", (trip_id,)
    )
    result = cursor.fetchone()
    if not result:
        return {'seats': 0}  # No trip or coach found
    total_seats = result['Seats']

    # Get the total number of booked seats for the trip
    cursor.execute(
        "SELECT COALESCE(SUM(`Number of people`), 0) AS booked_seats FROM booking WHERE TripID = %s",
        (trip_id,)
    )
    booked_result = cursor.fetchone()
    booked_seats = booked_result['booked_seats']

    available_seats = total_seats - booked_seats
    return {'seats': max(0, available_seats)}  # Ensure no negative values


@app.route("/lookup", methods=['GET', 'POST']) 
def lookup():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get all tables
    cursor.execute('SHOW TABLES')
    tableList = cursor.fetchall()

    # Get selected table from request (default: 'customer')
    tableSelected = request.form.get('tableSelect', 'customer')
    
    # Get columns for the selected table
    cursor.execute(f'SHOW COLUMNS FROM `{tableSelected}`')
    columnList = cursor.fetchall()
    columnNames = [col['Field'] for col in columnList]

    # Get selected column and data input
    columnSelected = request.form.get('columnSelect')
    dataSelected = request.form.get('dataSelect')

    displayData = []

    # Case 1: Searching within a specific column
    if tableSelected and dataSelected and columnSelected:
        query = f"SELECT * FROM `{tableSelected}` WHERE `{columnSelected}` LIKE %s"
        cursor.execute(query, (f"%{dataSelected}%",))
        displayData = cursor.fetchall()
        print("Searching within specific column")

    # Case 2: Fetching only a specific column's data (without filtering)
    elif columnSelected in columnNames:
        query = f"SELECT `{columnSelected}` FROM `{tableSelected}`"
        cursor.execute(query)
        displayData = cursor.fetchall()
        print("Fetching column data")

    # Case 3: Searching across the entire table for data (no column specified)
    elif tableSelected and dataSelected:
        cursor.execute(f"SHOW COLUMNS FROM `{tableSelected}`")
        columns = [col["Field"] for col in cursor.fetchall()]
        
        where_clause = " OR ".join([f"`{col}` LIKE %s" for col in columns])
        query = f"SELECT * FROM `{tableSelected}` WHERE {where_clause}"
        
        cursor.execute(query, tuple([f"%{dataSelected}%"] * len(columns)))
        displayData = cursor.fetchall()
        print("Searching across all columns")

    # Case 4: Default - Fetch all rows from the table
    else:
        query = f"SELECT * FROM `{tableSelected}`"
        cursor.execute(query)
        displayData = cursor.fetchall()
        print("Fetching all data from table")

    # Get upcoming trips
    cursor.execute("SELECT * FROM trip WHERE STR_TO_DATE(Date, '%d/%m/%Y') >= CURDATE() ORDER BY STR_TO_DATE(Date, '%d/%m/%Y') ASC")
    upcomingTrips = cursor.fetchall()
    print(upcomingTrips)

    

    selected_section = request.args.get('selectedSection') or request.form.get('selectedSection')

    return render_template("lookup_tab.html",
                           tableList=tableList,
                           columnList=columnList,
                           displayData=displayData,
                           amountOfData=len(displayData),
                           selected_section=selected_section,
                           upcomingTrips=upcomingTrips)

if __name__ == "__main__":
    app.run(debug=True)
