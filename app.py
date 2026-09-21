from datetime import date

from flask import Flask, render_template, request, redirect, url_for

from database import get_db_connection


app = Flask(__name__)

FINE_PER_DAY = 5


def close_db(connection, cursor):
    cursor.close()
    connection.close()


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def home():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total_books
        FROM Book
    """)
    total_books = cursor.fetchone()["total_books"]

    cursor.execute("""
        SELECT COUNT(*) AS total_students
        FROM Student
    """)
    total_students = cursor.fetchone()["total_students"]

    cursor.execute("""
        SELECT COUNT(*) AS active_borrows
        FROM Borrow
        WHERE Status = 'Borrowed'
    """)
    active_borrows = cursor.fetchone()["active_borrows"]

    cursor.execute("""
        SELECT COUNT(*) AS overdue_count
        FROM Borrow
        WHERE Status = 'Borrowed'
          AND Due_Date < CURDATE()
    """)
    overdue_count = cursor.fetchone()["overdue_count"]

    cursor.execute("""
        SELECT
            br.Borrow_ID,
            s.Name AS Student_Name,
            b.Title AS Book_Title,
            br.Issue_Date,
            br.Due_Date,
            br.Status
        FROM Borrow br
        JOIN Student s
            ON br.Student_ID = s.Student_ID
        JOIN Book b
            ON br.Book_ID = b.Book_ID
        ORDER BY br.Borrow_ID DESC
        LIMIT 5
    """)

    recent_borrows = cursor.fetchall()

    close_db(connection, cursor)

    return render_template(
        "index.html",
        total_books=total_books,
        total_students=total_students,
        active_borrows=active_borrows,
        overdue_count=overdue_count,
        recent_borrows=recent_borrows
    )


# ============================================================
# BOOK MANAGEMENT
# ============================================================

@app.route("/books")
def books():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    availability = request.args.get("availability", "").strip()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    conditions = []
    params = []

    if search:

        conditions.append("""
            (
                Title LIKE %s
                OR Author LIKE %s
                OR Category LIKE %s
                OR ISBN LIKE %s
                OR Publisher LIKE %s
            )
        """)

        value = f"%{search}%"

        params.extend([
            value,
            value,
            value,
            value,
            value
        ])

    if category:

        conditions.append(
            "Category = %s"
        )

        params.append(category)

    if availability == "available":

        conditions.append(
            "Available_Quantity > 0"
        )

    elif availability == "unavailable":

        conditions.append(
            "Available_Quantity = 0"
        )

    query = """
        SELECT *
        FROM Book
    """

    if conditions:

        query += """
            WHERE
        """

        query += " AND ".join(conditions)

    query += """
        ORDER BY Book_ID
    """

    cursor.execute(
        query,
        tuple(params)
    )

    books = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT Category
        FROM Book
        WHERE Category IS NOT NULL
          AND Category <> ''
        ORDER BY Category
    """)

    categories = cursor.fetchall()

    close_db(connection, cursor)

    return render_template(
        "books.html",
        books=books,
        categories=categories,
        search=search,
        selected_category=category,
        availability=availability
    )


# ============================================================
# ADD BOOK
# ============================================================

@app.route("/books/add", methods=["GET", "POST"])
def add_book():

    if request.method == "POST":

        book_id = request.form["book_id"].strip()
        title = request.form["title"].strip()
        author = request.form["author"].strip()
        category = request.form["category"].strip()
        publisher = request.form["publisher"].strip()
        isbn = request.form["isbn"].strip()

        try:

            quantity = int(
                request.form["quantity"]
            )

        except ValueError:

            return "Invalid quantity"

        if quantity < 1:

            return "Quantity must be at least 1"

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO Book
            (
                Book_ID,
                Title,
                Author,
                Category,
                Publisher,
                ISBN,
                Quantity,
                Available_Quantity
            )
            VALUES
            (
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            book_id,
            title,
            author,
            category,
            publisher,
            isbn,
            quantity,
            quantity
        ))

        connection.commit()

        close_db(
            connection,
            cursor
        )

        return redirect(
            url_for("books")
        )

    return render_template(
        "add_book.html"
    )


# ============================================================
# EDIT BOOK
# ============================================================

@app.route(
    "/books/edit/<int:book_id>",
    methods=["GET", "POST"]
)
def edit_book(book_id):

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    if request.method == "POST":

        title = request.form["title"].strip()
        author = request.form["author"].strip()
        category = request.form["category"].strip()
        publisher = request.form["publisher"].strip()
        isbn = request.form["isbn"].strip()

        try:

            new_quantity = int(
                request.form["quantity"]
            )

        except ValueError:

            close_db(
                connection,
                cursor
            )

            return "Invalid quantity"

        if new_quantity < 1:

            close_db(
                connection,
                cursor
            )

            return "Quantity must be at least 1"

        cursor.execute("""
            SELECT
                Quantity,
                Available_Quantity
            FROM Book
            WHERE Book_ID = %s
        """, (book_id,))

        current_book = cursor.fetchone()

        if not current_book:

            close_db(
                connection,
                cursor
            )

            return "Book not found"

        borrowed_count = (
            current_book["Quantity"]
            -
            current_book["Available_Quantity"]
        )

        if new_quantity < borrowed_count:

            close_db(
                connection,
                cursor
            )

            return (
                f"Cannot reduce quantity below "
                f"{borrowed_count}. "
                f"{borrowed_count} copy/copies "
                f"are currently borrowed."
            )

        new_available_quantity = (
            new_quantity
            -
            borrowed_count
        )

        cursor.execute("""
            UPDATE Book
            SET
                Title = %s,
                Author = %s,
                Category = %s,
                Publisher = %s,
                ISBN = %s,
                Quantity = %s,
                Available_Quantity = %s
            WHERE Book_ID = %s
        """, (
            title,
            author,
            category,
            publisher,
            isbn,
            new_quantity,
            new_available_quantity,
            book_id
        ))

        connection.commit()

        close_db(
            connection,
            cursor
        )

        return redirect(
            url_for("books")
        )

    cursor.execute("""
        SELECT *
        FROM Book
        WHERE Book_ID = %s
    """, (book_id,))

    book = cursor.fetchone()

    close_db(
        connection,
        cursor
    )

    if not book:

        return "Book not found"

    return render_template(
        "edit_book.html",
        book=book
    )


# ============================================================
# DELETE BOOK
# ============================================================

@app.route(
    "/books/delete/<int:book_id>",
    methods=["POST"]
)
def delete_book(book_id):

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT COUNT(*) AS borrow_count
        FROM Borrow
        WHERE Book_ID = %s
    """, (book_id,))

    borrow_count = cursor.fetchone()[
        "borrow_count"
    ]

    if borrow_count > 0:

        close_db(
            connection,
            cursor
        )

        return (
            "This book cannot be deleted "
            "because it has borrowing records."
        )

    cursor.execute("""
        DELETE FROM Book
        WHERE Book_ID = %s
    """, (book_id,))

    connection.commit()

    close_db(
        connection,
        cursor
    )

    return redirect(
        url_for("books")
    )


# ============================================================
# MEMBER MANAGEMENT
# ============================================================

@app.route("/members")
def members():

    search = request.args.get(
        "search",
        ""
    ).strip()

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    if search:

        value = f"%{search}%"

        cursor.execute("""
            SELECT
                s.Student_ID,
                s.Name,
                s.Email,
                s.Department,
                s.Year,

                COUNT(
                    CASE
                        WHEN br.Status = 'Borrowed'
                        THEN 1
                    END
                ) AS Active_Borrows

            FROM Student s

            LEFT JOIN Borrow br
                ON s.Student_ID = br.Student_ID

            WHERE
                s.Name LIKE %s
                OR s.Email LIKE %s
                OR s.Department LIKE %s

            GROUP BY
                s.Student_ID,
                s.Name,
                s.Email,
                s.Department,
                s.Year

            ORDER BY s.Student_ID
        """, (
            value,
            value,
            value
        ))

    else:

        cursor.execute("""
            SELECT
                s.Student_ID,
                s.Name,
                s.Email,
                s.Department,
                s.Year,

                COUNT(
                    CASE
                        WHEN br.Status = 'Borrowed'
                        THEN 1
                    END
                ) AS Active_Borrows

            FROM Student s

            LEFT JOIN Borrow br
                ON s.Student_ID = br.Student_ID

            GROUP BY
                s.Student_ID,
                s.Name,
                s.Email,
                s.Department,
                s.Year

            ORDER BY s.Student_ID
        """)

    members = cursor.fetchall()

    close_db(
        connection,
        cursor
    )

    return render_template(
        "members.html",
        members=members,
        search=search
    )


# ============================================================
# ADD MEMBER
# ============================================================

@app.route(
    "/members/add",
    methods=["GET", "POST"]
)
def add_member():

    if request.method == "POST":

        student_id = request.form[
            "student_id"
        ].strip()

        name = request.form[
            "name"
        ].strip()

        email = request.form[
            "email"
        ].strip()

        department = request.form[
            "department"
        ].strip()

        year = request.form[
            "year"
        ].strip()

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO Student
            (
                Student_ID,
                Name,
                Email,
                Department,
                Year
            )
            VALUES
            (
                %s, %s, %s, %s, %s
            )
        """, (
            student_id,
            name,
            email,
            department,
            year
        ))

        connection.commit()

        close_db(
            connection,
            cursor
        )

        return redirect(
            url_for("members")
        )

    return render_template(
        "add_member.html"
    )


# ============================================================
# MEMBER BORROWING HISTORY
# ============================================================

@app.route(
    "/members/<int:student_id>"
)
def member_history(student_id):

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM Student
        WHERE Student_ID = %s
    """, (student_id,))

    student = cursor.fetchone()

    if not student:

        close_db(
            connection,
            cursor
        )

        return "Student not found"

    cursor.execute("""
        SELECT
            br.Borrow_ID,
            b.Title AS Book_Title,
            br.Issue_Date,
            br.Due_Date,
            br.Return_Date,
            br.Status

        FROM Borrow br

        JOIN Book b
            ON br.Book_ID = b.Book_ID

        WHERE br.Student_ID = %s

        ORDER BY br.Borrow_ID DESC
    """, (student_id,))

    history = cursor.fetchall()

    close_db(
        connection,
        cursor
    )

    return render_template(
        "member_history.html",
        student=student,
        history=history
    )


# ============================================================
# BORROW / ISSUE BOOK
# ============================================================

@app.route(
    "/borrow",
    methods=["GET", "POST"]
)
def borrow():

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    if request.method == "POST":

        student_id = request.form[
            "student_id"
        ]

        book_id = request.form[
            "book_id"
        ]

        librarian_id = request.form[
            "librarian_id"
        ]

        due_date = request.form[
            "due_date"
        ]

        cursor.execute("""
            SELECT
                Available_Quantity
            FROM Book
            WHERE Book_ID = %s
        """, (book_id,))

        book = cursor.fetchone()

        if not book:

            close_db(
                connection,
                cursor
            )

            return "Book not found"

        if book[
            "Available_Quantity"
        ] <= 0:

            close_db(
                connection,
                cursor
            )

            return "Book is currently unavailable"

        cursor.execute("""
            SELECT
                COALESCE(
                    MAX(Borrow_ID),
                    0
                ) + 1 AS next_id
            FROM Borrow
        """)

        borrow_id = cursor.fetchone()[
            "next_id"
        ]

        cursor.execute("""
            INSERT INTO Borrow
            (
                Borrow_ID,
                Student_ID,
                Book_ID,
                Librarian_ID,
                Issue_Date,
                Due_Date,
                Status
            )
            VALUES
            (
                %s, %s, %s, %s,
                %s, %s, 'Borrowed'
            )
        """, (
            borrow_id,
            student_id,
            book_id,
            librarian_id,
            date.today(),
            due_date
        ))

        cursor.execute("""
            UPDATE Book
            SET
                Available_Quantity =
                Available_Quantity - 1
            WHERE Book_ID = %s
        """, (book_id,))

        connection.commit()

        close_db(
            connection,
            cursor
        )

        return redirect(
            url_for("borrow")
        )

    cursor.execute("""
        SELECT *
        FROM Student
        ORDER BY Student_ID
    """)

    students = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM Book
        WHERE Available_Quantity > 0
        ORDER BY Book_ID
    """)

    books = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM Librarian
        ORDER BY Librarian_ID
    """)

    librarians = cursor.fetchall()

    cursor.execute("""
        SELECT
            br.Borrow_ID,
            s.Name AS Student_Name,
            b.Title AS Book_Title,
            l.Name AS Librarian_Name,
            br.Issue_Date,
            br.Due_Date,
            br.Return_Date,
            br.Status

        FROM Borrow br

        JOIN Student s
            ON br.Student_ID = s.Student_ID

        JOIN Book b
            ON br.Book_ID = b.Book_ID

        JOIN Librarian l
            ON br.Librarian_ID = l.Librarian_ID

        ORDER BY br.Borrow_ID DESC
    """)

    borrow_records = cursor.fetchall()

    close_db(
        connection,
        cursor
    )

    return render_template(
        "borrow.html",
        students=students,
        books=books,
        librarians=librarians,
        borrow_records=borrow_records
    )


# ============================================================
# RETURN BOOK + FINE CREATION
# ============================================================

@app.route(
    "/return/<int:borrow_id>",
    methods=["POST"]
)
def return_book(borrow_id):

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            Book_ID,
            Due_Date

        FROM Borrow

        WHERE Borrow_ID = %s
          AND Status = 'Borrowed'
    """, (borrow_id,))

    borrow_record = cursor.fetchone()

    if not borrow_record:

        close_db(
            connection,
            cursor
        )

        return (
            "Borrow record not found "
            "or book already returned."
        )

    book_id = borrow_record[
        "Book_ID"
    ]

    due_date = borrow_record[
        "Due_Date"
    ]

    days_overdue = max(
        (date.today() - due_date).days,
        0
    )

    fine_amount = (
        days_overdue *
        FINE_PER_DAY
    )

    cursor.execute("""
        UPDATE Borrow
        SET
            Return_Date = %s,
            Status = 'Returned'

        WHERE Borrow_ID = %s
    """, (
        date.today(),
        borrow_id
    ))

    cursor.execute("""
        UPDATE Book
        SET
            Available_Quantity =
            Available_Quantity + 1

        WHERE Book_ID = %s
    """, (book_id,))

    if fine_amount > 0:

        cursor.execute("""
            INSERT INTO Fine
            (
                Borrow_ID,
                Amount,
                Paid_Status
            )
            VALUES
            (
                %s,
                %s,
                'Unpaid'
            )
        """, (
            borrow_id,
            fine_amount
        ))

    connection.commit()

    close_db(
        connection,
        cursor
    )

    return redirect(
        url_for("borrow")
    )


# ============================================================
# OVERDUE BOOKS
# ============================================================

@app.route("/overdue")
def overdue():

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            br.Borrow_ID,
            s.Name AS Student_Name,
            b.Title AS Book_Title,
            br.Due_Date,

            DATEDIFF(
                CURDATE(),
                br.Due_Date
            ) AS Days_Overdue,

            DATEDIFF(
                CURDATE(),
                br.Due_Date
            ) * %s AS Estimated_Fine

        FROM Borrow br

        JOIN Student s
            ON br.Student_ID = s.Student_ID

        JOIN Book b
            ON br.Book_ID = b.Book_ID

        WHERE
            br.Status = 'Borrowed'
            AND br.Due_Date < CURDATE()

        ORDER BY br.Due_Date
    """, (FINE_PER_DAY,))

    overdue_records = cursor.fetchall()

    close_db(
        connection,
        cursor
    )

    return render_template(
        "overdue.html",
        overdue_records=overdue_records,
        fine_per_day=FINE_PER_DAY
    )


# ============================================================
# FINE MANAGEMENT
# ============================================================

@app.route("/fines")
def fines():

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            f.Fine_ID,
            f.Borrow_ID,
            s.Name AS Student_Name,
            b.Title AS Book_Title,
            f.Amount,
            f.Paid_Status

        FROM Fine f

        JOIN Borrow br
            ON f.Borrow_ID = br.Borrow_ID

        JOIN Student s
            ON br.Student_ID = s.Student_ID

        JOIN Book b
            ON br.Book_ID = b.Book_ID

        ORDER BY f.Fine_ID DESC
    """)

    fines = cursor.fetchall()

    close_db(
        connection,
        cursor
    )

    return render_template(
        "fines.html",
        fines=fines
    )


@app.route(
    "/fines/pay/<int:fine_id>",
    methods=["POST"]
)
def pay_fine(fine_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE Fine
        SET Paid_Status = 'Paid'
        WHERE Fine_ID = %s
    """, (fine_id,))

    connection.commit()

    close_db(
        connection,
        cursor
    )

    return redirect(
        url_for("fines")
    )


# ============================================================
# RESERVATIONS
# ============================================================

@app.route(
    "/reservations",
    methods=["GET", "POST"]
)
def reservations():

    connection = get_db_connection()
    cursor = connection.cursor(
        dictionary=True
    )

    if request.method == "POST":

        student_id = request.form[
            "student_id"
        ]

        book_id = request.form[
            "book_id"
        ]

        cursor.execute("""
            SELECT
                Available_Quantity
            FROM Book
            WHERE Book_ID = %s
        """, (book_id,))

        book = cursor.fetchone()

        if not book:

            close_db(
                connection,
                cursor
            )

            return "Book not found"

        if book[
            "Available_Quantity"
        ] > 0:

            close_db(
                connection,
                cursor
            )

            return (
                "This book is currently available. "
                "Reservation is not required."
            )

        cursor.execute("""
            SELECT COUNT(*) AS existing
            FROM Reservation

            WHERE Student_ID = %s
              AND Book_ID = %s
              AND Status = 'Waiting'
        """, (
            student_id,
            book_id
        ))

        existing = cursor.fetchone()[
            "existing"
        ]

        if existing > 0:

            close_db(
                connection,
                cursor
            )

            return (
                "You already have an active "
                "reservation for this book."
            )

        cursor.execute("""
            INSERT INTO Reservation
            (
                Student_ID,
                Book_ID,
                Reservation_Date,
                Status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'Waiting'
            )
        """, (
            student_id,
            book_id,
            date.today()
        ))

        connection.commit()

        close_db(
            connection,
            cursor
        )

        return redirect(
            url_for("reservations")
        )

    cursor.execute("""
        SELECT *
        FROM Student
        ORDER BY Student_ID
    """)

    students = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM Book
        WHERE Available_Quantity = 0
        ORDER BY Book_ID
    """)

    unavailable_books = cursor.fetchall()

    cursor.execute("""
        SELECT
            r.Reservation_ID,
            s.Name AS Student_Name,
            b.Title AS Book_Title,
            r.Reservation_Date,
            r.Status

        FROM Reservation r

        JOIN Student s
            ON r.Student_ID = s.Student_ID

        JOIN Book b
            ON r.Book_ID = b.Book_ID

        ORDER BY r.Reservation_ID DESC
    """)

    reservation_records = cursor.fetchall()

    close_db(
        connection,
        cursor
    )

    return render_template(
        "reservations.html",
        students=students,
        unavailable_books=unavailable_books,
        reservation_records=reservation_records
    )


@app.route(
    "/reservations/cancel/<int:reservation_id>",
    methods=["POST"]
)
def cancel_reservation(reservation_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE Reservation

        SET Status = 'Cancelled'

        WHERE Reservation_ID = %s
          AND Status = 'Waiting'
    """, (reservation_id,))

    connection.commit()

    close_db(
        connection,
        cursor
    )

    return redirect(
        url_for("reservations")
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )