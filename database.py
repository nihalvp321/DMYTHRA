import sqlite3
import bcrypt

# Connect to the SQLite database
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Enable foreign key constraints
cursor.execute("PRAGMA foreign_keys = OFF;")

# Drop existing tables (only if resetting database)
cursor.execute("DROP TABLE IF EXISTS bookings")
cursor.execute("DROP TABLE IF EXISTS seats")
cursor.execute("DROP TABLE IF EXISTS motivation_class")
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("DROP TABLE IF EXISTS admin")
cursor.execute("DROP TABLE IF EXISTS user_book")

cursor.execute("PRAGMA foreign_keys = ON;")

# Create users table
cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        udid TEXT UNIQUE NOT NULL CHECK(udid LIKE 'UD%'),
        phone TEXT NOT NULL CHECK(length(phone) >= 10),
        email TEXT UNIQUE NOT NULL CHECK(email LIKE '%@%'),
        profile_image TEXT
    )
''')

# Create admin table
cursor.execute('''
    CREATE TABLE admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
''')

# Insert default admin user (if not exists)
admin_username = "admin"
admin_password = "Admin@123"  # Change this to a strong password

cursor.execute("SELECT * FROM admin WHERE username = ?", (admin_username,))
if not cursor.fetchone():
    hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)", (admin_username, hashed_password))

# Create motivation_class table
cursor.execute('''
    CREATE TABLE motivation_class (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_name TEXT NOT NULL,
        venue TEXT NOT NULL,
        time TEXT NOT NULL,
        teacher_image TEXT
    )
''')

# Create seats table with class_id as a foreign key
cursor.execute('''
    CREATE TABLE IF NOT EXISTS seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seat_number TEXT NOT NULL,
        status TEXT DEFAULT 'available',
        class_id INTEGER NOT NULL,
        FOREIGN KEY (class_id) REFERENCES motivation_class(id) ON DELETE CASCADE,
        UNIQUE (class_id, seat_number)  -- Prevents duplicate seat numbers in the same class
    )
''')


##Modify `seats` table to store class_id and ensure seat uniqueness within the class
cursor.execute('''CREATE TABLE IF NOT EXISTS seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seat_number TEXT NOT NULL,
    status TEXT DEFAULT 'available',
    class_id INTEGER NOT NULL,
    FOREIGN KEY (class_id) REFERENCES motivation_class(id) ON DELETE CASCADE,
    UNIQUE (class_id, seat_number)  -- Prevents duplicate seat numbers in the same class
)''')

##Modify `user_book` to track bookings per class
cursor.execute('''CREATE TABLE IF NOT EXISTS user_book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    phone TEXT NOT NULL,
    seat_number TEXT NOT NULL,
    class_id INTEGER NOT NULL,
    FOREIGN KEY (seat_number) REFERENCES seats(seat_number) ON DELETE CASCADE,
    FOREIGN KEY (class_id) REFERENCES motivation_class(id) ON DELETE CASCADE
)''')

# Commit and close the connection
conn.commit()
conn.close()

print("✅ Database updated successfully. Admin user and tables created.")
