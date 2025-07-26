from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify,g
import sqlite3
import os
import re
import bcrypt
from PIL import Image
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
from flask import g

app = Flask(__name__)
app.secret_key = "supersecretkey"  
DATABASE = "users.db"
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER 
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

 
def query_db(query, args=(), one=False, commit=False):
    """Query the database and return results as tuples."""
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()
        cur.execute(query, args)

        if commit:
            conn.commit()

        result = cur.fetchall()
        return (result[0] if result else None) if one else result



def resize_image(image_path):
    with Image.open(image_path) as img:
        img = img.resize((150, 150))  # Resize to 150x150 pixels (adjust as needed)
        img.save(image_path)  # Save the resized image

@app.before_request
def assign_sponsor_id():
    if 'sponsor_id' not in session:
        session['sponsor_id'] = str(uuid.uuid4())
    g.sponsor_id = session['sponsor_id']


#user
@app.route('/')
def home():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT uf.feedback, uf.rating, u.username, u.email, u.phone, u.profile_image
        FROM user_feedbacks uf
        JOIN users u ON uf.user_id = u.id
        ORDER BY uf.id DESC''')
    feedbacks = c.fetchall()
    conn.close()
    return render_template('main.html', feedbacks=feedbacks)

@app.route('/userregister', methods=['GET', 'POST'])
def userregister():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        udid = request.form.get('udid')
        phone = request.form.get('phone')
        email = request.form.get('email')

        # ✅ Validations
        if not re.match(r'^UD\d{3}$', udid):
            flash("UDID No must start with 'UD' followed by exactly 3 digits (e.g., UD123).", "error")
            return redirect(url_for('userregister'))
        if not re.match(r'^[a-zA-Z0-9_.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]+$', email):
            flash("Invalid email format!", "error")
            return redirect(url_for('userregister'))
        if not re.match(r'^\d{10}$', phone):
            flash("Phone number must be 10 digits!", "error")
            return redirect(url_for('userregister'))
        if not re.match(r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
            flash("Password must be at least 8 characters, include 1 uppercase letter, 1 number, and 1 special character.", "error")
            return redirect(url_for('userregister'))
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('userregister'))

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        image_filename = "noprofile.png"

        try:
            query_db('''
                INSERT INTO users (username, password, udid, phone, email, profile_image)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (username, hashed_password, udid, phone, email, image_filename), commit=True
            )
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('userlogin'))
        except sqlite3.IntegrityError:
            flash("Username, UDID No, or Email already exists!", "error")

    return render_template('userregister.html')


@app.route('/userlogin', methods=['GET', 'POST'])
def userlogin():
    if request.method == 'POST':
        udid = request.form['udid']
        password = request.form['password']

        user = query_db('SELECT id, username, password FROM users WHERE udid = ?', (udid,), one=True)

        if user:
            user_id, username, hashed_password = user
            hashed_password = hashed_password.encode('utf-8')

            if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                session['user_id'] = user_id
                session['user'] = username  # ✅ Unified session key
                flash("Login Successful!", "success")
                return redirect(url_for('userhome'))
            else:
                flash("Invalid Password!", "error")
        else:
            flash("Invalid UDID No!", "error")

    return render_template('userlogin.html')

@app.route('/userhome')
def userhome():
    if 'user' not in session:
        return redirect(url_for('userlogin'))

    # Fetch user details
    user_data = query_db(
        "SELECT username, profile_image, id FROM users WHERE username = ?", 
        (session['user'],), one=True
    )

    if not user_data:
        flash("User not found. Please log in again.", "error")
        return redirect(url_for('userlogin'))

    username, profile_image, user_id = user_data
    profile_image = profile_image or "noprofile.png"
    session['user_id'] = user_id  # Store for like usage

    # Fetch all posts and related user info
    posts = query_db("""
        SELECT skills.id, skills.media, skills.caption, skills.likes, users.username, users.profile_image 
        FROM skills 
        JOIN users ON skills.user_id = users.id 
        ORDER BY skills.id DESC
    """)

    # Create the post list with liked status
    posts_list = []
    for row in posts:
        post_id, media, caption, like_count, post_user, post_profile = row
        posts_list.append({
            "id": post_id,
            "media": media,
            "caption": caption,
            "likes": like_count,
            "username": post_user,
            "profile_image": post_profile or "default-profile.png",
        })

    return render_template(
        'userhome.html',
        username=username,
        profile_image=profile_image,
        posts=posts_list,
        current_time=datetime.now().timestamp()
    )

@app.after_request
def add_header(response):
    # Prevent caching of authenticated pages
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response




@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return redirect(url_for('userlogin'))

    current_username = session['user']

    new_username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    phone = request.form.get('phone')
    profile_image = request.files.get('profile_image')

    if new_username and new_username != current_username:
        existing_user = query_db("SELECT * FROM users WHERE username = ?", [new_username], one=True)
        if existing_user:
            flash("Username already taken. Please choose a different one.", "danger")
            return redirect(url_for('userhome'))
    else:
        new_username = current_username

    updates = []
    values = []

    if new_username != current_username:
        updates.append("username = ?")
        values.append(new_username)

    if email:
        updates.append("email = ?")
        values.append(email)

    if phone:
        updates.append("phone = ?")
        values.append(phone)

    if password:
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        updates.append("password = ?")
        values.append(hashed_password)

    if profile_image:
        filename = f"{new_username}_profile.png"
        filepath = os.path.join("static/uploads", filename)
        profile_image.save(filepath)
        updates.append("profile_image = ?")
        values.append(filename)

    if updates:
        values.append(current_username)
        query_db(f"UPDATE users SET {', '.join(updates)} WHERE username = ?", values)
        session['user'] = new_username

    flash("Profile updated successfully!", "success")
    return redirect(url_for('userhome'))


@app.route('/delete_profile_image', methods=['POST'])
def delete_profile_image():
    if 'user' not in session:
        return redirect(url_for('userlogin'))

    user = session['user']

    user_data = query_db("SELECT profile_image FROM users WHERE username = ?", (user,), one=True)

    if user_data and user_data[0]:
        image_path = os.path.join("static/uploads", user_data[0])
        if os.path.exists(image_path):
            os.remove(image_path)

    query_db("UPDATE users SET profile_image = ? WHERE username = ?", ("noprofile.png", user))

    flash("Profile image deleted successfully!", "success")
    return redirect(url_for('userhome'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))  # This should render main.html

@app.route("/user_motivation", methods=["GET", "POST"])
def user_motivation():
    """Display available motivation classes and their seat availability."""
    # Corrected column order to match HTML expectations
    motivation_classes = query_db(
        "SELECT id, teacher_name, venue, time, teacher_image FROM motivation_class"
    )

    if not motivation_classes:
        return "No motivation classes found!"

    available_seats = {}
    for class_ in motivation_classes:
        class_id = class_[0]  # Accessing `id` using tuple indexing
        available_seats[class_id] = query_db(
            "SELECT seat_number FROM seats WHERE class_id = ? AND status = 'available'", (class_id,)
        )

    return render_template(
        "usermotivation.html",
        motivation_classes=motivation_classes,
        available_seats=available_seats
    )





@app.route('/book_seat/<int:class_id>/<seat_number>', methods=['POST'])
def book_seat(class_id, seat_number):
    name = request.form.get("name")
    age = request.form.get("age")
    phone = request.form.get("phone")

    if not name or not age or not phone:
        flash("Please fill in all fields!", "error")
        return redirect(url_for('user_motivation'))

    # Debugging: Check seat existence
    print(f"Trying to book seat {seat_number} for class {class_id}")

    # Check if the seat is already booked
    existing_booking = query_db("SELECT * FROM user_book WHERE seat_number = ? AND class_id = ?", 
                                (seat_number, class_id), one=True)
    
    if existing_booking:
        flash(f"Seat {seat_number} is already booked!", "error")
    else:
        with sqlite3.connect(DATABASE) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO user_book (name, age, phone, seat_number, class_id) VALUES (?, ?, ?, ?, ?)", 
                        (name, age, phone, seat_number, class_id))
            cur.execute("UPDATE seats SET status='booked' WHERE seat_number=? AND class_id=?", 
                        (seat_number, class_id))  
            conn.commit()
        
        print(f"Seat {seat_number} successfully booked!")
        flash(f"Seat {seat_number} booked successfully!", "success")

    return redirect(url_for('user_motivation'))

@app.route('/skills', methods=['GET', 'POST'])
def skills():
    if 'user_id' not in session:
        return redirect(url_for('userlogin'))

    user_id = session['user_id']
    
    user_row = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    user = {
        "id": user_row[0],
        "username": user_row[1],
        "password": user_row[2],
        "udid": user_row[3],
        "phone": user_row[4],
        "email": user_row[5],
        "profile_image": user_row[6] if user_row[6] else "noprofile.png"
    }

    # Only show posts uploaded by the logged-in user
    posts = query_db("""
        SELECT skills.id, skills.media, skills.caption, skills.likes, users.username, users.profile_image 
        FROM skills 
        JOIN users ON skills.user_id = users.id 
        WHERE users.id = ?
        ORDER BY skills.id DESC
    """, (user_id,))

    posts_list = []
    for row in posts:
        post_id = row[0]
        posts_list.append({
            "id": post_id,
            "media": row[1],
            "caption": row[2],
            "likes": row[3],
            "username": row[4],
            "profile_image": row[5] if row[5] else "default-profile.png",
        })

    return render_template(
        'user_skills.html',
        user=user,
        posts=posts_list,
        current_time=datetime.now().timestamp()
    )




# Route: Upload a Skill Post
@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        flash("You must be logged in to upload skills!", "error")
        return redirect(url_for('userlogin'))

    file = request.files.get('media')
    caption = request.form.get('caption', '')
    user_id = session['user_id']

    if not file:
        flash("Please select a file to upload!", "error")
        return redirect(url_for('skills'))

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    ext = os.path.splitext(filename)[1].lower()

    image_extensions = ['.jpg', '.jpeg', '.png', '.webp']

    if ext in image_extensions:
        image = Image.open(file)
        resized_image = image.resize((500, 500))  # Resize to 500x500
        resized_image.save(filepath)
    else:
        file.save(filepath)  # Save video or unsupported format directly

    query_db("INSERT INTO skills (user_id, media, caption) VALUES (?, ?, ?)", 
             (user_id, filename, caption), commit=True)

    flash("Skill uploaded successfully!", "success")
    return redirect(url_for('skills'))



    
@app.route('/update_post', methods=['POST'])
def update_post():
    if 'user_id' not in session:
        return redirect(url_for('userlogin'))

    user_id = session['user_id']
    post_id = request.form.get('post_id')
    new_caption = request.form.get('caption', '').strip()

    if post_id and new_caption:
        query_db(
            "UPDATE skills SET caption = ? WHERE id = ? AND user_id = ?",
            (new_caption, post_id, user_id),
            commit=True
        )
        flash("Caption updated successfully!", "success")
    else:
        flash("Caption cannot be empty!", "error")

    return redirect(url_for('skills'))



@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('userlogin'))

    user_id = session['user_id']

    # Get media filename to delete from storage
    post = query_db("SELECT media FROM skills WHERE id = ? AND user_id = ?", (post_id, user_id), one=True)
    if post:
        media_path = os.path.join(app.config['UPLOAD_FOLDER'], post[0])
        if os.path.exists(media_path):
            os.remove(media_path)

        # Delete from database
        query_db("DELETE FROM skills WHERE id = ? AND user_id = ?", (post_id, user_id), commit=True)
        flash("Post deleted successfully.", "success")
    else:
        flash("Post not found or unauthorized.", "error")

    return redirect(url_for('skills'))

@app.route('/user_get_accessories',methods=['GET','POST'])
def user_get_accessories():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('user_accessories.html')
 
@app.route('/submit_accessory_request', methods=['POST'])
def submit_accessory_request():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    category = request.form['category']
    description = request.form['description']

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO accessories_requests (user_id, category, description)
        VALUES (?, ?, ?)
    ''', (user_id, category, description))
    conn.commit()
    conn.close()

    flash('Your request has been submitted successfully!', 'success')
    return redirect(url_for('user_get_accessories'))

@app.route('/user_feedback',methods=['GET','POST'])
def user_feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('user_feedback.html')

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    feedback = request.form.get('feedback')
    rating = request.form.get('rating', type=int)

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_feedbacks (user_id, feedback, rating) VALUES (?, ?, ?)",
                   (session['user_id'], feedback, rating))
    conn.commit()
    conn.close()

    flash('Thank you for your feedback!')
    return redirect(url_for('userhome'))



#sponsor
@app.route('/sponsorhome')
def sponsor_home():
    return render_template('sponsorhome.html')

@app.route('/sponsorskills')
def sponsor_skills():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all skill posts with user details
    cursor.execute('''
        SELECT skills.id, skills.media, skills.caption, users.username, users.profile_image
        FROM skills
        JOIN users ON skills.user_id = users.id
        ORDER BY skills.id DESC
    ''')
    posts = cursor.fetchall()
    conn.close()

    # Format posts without likes
    posts_list = []
    for row in posts:
        posts_list.append({
            "id": row["id"],
            "media": row["media"],
            "caption": row["caption"],
            "username": row["username"],
            "profile_image": row["profile_image"] if row["profile_image"] else "noprofile.png",
        })

    return render_template('sponsor_skills.html', posts=posts_list, current_time=datetime.now().timestamp())

@app.route('/sponsor_post/<int:post_id>', methods=['GET', 'POST'])
def sponsor_post(post_id):
    if request.method == 'POST':
        sponsor_name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        amount = request.form['amount']

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sponsorships (post_id, sponsor_name, phone, email, amount)
            VALUES (?, ?, ?, ?, ?)
        ''', (post_id, sponsor_name, phone, email, amount))
        conn.commit()
        conn.close()

        return redirect(url_for('payment_success'))
    return render_template('sponsor_form.html', post_id=post_id)

@app.route('/payment_success')
def payment_success():
    return render_template('payment_success.html')

@app.route('/sponsoraccessories', methods=['GET'])
def sponsor_accessories():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Fetch accessories requests along with user info and profile
    cur.execute('''
        SELECT ar.id, ar.category, ar.description, u.username, u.phone, u.email, 
               COALESCE(u.profile_image, 'noprofile.png') AS profile_image
        FROM accessories_requests ar
        JOIN users u ON ar.user_id = u.id
        ORDER BY ar.id DESC
    ''')
    
    requests = cur.fetchall()
    conn.close()

    return render_template('sponsor_accessories.html', requests=requests, current_time=datetime.now().timestamp())

@app.route('/sponsor_accessory_amount/<int:request_id>', methods=['GET', 'POST'])
def sponsor_accessory_amount(request_id):
    if request.method == 'POST':
        print("🔍 FORM DATA:", request.form.to_dict())

        # Safely get form fields to avoid KeyError
        sponsor_name = request.form.get('sponsor_name')
        phone = request.form.get('phone')
        email = request.form.get('email', '')
        amount = request.form.get('amount')

        # Basic validation in case required fields are still missing
        if not sponsor_name or not phone or not amount:
            return "Missing required fields.", 400

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO accessory_sponsorships (sponsor_name, phone, email, amount, request_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (sponsor_name, phone, email, amount, request_id))
        conn.commit()
        conn.close()

        return redirect(url_for('dummy_payment'))

    return render_template('sponsor_accessory_amount.html', request_id=request_id)


@app.route('/dummy_payment')
def dummy_payment():
    return render_template('dummy_payment.html')




#admin
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = bcrypt.hashpw("Admin@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def query_db(query, args=(), one=False, commit=False):
    """Query the database and return results as tuples."""
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()
        cur.execute(query, args)

        if commit:
            conn.commit()

        result = cur.fetchall()
        return (result[0] if result else None) if one else result

# Admin Login Route
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')):
         session['admin'] = username
         return redirect(url_for('admin_dashboard'))
        else:
          flash("Invalid Admin Credentials!", "admin_error")

    
    return render_template('admin_login.html')

from flask import make_response

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' not in session:
        # Redirect to login if admin is not in session
        return redirect(url_for('admin_login'))
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row  # So we can use column names like user['profile_image']
    cursor = conn.cursor()

    # Search functionality
    search_query = request.form.get('search_query', '')
    if search_query:
        cursor.execute("SELECT * FROM users WHERE udid LIKE ?", ('%' + search_query + '%',))
    else:
        cursor.execute("SELECT * FROM users")
    
    users = cursor.fetchall()
    conn.close()
    
    # Prevent caching of this page
    response = make_response(render_template('admin_dashboard.html', users=users))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/motivation_class')
def admin_motivation_class():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    motivation_classes = query_db("SELECT * FROM motivation_class")
    
    return render_template("admin_motivation.html", motivation_classes=motivation_classes)


@app.route('/admin/add_motivation_class', methods=['POST'])
def add_motivation_class():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    teacher_name = request.form.get('teacher_name')
    venue = request.form.get('venue')
    time = request.form.get('time')
    teacher_photo = request.files.get('teacher_photo')

    if not teacher_name or not venue or not time or not teacher_photo:
        flash("Missing required fields!", "error")
        return redirect(url_for('admin_motivation_class'))

    # Save Image
    filename = None
    if teacher_photo and teacher_photo.filename:
        filename = secure_filename(teacher_photo.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        teacher_photo.save(upload_path)

    # Insert Data - Order of columns fixed to match retrieval
    query_db(
        "INSERT INTO motivation_class (teacher_name, venue, time, teacher_image) VALUES (?, ?, ?, ?)",
        (teacher_name, venue, time, filename),
        commit=True
    )

    flash("Motivation class added successfully!", "success")
    return redirect(url_for('admin_motivation_class'))



@app.route('/admin/update_motivation_class/<int:class_id>', methods=['POST'])
def update_motivation_class(class_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    teacher_name = request.form.get('teacher_name')
    venue = request.form.get('venue')
    time = request.form.get('time')
    teacher_photo = request.files.get('teacher_photo')

    # Ensure the upload folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()

        # ✅ If a new image is uploaded, update it
        if teacher_photo and teacher_photo.filename:
            filename = secure_filename(teacher_photo.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            teacher_photo.save(filepath)

            cur.execute("""
                UPDATE motivation_class 
                SET teacher_name=?, venue=?, time=?, teacher_image=? 
                WHERE id=?
            """, (teacher_name, venue, time, filename, class_id))
        else:
            cur.execute("""
                UPDATE motivation_class 
                SET teacher_name=?, venue=?, time=? 
                WHERE id=?
            """, (teacher_name, venue, time, class_id))

        conn.commit()

    flash("Motivation class updated successfully!", "success")
    return redirect(url_for('admin_motivation_class'))

@app.route('/admin/delete_motivation_class/<int:class_id>', methods=['POST'])
def delete_motivation_class(class_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()

        # ✅ Check if there are dependent records
        cur.execute("SELECT id FROM seats WHERE class_id=?", (class_id,))
        seat_exists = cur.fetchone()

        cur.execute("SELECT id FROM user_book WHERE class_id=?", (class_id,))
        booking_exists = cur.fetchone()

        # ✅ If dependent records exist, delete them first
        if seat_exists:
            cur.execute("DELETE FROM seats WHERE class_id=?", (class_id,))
        if booking_exists:
            cur.execute("DELETE FROM user_book WHERE class_id=?", (class_id,))

        # ✅ Now delete the class
        cur.execute("DELETE FROM motivation_class WHERE id=?", (class_id,))
        conn.commit()

    flash("Motivation class deleted successfully!", "success")
    return redirect(url_for('admin_motivation_class'))


@app.route('/admin/add_seat/<int:class_id>', methods=['POST'])
def add_seat(class_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    seat_number = request.form.get("seat_number")

    if not seat_number:
        flash("Please enter a seat number!", "error")
        return redirect(url_for('admin_motivation_class'))

    # Check if the seat number already exists for the given class
    existing_seat = query_db("SELECT * FROM seats WHERE class_id = ? AND seat_number = ?", 
                             (class_id, seat_number), one=True)

    if existing_seat:
        flash(f"Seat {seat_number} already exists for this class!", "error")
    else:
        with sqlite3.connect(DATABASE) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO seats (class_id, seat_number, status) VALUES (?, ?, 'available')", 
                        (class_id, seat_number))
            conn.commit()

        flash(f"Seat {seat_number} added successfully!", "success")

    return redirect(url_for('admin_motivation_class'))



@app.route('/admin/booked_seats/<int:class_id>')
def booked_seats(class_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    # Fetch booked seats with user details
    booked_seats = query_db('''
        SELECT name, age, phone, seat_number 
        FROM user_book 
        WHERE class_id = ?
    ''', (class_id,))

    # Fetch all seats for the selected class
    all_seats = query_db("SELECT seat_number FROM seats WHERE class_id = ?", (class_id,))

    # Convert booked_seats into a dictionary (handling tuples correctly)
    booked_seats_dict = {seat[3]: seat for seat in booked_seats}  # seat_number is at index 3

    return render_template(
        "admin_book_seats.html",
        booked_seats=booked_seats_dict,
        all_seats=all_seats,
        class_id=class_id
    )


@app.route('/admin/view_user_skills', methods=['GET', 'POST'])
def view_user_skills():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT skills.id, skills.media, skills.caption, skills.likes, users.username, users.profile_image
        FROM skills
        JOIN users ON skills.user_id = users.id
        ORDER BY skills.id DESC
    ''')
    posts = cursor.fetchall()
    conn.close()

    posts_list = [
        {
            "id": row["id"],
            "media": row["media"],
            "caption": row["caption"],
            "username": row["username"],
            "profile_image": row["profile_image"] if row["profile_image"] else "noprofile.png",
        }
        for row in posts
    ]

    return render_template('view_user_skills.html', posts=posts_list, current_time=datetime.now().timestamp())

@app.route('/view_accessories_requests', methods=['GET', 'POST'])
def view_accessories_requests():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute('''
        SELECT ar.id, ar.category, ar.description, u.username, u.phone, u.email
        FROM accessories_requests ar
        JOIN users u ON ar.user_id = u.id
        ORDER BY ar.id DESC
    ''')
    
    requests = cur.fetchall()
    conn.close()

    return render_template('view_accessories_requests.html', requests=requests)

from datetime import datetime

@app.route('/admin_view_feedbacks', methods=['GET', 'POST'])
def admin_view_feedbacks():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Include profile_image from users table
    cur.execute('''
        SELECT uf.feedback, uf.rating, u.username, u.email, u.phone, u.profile_image
        FROM user_feedbacks uf
        JOIN users u ON uf.user_id = u.id
        ORDER BY uf.id DESC
    ''')

    feedbacks = cur.fetchall()
    conn.close()

    return render_template('view_feedbacks.html', feedbacks=feedbacks, current_time=datetime.now().timestamp())

@app.route('/admin_skill_payments', methods=['GET', 'POST'])
def admin_skill_payments():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute('''
        SELECT s.id, s.sponsor_name, s.phone, s.email, s.amount, s.timestamp, s.payment_status,
               sk.caption, sk.media,
               u.username, u.profile_image, u.phone AS user_phone
        FROM sponsorships s
        JOIN skills sk ON s.post_id = sk.id
        JOIN users u ON sk.user_id = u.id
        ORDER BY s.timestamp DESC
    ''')

    payments = cur.fetchall()
    conn.close()

    return render_template('admin_skill_payments.html', payments=payments, current_time=datetime.now().timestamp())


@app.route('/mark_payment_done/<int:sponsorship_id>', methods=['POST'])
def mark_payment_done(sponsorship_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("UPDATE sponsorships SET payment_status = 'done' WHERE id = ?", (sponsorship_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin_skill_payments'))

@app.route('/admin_accessory_payments', methods=['GET', 'POST'])
def admin_accessory_payments():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute('''
        SELECT asp.id, asp.sponsor_name, asp.amount, asp.payment_status,  -- ✅ Include this!
               u.username, u.phone AS user_phone, u.email AS user_email,
               COALESCE(u.profile_image, 'noprofile.png') AS profile_image,
               ar.category, ar.description
        FROM accessory_sponsorships asp
        JOIN accessories_requests ar ON asp.request_id = ar.id
        JOIN users u ON ar.user_id = u.id
        ORDER BY asp.id DESC
    ''')
    payments = cur.fetchall()
    conn.close()

    return render_template('admin_accessory_payment.html', payments=payments)

@app.route('/mark_payment/<int:payment_id>', methods=['POST'])
def mark_payment(payment_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("UPDATE accessory_sponsorships SET payment_status = 'done' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin_accessory_payments'))  # ✅ return after update







# Admin Logout
@app.route('/admin/logout')
def admin_logout():
    # Clear the admin session
    session.pop('admin', None)
    flash("Logged out successfully!", "success")

    # Prevent caching
    response = make_response(redirect(url_for('admin_login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response

if __name__ == "__main__":
    app.run(debug=True)