from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_mysqldb import MySQL
import MySQLdb.cursors
import secrets
import re
import geonamescache
from datetime import datetime, timedelta
from fpdf import FPDF
import io

app = Flask(__name__)

app.secret_key = secrets.token_hex(32)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'silverdawncoaches'

mysql = MySQL(app)

@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    msg = None
    form_data = {}
    invalid_fields = []

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

        form_data = {
            'fname': fname,
            'lname': lname,
            'email': email,
            'phone': phone,
            'city': city,
            'address1': addressOne,
            'address2': addressTwo,
            'postcode': postCode,
            'notes': notes
        }

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
                form_data = {}  # Clear form data on successful submission
            except Exception as e:
                print(e)
                msg = "Customer could not be added"
        else:
            if not fname.isalpha():
                invalid_fields.append('fname')
                msg = "Enter a valid first name"
            if not lname.isalpha():
                invalid_fields.append('lname')
                msg = "Enter a valid last name"
            if not validEmail:
                invalid_fields.append('email')
                msg = "Enter a valid email"
            if len(phone) > 20:
                invalid_fields.append('phone')
                msg = "Enter a valid phone number"
            if not validCity:
                invalid_fields.append('city')
                msg = "Enter a valid city name"
            if not validPost:
                invalid_fields.append('postcode')
                msg = "Enter a valid PostCode"

    return render_template('index.html', title="Home", msg=msg, form_data=form_data, invalid_fields=invalid_fields)




@app.route("/admin", methods=['GET', 'POST'])
def admin():
    msg = None
    if 'dismiss' in request.args:
        msg = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        login_attempts = session.get('login_attempts', 0)
        last_attempt_time = session.get('last_attempt_time')

        if last_attempt_time:
            last_attempt_time = datetime.strptime(last_attempt_time, '%Y-%m-%d %H:%M:%S.%f')
            if datetime.now() - last_attempt_time < timedelta(minutes=5):
                msg = "Too many login attempts. Please try again later."
                return render_template("admin_tab.html", title="Admin Login", msg=msg)

        if login_attempts >= 3:
            session['last_attempt_time'] = str(datetime.now())
            msg = "Too many login attempts. Please try again later."
        elif username == "goober" and password == "root":
            session['admin_logged_in'] = True
            session['login_attempts'] = 0  # Reset login attempts on successful login
            return redirect(url_for('access'))
        else:
            session['login_attempts'] = login_attempts + 1
            msg = "Incorrect Credential"
            print(msg)

    return render_template("admin_tab.html", title="Admin Login", msg=msg)



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
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))

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
            drivers = cursor.fetchall()

            cursor.execute(f'SELECT * FROM coach;')
            coaches = cursor.fetchall()

            return render_template("access_tab.html",
                                    title="Admin | Trip",
                                    tables=tables,
                                    adminAction=adminAction, 
                                    destinations=destinations, 
                                    drivers=drivers, 
                                    coaches=coaches)
        
        if adminAction == "finance":
            cursor.execute("SELECT * FROM silverdawncoaches.destination")
            financeArray = cursor.fetchall()

            finaceTrip = session.get('finaceTrip')
            finData = session.get('finData')
            total_seats_booked = session.get('total_seats_booked')
            percentage_seats_booked = session.get('percentage_seats_booked')
            total_revenue = session.get('total_revenue')

            return render_template("access_tab.html",
                                   title="Admin | Finance",
                                   tables=tables,
                                   adminAction=adminAction, 
                                   financeArray=financeArray,
                                   finaceTrip=finaceTrip,
                                   finData=finData,
                                   total_seats_booked=total_seats_booked,
                                   percentage_seats_booked=percentage_seats_booked,
                                   total_revenue=total_revenue)

        if adminAction == "edit":
            if request.method == "POST":
                tableForm = request.form.get("tableSelect")
                action = request.form.get("doWhat")

                if not tableForm or not action:
                    return render_template("access_tab.html", title="Admin | Edit", tables=tables, msg="Select a table and action.")

                # Store in session safely
                session['tableForm'] = tableForm
                session['action'] = action

                # Check if table exists before querying
                validTables = ['driver', 'destination', 'coach']
                if tableForm not in validTables:
                    return render_template("access_tab.html", title="Admin | Edit", tables=tables, msg="Invalid table selection.")

                # Add action logic
                if action == "add":
                    cursor.execute(f'SHOW COLUMNS FROM `{tableForm}`')
                    attributes = cursor.fetchall()[1:]  # Exclude the primary key (first column)
                    return render_template("access_tab.html", title="Admin | Edit", tables=tables, action=action, attributes=attributes, tableForm=tableForm, adminAction=adminAction)

                elif action == "remove":
                    cursor.execute(f"SELECT * FROM `{tableForm}`")
                    displayData = cursor.fetchall()
                    return render_template("access_tab.html", title="Admin | Edit", tables=tables, action=action, tableList=tableForm, displayData=displayData, amountOfData=len(displayData), adminAction=adminAction)

            return render_template("access_tab.html", title="Admin | Edit", tables=tables, adminAction=adminAction)

        return render_template("access_tab.html", title="Admin | Edit", tables=tables, adminAction=adminAction)

    finally:
        cursor.close()




@app.route('/add', methods=['GET', 'POST'])
def add():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    tableForm = session.pop('tableForm')
    action = session.pop('action')
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    cursor.execute(f'SHOW COLUMNS FROM `{tableForm}`')
    attributes = cursor.fetchall()[1:]  # Exclude the primary key (first column)
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


@app.route('/delete', methods=['GET'])
def delete():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    tableForm = session.get('tableForm')
    idRemove = request.args.get('id')
    cursor.execute(f'SHOW COLUMNS FROM `{tableForm}`')
    columnList = cursor.fetchall()
    columnNames = [col['Field'] for col in columnList]
    query = f"DELETE FROM `{tableForm}` WHERE `{columnNames[0]}` = %s"
    cursor.execute(query, (idRemove,))
    mysql.connection.commit()

    return redirect(url_for('access'))

@app.route('/action', methods=['POST'])
def action():
    adminAction = request.form.get('adminAction')
    if adminAction:
        session['adminAction'] = adminAction
    return redirect(url_for('access'))


@app.route('/finance', methods=['GET', 'POST'])
def finance():
    if request.method == "POST":
        finaceTrip = request.form.get("finaceTrip")
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Fetch destination details
        cursor.execute('''
            SELECT * FROM silverdawncoaches.destination WHERE DestinationID = %s;
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


@app.route('/postCodeLookup', methods=['GET', 'POST'])
def postCodeLookup():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if request.method == "POST":
        postcode = request.form.get('postcode')
        print(postcode)
        session['postcode'] = postcode
    
        # Use a LIKE query with a wildcard to match postcodes that start with the given input
        cursor.execute("SELECT * FROM customer WHERE Postcode LIKE %s", (postcode + '%',))
        customersPostcode = cursor.fetchall()
        print(customersPostcode)
        session['customersPostcode'] = customersPostcode
        session['selected_section'] = 'searchPostcodes'
        
        return redirect(url_for('lookup'))
    return redirect(url_for('lookup'))





@app.route('/generatePdf', methods=['GET'])
def generatePdf():
    customerDataPdf = session.get('customersPostcode')
    postcode = session.get('postcode')
   
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Add table headers
    headers = ["Name", "Address Line 1", "Address Line 2", "Postcode"]
    for header in headers:
        pdf.cell(40, 10, header, 1)
    pdf.ln()

    # Add table rows
    if customerDataPdf:
        for row in customerDataPdf:
            name = f"{row['First Name']} {row['Surname']}"
            address1 = row['Address Line 1']
            address2 = row['Address Line 2']
            postcodeTb = row['Postcode']
            pdf.cell(40, 10, name, 1)
            pdf.cell(40, 10, address1, 1)
            pdf.cell(40, 10, address2, 1)
            pdf.cell(40, 10, postcodeTb, 1)
            pdf.ln()

    # Save the PDF to a BytesIO object
    pdf_output = io.BytesIO()
    pdf_output.write(pdf.output(dest='S').encode('latin1'))
    pdf_output.seek(0)
    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    print(f"search: {postcode}")
    # Create the file name
    file_name = f"{postcode}_{current_date}.pdf"
    return send_file(pdf_output, download_name=file_name, as_attachment=True)


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

    # Store the selected section in the session
    if request.method == "POST":
        selected_section = request.form.get('selectedSection', 'searchPostcodes')
        session['selected_section'] = selected_section  # Update the session with the new section
    else:
        selected_section = session.get('selected_section', 'searchPostcodes')

    # Case 1: Searching within a specific column
    if tableSelected and dataSelected and columnSelected:
        query = f"SELECT * FROM `{tableSelected}` WHERE `{columnSelected}` LIKE %s"
        cursor.execute(query, (f"%{dataSelected}%",))
        displayData = cursor.fetchall()

    # Case 2: Fetching only a specific column's data
    elif columnSelected in columnNames:
        query = f"SELECT `{columnSelected}` FROM `{tableSelected}`"
        cursor.execute(query)
        displayData = cursor.fetchall()

    # Case 3: Searching across the entire table
    elif tableSelected and dataSelected:
        cursor.execute(f"SHOW COLUMNS FROM `{tableSelected}`")
        columns = [col["Field"] for col in cursor.fetchall()]

        where_clause = " OR ".join([f"`{col}` LIKE %s" for col in columns])
        query = f"SELECT * FROM `{tableSelected}` WHERE {where_clause}"
        
        cursor.execute(query, tuple([f"%{dataSelected}%"] * len(columns)))
        displayData = cursor.fetchall()

    # Case 4: Default - Fetch all rows from the table
    else:
        query = f"SELECT * FROM `{tableSelected}`"
        cursor.execute(query)
        displayData = cursor.fetchall()

    # Fetch upcoming trips
    cursor.execute("SELECT * FROM trip WHERE STR_TO_DATE(Date, '%d/%m/%Y') >= CURDATE() ORDER BY STR_TO_DATE(Date, '%d/%m/%Y') ASC")
    upcomingTrips = cursor.fetchall()

    for trip in upcomingTrips:
        cursor.execute("""
            SELECT d.Destination, d.Hotel, d.Cost, d.Days, c.Registration
            FROM destination d
            JOIN coach c ON c.CoachID = %s
            WHERE d.DestinationID = %s
        """, (trip['CoachID'], trip['DestinationID']))
        destination = cursor.fetchone()

        if destination:
            trip.update(destination)

    # Fetch destinations and trip dates for the Trip Passengers section
    cursor.execute("SELECT DISTINCT DestinationID, Destination FROM destination")
    destinations = cursor.fetchall()

    cursor.execute("SELECT DISTINCT Date FROM trip")
    tripDates = cursor.fetchall()

    customersPostcode = session.get('customersPostcode', [])
    passengers = session.get('passengers', [])

    return render_template("lookup_tab.html",
                           tableList=tableList,
                           columnList=columnList,
                           displayData=displayData,
                           amountOfData=len(displayData),
                           selected_section=selected_section,
                           upcomingTrips=upcomingTrips,
                           customersPostcode=customersPostcode,
                           destinations=destinations,
                           tripDates=tripDates,
                           passengers=passengers)

@app.route('/tripPassengersLookup', methods=['POST'])
def tripPassengersLookup():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    tripDestination = request.form.get('tripDestination')
    tripDate = request.form.get('tripDate')

    # Fetch passenger details for the selected trip
    cursor.execute("""
        SELECT c.`First Name`, c.Surname, c.Email, c.`Phone Number`, b.`Special Request`
        FROM booking b
        JOIN customer c ON b.CustomerID = c.CustomerID
        JOIN trip t ON b.TripID = t.TripID
        WHERE t.DestinationID = %s AND t.Date = %s
    """, (tripDestination, tripDate))
    passengers = cursor.fetchall()

    session['passengers'] = passengers
    session['selected_section'] = 'tripPassengers'

    return redirect(url_for('lookup'))

@app.route('/getTripDates', methods=['GET'])
def getTripDates():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    destination_id = request.args.get('destination')
    
    cursor.execute("SELECT Date FROM trip WHERE DestinationID = %s", (destination_id,))
    dates = cursor.fetchall()
    date_list = [date['Date'] for date in dates]
    
    return {'dates': date_list}


if __name__ == "__main__":
    app.run(debug=True)