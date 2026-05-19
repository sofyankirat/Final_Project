"""
Main Flask Application
Student Recommendation and Attendance System
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for  # type: ignore[import]
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore[import]
from werkzeug.utils import secure_filename  # type: ignore[import]
from datetime import datetime, timedelta
import secrets
import smtplib
import html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
import os
import base64
import binascii
import json
from typing import Any, cast
from dotenv import load_dotenv  # type: ignore[import]
from database import init_db, get_db_connection  # type: ignore[import]

# Load environment variables
load_dotenv()

# Get base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'app', 'templates'),
    static_folder=os.path.join(BASE_DIR, 'app', 'static'),
    static_url_path='/static'
)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SESSION_TIMEOUT'] = 3600  # 1 hour
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB upload limit

ALLOWED_CHAT_UPLOAD_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'csv',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
    'mp4', 'mov', 'avi', 'mkv', 'webm',
    'mp3', 'wav', 'm4a',
    'zip', 'rar'
}

# Email Configuration
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS', 'your-email@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'your-email-password')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
HELP_RECEIVER_EMAIL = os.getenv('HELP_RECEIVER_EMAIL', 'www.sofyankirat123@gmail.com')

# Initialize database
init_db()


def to_clean_string(value: Any) -> str:
    """Safely convert request values to trimmed strings."""
    if value is None:
        return ''
    return str(value).strip()


def to_int_value(value: Any, default: int = 0) -> int:
    """Safely convert mixed DB values to int."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def to_float_value(value: Any, default: float = 0.0) -> float:
    """Safely convert mixed values to float."""
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def has_additional_info(user_id: int):
    """Check if the user already submitted additional info."""
    connection = get_db_connection()
    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM user_additional_info WHERE user_id = %s LIMIT 1", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        return result is not None
    except Exception as error:
        print(f"Additional info check error: {str(error)}")
        return False
    finally:
        connection.close()

def send_verification_email(email, verification_token):
    """Send verification email to the user"""
    try:
        subject = "Email Verification - Hamas"
        verification_link = f"{request.host_url}verify-email/{verification_token}"
        
        body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Email Verification</h2>
            <p>Welcome to the Student Recommendation and Attendance System!</p>
            <p>Please click the link below to verify your email address:</p>
            <a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                Verify Email
            </a>
            <p>Or copy this link in your browser:</p>
            <p>{verification_link}</p>
            <p>This verification link will expire in 24 hours.</p>
            <p>If you didn't sign up for this account, please ignore this email.</p>
        </body>
        </html>
        """
        
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"Hamas <{EMAIL_ADDRESS}>"
        message["To"] = email
        
        part = MIMEText(body, "html")
        message.attach(part)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, email, message.as_string())
        
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


def normalize_email_address(value: Any) -> str:
    """Normalize email-ish values from env/user input."""
    cleaned = to_clean_string(value).lower()
    if cleaned.startswith('mailto:'):
        cleaned = cleaned[len('mailto:'):]
    if cleaned.startswith('www.'):
        cleaned = cleaned[len('www.'):]
    return cleaned


def send_help_request_email(user_name: str, user_email: str, subject: str, message: str) -> bool:
    """Send help form submission to support inbox."""
    try:
        support_email = normalize_email_address(HELP_RECEIVER_EMAIL)
        if not support_email or '@' not in support_email:
            print('Help email delivery skipped: invalid HELP_RECEIVER_EMAIL')
            return False

        safe_name = html.escape(to_clean_string(user_name))
        safe_email = html.escape(to_clean_string(user_email))
        safe_subject = html.escape(to_clean_string(subject))
        safe_message = html.escape(to_clean_string(message)).replace('\n', '<br>')
        submitted_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        body = f"""
        <!DOCTYPE html>
        <html>
        <body style=\"font-family: Arial, sans-serif; color: #111827;\">
            <h2 style=\"margin-bottom: 8px;\">New Help Request</h2>
            <p style=\"margin: 0 0 14px; color: #4b5563;\">A new message was submitted from the Help page.</p>

            <table cellpadding=\"8\" cellspacing=\"0\" style=\"border-collapse: collapse; width: 100%; max-width: 640px;\">
                <tr><td style=\"font-weight:700; border:1px solid #e5e7eb; width:150px;\">Name</td><td style=\"border:1px solid #e5e7eb;\">{safe_name}</td></tr>
                <tr><td style=\"font-weight:700; border:1px solid #e5e7eb;\">Email</td><td style=\"border:1px solid #e5e7eb;\">{safe_email}</td></tr>
                <tr><td style=\"font-weight:700; border:1px solid #e5e7eb;\">Subject</td><td style=\"border:1px solid #e5e7eb;\">{safe_subject}</td></tr>
                <tr><td style=\"font-weight:700; border:1px solid #e5e7eb;\">Submitted at</td><td style=\"border:1px solid #e5e7eb;\">{submitted_at}</td></tr>
                <tr><td style=\"font-weight:700; border:1px solid #e5e7eb; vertical-align:top;\">Message</td><td style=\"border:1px solid #e5e7eb;\">{safe_message}</td></tr>
            </table>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Help Request: {to_clean_string(subject)}"
        msg["From"] = f"Hamas <{EMAIL_ADDRESS}>"
        msg["To"] = support_email

        normalized_sender = normalize_email_address(user_email)
        if normalized_sender and '@' in normalized_sender:
            msg["Reply-To"] = normalized_sender

        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, [support_email], msg.as_string())

        return True
    except Exception as error:
        print(f"Error sending help request email: {error}")
        return False

def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ================== ROUTES ==================

@app.route('/')
def index():
    """Home page - always redirect to login"""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = to_clean_string(data.get('email', ''))
        password = to_clean_string(data.get('password', ''))
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400
        
        try:
            connection = get_db_connection()
            if connection is None:
                return jsonify({'success': False, 'message': 'Database connection error'}), 500

            cursor = connection.cursor()
            cursor.execute("SELECT id, password, is_verified FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if user:
                user_id = to_int_value(user[0])
                hashed_password = str(user[1])
                is_verified = bool(user[2])
            else:
                user_id = 0
                hashed_password = ''
                is_verified = False

            if user and check_password_hash(hashed_password, password):
                if not is_verified:  # Check if email is verified
                    return jsonify({'success': False, 'message': 'Please verify your email first'}), 401
                
                session['user_id'] = user_id
                session['email'] = email
                redirect_target = url_for('dashboard') if has_additional_info(user_id) else url_for('additional_info')
                return jsonify({'success': True, 'message': 'Login successful', 'redirect': redirect_target})
            else:
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
        
        except Exception as e:
            print(f"Login error: {str(e)}")
            return jsonify({'success': False, 'message': 'An error occurred during login'}), 500
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = to_clean_string(data.get('email', ''))
        password = to_clean_string(data.get('password', ''))
        confirm_password = to_clean_string(data.get('confirm_password', ''))
        
        # Validation
        if not email or not password or not confirm_password:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
        
        # Check if email already exists
        try:
            connection = get_db_connection()
            if connection is None:
                return jsonify({'success': False, 'message': 'Database connection error'}), 500

            cursor = connection.cursor()
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Email already registered'}), 409
            
            # Generate verification token
            verification_token = secrets.token_urlsafe(32)
            hashed_password = generate_password_hash(password)
            
            # Insert new user
            cursor.execute(
                "INSERT INTO users (email, password, verification_token, token_expiry) VALUES (%s, %s, %s, %s)",
                (email, hashed_password, verification_token, datetime.now() + timedelta(hours=24))
            )
            connection.commit()
            cursor.close()
            connection.close()
            
            # Send verification email
            if send_verification_email(email, verification_token):
                return jsonify({
                    'success': True, 
                    'message': 'Registration successful! Please check your email to verify your account.'
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': 'Registration successful but email could not be sent. Please try again later.'
                }), 500
        
        except Exception as e:
            print(f"Registration error: {str(e)}")
            return jsonify({'success': False, 'message': 'An error occurred during registration'}), 500
    
    return render_template('register.html')

@app.route('/verify-email/<token>')
def verify_email(token):
    """Verify email with token"""
    try:
        if not token or token.strip() == '':
            return render_template('email_verification.html', success=False, message='Invalid verification token')
        
        connection = get_db_connection()
        if connection is None:
            return render_template('email_verification.html', success=False, message='Database connection error. Please try again later.')
        
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, token_expiry FROM users WHERE verification_token = %s",
            (token,)
        )
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return render_template('email_verification.html', success=False, message='Invalid verification token or already verified')
        
        # Check if token expired
        try:
            expiry_value = user[1]
            if isinstance(expiry_value, datetime):
                token_expiry = expiry_value
            else:
                token_expiry = datetime.fromisoformat(str(expiry_value))

            if token_expiry < datetime.now():
                cursor.close()
                connection.close()
                return render_template('email_verification.html', success=False, message='Verification token has expired. Please register again.')
        except Exception:
            pass
        
        # Update user as verified
        try:
            user_id = to_int_value(user[0])
            cursor.execute(
                "UPDATE users SET is_verified = TRUE, verification_token = NULL, token_expiry = NULL WHERE id = %s",
                (user_id,)
            )
            connection.commit()
            print(f"User {user_id} email verified successfully")
            cursor.close()
            connection.close()
            
            return render_template('email_verification.html', success=True, message='Email verified successfully! You can now login.')
        except Exception as update_error:
            print(f"Database update error: {str(update_error)}")
            cursor.close()
            connection.close()
            return render_template('email_verification.html', success=False, message='Error verifying email. Please try again.')
    
    except Exception as e:
        print(f"Email verification error: {str(e)}")
        return render_template('email_verification.html', success=False, message=f'An error occurred: {str(e)}')

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    user_id = session.get('user_id')
    email = session.get('email', '')
    
    # Default fallback is capitalized email prefix
    username = email.split('@')[0].capitalize() if email else 'User'
    
    # Fetch real first name from additional info
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = result[0]
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching user name: {e}")
        
    return render_template('dashboard.html', username=username, email=email,
                           profile_photo=_get_profile_photo(user_id))


def get_static_root() -> str:
    """Return a guaranteed static directory path."""
    static_folder = app.static_folder
    if static_folder:
        return static_folder
    return os.path.join(BASE_DIR, 'app', 'static')


def is_allowed_chat_upload(filename: str) -> bool:
    """Validate file extension for AI chat attachments."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_CHAT_UPLOAD_EXTENSIONS


def _get_profile_photo(user_id):
    """Return the URL for the user's profile photo, or None if none exists."""
    static_root = get_static_root()
    path = os.path.join(static_root, 'uploads', f'profile_{user_id}.jpg')
    if os.path.exists(path):
        return url_for('static', filename=f'uploads/profile_{user_id}.jpg')
    return None




@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    user_id = to_int_value(session.get('user_id'))
    email   = session.get('email', '')
    username = email.split('@')[0].capitalize() if email else 'User'
    info = None
    saved = request.args.get('saved', False)

    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT * FROM user_additional_info WHERE user_id = %s LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            row_data: dict[str, Any] = {}
            if row and cursor.description:
                columns = [description[0] for description in cursor.description]
                row_data = dict(zip(columns, row))
            if row_data:
                first_name = to_clean_string(row_data.get('first_name'))
                if first_name:
                    username = first_name
                info = row_data
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching profile: {e}")

    return render_template('profile.html',
                           username=username,
                           email=email,
                           info=info,
                           profile_photo=_get_profile_photo(user_id),
                           saved=saved)


@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    """Save updated profile fields — only overwrite fields that were actually submitted."""
    user_id = to_int_value(session.get('user_id'))

    try:
        connection = get_db_connection()
        if not connection:
            return redirect(url_for('profile', saved=0))

        # ── Step 0: save profile photo if provided ─────────────────────────────
        photo_data = to_clean_string(request.form.get('profile_photo_data', ''))
        if photo_data and photo_data.startswith('data:image'):
            try:
                _header, encoded = photo_data.split(',', 1)
                img_bytes = base64.b64decode(encoded)
                static_root = get_static_root()
                uploads_dir = os.path.join(static_root, 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                photo_path = os.path.join(uploads_dir, f'profile_{user_id}.jpg')
                with open(photo_path, 'wb') as fh:
                    fh.write(img_bytes)
            except Exception as photo_err:
                print(f'Photo save error: {photo_err}')

        # ── Step 1: fetch the existing row so we can fall back to it ────────────
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                first_name, age, program, gender, level,
                is_working, failed_subjects, discipline_score,
                analytical_score, practical_score, gpa, screen_hours
            FROM user_additional_info
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,)
        )
        existing_row = cursor.fetchone()
        existing: dict[str, Any] = {}
        if existing_row:
            (
                existing['first_name'],
                existing['age'],
                existing['program'],
                existing['gender'],
                existing['level'],
                existing['is_working'],
                existing['failed_subjects'],
                existing['discipline_score'],
                existing['analytical_score'],
                existing['practical_score'],
                existing['gpa'],
                existing['screen_hours'],
            ) = existing_row
        cursor.close()

        # ── Step 2: helper — use submitted value if non-empty, else keep DB value ─
        def pick_str(field, fallback=''):
            val = to_clean_string(request.form.get(field, ''))
            return val if val else (existing.get(field) or fallback)

        def pick_int(field, fallback=0):
            val = to_clean_string(request.form.get(field, ''))
            if val:
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    pass
            return existing.get(field) if existing.get(field) is not None else fallback

        def pick_float(field, fallback=0.0):
            val = to_clean_string(request.form.get(field, ''))
            if val:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
            return existing.get(field) if existing.get(field) is not None else fallback

        # ── Step 3: resolve each field ─────────────────────────────────────────
        first_name       = pick_str('first_name')
        age              = pick_int('age')
        program          = pick_str('program')
        gender           = pick_str('gender')
        level            = pick_int('level')
        is_working_raw   = pick_str('is_working', 'No')
        is_working       = is_working_raw.lower() == 'yes'
        failed_subjects  = pick_int('failed_subjects')
        discipline_score = pick_int('discipline_score')
        analytical_score = pick_int('analytical_score')
        practical_score  = pick_int('practical_score')
        gpa              = pick_float('gpa')
        screen_hours     = pick_float('screen_hours')

        # ── Step 4: upsert with the merged values ───────────────────────────────
        cursor2 = connection.cursor()
        cursor2.execute(
            """
            INSERT INTO user_additional_info (
                user_id, first_name, age, program, gender, level,
                is_working, failed_subjects, discipline_score,
                analytical_score, practical_score, gpa, screen_hours
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                first_name = VALUES(first_name),
                age = VALUES(age),
                program = VALUES(program),
                gender = VALUES(gender),
                level = VALUES(level),
                is_working = VALUES(is_working),
                failed_subjects = VALUES(failed_subjects),
                discipline_score = VALUES(discipline_score),
                analytical_score = VALUES(analytical_score),
                practical_score = VALUES(practical_score),
                gpa = VALUES(gpa),
                screen_hours = VALUES(screen_hours)
            """,
            (user_id, first_name, age, program, gender, level,
             is_working, failed_subjects, discipline_score,
             analytical_score, practical_score, gpa, screen_hours)
        )
        connection.commit()
        cursor2.close()
        connection.close()

    except Exception as e:
        print(f"Profile update error: {e}")

    return redirect(url_for('profile', saved=1))


@app.route('/logout')
def logout():
    """Logout — clear session and redirect to login"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/additional-info', methods=['GET', 'POST'])
@login_required
def additional_info():
    """Additional information page shown after login"""
    user_id = to_int_value(session.get('user_id'))

    if user_id <= 0:
        return redirect(url_for('login'))

    if request.method == 'GET' and has_additional_info(user_id):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        first_name = to_clean_string(request.form.get('first_name'))
        age = to_int_value(request.form.get('age'))
        program = to_clean_string(request.form.get('program'))
        gender = to_clean_string(request.form.get('gender'))
        level = to_int_value(request.form.get('level'))
        is_working = to_clean_string(request.form.get('is_working')).lower() == 'yes'
        failed_subjects = to_int_value(request.form.get('failed_subjects'))
        discipline_score = to_int_value(request.form.get('discipline_score'))
        analytical_score = to_int_value(request.form.get('analytical_score'))
        practical_score = to_int_value(request.form.get('practical_score'))
        gpa = to_float_value(request.form.get('gpa'))
        screen_hours = to_float_value(request.form.get('screen_hours'))

        if not first_name or age <= 0 or not program or not gender or level <= 0:
            return render_template('additional_info.html')

        connection = get_db_connection()
        if connection is None:
            return render_template('additional_info.html')

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO user_additional_info (
                    user_id, first_name, age, program, gender, level,
                    is_working, failed_subjects, discipline_score,
                    analytical_score, practical_score, gpa, screen_hours
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    first_name = VALUES(first_name),
                    age = VALUES(age),
                    program = VALUES(program),
                    gender = VALUES(gender),
                    level = VALUES(level),
                    is_working = VALUES(is_working),
                    failed_subjects = VALUES(failed_subjects),
                    discipline_score = VALUES(discipline_score),
                    analytical_score = VALUES(analytical_score),
                    practical_score = VALUES(practical_score),
                    gpa = VALUES(gpa),
                    screen_hours = VALUES(screen_hours)
                """,
                (
                    user_id,
                    first_name,
                    age,
                    program,
                    gender,
                    level,
                    is_working,
                    failed_subjects,
                    discipline_score,
                    analytical_score,
                    practical_score,
                    gpa,
                    screen_hours,
                )
            )
            connection.commit()
            cursor.close()
        except Exception as error:
            print(f"Additional info save error: {str(error)}")
            return render_template('additional_info.html')
        finally:
            connection.close()

        return redirect(url_for('dashboard'))
    return render_template('additional_info.html')


@app.route('/recommendations', methods=['GET', 'POST'])
@login_required
def recommendations():
    """Recommendation page and form handler"""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')
    
    # Default fallback is capitalized email prefix
    username = email.split('@')[0].capitalize() if email else 'User'
    
    # Fetch real first name from additional info
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = result[0]
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching user name: {e}")
        
    score = None
    recommended = False
    reason = ""
    recommendation_history: list[dict[str, Any]] = []
    selected_history_id = to_int_value(request.args.get('history_id'))
    
    profile_photo = _get_profile_photo(user_id)


    if request.method == 'POST':
        # Safely receive and clean the 4 new manual fields
        weekly_avg_study_hours = to_float_value(request.form.get('weekly_avg_study_hours_subject'))
        attendance_count = to_int_value(request.form.get('attendance_count'))
        course_name = to_clean_string(request.form.get('Course_name'))
        professors = to_clean_string(request.form.get('professors'))

        # Placeholder logic for AI prediction model
        score = 85 
        recommended = True
        reason = f"Based on your high attendance ({attendance_count}) and {weekly_avg_study_hours} weekly study hours with {professors}, {course_name} is considered a perfect match for your profile."

        # Sticky form data
        form_data = {
            'Course_name': course_name,
            'professors': professors,
            'weekly_avg_study_hours_subject': weekly_avg_study_hours,
            'attendance_count': attendance_count
        }

        default_history_title = f"{course_name} - {professors} - {weekly_avg_study_hours:g} - {attendance_count}"
        new_history_id = None
        try:
            history_connection = get_db_connection()
            if history_connection:
                history_cursor = history_connection.cursor()
                history_cursor.execute(
                    """
                    INSERT INTO user_recommendation_history (
                        user_id, title, course_name, professor_name,
                        study_hours, attendance_count, score, recommended, reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        default_history_title,
                        course_name,
                        professors,
                        weekly_avg_study_hours,
                        attendance_count,
                        score,
                        recommended,
                        reason,
                    )
                )
                history_connection.commit()
                new_history_id = history_cursor.lastrowid
                history_cursor.close()
                history_connection.close()
        except Exception as error:
            print(f"Recommendation history save error: {error}")

        # Redirect to the new history item so results render from DB (clean PRG)
        if new_history_id:
            return redirect(url_for('recommendations', history_id=new_history_id))
        return redirect(url_for('recommendations'))
    
    # GET logic: results come from history_id query param (DB) — session fallback removed
    score = None
    recommended = False
    reason = ""
    form_data = {}

    try:
        history_connection = get_db_connection()
        if history_connection:
            history_cursor = history_connection.cursor()
            history_cursor.execute(
                """
                SELECT id, title, course_name, professor_name, study_hours,
                       attendance_count, score, recommended, reason, created_at
                FROM user_recommendation_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (user_id,)
            )
            rows = history_cursor.fetchall()
            history_cursor.close()
            history_connection.close()

            for row in rows:
                created_at_value = row[9]
                if isinstance(created_at_value, datetime):
                    created_at_text = created_at_value.strftime('%Y-%m-%d %I:%M %p')
                else:
                    created_at_text = to_clean_string(created_at_value)

                entry = {
                    'id': to_int_value(row[0]),
                    'title': to_clean_string(row[1]),
                    'course_name': to_clean_string(row[2]),
                    'professor_name': to_clean_string(row[3]),
                    'study_hours': to_float_value(row[4]),
                    'attendance_count': to_int_value(row[5]),
                    'score': to_float_value(row[6]),
                    'recommended': bool(row[7]),
                    'reason': to_clean_string(row[8]),
                    'created_at': created_at_text,
                }
                recommendation_history.append(entry)

            if selected_history_id > 0:
                selected_entry = next(
                    (entry for entry in recommendation_history if to_int_value(entry.get('id')) == selected_history_id),
                    None
                )
                if selected_entry:
                    score = to_float_value(selected_entry.get('score'))
                    recommended = bool(selected_entry.get('recommended'))
                    reason = to_clean_string(selected_entry.get('reason'))
                    form_data = {
                        'Course_name': to_clean_string(selected_entry.get('course_name')),
                        'professors': to_clean_string(selected_entry.get('professor_name')),
                        'weekly_avg_study_hours_subject': to_float_value(selected_entry.get('study_hours')),
                        'attendance_count': to_int_value(selected_entry.get('attendance_count')),
                    }
    except Exception as error:
        print(f"Recommendation history fetch error: {error}")




    return render_template(
        'recommendations.html', 
        username=username, 
        email=email,
        profile_photo=profile_photo,
        score=score,
        recommended=recommended,
        reason=reason,
        form_data=form_data,
        recommendation_history=recommendation_history,
        selected_history_id=selected_history_id
    )


@app.route('/recommendations/delete/<int:history_id>', methods=['POST'])
@login_required
def delete_recommendation_history(history_id: int):
    """Delete a saved recommendation history item for the current user."""
    user_id = to_int_value(session.get('user_id'))
    deleted = False
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM user_recommendation_history WHERE id = %s AND user_id = %s",
                (history_id, user_id)
            )
            deleted = cursor.rowcount > 0
            connection.commit()
            cursor.close()
            connection.close()
    except Exception as error:
        print(f"Recommendation history delete error: {error}")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': deleted})

    return redirect(url_for('recommendations'))


@app.route('/ai-agent')
@login_required
def ai_agent():
    """AI Agent chat page"""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')

    username = email.split('@')[0].capitalize() if email else 'User'

    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = result[0]
            cursor.close()
            connection.close()
    except Exception as error:
        print(f"Error fetching user name: {error}")

    return render_template(
        'ai_agent.html',
        username=username,
        email=email,
        profile_photo=_get_profile_photo(user_id)
    )


@app.route('/our-team')
@login_required
def our_team():
    """Our Team page"""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')

    username = email.split('@')[0].capitalize() if email else 'User'

    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = result[0]
            cursor.close()
            connection.close()
    except Exception as error:
        print(f"Error fetching user name: {error}")

    return render_template(
        'our_team.html',
        username=username,
        email=email,
        profile_photo=_get_profile_photo(user_id)
    )


@app.route('/help', methods=['GET', 'POST'])
@login_required
def help():
    """Help page: feature overview + contact form."""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')

    username = email.split('@')[0].capitalize() if email else 'User'
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = str(result[0])
            cursor.close()
            connection.close()
    except Exception as error:
        print(f"Error fetching user name: {error}")

    sent = to_int_value(request.args.get('sent')) == 1
    error_msg = ''
    form_data: dict[str, str] = {'subject': '', 'message': ''}

    if request.method == 'POST':
        subject = to_clean_string(request.form.get('subject'))
        message = to_clean_string(request.form.get('message'))
        form_data = {'subject': subject, 'message': message}

        if not subject or not message:
            error_msg = 'Please fill in both Subject and Your question.'
        else:
            connection2 = get_db_connection()
            if connection2 is None:
                error_msg = 'Database connection error. Please try again.'
            else:
                cursor2 = None
                try:
                    cursor2 = connection2.cursor()
                    cursor2.execute(
                        """
                        INSERT INTO help_requests (user_id, email, subject, message)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (user_id, email, subject, message)
                    )
                    connection2.commit()
                    email_delivered = send_help_request_email(
                        user_name=username,
                        user_email=email,
                        subject=subject,
                        message=message
                    )
                    if not email_delivered:
                        error_msg = 'Your message was saved, but email delivery failed. Please check SMTP/HELP_RECEIVER_EMAIL settings.'
                        sent = True
                        form_data = {'subject': '', 'message': ''}
                        return render_template(
                            'help.html',
                            username=username,
                            email=email,
                            profile_photo=_get_profile_photo(user_id),
                            sent=sent,
                            error=error_msg,
                            form_data=form_data
                        )
                    return redirect(url_for('help', sent=1))
                except Exception as db_error:
                    print(f"Help request save error: {db_error}")
                    error_msg = 'Could not send your message right now. Please try again.'
                finally:
                    try:
                        if cursor2 is not None:
                            cursor2.close()
                    except Exception:
                        pass

                    try:
                        connection2.close()
                    except Exception:
                        pass

    return render_template(
        'help.html',
        username=username,
        email=email,
        profile_photo=_get_profile_photo(user_id),
        sent=sent,
        error=error_msg,
        form_data=form_data
    )


@app.route('/api/ai-chat-state', methods=['GET'])
@login_required
def ai_chat_state():
    """Get persisted AI chat state for the logged-in user."""
    user_id = to_int_value(session.get('user_id'))

    connection = get_db_connection()
    if connection is None:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT chat_data, chat_counter, current_chat_id FROM user_ai_chat_state WHERE user_id = %s LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return jsonify({'success': True, 'state': None})

        raw_chat_data = to_clean_string(row[0])
        chat_data = json.loads(raw_chat_data) if raw_chat_data else {'chat_1': []}

        return jsonify({
            'success': True,
            'state': {
                'chats': chat_data,
                'chatCounter': to_int_value(row[1], 1),
                'currentChatId': to_clean_string(row[2]) or 'chat_1'
            }
        })
    except Exception as error:
        print(f"AI chat state fetch error: {str(error)}")
        return jsonify({'success': False, 'message': 'Failed to load chat history'}), 500
    finally:
        connection.close()


@app.route('/api/ai-chat-state', methods=['POST'])
@login_required
def save_ai_chat_state():
    """Persist AI chat state for the logged-in user."""
    user_id = to_int_value(session.get('user_id'))
    payload = request.get_json(silent=True) or {}

    chats = payload.get('chats', {'chat_1': []})
    chat_counter = to_int_value(payload.get('chatCounter', 1), 1)
    current_chat_id = to_clean_string(payload.get('currentChatId', 'chat_1')) or 'chat_1'

    if not isinstance(chats, dict):
        return jsonify({'success': False, 'message': 'Invalid chats format'}), 400

    connection = get_db_connection()
    if connection is None:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO user_ai_chat_state (user_id, chat_data, chat_counter, current_chat_id)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                chat_data = VALUES(chat_data),
                chat_counter = VALUES(chat_counter),
                current_chat_id = VALUES(current_chat_id)
            """,
            (user_id, json.dumps(chats), chat_counter, current_chat_id)
        )
        connection.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as error:
        print(f"AI chat state save error: {str(error)}")
        return jsonify({'success': False, 'message': 'Failed to save chat history'}), 500
    finally:
        connection.close()


@app.route('/api/ai-chat-attachment', methods=['POST'])
@login_required
def upload_ai_chat_attachment():
    """Upload and persist an attachment file for AI chat messages."""
    user_id = to_int_value(session.get('user_id'))

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    uploaded_file = request.files['file']
    original_name = to_clean_string(uploaded_file.filename)

    if not original_name:
        return jsonify({'success': False, 'message': 'Invalid file name'}), 400

    safe_name = secure_filename(original_name)
    if not safe_name:
        return jsonify({'success': False, 'message': 'Invalid file name'}), 400

    if not is_allowed_chat_upload(safe_name):
        return jsonify({'success': False, 'message': 'This file type is not allowed'}), 400

    try:
        extension = os.path.splitext(safe_name)[1].lower()
        unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(6)}{extension}"

        static_root = get_static_root()
        user_upload_dir = os.path.join(static_root, 'uploads', 'ai_chat', f'user_{user_id}')
        os.makedirs(user_upload_dir, exist_ok=True)

        saved_path = os.path.join(user_upload_dir, unique_name)
        uploaded_file.save(saved_path)

        file_url = url_for('static', filename=f'uploads/ai_chat/user_{user_id}/{unique_name}')
        mime_type = to_clean_string(uploaded_file.mimetype)

        return jsonify({
            'success': True,
            'fileName': original_name,
            'fileUrl': file_url,
            'mimeType': mime_type
        })
    except Exception as error:
        print(f"AI chat attachment upload error: {str(error)}")
        return jsonify({'success': False, 'message': 'Failed to upload attachment'}), 500


@app.route('/attendance')
@login_required
def attendance():
    """Smart Attendance enrollment page"""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')
    username = email.split('@')[0].capitalize() if email else 'User'
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = result[0]
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching user name: {e}")
    return render_template('attendance.html', username=username, email=email,
                           profile_photo=_get_profile_photo(user_id))


@app.route('/api/attendance/enroll', methods=['POST'])
@login_required
def attendance_enroll():
    """Accept five enrollment captures from the web UI."""
    payload = request.get_json(silent=True) or {}
    captures = payload.get('captures', [])

    if not isinstance(captures, list) or len(captures) != 5:
        return jsonify({'success': False, 'message': 'Please send exactly 5 captures.'}), 400

    user_id = to_int_value(session.get('user_id'))
    static_root = get_static_root()
    upload_dir = os.path.join(static_root, 'uploads', 'attendance', f'user_{user_id}')
    os.makedirs(upload_dir, exist_ok=True)

    attendance_root = os.path.abspath(os.path.join(BASE_DIR, '..', 'Smart-Attendance-System'))
    export_dir = os.path.join(attendance_root, 'database', 'web_enrollments', f'user_{user_id}')
    try:
        os.makedirs(export_dir, exist_ok=True)
    except OSError:
        export_dir = ''

    saved_files = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    for index, entry in enumerate(captures, start=1):
        if not isinstance(entry, dict):
            return jsonify({'success': False, 'message': 'Capture payload format is invalid.'}), 400

        data_url = to_clean_string(entry.get('dataUrl'))
        label = to_clean_string(entry.get('label', f'position_{index}'))
        if not data_url.startswith('data:image/') or ',' not in data_url:
            return jsonify({'success': False, 'message': 'Capture image data is invalid.'}), 400

        safe_label = ''.join(ch for ch in label.lower() if ch.isalnum() or ch in ('-', '_'))
        if not safe_label:
            safe_label = f'position_{index}'

        _, encoded = data_url.split(',', 1)
        try:
            image_bytes = base64.b64decode(encoded)
        except (ValueError, binascii.Error):
            return jsonify({'success': False, 'message': 'Could not decode image data.'}), 400

        filename = f'{timestamp}_{index}_{safe_label}.jpg'
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, 'wb') as file_handle:
            file_handle.write(image_bytes)
        saved_files.append(filename)

        if export_dir:
            export_path = os.path.join(export_dir, filename)
            try:
                with open(export_path, 'wb') as export_handle:
                    export_handle.write(image_bytes)
            except OSError:
                pass

    return jsonify({'success': True, 'files': saved_files})


# ================== ERROR HANDLERS ==================

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Page not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
