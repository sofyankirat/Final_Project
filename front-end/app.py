"""
Main Flask Application
Student Recommendation and Attendance System
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, Response  # type: ignore[import]
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore[import]
from werkzeug.utils import secure_filename  # type: ignore[import]
from datetime import datetime, timedelta, date, time
import secrets
import smtplib
import html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
import os
import sys
import base64
import binascii
import json
import subprocess
from typing import Any, cast
from dotenv import load_dotenv  # type: ignore[import]
from database import init_db, get_db_connection  # type: ignore[import]

# Add Smart-Attendance-System to the Python path so web_enroll can be imported
_ATTENDANCE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Smart-Attendance-System'))
if _ATTENDANCE_ROOT not in sys.path:
    sys.path.insert(0, _ATTENDANCE_ROOT)

try:
    import web_enroll
    import web_recognize
except Exception as _import_err:
    print(f"Warning: could not import web_enroll or web_recognize directly: {_import_err}")
    web_enroll = None
    web_recognize = None

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
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit (5 base64 captures)

@app.after_request
def add_header(response):
    # Set aggressive cache headers for static files to make page image loading instant
    if 'Cache-Control' not in response.headers:
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response

import recommendation_model




def get_enrolled_database():
    import pickle
    db_dir = os.getenv('SQLITE_DB_DIR')
    if db_dir:
        db_path = os.path.join(db_dir, 'database.pkl')
    else:
        db_path = os.path.join(_ATTENDANCE_ROOT, 'database', 'database.pkl')
        
    if os.path.exists(db_path):
        try:
            with open(db_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            backup = db_path + ".bak"
            if os.path.exists(backup):
                try:
                    with open(backup, 'rb') as f:
                        return pickle.load(f)
                except Exception:
                    pass
    return {}



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
SKIP_EMAIL_VERIFICATION = os.getenv('SKIP_EMAIL_VERIFICATION', 'True').lower() == 'true'

# Initialize database
init_db()


def to_clean_string(value: Any) -> str:
    """Safely convert request values to trimmed strings."""
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return value.decode('utf-8', errors='replace').strip()
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


SEMESTER_START = date(2026, 2, 1)
SEMESTER_END = date(2026, 6, 30)

def get_local_now() -> datetime:
    """Get current datetime in UTC+2 (Cairo/Egypt) timezone, naive."""
    import datetime as dt
    tz_offset = dt.timezone(dt.timedelta(hours=2))
    return dt.datetime.now(dt.timezone.utc).astimezone(tz_offset).replace(tzinfo=None)


WEEKDAY_MAP = {
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6
}

def count_weekday_occurrences(start_date, end_date, weekday: int) -> int:
    """
    Count how many times a given weekday occurs between start_date and end_date (inclusive).
    weekday: 0=Monday ... 6=Sunday
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date.split()[0], "%Y-%m-%d").date()
    elif hasattr(start_date, 'date'):
        start_date = start_date.date()
        
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date.split()[0], "%Y-%m-%d").date()
    elif hasattr(end_date, 'date'):
        end_date = end_date.date()

    count = 0
    curr = start_date
    while curr <= end_date:
        if curr.weekday() == weekday:
            count += 1
        curr += timedelta(days=1)
    return count

def parse_days_to_weekdays(days_str: str) -> list[int]:
    """Cleanly parse days string like 'Monday' or 'Mon, Wed' to list of weekday integers."""
    weekdays = []
    if not days_str:
        return weekdays
    parts = [p.strip().lower() for p in days_str.replace(',', ' ').split()]
    for p in parts:
        if p in WEEKDAY_MAP:
            weekdays.append(WEEKDAY_MAP[p])
    return weekdays

def mark_attendance(student_id: int, weekday: int):
    """
    Mark attendance for student_id for the most recent date matching weekday.
    Increases that student's stored attendance percentage for that weekday.
    """
    now = get_local_now()
    days_ago = (now.weekday() - weekday) % 7
    target_date = now - timedelta(days=days_ago)
    date_str = target_date.strftime("%Y-%m-%d")
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id FROM user_course_schedule WHERE user_id = %s",
                (student_id,)
            )
            rows = cursor.fetchall()
            matching_course_id = None
            
            for row in rows:
                sch_id = row[0]
                cursor.execute(
                    "SELECT days FROM user_course_schedule WHERE id = %s",
                    (sch_id,)
                )
                days_row = cursor.fetchone()
                if days_row:
                    c_days = parse_days_to_weekdays(to_clean_string(days_row[0]))
                    if weekday in c_days:
                        matching_course_id = sch_id
                        break
            
            if matching_course_id is None:
                cursor.execute(
                    "SELECT 1 FROM attendance WHERE user_id = %s AND date(attendance_date) = %s AND course_id IS NULL LIMIT 1",
                    (student_id, date_str)
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM attendance WHERE user_id = %s AND date(attendance_date) = %s AND course_id = %s LIMIT 1",
                    (student_id, date_str, matching_course_id)
                )
            
            if cursor.fetchone() is None:
                today_datetime = target_date.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO attendance (user_id, course_id, attendance_date, status, created_at) VALUES (%s, %s, %s, TRUE, %s)",
                    (student_id, matching_course_id, today_datetime, today_datetime)
                )
                connection.commit()
            cursor.close()
        except Exception as e:
            print(f"Error marking attendance: {e}")
        finally:
            connection.close()

def get_current_active_course_id(student_id: int):
    """Check if there is a course in the student's schedule active at the current time and weekday."""
    now = get_local_now()
    weekday = now.weekday()
    current_time = now.time()
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, start_time, end_time, days FROM user_course_schedule WHERE user_id = %s",
                (student_id,)
            )
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            
            for row in rows:
                sch_id, start_val, end_val, days_str = row
                c_days = parse_days_to_weekdays(to_clean_string(days_str))
                if weekday in c_days:
                    def _to_time(val):
                        if val is None:
                            return None
                        if hasattr(val, 'seconds'):
                            total = int(val.total_seconds())
                            h = total // 3600
                            m = (total % 3600) // 60
                            return time(h, m)
                        if isinstance(val, time):
                            return val
                        s = str(val).strip()
                        for fmt in ("%H:%M:%S", "%H:%M"):
                            try:
                                return datetime.strptime(s, fmt).time()
                            except ValueError:
                                pass
                        return None
                    
                    st = _to_time(start_val)
                    et = _to_time(end_val)
                    if st and et:
                        if st <= current_time <= et:
                            return sch_id
        except Exception as e:
            print(f"Error finding active course: {e}")
    return None

def get_weekly_attendance(student_id: int) -> dict[str, float]:
    """
    Get weekday attendance percentages (Mon-Sun) based on weekday occurrences in the semester.
    Returns: {"Mon": 45.2, "Tue": 50.0, ...}
    """
    days_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    result = {name: 0.0 for name in days_map.values()}
    
    increments = {}
    for wd in range(7):
        occ = count_weekday_occurrences(SEMESTER_START, SEMESTER_END, wd)
        increments[wd] = (100.0 / occ if occ > 0 else 0.0) * 2.0

    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT attendance_date FROM attendance WHERE user_id = %s",
                (student_id,)
            )
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            attendance_by_wd = {wd: 0 for wd in range(7)}
            unique_dates = set()
            for row in rows:
                dt = row[0]
                if not dt:
                    continue
                if isinstance(dt, str):
                    try:
                        if ' ' in dt:
                            dt_obj = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                        else:
                            dt_obj = datetime.strptime(dt, "%Y-%m-%d")
                    except ValueError:
                        continue
                else:
                    dt_obj = dt
                    
                dt_date = dt_obj.date() if hasattr(dt_obj, 'date') else dt_obj
                if SEMESTER_START <= dt_date <= SEMESTER_END:
                    unique_dates.add(dt_date)
                    
            for dt_date in unique_dates:
                wd = dt_date.weekday()
                attendance_by_wd[wd] += 1
                
            for wd in range(7):
                pct = min(100.0, attendance_by_wd[wd] * increments[wd])
                result[days_map[wd]] = round(pct, 1)
    except Exception as e:
        print(f"Error in get_weekly_attendance: {e}")
    return result

def calculate_overall_attendance_rate(courses_data: list[dict[str, Any]]) -> float:
    """Calculate the overall weighted attendance rate across all enrolled courses with a 2.0x scale."""
    total_present = sum(c.get('present_count', 0) for c in courses_data)
    total_lectures = sum(c.get('total_lectures', 0) for c in courses_data)
    if total_lectures > 0:
        return min(100.0, round((total_present * 2.0 / total_lectures) * 100, 1))
    return 0.0


def get_user_courses_data(user_id: int) -> list[dict[str, Any]]:
    """Fetch user's selected courses with dynamic attendance percent based on database records."""
    courses_data = []
    colors = ['#ff6b35', '#e8c547', '#3b82f6', '#22c55e', '#a855f7', '#ec4899', '#14b8a6', '#f43f5e']
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, course_name, days FROM user_course_schedule WHERE user_id = %s ORDER BY course_name",
                (user_id,)
            )
            rows = cursor.fetchall()
            
            # Fetch all attendance records for this user to calculate present counts
            cursor.execute(
                "SELECT course_id, attendance_date FROM attendance WHERE user_id = %s",
                (user_id,)
            )
            att_rows = cursor.fetchall()
            cursor.close()
            connection.close()
            
            # Organize attendance by course_id (all records within semester)
            schedule_ids = {row[0] for row in rows}
            att_by_course = {}
            general_att_dates = []
            
            for r in att_rows:
                cid = r[0]
                dt = r[1]
                if not dt:
                    continue
                if isinstance(dt, str):
                    try:
                        if ' ' in dt:
                            dt_obj = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                        else:
                            dt_obj = datetime.strptime(dt, "%Y-%m-%d")
                    except ValueError:
                        continue
                else:
                    dt_obj = dt
                
                dt_date = dt_obj.date() if hasattr(dt_obj, 'date') else dt_obj
                if SEMESTER_START <= dt_date <= SEMESTER_END:
                    if cid is None or cid not in schedule_ids:
                        general_att_dates.append(dt_date)
                    else:
                        att_by_course.setdefault(cid, []).append(dt_date)
            
            for idx, row in enumerate(rows):
                sch_id = row[0]
                name = to_clean_string(row[1])
                days_str = to_clean_string(row[2])
                
                # Calculate total lectures
                weekdays = parse_days_to_weekdays(days_str)
                total_lectures = 0
                for wd in weekdays:
                    total_lectures += count_weekday_occurrences(SEMESTER_START, SEMESTER_END, wd)
                
                # Calculate present count
                present_list = att_by_course.get(sch_id, [])
                present_count = len(present_list)
                
                # Compute pct with a 2.0x scale
                if total_lectures > 0:
                    pct = min(100.0, round((present_count * 2.0 / total_lectures) * 100, 1))
                else:
                    pct = 0.0
                
                clr = colors[idx % len(colors)]
                courses_data.append({
                    'name': name,
                    'pct': pct,
                    'clr': clr,
                    'id': sch_id,
                    'present_count': present_count,
                    'total_lectures': total_lectures
                })
                
            pass
    except Exception as e:
        print(f"Error fetching user courses: {e}")

    # Fallback to default set of courses if none selected
    if not courses_data:
        default_names = ['Mathematics', 'Physics', 'Computer Sci.', 'Data Structures', 'English']
        for idx, name in enumerate(default_names):
            import hashlib
            hash_val = int(hashlib.md5(f"{name}_{user_id}".encode()).hexdigest(), 16)
            pct = 40 + (hash_val % 59)
            clr = colors[idx % len(colors)]
            courses_data.append({
                'name': name,
                'pct': pct,
                'clr': clr,
                'id': None,
                'present_count': int(pct / 10),
                'total_lectures': 10
            })
    return courses_data


def get_weekly_attendance_stats(user_id: int) -> list[float]:
    """Calculate weekly attendance rate (Mon-Sun) based on semester calculations."""
    weekly_dict = get_weekly_attendance(user_id)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return [weekly_dict.get(d, 0.0) for d in days]


def has_additional_info(user_id: int):
    """Check if the user already submitted additional info."""
    import time
    for attempt in range(3):
        connection = get_db_connection()
        if connection is None:
            if attempt < 2:
                time.sleep(0.1)
                continue
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM user_additional_info WHERE user_id = %s LIMIT 1", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception as error:
            print(f"Additional info check error (attempt {attempt + 1}): {str(error)}")
            if attempt < 2:
                time.sleep(0.1)
                continue
            return False
        finally:
            if connection:
                connection.close()


def has_course_schedule(user_id: int):
    """Check if the user already submitted their course schedule."""
    import time
    for attempt in range(3):
        connection = get_db_connection()
        if connection is None:
            if attempt < 2:
                time.sleep(0.1)
                continue
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM user_course_schedule WHERE user_id = %s LIMIT 1", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception as error:
            print(f"Course schedule check error (attempt {attempt + 1}): {str(error)}")
            if attempt < 2:
                time.sleep(0.1)
                continue
            return False
        finally:
            if connection:
                connection.close()

def send_verification_email(email, verification_token):
    """Send verification email to the user"""
    try:
        import requests
    except ImportError:
        requests = None

    try:
        subject = "Email Verification - Hamas"
        verification_link = f"{request.host_url}verify-email/{verification_token}"
        
        # Normalize sender and recipient emails for header and envelope
        sender_email = normalize_email_address(EMAIL_ADDRESS)
        recipient_email = normalize_email_address(email)
        
        print(f"\n[EMAIL VERIFICATION LINK FOR {recipient_email}]: {verification_link}\n")
        
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email_logs.txt')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().isoformat()}] Verification link for {recipient_email}: {verification_link}\n")
        except Exception as log_err:
            print(f"Error writing email log: {log_err}")
        
        body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Email Verification</h2>
            <p>Welcome to the Student Recommendation and Attendance System!</p>
            <p>Please click the link below to verify your email address:</p>
            <a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Verify Email
            </a>
            <p>Or copy this link in your browser:</p>
            <p>{verification_link}</p>
            <p>This verification link will expire in 24 hours.</p>
            <p>If you didn't sign up for this account, please ignore this email.</p>
        </body>
        </html>
        """
        
        # Try sending using Brevo HTTP API (Port 443, not blocked by Railway)
        brevo_api_key = os.getenv('BREVO_API_KEY')
        if not brevo_api_key and EMAIL_PASSWORD and (EMAIL_PASSWORD.startswith("xkeysib-") or len(EMAIL_PASSWORD) > 40):
            brevo_api_key = EMAIL_PASSWORD

        if brevo_api_key and requests:
            print("Attempting to send email via Brevo HTTP API...")
            headers = {
                "accept": "application/json",
                "api-key": brevo_api_key,
                "content-type": "application/json"
            }
            payload = {
                "sender": {
                    "name": "Hamas",
                    "email": sender_email
                },
                "to": [
                    {
                        "email": recipient_email
                    }
                ],
                "subject": subject,
                "htmlContent": body
            }
            try:
                res = requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=8.0)
                if res.status_code in [200, 201, 202]:
                    print("Email sent successfully via Brevo HTTP API.")
                    return True
                else:
                    print(f"Brevo HTTP API failed with status {res.status_code}: {res.text}")
            except Exception as http_err:
                print(f"Brevo HTTP API request failed: {str(http_err)}")

        # Fallback to standard SMTP
        print("Falling back to SMTP email transmission...")
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"Hamas <{sender_email}>"
        message["To"] = recipient_email
        
        part = MIMEText(body, "html")
        message.attach(part)
        
        # Send email with a 5-second timeout to prevent hanging when SMTP is blocked/unreachable
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5.0) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(normalize_email_address(EMAIL_ADDRESS), EMAIL_PASSWORD)
            server.sendmail(sender_email, recipient_email, message.as_string())
        
        print("Email sent successfully via SMTP.")
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
        <body style="font-family: Arial, sans-serif; color: #111827;">
            <h2 style="margin-bottom: 8px;">New Help Request</h2>
            <p style="margin: 0 0 14px; color: #4b5563;">A new message was submitted from the Help page.</p>

            <table cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 640px;">
                <tr><td style="font-weight:700; border:1px solid #e5e7eb; width:150px;">Name</td><td style="border:1px solid #e5e7eb;">{safe_name}</td></tr>
                <tr><td style="font-weight:700; border:1px solid #e5e7eb;">Email</td><td style="border:1px solid #e5e7eb;">{safe_email}</td></tr>
                <tr><td style="font-weight:700; border:1px solid #e5e7eb;">Subject</td><td style="border:1px solid #e5e7eb;">{safe_subject}</td></tr>
                <tr><td style="font-weight:700; border:1px solid #e5e7eb;">Submitted at</td><td style="border:1px solid #e5e7eb;">{submitted_at}</td></tr>
                <tr><td style="font-weight:700; border:1px solid #e5e7eb; vertical-align:top;">Message</td><td style="border:1px solid #e5e7eb;">{safe_message}</td></tr>
            </table>
        </body>
        </html>
        """

        sender_email = normalize_email_address(EMAIL_ADDRESS)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Help Request: {to_clean_string(subject)}"
        msg["From"] = f"Hamas <{sender_email}>"
        msg["To"] = support_email

        normalized_sender = normalize_email_address(user_email)
        if normalized_sender and '@' in normalized_sender:
            msg["Reply-To"] = normalized_sender

        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(normalize_email_address(EMAIL_ADDRESS), EMAIL_PASSWORD)
            server.sendmail(sender_email, [support_email], msg.as_string())

        return True
    except Exception as error:
        print(f"Error sending help request email: {error}")
        return False


def send_session_report_email(students, course_id=None):
    """Send a session report email containing recognized students and their IDs to sofyankirat123@gmail.com."""
    recipient_email = "sofyankirat123@gmail.com"
    try:
        import requests
    except ImportError:
        requests = None

    try:
        subject = "AI Attendance System - Recognized Students Report"
        
        course_name = "N/A"
        if course_id:
            try:
                connection = get_db_connection()
                if connection:
                    cursor = connection.cursor()
                    cursor.execute("SELECT course_name FROM user_course_schedule WHERE id = %s LIMIT 1", (course_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        course_name = to_clean_string(row[0])
                    cursor.close()
                    connection.close()
            except Exception as e:
                print(f"Error fetching course name for email: {e}")
        
        sender_email = normalize_email_address(EMAIL_ADDRESS)
        
        rows_html = ""
        for s in students:
            rows_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #e5e7eb;">{s.get('id')}</td>
                <td style="padding: 8px; border: 1px solid #e5e7eb;">{s.get('name')}</td>
                <td style="padding: 8px; border: 1px solid #e5e7eb;">{s.get('email')}</td>
            </tr>
            """
            
        body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Recognized Students Session Report</h2>
            <p>The camera stream session has completed successfully. Below is the list of recognized students whose attendance data has been updated on the website:</p>
            
            <p><strong>Course/Class:</strong> {course_name}</p>
            <p><strong>Date:</strong> {get_local_now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background-color: #f3f4f6;">
                        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Student ID</th>
                        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Name</th>
                        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Email Address</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="3" style="padding: 8px; border: 1px solid #e5e7eb; text-align: center;">No students recognized.</td></tr>'}
                </tbody>
            </table>
            
            <p style="margin-top: 20px; font-size: 12px; color: #666;">This is an automated system notification.</p>
        </body>
        </html>
        """
        
        # Try Brevo HTTP API
        brevo_api_key = os.getenv('BREVO_API_KEY')
        if not brevo_api_key and EMAIL_PASSWORD and (EMAIL_PASSWORD.startswith("xkeysib-") or len(EMAIL_PASSWORD) > 40):
            brevo_api_key = EMAIL_PASSWORD

        if brevo_api_key and requests:
            headers = {
                "accept": "application/json",
                "api-key": brevo_api_key,
                "content-type": "application/json"
            }
            payload = {
                "sender": {
                    "name": "Hamas",
                    "email": sender_email
                },
                "to": [
                    {
                        "email": recipient_email
                    }
                ],
                "subject": subject,
                "htmlContent": body
            }
            try:
                res = requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=8.0)
                if res.status_code in [200, 201, 202]:
                    print("Session report email sent successfully via Brevo.")
                    return True
                else:
                    print(f"Brevo HTTP API failed for session report with status {res.status_code}: {res.text}")
            except Exception as http_err:
                print(f"Brevo HTTP API request failed for session report: {str(http_err)}")

        # Fallback to standard SMTP
        print("Falling back to SMTP for session report email...")
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"Hamas <{sender_email}>"
        message["To"] = recipient_email
        
        part = MIMEText(body, "html")
        message.attach(part)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5.0) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(normalize_email_address(EMAIL_ADDRESS), EMAIL_PASSWORD)
            server.sendmail(sender_email, recipient_email, message.as_string())
        
        print("Session report email sent successfully via SMTP.")
        return True
    except Exception as e:
        print(f"Error sending session report email: {str(e)}")
        return False


def login_required(f):
    """Decorator to check if user is logged in and completed setup flow"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user_id = to_int_value(session.get('user_id'))
        # Avoid redirect loops on setup pages, static resources, or logout
        if request.endpoint not in ('additional_info', 'course_schedule', 'logout', 'static'):
            if not has_additional_info(user_id):
                return redirect(url_for('additional_info'))
            if not has_course_schedule(user_id):
                return redirect(url_for('course_schedule'))
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
        email = normalize_email_address(data.get('email', ''))
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
                hashed_password = to_clean_string(user[1])
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
                if not has_additional_info(user_id):
                    redirect_target = url_for('additional_info')
                elif not has_course_schedule(user_id):
                    redirect_target = url_for('course_schedule')
                else:
                    redirect_target = url_for('dashboard')
                return jsonify({'success': True, 'message': 'Login successful', 'redirect': redirect_target})
            else:
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
        
        except Exception as e:
            print(f"Login error: {str(e)}")
            return jsonify({'success': False, 'message': 'An error occurred during login'}), 500
    
    return render_template('login.html')


@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email for unverified accounts."""
    data = request.get_json() if request.is_json else request.form
    email = normalize_email_address(data.get('email', ''))

    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    try:
        connection = get_db_connection()
        if connection is None:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = connection.cursor()
        cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'No account found for this email'}), 404

        user_id = to_int_value(user[0])
        is_verified = bool(user[1])

        if is_verified:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Email already verified. Please login.'}), 400

        verification_token = secrets.token_urlsafe(32)
        cursor.execute(
            "UPDATE users SET verification_token = %s, token_expiry = %s WHERE id = %s",
            (verification_token, datetime.now() + timedelta(hours=24), user_id)
        )
        connection.commit()
        cursor.close()
        connection.close()

        if send_verification_email(email, verification_token):
            return jsonify({'success': True, 'message': 'Verification email sent. Please check your inbox.'})

        else:
            # If email failed to send, auto-verify user to avoid lockouts
            connection = get_db_connection()
            if connection:
                try:
                    cursor = connection.cursor()
                    cursor.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (user_id,))
                    connection.commit()
                    cursor.close()
                except Exception as db_err:
                    print(f"Error auto-verifying user: {db_err}")
                finally:
                    connection.close()

            return jsonify({
                'success': True,
                'message': 'SMTP verification email failed to send, so your account was automatically verified. You can log in now!',
                'email_verification_sent': False
            })
    except Exception as error:
        print(f"Resend verification error: {str(error)}")
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = normalize_email_address(data.get('email', ''))
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
            
            # Check if password already exists by comparing against all user passwords
            cursor.execute("SELECT password FROM users")
            existing_passwords = cursor.fetchall()
            
            for (existing_hash,) in existing_passwords:
                if check_password_hash(existing_hash, password):
                    cursor.close()
                    connection.close()
                    return jsonify({'success': False, 'message': 'Password already exists'}), 409
            
            # Generate verification token and hash password
            verification_token = secrets.token_urlsafe(32)
            hashed_password = generate_password_hash(password)
            
            # Insert new user
            is_verified_value = True if SKIP_EMAIL_VERIFICATION else False
            cursor.execute(
                "INSERT INTO users (email, password, is_verified, verification_token, token_expiry) VALUES (%s, %s, %s, %s, %s)",
                (email, hashed_password, is_verified_value, verification_token, datetime.now() + timedelta(hours=24))
            )
            connection.commit()
            cursor.close()
            connection.close()
            
            # If skipping verification, return success immediately
            if SKIP_EMAIL_VERIFICATION:
                return jsonify({
                    'success': True,
                    'message': 'Registration successful! Redirecting to login...',
                    'email_verification_sent': False
                })
            
            # Send verification email
            if send_verification_email(email, verification_token):
                return jsonify({
                    'success': True, 
                    'message': 'Registration successful! Please check your email to verify your account.'
                })
            else:
                # If email failed to send, auto-verify user to avoid lockouts
                connection = get_db_connection()
                if connection:
                    try:
                        cursor = connection.cursor()
                        cursor.execute("UPDATE users SET is_verified = TRUE WHERE email = %s", (email,))
                        connection.commit()
                        cursor.close()
                    except Exception as db_err:
                        print(f"Error auto-verifying user on register: {db_err}")
                    finally:
                        connection.close()

                return jsonify({
                    'success': True, 
                    'message': 'Registration successful! SMTP verification email failed to send, so your account was automatically verified. Redirecting to login...',
                    'email_verification_sent': False
                })
        
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
    
    gpa_value = None
    # Fetch real first name and GPA from additional info
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT first_name, gpa FROM user_additional_info WHERE user_id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            if result:
                if result[0]:
                    username = result[0]
                gpa_value = float(result[1]) if result[1] is not None else None
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching user name: {e}")
        
    courses = get_user_courses_data(to_int_value(user_id))

    # Fetch recommendation history for dashboard cards
    recommendation_history: list[dict[str, Any]] = []

    try:
        rec_conn = get_db_connection()
        if rec_conn:
            rec_cursor = rec_conn.cursor()
            rec_cursor.execute(
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
            rec_rows = rec_cursor.fetchall()
            rec_cursor.close()
            rec_conn.close()

            for row in rec_rows:
                created_at_value = row[9]
                if isinstance(created_at_value, datetime):
                    created_at_text = created_at_value.strftime('%Y-%m-%d %I:%M %p')
                else:
                    created_at_text = to_clean_string(created_at_value)

                recommendation_history.append({
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
                })
    except Exception as rec_err:
        print(f"Error fetching recommendation history for dashboard: {rec_err}")

    weekly_data = get_weekly_attendance_stats(to_int_value(user_id))
    attendance_rate = calculate_overall_attendance_rate(courses)
    return render_template('dashboard.html', username=username, email=email,
                           profile_photo=_get_profile_photo(user_id), gpa=gpa_value,
                           courses=courses, recommendation_history=recommendation_history,
                           weekly_data=weekly_data, attendance_rate=attendance_rate)


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
    db_dir = os.getenv('SQLITE_DB_DIR')
    if db_dir:
        uploads_dir = os.path.join(db_dir, 'uploads')
        path = os.path.join(uploads_dir, f'profile_{user_id}.jpg')
        if os.path.exists(path):
            return url_for('serve_profile_photo', user_id=user_id)
            
    static_root = get_static_root()
    path = os.path.join(static_root, 'uploads', f'profile_{user_id}.jpg')
    if os.path.exists(path):
        return url_for('static', filename=f'uploads/profile_{user_id}.jpg')
    return None


@app.route('/uploads/profile/<int:user_id>')
def serve_profile_photo(user_id):
    db_dir = os.getenv('SQLITE_DB_DIR')
    if not db_dir:
        return "Not found", 404
    uploads_dir = os.path.join(db_dir, 'uploads')
    photo_path = os.path.join(uploads_dir, f'profile_{user_id}.jpg')
    if os.path.exists(photo_path):
        return send_from_directory(uploads_dir, f'profile_{user_id}.jpg')
    return "Not found", 404




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


@app.route('/assessment')
@login_required
def assessment():
    """Separate dedicated assessment page to avoid lag and show results."""
    course_name = request.args.get('course', 'Selected Course')
    return render_template('assessment.html', course_name=course_name)


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
                db_dir = os.getenv('SQLITE_DB_DIR')
                if db_dir:
                    uploads_dir = os.path.join(db_dir, 'uploads')
                else:
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
                student_id, first_name, age, program, gender, level,
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
                existing['student_id'],
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
        student_id       = pick_str('student_id')
        if student_id and (not student_id.isdigit() or len(student_id) != 9):
            student_id = existing.get('student_id') or ''
        first_name       = pick_str('first_name')
        age              = pick_int('age')
        program          = pick_str('program')
        gender           = pick_str('gender')
        level            = pick_int('level')
        is_working_raw   = pick_str('is_working', 'No')
        # DB stores is_working as 0/1 int; ensure we compare as a string
        is_working_str   = str(is_working_raw).strip()
        is_working       = is_working_str.lower() in ('yes', '1', 'true')
        failed_subjects  = pick_int('failed_subjects')
        discipline_score = pick_int('discipline_score')
        analytical_score = pick_int('analytical_score')
        practical_score  = pick_int('practical_score')
        gpa              = pick_float('gpa')
        screen_hours     = pick_float('screen_hours')

        # ── Step 4: upsert with the merged values ───────────────────────────────
        cursor2 = connection.cursor()
        if existing_row:
            print(f"[PROFILE_UPDATE] Updating existing row for user_id={user_id}")
            params = (student_id, first_name, age, program, gender, level,
                      is_working, failed_subjects, discipline_score,
                      analytical_score, practical_score, gpa, screen_hours,
                      user_id)
            print(f"[PROFILE_UPDATE] Params: {params}")
            cursor2.execute(
                """
                UPDATE user_additional_info SET
                    student_id = %s, first_name = %s, age = %s, program = %s,
                    gender = %s, level = %s, is_working = %s,
                    failed_subjects = %s, discipline_score = %s,
                    analytical_score = %s, practical_score = %s,
                    gpa = %s, screen_hours = %s
                WHERE user_id = %s
                """,
                params
            )
            print(f"[PROFILE_UPDATE] Update rowcount: {cursor2.rowcount}")
        else:
            print(f"[PROFILE_UPDATE] Inserting new row for user_id={user_id}")
            params = (user_id, student_id, first_name, age, program, gender, level,
                      is_working, failed_subjects, discipline_score,
                      analytical_score, practical_score, gpa, screen_hours)
            print(f"[PROFILE_UPDATE] Params: {params}")
            cursor2.execute(
                """
                INSERT INTO user_additional_info (
                    user_id, student_id, first_name, age, program, gender, level,
                    is_working, failed_subjects, discipline_score,
                    analytical_score, practical_score, gpa, screen_hours
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                params
            )
            print(f"[PROFILE_UPDATE] Insert rowcount: {cursor2.rowcount}")
        connection.commit()
        print("[PROFILE_UPDATE] Committed successfully.")
        cursor2.close()
        connection.close()

        return redirect(url_for('profile', saved=1))

    except Exception as e:
        print(f"Profile update error: {e}")
        import traceback; traceback.print_exc()
        return redirect(url_for('profile', saved=0))


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
        if not has_course_schedule(user_id):
            return redirect(url_for('course_schedule'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        student_id = to_clean_string(request.form.get('student_id'))
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

        if not student_id or not student_id.isdigit() or len(student_id) != 9 or not first_name or age <= 0 or not program or not gender or level <= 0:
            return render_template('additional_info.html')

        connection = get_db_connection()
        if connection is None:
            return render_template('additional_info.html')

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM user_additional_info WHERE user_id = %s", (user_id,))
            exists = cursor.fetchone()

            if exists:
                cursor.execute(
                    """
                    UPDATE user_additional_info SET
                        student_id = %s,
                        first_name = %s,
                        age = %s,
                        program = %s,
                        gender = %s,
                        level = %s,
                        is_working = %s,
                        failed_subjects = %s,
                        discipline_score = %s,
                        analytical_score = %s,
                        practical_score = %s,
                        gpa = %s,
                        screen_hours = %s
                    WHERE user_id = %s
                    """,
                    (
                        student_id,
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
                        user_id
                    )
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_additional_info (
                        user_id, student_id, first_name, age, program, gender, level,
                        is_working, failed_subjects, discipline_score,
                        analytical_score, practical_score, gpa, screen_hours
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        student_id,
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
                        screen_hours
                    )
                )
            connection.commit()
            cursor.close()
        except Exception as error:
            print(f"Additional info save error: {str(error)}")
            return render_template('additional_info.html')
        finally:
            connection.close()

        return redirect(url_for('course_schedule'))
    return render_template('additional_info.html')


@app.route('/course-schedule', methods=['GET', 'POST'])
@login_required
def course_schedule():
    """Course schedule setup page shown after additional info"""
    user_id = to_int_value(session.get('user_id'))

    if user_id <= 0:
        return redirect(url_for('login'))

    if not has_additional_info(user_id):
        return redirect(url_for('additional_info'))

    if request.method == 'GET' and has_course_schedule(user_id) and not request.args.get('edit'):
        return redirect(url_for('dashboard'))

    existing_schedule = []
    if request.method == 'GET' and has_course_schedule(user_id):
        try:
            connection = get_db_connection()
            if connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT course_name, start_time, end_time, days
                    FROM user_course_schedule
                    WHERE user_id = %s
                    ORDER BY start_time
                    """,
                    (user_id,)
                )
                rows = cursor.fetchall()
                cursor.close()
                connection.close()
                for row in rows:
                    def _fmt_time(val):
                        if val is None:
                            return ''
                        if hasattr(val, 'seconds'):
                            total = int(val.total_seconds())
                            h = total // 3600
                            m = (total % 3600) // 60
                            return f"{h:02d}:{m:02d}"
                        return str(val)[:5]
                    existing_schedule.append({
                        'course_name': to_clean_string(row[0]),
                        'start_time': _fmt_time(row[1]),
                        'end_time': _fmt_time(row[2]),
                        'days': to_clean_string(row[3])
                    })
        except Exception as error:
            print(f"Error prefetching schedule for edit: {error}")


    if request.method == 'POST':
        course_names = request.form.getlist('course_name')
        start_times = request.form.getlist('start_time')
        end_times = request.form.getlist('end_time')
        days_list = request.form.getlist('days')

        # Minimal server-side validation (client already enforces this)
        if not course_names:
            return render_template('course_schedule.html'), 400

        if len(course_names) > 8:
            return render_template('course_schedule.html'), 400

        if not (len(course_names) == len(start_times) == len(end_times) == len(days_list)):
            return render_template('course_schedule.html'), 400

        def _to_minutes(value: str) -> int | None:
            try:
                parts = value.split(':')
                if len(parts) != 2:
                    return None
                hours = int(parts[0])
                minutes = int(parts[1])
                return hours * 60 + minutes
            except Exception:
                return None

        allowed_min = _to_minutes('08:00')
        allowed_max = _to_minutes('18:00')

        # Validate all rows first (do not partially save)
        entries: list[tuple[str, str, str, str, int, int]] = []
        for i in range(len(course_names)):
            name = to_clean_string(course_names[i])
            start = to_clean_string(start_times[i])
            end = to_clean_string(end_times[i])
            days = to_clean_string(days_list[i])

            # All 4 fields required
            if not (name and start and end and days):
                return render_template('course_schedule.html'), 400

            # Only one day allowed per course
            if ',' in days:
                return render_template('course_schedule.html'), 400

            start_min = _to_minutes(start)
            end_min = _to_minutes(end)
            if start_min is None or end_min is None or allowed_min is None or allowed_max is None:
                return render_template('course_schedule.html'), 400

            # Enforce 08:00 - 18:00 window and end after start
            if start_min < allowed_min or start_min > allowed_max:
                return render_template('course_schedule.html'), 400
            if end_min < allowed_min or end_min > allowed_max:
                return render_template('course_schedule.html'), 400
            if start_min >= end_min:
                return render_template('course_schedule.html'), 400

            entries.append((name, start, end, days, start_min, end_min))

        # Disallow overlaps on the same day
        entries_by_day: dict[str, list[tuple[int, int]]] = {}
        for (_, _, _, day, start_min, end_min) in entries:
            entries_by_day.setdefault(day, []).append((start_min, end_min))

        for day, intervals in entries_by_day.items():
            intervals_sorted = sorted(intervals, key=lambda t: t[0])
            for idx in range(1, len(intervals_sorted)):
                prev_start, prev_end = intervals_sorted[idx - 1]
                cur_start, cur_end = intervals_sorted[idx]
                # overlap if current starts before previous ends
                if cur_start < prev_end:
                    return render_template('course_schedule.html'), 400

        connection = get_db_connection()
        if connection is None:
            return render_template('course_schedule.html')

        try:
            cursor = connection.cursor()
            
            # Fetch existing course schedule entries for this user
            cursor.execute(
                "SELECT id, course_name, start_time, end_time, days FROM user_course_schedule WHERE user_id = %s",
                (user_id,)
            )
            existing_rows = cursor.fetchall()
            
            # Map them by (course_name.strip().lower(), days.strip().lower())
            existing_by_key = {}
            for row in existing_rows:
                db_id = row[0]
                db_name = to_clean_string(row[1]).strip().lower()
                db_days = to_clean_string(row[4]).strip().lower()
                existing_by_key[(db_name, db_days)] = row
            
            kept_ids = set()
            
            for (name, start, end, days, _, _) in entries:
                key = (name.strip().lower(), days.strip().lower())
                if key in existing_by_key:
                    db_id = existing_by_key[key][0]
                    # Update start_time and end_time
                    cursor.execute(
                        """
                        UPDATE user_course_schedule 
                        SET start_time = %s, end_time = %s 
                        WHERE id = %s
                        """,
                        (start, end, db_id)
                    )
                    kept_ids.add(db_id)
                else:
                    # Insert new course entry
                    cursor.execute(
                        """
                        INSERT INTO user_course_schedule (
                            user_id, course_name, start_time, end_time, days
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        (user_id, name, start, end, days)
                    )
            
            # Delete any courses that were not kept
            for key, row in existing_by_key.items():
                db_id = row[0]
                if db_id not in kept_ids:
                    cursor.execute(
                        "DELETE FROM user_course_schedule WHERE id = %s",
                        (db_id,)
                    )

            connection.commit()
            cursor.close()
        except Exception as error:
            print(f"Course schedule save error: {str(error)}")
            return render_template('course_schedule.html')
        finally:
            connection.close()

        return redirect(url_for('dashboard'))

    return render_template('course_schedule.html', existing_schedule=existing_schedule, has_schedule=has_course_schedule(user_id))


@app.route('/recommendations', methods=['GET', 'POST'])
@login_required
def recommendations():
    """Recommendation page and form handler"""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')
    
    # Default fallback is capitalized email prefix
    username = email.split('@')[0].capitalize() if email else 'User'
    
    # Fetch real first name and student_id from additional info
    student_id = ''
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name, student_id FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result:
                if result[0]:
                    username = result[0]
                if result[1]:
                    student_id = result[1]
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

        # Fetch student's profile info for ML prediction
        student_info = None
        try:
            db_conn = get_db_connection()
            if db_conn:
                db_curr = db_conn.cursor()
                db_curr.execute(
                    """
                    SELECT age, program, gender, level, is_working, failed_subjects, 
                           discipline_score, analytical_score, practical_score, gpa, screen_hours
                    FROM user_additional_info 
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (user_id,)
                )
                db_row = db_curr.fetchone()
                db_curr.close()
                db_conn.close()
                if db_row:
                    student_info = {
                        'age': int(db_row[0]) if db_row[0] is not None else 20,
                        'program': db_row[1] if db_row[1] is not None else 'Statistics and Computer Science',
                        'gender': db_row[2] if db_row[2] is not None else 'Male',
                        'level': int(db_row[3]) if db_row[3] is not None else 1,
                        'is_working': int(db_row[4]) if db_row[4] is not None else 0,
                        'failed_subjects': int(db_row[5]) if db_row[5] is not None else 0,
                        'discipline_score': int(db_row[6]) if db_row[6] is not None else 7,
                        'analytical_score': int(db_row[7]) if db_row[7] is not None else 7,
                        'practical_score': int(db_row[8]) if db_row[8] is not None else 7,
                        'gpa': float(db_row[9]) if db_row[9] is not None else 3.0,
                        'screen_hours': float(db_row[10]) if db_row[10] is not None else 4.0
                    }
        except Exception as e:
            print(f"Error retrieving student additional info: {e}")

        if not student_info:
            student_info = {
                'age': 20,
                'program': 'Statistics and Computer Science',
                'gender': 'Male',
                'level': 1,
                'is_working': 0,
                'failed_subjects': 0,
                'discipline_score': 7,
                'analytical_score': 7,
                'practical_score': 7,
                'gpa': 3.0,
                'screen_hours': 4.0
            }

        # Call prediction model and LLM reasoning
        try:
            prediction = recommendation_model.predict_recommendation(
                student_info=student_info,
                course_name=course_name,
                professor_name=professors,
                study_hours=weekly_avg_study_hours,
                attendance_percentage=attendance_count
            )
            score = prediction['score']
            recommended = prediction['recommended']
            reason = recommendation_model.generate_llm_reasoning(prediction)
        except Exception as pred_err:
            import traceback
            traceback.print_exc()
            print(f"Prediction error: {pred_err}")
            # Fallback values
            score = 75.0
            recommended = True
            
            # Construct a structured fallback object to call detailed reasoning formatter
            fallback_prediction = {
                'score': score,
                'recommended': recommended,
                'features': {
                    'student_program': student_info.get('program', 'Statistics and Computer Science'),
                    'student_level': student_info.get('level', 1),
                    'GPA': student_info.get('gpa', 3.0),
                    'analytical_score': student_info.get('analytical_score', 7),
                    'practical_score': student_info.get('practical_score', 7),
                    'total_failed_subjects': student_info.get('failed_subjects', 0),
                    'is_employed': student_info.get('is_working', 0),
                    'course_name': course_name if course_name else "Selected Course",
                    'course_category': "Core/Optional",
                    'course_difficulty': 3,
                    'course_credit_hours': 3,
                    'is_required': "Required",
                    'professor_name': professors if professors else "Selected Professor",
                    'professor_avg_teaching_score': 8,
                    'professor_avg_pass_percentage': 80,
                    'weekly_avg_study_hours_subject': weekly_avg_study_hours,
                    'student_attendance_percentage_subject': attendance_count
                }
            }
            reason = recommendation_model.generate_llm_reasoning(fallback_prediction)

        # Sticky form data
        form_data = {
            'Course_name': course_name,
            'professors': professors,
            'weekly_avg_study_hours_subject': weekly_avg_study_hours,
            'attendance_count': attendance_count
        }

        default_history_title = f"{course_name} - {professors} - {weekly_avg_study_hours:g} hrs - {attendance_count}%"
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
        selected_history_id=selected_history_id,
        student_id=student_id
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
        profile_photo=_get_profile_photo(user_id),
        user_id=user_id
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


@app.route('/schedule')
@login_required
def schedule():
    """Weekly schedule timetable page."""
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

    # Fetch the course schedule
    schedule_entries: list[dict] = []
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT course_name, start_time, end_time, days
                FROM user_course_schedule
                WHERE user_id = %s
                ORDER BY start_time
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            for row in rows:
                # start_time / end_time may come back as timedelta from MySQL
                def _fmt_time(val):
                    if val is None:
                        return ''
                    if hasattr(val, 'seconds'):
                        # timedelta
                        total = int(val.total_seconds())
                        h = total // 3600
                        m = (total % 3600) // 60
                        return f"{h:02d}:{m:02d}"
                    return str(val)[:5]  # "HH:MM:SS" → "HH:MM"

                schedule_entries.append({
                    'course_name': to_clean_string(row[0]),
                    'start_time': _fmt_time(row[1]),
                    'end_time': _fmt_time(row[2]),
                    'day': to_clean_string(row[3]),
                })
    except Exception as error:
        print(f"Error fetching schedule: {error}")

    return render_template(
        'schedule.html',
        username=username,
        email=email,
        profile_photo=_get_profile_photo(user_id),
        schedule_entries=schedule_entries,
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
                username = to_clean_string(result[0])
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
        is_postgres = connection.__class__.__name__ == 'PostgresConnectionWrapper'
        
        if is_postgres:
            cursor.execute(
                """
                INSERT INTO user_ai_chat_state (user_id, chat_data, chat_counter, current_chat_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    chat_data = EXCLUDED.chat_data,
                    chat_counter = EXCLUDED.chat_counter,
                    current_chat_id = EXCLUDED.current_chat_id
                """,
                (user_id, json.dumps(chats), chat_counter, current_chat_id)
            )
        else:
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_ai_chat_state (user_id, chat_data, chat_counter, current_chat_id)
                VALUES (%s, %s, %s, %s)
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


@app.route('/api/ai-chat', methods=['POST'])
@login_required
def ai_chat():
    """Endpoint to handle AI Agent chat queries integrated with Mini_RAG / Gemini"""
    import requests
    user_id = to_int_value(session.get('user_id'))
    payload = request.get_json() or {}
    
    message = to_clean_string(payload.get('message', ''))
    file_url = to_clean_string(payload.get('fileUrl', ''))
    mime_type = to_clean_string(payload.get('mimeType', ''))
    chat_history = payload.get('chatHistory', [])

    # If the message is completely empty and there is no file, return early
    if not message and not file_url:
        return jsonify({'success': False, 'message': 'Empty message'}), 400

    # Project ID is default 1 for the chatbot in Mini_RAG
    project_id = 1
    mini_rag_url = os.getenv("MINI_RAG_URL", "http://localhost:8000")
    
    # 1. Resolve local path if attachment is provided
    local_path = None
    if file_url:
        try:
            if file_url.startswith('/static/'):
                relative_path = file_url[8:]  # remove '/static/'
                local_path = os.path.join(get_static_root(), relative_path)
            elif file_url.startswith('static/'):
                relative_path = file_url[7:]
                local_path = os.path.join(get_static_root(), relative_path)
            else:
                local_path = file_url
        except Exception as e:
            print(f"Error mapping file url to local path: {e}")

    # Helper function to get Gemini Key dynamically
    def get_gemini_api_key():
        key = os.getenv("GEMINI_API_KEY")
        if key:
            return key
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rag_env = os.path.join(base_dir, 'Mini_RAG', 'src', '.env')
            if os.path.exists(rag_env):
                with open(rag_env, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('GEMINI_API_KEY='):
                            val = line.split('=', 1)[1].strip()
                            if val.startswith('"') and val.endswith('"'):
                                val = val[1:-1]
                            elif val.startswith("'") and val.endswith("'"):
                                val = val[1:-1]
                            if val:
                                return val
        except Exception:
            pass
        return "AIzaSyAC5TJFtOt9bY3G8bVE_8VbtR3iYKqK-mA"  # fallback default

    # Direct Gemini API Caller
    def call_gemini_direct(prompt_text, chat_hist, img_path=None, mtype=None):
        gemini_key = get_gemini_api_key()
        if not gemini_key or gemini_key.strip() == "" or gemini_key == "AIzaSyAC5TJFtOt9bY3G8bVE_8VbtR3iYKqK-mA":
            return """⚠️ **Gemini API Key Blocked/Missing:** The configured Gemini API key is either missing or has been blocked by Google as leaked.

To configure a new working key:
1. Go to **[Google AI Studio](https://aistudio.google.com/)** and create a new API key.
2. Open the **`front-end/.env`** file in your project and update the key:
   ```env
   GEMINI_API_KEY="your_new_api_key"
   ```
3. Open the **`Mini_RAG/src/.env`** file and update the key:
   ```env
   GEMINI_API_KEY="your_new_api_key"
   ```
4. Restart your Flask server."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        headers = {"Content-Type": "application/json"}
        
        contents = []
        # Parse history
        if chat_hist:
            for msg in chat_hist:
                sender = msg.get("sender")
                text = msg.get("text", "")
                if not text:
                    continue
                role = "user" if sender == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": text}]
                })
        
        # Add current message
        current_parts = []
        if img_path and mtype and os.path.exists(img_path):
            try:
                with open(img_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                current_parts.append({
                    "inlineData": {
                        "mimeType": mtype,
                        "data": encoded_string
                    }
                })
            except Exception as e:
                print(f"Error encoding image for Gemini: {e}")
                
        if prompt_text:
            current_parts.append({"text": prompt_text})
        elif not current_parts:
            current_parts.append({"text": ""})
            
        contents.append({
            "role": "user",
            "parts": current_parts
        })
        
        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": "You are the AI Assistant for the Student Portal. Answer student questions about courses, schedules, and academic topics. Be helpful, informative, and professional. Avoid saying you are in a demo, placeholder, or mock mode."}]
            }
        }
        
        rate_limit_exceeded = False
        max_retries = 3
        retry_delay = 2.5
        for attempt in range(max_retries):
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=20)
                if res.status_code == 200:
                    res_json = res.json()
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                elif res.status_code == 429:
                    rate_limit_exceeded = True
                    print(f"Direct Gemini API rate limit (429) hit, retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    print(f"Direct Gemini API error {res.status_code}: {res.text}")
                    if res.status_code == 403 or "leaked" in res.text or "API key" in res.text:
                        return """⚠️ **Gemini API Key Blocked:** Your Gemini API key has been flagged as **leaked** and has been deactivated by Google.

To restore AI Agent functionality, please follow these steps:
1. Go to **[Google AI Studio](https://aistudio.google.com/)** and create a new API key.
2. Open the **`front-end/.env`** file in your project and update the key:
   ```env
   GEMINI_API_KEY="your_new_api_key"
   ```
3. Open the **`Mini_RAG/src/.env`** file and update the key:
   ```env
   GEMINI_API_KEY="your_new_api_key"
   ```
4. Restart your Flask server."""
                    break
            except Exception as e:
                print(f"Direct Gemini API exception: {e}")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2

        if rate_limit_exceeded:
            return "⚠️ **AI service temporarily out of credits or rate-limited.** Please wait a moment and try again."
        
        return "⚠️ **AI service temporarily unavailable.** Please try again in a few moments."

    # Check if attachment is an image or PDF
    is_image = mime_type.startswith('image/') if mime_type else (file_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')) if file_url else False)
    is_pdf = (mime_type == 'application/pdf') if mime_type else (file_url.lower().endswith('.pdf') if file_url else False)
    is_direct_gemini = is_image or is_pdf

    # 2. If it's an image/photo or PDF, we process it using Gemini directly
    if is_direct_gemini:
        if not local_path or not os.path.exists(local_path):
            return jsonify({'success': False, 'message': 'The uploaded file could not be found. Please try uploading again.'}), 404
        
        mtype = 'application/pdf' if is_pdf else mime_type
        response_text = call_gemini_direct(message, chat_history, local_path, mtype)
        if response_text:
            return jsonify({'success': True, 'answer': response_text})
        else:
            return jsonify({'success': False, 'message': 'Failed to process attachment. The AI service may not support this file type, or the API key may be invalid.'}), 500

    # 3. Otherwise, try to call Mini_RAG service
    try:
        # A. If there is a document attachment, ingest it first via Mini_RAG
        if local_path and os.path.exists(local_path) and not is_image:
            # Upload file
            upload_url = f"{mini_rag_url}/api/v1/data/upload/{project_id}"
            filename = os.path.basename(local_path)
            with open(local_path, 'rb') as f:
                files = {'file': (filename, f, mime_type or 'application/octet-stream')}
                up_res = requests.post(upload_url, files=files, timeout=15)
            
            if up_res.status_code == 200:
                up_data = up_res.json()
                file_id = up_data.get("file_id")
                
                # Process file
                process_url = f"{mini_rag_url}/api/v1/data/process/{project_id}"
                proc_payload = {
                    "file_id": file_id,
                    "chunk_size": 1000,
                    "overlap_size": 200,
                    "do_reset": 0
                }
                proc_res = requests.post(process_url, json=proc_payload, timeout=20)
                
                if proc_res.status_code == 200:
                    # Push vector index
                    push_url = f"{mini_rag_url}/api/v1/nlp/index/push/{project_id}"
                    push_res = requests.post(push_url, json={"do_reset": 0}, timeout=60)
                    if push_res.status_code != 200:
                        print(f"Warning: Mini_RAG index push returned status {push_res.status_code}")
                else:
                    print(f"Warning: Mini_RAG file process returned status {proc_res.status_code}")
            else:
                print(f"Warning: Mini_RAG file upload returned status {up_res.status_code}")

        # B. Call RAG Answer endpoint
        answer_url = f"{mini_rag_url}/api/v1/nlp/index/answer/{project_id}"
        # Map chat history to Mini_RAG expectations
        mapped_history = []
        for msg in chat_history:
            sender = msg.get("sender")
            text = msg.get("text", "")
            if not text:
                continue
            mapped_history.append({
                "role": "user" if sender == "user" else "assistant",
                "text": text
            })

        rag_payload = {
            "text": message,
            "limit": 5,
            "chat_history": mapped_history
        }
        
        answer_res = requests.post(answer_url, json=rag_payload, timeout=20)
        if answer_res.status_code == 200:
            ans_data = answer_res.json()
            answer_text = ans_data.get("answer")
            if answer_text:
                return jsonify({'success': True, 'answer': answer_text})
        elif answer_res.status_code == 400:
            err_data = answer_res.json()
            err_msg = err_data.get("message") or "No relevant information found in the knowledge base for your question."
            return jsonify({'success': True, 'answer': f"⚠️ {err_msg}"})
            
    except requests.exceptions.RequestException as e:
        print(f"Mini_RAG service unreachable or failed. Falling back to direct Gemini: {e}")

    # 4. Fallback to direct Gemini
    print("Falling back to direct Gemini...")
    
    # If a document (PDF or TXT) was uploaded, extract its text content to pass to Gemini
    doc_context = ""
    if local_path and os.path.exists(local_path) and not is_image:
        try:
            fn = os.path.basename(local_path)
            if mime_type == 'application/pdf' or fn.endswith('.pdf'):
                # Extract PDF text
                try:
                    import fitz # PyMuPDF
                    doc = fitz.open(local_path)
                    pdf_text = ""
                    for page in doc:
                        pdf_text += page.get_text()
                    if pdf_text:
                        doc_context = f"\n\n[Content from uploaded document '{fn}']:\n{pdf_text}\n"
                except ImportError:
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(local_path)
                        pdf_text = ""
                        for page in reader.pages:
                            pdf_text += page.extract_text() or ""
                        if pdf_text:
                            doc_context = f"\n\n[Content from uploaded document '{fn}']:\n{pdf_text}\n"
                    except Exception as e:
                        print(f"Error reading PDF: {e}")
            elif mime_type.startswith('text/') or fn.endswith('.txt') or fn.endswith('.json') or fn.endswith('.csv'):
                with open(local_path, 'r', encoding='utf-8', errors='ignore') as f:
                    txt_content = f.read()
                if txt_content:
                    doc_context = f"\n\n[Content from uploaded file '{fn}']:\n{txt_content}\n"
        except Exception as e:
            print(f"Error extracting document text: {e}")

    final_message = message
    if doc_context:
        final_message = f"{doc_context}\n\nUser Question:\n{message}"

    fallback_text = call_gemini_direct(final_message, chat_history, local_path if is_direct_gemini else None, ('application/pdf' if is_pdf else mime_type) if is_direct_gemini else None)
    if fallback_text:
        return jsonify({'success': True, 'answer': fallback_text})
    
    # If all fails
    return jsonify({
        'success': False, 
        'message': 'Failed to generate response from both Mini_RAG and Gemini APIs.'
    }), 500


def is_user_enrolled(student_name: str, user_id: int = 0) -> bool:
    """Check if the student has successfully enrolled (exists in database.pkl)."""
    key_to_check = f"user_{user_id}" if user_id > 0 else student_name

    import pickle
    db_dir = os.getenv('SQLITE_DB_DIR')
    if db_dir:
        db_path = os.path.join(db_dir, 'database.pkl')
    else:
        db_path = os.path.join(_ATTENDANCE_ROOT, 'database', 'database.pkl')
    if os.path.exists(db_path):
        try:
            with open(db_path, 'rb') as f:
                db = pickle.load(f)
                return key_to_check in db
        except Exception as e:
            print(f"Error reading database.pkl: {e}. Trying backup...")
            backup = db_path + ".bak"
            if os.path.exists(backup):
                try:
                    with open(backup, 'rb') as f:
                        bdb = pickle.load(f)
                        return key_to_check in bdb
                except Exception:
                    pass
    return False


@app.route('/attendance')
@login_required
def attendance():
    """Smart Attendance enrollment page"""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')
    username = email.split('@')[0].capitalize() if email else 'User'
    student_name = username
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = to_clean_string(result[0])
                student_name = to_clean_string(result[0])
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching user name: {e}")
    
    enrolled = is_user_enrolled(student_name, user_id)
    courses = get_user_courses_data(user_id)
    weekly_data = get_weekly_attendance_stats(user_id)
    attendance_rate = calculate_overall_attendance_rate(courses)
    return render_template('attendance.html', username=username, email=email,
                           profile_photo=_get_profile_photo(user_id), enrolled=enrolled,
                           courses=courses, weekly_data=weekly_data, attendance_rate=attendance_rate)


def get_attendance_records(user_id: int) -> list[dict[str, Any]]:
    """
    Generate the complete attendance records list (both present and absent).
    """
    records = []
    
    try:
        connection = get_db_connection()
        if not connection:
            return []
        
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, course_name, start_time, end_time, days, created_at FROM user_course_schedule WHERE user_id = %s",
            (user_id,)
        )
        schedules = cursor.fetchall()
        
        cursor.execute(
            "SELECT id, course_id, attendance_date, status, created_at FROM attendance WHERE user_id = %s",
            (user_id,)
        )
        attendance_rows = cursor.fetchall()
        
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error fetching data for records: {e}")
        return []

    schedule_map = {}
    for sch in schedules:
        sch_id = sch[0]
        course_name = to_clean_string(sch[1])
        start_time_val = sch[2]
        end_time_val = sch[3]
        days_str = to_clean_string(sch[4])
        created_at_val = sch[5] if len(sch) > 5 else None
        
        weekdays = parse_days_to_weekdays(days_str)
        schedule_map[sch_id] = {
            'id': sch_id,
            'course_name': course_name,
            'start_time': start_time_val,
            'end_time': end_time_val,
            'weekdays': weekdays,
            'created_at': created_at_val
        }

    present_sessions = set()
    
    for row in attendance_rows:
        att_id = row[0]
        course_id = row[1]
        att_date = row[2]
        status = row[3]
        created_at = row[4] if len(row) > 4 else None
        
        dt_obj = None
        if created_at:
            if isinstance(created_at, datetime):
                dt_obj = created_at.replace(tzinfo=None)
            elif isinstance(created_at, str):
                try:
                    if ' ' in created_at:
                        dt_obj = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                    else:
                        dt_obj = datetime.strptime(created_at, "%Y-%m-%d")
                except ValueError:
                    pass
                    
        if not dt_obj:
            if not att_date:
                continue
            if isinstance(att_date, datetime):
                dt_obj = att_date.replace(tzinfo=None)
            elif isinstance(att_date, date):
                dt_obj = datetime.combine(att_date, time.min)
            elif isinstance(att_date, str):
                try:
                    if ' ' in att_date:
                        dt_obj = datetime.strptime(att_date, "%Y-%m-%d %H:%M:%S")
                    else:
                        dt_obj = datetime.strptime(att_date, "%Y-%m-%d")
                except ValueError:
                    continue
            else:
                continue
            
        if dt_obj:
            dt_obj = dt_obj + timedelta(hours=1)
        dt_date = dt_obj.date()
        
        matched_course_name = "General Class"
        if course_id in schedule_map:
            matched_course_name = schedule_map[course_id]['course_name']
            present_sessions.add((course_id, dt_date.strftime("%Y-%m-%d")))
        else:
            matched_sched_id = None
            for sch_id, sch in schedule_map.items():
                if dt_date.weekday() in sch['weekdays']:
                    def to_time_obj(t_val):
                        if isinstance(t_val, str):
                            try:
                                parts = t_val.split(':')
                                if len(parts) >= 2:
                                    return time(int(parts[0]), int(parts[1]))
                            except ValueError:
                                pass
                        elif isinstance(t_val, time):
                            return t_val
                        elif hasattr(t_val, 'hour'):
                            return time(t_val.hour, t_val.minute)
                        return None
                    
                    st = to_time_obj(sch['start_time'])
                    et = to_time_obj(sch['end_time'])
                    if st and et and st <= dt_obj.time() <= et:
                        matched_sched_id = sch_id
                        matched_course_name = sch['course_name']
                        break
            
            if matched_sched_id:
                present_sessions.add((matched_sched_id, dt_date.strftime("%Y-%m-%d")))
            
        records.append({
            'course_name': matched_course_name,
            'status': 'Present',
            'day': dt_obj.strftime("%A"),
            'date': dt_date,
            'time': dt_obj.strftime("%I:%M %p"),
            'sort_key': dt_obj
        })

    local_now = get_local_now()
    today_date = local_now.date()
    
    def to_time_obj_helper(t_val):
        if isinstance(t_val, str):
            try:
                parts = t_val.split(':')
                if len(parts) >= 2:
                    return time(int(parts[0]), int(parts[1]))
            except ValueError:
                pass
        elif isinstance(t_val, time):
            return t_val
        elif hasattr(t_val, 'hour'):
            return time(t_val.hour, t_val.minute)
        return None

    def parse_created_at_to_date(val) -> date:
        if not val:
            return SEMESTER_START
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        val_str = str(val).strip()
        try:
            if ' ' in val_str:
                dt_part = val_str.split(' ')[0]
                return datetime.strptime(dt_part, "%Y-%m-%d").date()
            return datetime.strptime(val_str, "%Y-%m-%d").date()
        except Exception:
            return SEMESTER_START

    for sch_id, sch in schedule_map.items():
        created_date = parse_created_at_to_date(sch.get('created_at'))
        start_checking_d = max(SEMESTER_START, created_date)
        
        current_d = start_checking_d
        while current_d <= today_date:
            wd = current_d.weekday()
            current_day_str = current_d.strftime("%Y-%m-%d")
            
            if wd in sch['weekdays']:
                end_t = to_time_obj_helper(sch['end_time'])
                start_t = to_time_obj_helper(sch['start_time'])
                if end_t and start_t:
                    session_ended = False
                    if current_d < today_date:
                        session_ended = True
                    elif current_d == today_date:
                        if end_t <= local_now.time():
                            session_ended = True
                    
                    if session_ended:
                        if (sch_id, current_day_str) not in present_sessions:
                            session_start_dt = datetime.combine(current_d, start_t)
                            records.append({
                                'course_name': sch['course_name'],
                                'status': 'Not Present',
                                'day': current_d.strftime("%A"),
                                'date': current_d,
                                'time': '—',
                                'sort_key': session_start_dt
                            })
            current_d += timedelta(days=1)

    records.sort(key=lambda x: x['sort_key'], reverse=True)
    return records


@app.route('/records')
@login_required
def records():
    """Attendance records log page"""
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
                username = to_clean_string(result[0])
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching user name: {e}")
    
    attendance_records = get_attendance_records(user_id)
    
    return render_template('records.html', username=username, email=email,
                           profile_photo=_get_profile_photo(user_id),
                           records=attendance_records)


@app.route('/api/attendance/enroll', methods=['POST'])
@login_required
def attendance_enroll():
    """Accept 5 browser captures, save to disk, run YOLO+ArcFace in one subprocess."""
    payload = request.get_json(silent=True) or {}
    captures = payload.get('captures', [])

    if not isinstance(captures, list) or len(captures) != 5:
        return jsonify({'success': False, 'message': 'Please capture all 5 positions.'}), 400

    user_id = to_int_value(session.get('user_id'))
    # Enroll the user under their unique database ID key to prevent name collisions
    student_name = f"user_{user_id}"

    # Save captured images to disk
    static_root = get_static_root()
    upload_dir = os.path.join(static_root, 'uploads', 'attendance', f'user_{user_id}')
    os.makedirs(upload_dir, exist_ok=True)

    # Clear any previous captures for this user to avoid accumulating old files
    if os.path.exists(upload_dir):
        for item in os.listdir(upload_dir):
            item_path = os.path.join(upload_dir, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
            except Exception as e:
                print(f"Error deleting file {item_path}: {e}")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    saved_paths: list[str] = []

    for idx, entry in enumerate(captures, 1):
        if not isinstance(entry, dict):
            return jsonify({'success': False, 'message': 'Invalid capture format.'}), 400
        data_url = to_clean_string(entry.get('dataUrl'))
        if not data_url.startswith('data:image/') or ',' not in data_url:
            return jsonify({'success': False, 'message': 'Invalid image data.'}), 400
        _, encoded = data_url.split(',', 1)
        try:
            img_bytes = base64.b64decode(encoded)
        except (ValueError, binascii.Error):
            return jsonify({'success': False, 'message': 'Could not decode image.'}), 400
        fpath = os.path.join(upload_dir, f'{timestamp}_{idx}.jpg')
        with open(fpath, 'wb') as fh:
            fh.write(img_bytes)
        saved_paths.append(fpath)

    try:
        # Try direct in-process call first to avoid process startup lag and speed up responses to <200ms
        try:
            if web_enroll is not None:
                result = web_enroll.process_images(student_name, saved_paths)
                return jsonify(result), 200
            else:
                raise ImportError("web_enroll is not loaded")
        except Exception as direct_err:
            print(f"Direct web_enroll.process_images failed, falling back to subprocess: {direct_err}")
            script_path = os.path.join(_ATTENDANCE_ROOT, 'web_enroll.py')
            venv_python = os.path.join(_ATTENDANCE_ROOT, 'venv', 'Scripts', 'python.exe')
            if not os.path.exists(venv_python):
                venv_python = sys.executable

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            proc = subprocess.run(
                [venv_python, script_path, student_name] + saved_paths,
                cwd=_ATTENDANCE_ROOT,
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                env=env, timeout=120,
            )
            for line in (proc.stdout or '').splitlines():
                if line.startswith('__RESULT_JSON__'):
                    try:
                        return jsonify(json.loads(line[len('__RESULT_JSON__'):])), 200
                    except json.JSONDecodeError:
                        pass
            error_detail = (proc.stderr or proc.stdout or 'Unknown error').strip()[-500:]
            return jsonify({'success': False, 'message': f'Enrollment error: {error_detail}'}), 200
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Enrollment timed out. Please try again.'}), 504
    except Exception as err:
        print(f"Attendance enrollment error: {err}")
        return jsonify({'success': False, 'message': f'Enrollment failed: {err}'}), 200


@app.route('/api/attendance/test-recognize', methods=['POST'])
@login_required
def attendance_test_recognize():
    """Accept a single image and run recognition against the enrolled database."""
    payload = request.get_json(silent=True) or {}
    data_url = payload.get('image', '')

    if not data_url or not data_url.startswith('data:image/') or ',' not in data_url:
        return jsonify({'success': False, 'message': 'Invalid image data.'}), 400

    _, encoded = data_url.split(',', 1)
    try:
        img_bytes = base64.b64decode(encoded)
    except (ValueError, binascii.Error):
        return jsonify({'success': False, 'message': 'Could not decode image.'}), 400

    # Save to temp file
    static_root = get_static_root()
    test_dir = os.path.join(static_root, 'uploads', 'attendance', 'test')
    os.makedirs(test_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fpath = os.path.join(test_dir, f'test_{timestamp}.jpg')
    with open(fpath, 'wb') as fh:
        fh.write(img_bytes)

    try:
        # Try direct in-process call first to avoid process startup lag and speed up responses to <200ms
        try:
            if web_recognize is not None:
                res_data = web_recognize.recognize(fpath)
                if isinstance(res_data, dict) and res_data.get('success'):
                    connection = get_db_connection()
                    if connection:
                        try:
                            cursor = connection.cursor()
                            for face in res_data.get('faces', []):
                                name_key = face.get('name')
                                if name_key and name_key.startswith('user_'):
                                    try:
                                        uid = int(name_key.split('_')[1])
                                        cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (uid,))
                                        row = cursor.fetchone()
                                        if row and row[0]:
                                            face['name'] = to_clean_string(row[0])
                                    except (IndexError, ValueError):
                                        pass
                            cursor.close()
                        except Exception as e:
                            print(f"Error fetching recognized user name: {e}")
                        finally:
                            connection.close()
                return jsonify(res_data)
            else:
                raise ImportError("web_recognize is not loaded")
        except Exception as direct_err:
            print(f"Direct web_recognize.recognize failed, falling back to subprocess: {direct_err}")
            script_path = os.path.join(_ATTENDANCE_ROOT, 'web_recognize.py')
            venv_python = os.path.join(_ATTENDANCE_ROOT, 'venv', 'Scripts', 'python.exe')
            if not os.path.exists(venv_python):
                venv_python = sys.executable

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            proc = subprocess.run(
                [venv_python, script_path, fpath],
                cwd=_ATTENDANCE_ROOT,
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                env=env, timeout=60,
            )
            for line in (proc.stdout or '').splitlines():
                if line.startswith('__RESULT_JSON__'):
                    try:
                        res_data = json.loads(line[len('__RESULT_JSON__'):])
                        if isinstance(res_data, dict) and res_data.get('success'):
                            connection = get_db_connection()
                            if connection:
                                try:
                                    cursor = connection.cursor()
                                    for face in res_data.get('faces', []):
                                        name_key = face.get('name')
                                        if name_key and name_key.startswith('user_'):
                                            try:
                                                uid = int(name_key.split('_')[1])
                                                cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (uid,))
                                                row = cursor.fetchone()
                                                if row and row[0]:
                                                    face['name'] = to_clean_string(row[0])
                                            except (IndexError, ValueError):
                                                pass
                                    cursor.close()
                                except Exception as e:
                                    print(f"Error fetching recognized user name: {e}")
                                finally:
                                    connection.close()
                        return jsonify(res_data)
                    except json.JSONDecodeError:
                        pass
            error_detail = (proc.stderr or proc.stdout or 'Unknown error').strip()[-500:]
            return jsonify({'success': False, 'message': f'Recognition error: {error_detail}'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Recognition timed out.'}), 504
    except Exception as err:
        return jsonify({'success': False, 'message': f'Error: {err}'}), 500



@app.route('/api/attendance/stats', methods=['GET'])
def get_attendance_stats_api():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    user_id = to_int_value(user_id)
    courses = get_user_courses_data(user_id)
    weekly_data = get_weekly_attendance_stats(user_id)
    attendance_rate = calculate_overall_attendance_rate(courses)
    
    return jsonify({
        'success': True,
        'courses': courses,
        'weekly_data': weekly_data,
        'attendance_rate': attendance_rate
    })


@app.route('/api/notifications', methods=['GET'])
def get_notifications_api():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    user_id = to_int_value(user_id)
    notifications = []
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT a.attendance_date, c.course_name, a.created_at 
                FROM attendance a
                LEFT JOIN user_course_schedule c ON a.course_id = c.id
                WHERE a.user_id = %s
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT 3
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            
            for row in rows:
                att_date = row[0]
                course_name = to_clean_string(row[1]) if row[1] else "General Class"
                created_at = row[2] if len(row) > 2 else None
                
                dt_obj = None
                if created_at:
                    if isinstance(created_at, datetime):
                        dt_obj = created_at.replace(tzinfo=None)
                    elif isinstance(created_at, str):
                        try:
                            if ' ' in created_at:
                                dt_obj = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                            else:
                                dt_obj = datetime.strptime(created_at, "%Y-%m-%d")
                        except ValueError:
                            pass
                
                if not dt_obj:
                    if isinstance(att_date, datetime):
                        dt_obj = att_date.replace(tzinfo=None)
                    elif isinstance(att_date, str):
                        try:
                            if ' ' in att_date:
                                dt_obj = datetime.strptime(att_date, "%Y-%m-%d %H:%M:%S")
                            else:
                                dt_obj = datetime.strptime(att_date, "%Y-%m-%d")
                        except ValueError:
                            pass

                if dt_obj:
                    dt_obj = dt_obj + timedelta(hours=1)
                    time_str = dt_obj.strftime('%I:%M %p')
                    date_str = dt_obj.strftime('%Y-%m-%d')
                else:
                    if isinstance(att_date, date):
                        time_str = "—"
                        date_str = att_date.strftime('%Y-%m-%d')
                    else:
                        time_str = "Recent"
                        date_str = "Today"
                
                notifications.append({
                    'title': 'Attendance Marked',
                    'message': f'Marked present in {course_name}.',
                    'time': f'{date_str} at {time_str}'
                  })
    except Exception as e:
        print(f"Error fetching notifications: {e}")
    
    return jsonify({
        'success': True,
        'notifications': notifications
    })



@app.route('/stream/frame', methods=['POST'])
def receive_stream_frame():
    """Receive raw JPEG bytes from ESP32-CAM or simulator, perform face recognition, and mark present."""
    img_bytes = request.data
    if not img_bytes:
        if 'file' in request.files:
            img_bytes = request.files['file'].read()
        else:
            return jsonify({'success': False, 'message': 'No image data received.'}), 400

    static_root = get_static_root()
    test_dir = os.path.join(static_root, 'uploads', 'attendance', 'test')
    os.makedirs(test_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    fpath = os.path.join(test_dir, f'esp32_{timestamp}.jpg')
    with open(fpath, 'wb') as fh:
        fh.write(img_bytes)

    res_data = None
    try:
        if web_recognize is not None:
            res_data = web_recognize.recognize(fpath)
        else:
            raise ImportError("web_recognize is not loaded")
    except Exception as direct_err:
        print(f"Direct web_recognize failed in stream/frame, trying subprocess: {direct_err}")
        script_path = os.path.join(_ATTENDANCE_ROOT, 'web_recognize.py')
        venv_python = os.path.join(_ATTENDANCE_ROOT, 'venv', 'Scripts', 'python.exe')
        if not os.path.exists(venv_python):
            venv_python = sys.executable

        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            proc = subprocess.run(
                [venv_python, script_path, fpath],
                cwd=_ATTENDANCE_ROOT,
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                env=env, timeout=60,
            )
            for line in (proc.stdout or '').splitlines():
                if line.startswith('__RESULT_JSON__'):
                    try:
                        res_data = json.loads(line[len('__RESULT_JSON__'):])
                        break
                    except json.JSONDecodeError:
                        pass
        except Exception as sub_err:
            print(f"Subprocess recognition failed: {sub_err}")

    try:
        if os.path.exists(fpath):
            os.remove(fpath)
    except Exception:
        pass

    if not res_data or not res_data.get('success'):
        err_msg = res_data.get('message', 'Recognition failed') if res_data else 'No recognition result output'
        return jsonify({'success': False, 'message': err_msg}), 200

    faces = res_data.get('faces', [])
    recognized_names = []
    for face in faces:
        name = face.get('name')
        if name and name != "Unknown":
            recognized_names.append(name)

    if recognized_names:
        connection = get_db_connection()
        if connection is not None:
            cursor = connection.cursor()
            today = get_local_now().strftime("%Y-%m-%d")
            test_user_override = to_int_value(request.args.get('test_user_id'))
            course_id = to_int_value(request.args.get('course_id')) or None
            logged_count = 0
            recognized_students = []

            for key in recognized_names:
                user_id = None
                if test_user_override:
                    user_id = test_user_override
                elif key.startswith("user_"):
                    try:
                        user_id = int(key.split("_")[1])
                    except (IndexError, ValueError):
                        continue
                else:
                    try:
                        user_id = int(key)
                    except ValueError:
                        continue

                if user_id is None:
                    continue

                cursor.execute("SELECT email FROM users WHERE id = %s LIMIT 1", (user_id,))
                user_row = cursor.fetchone()
                if user_row is None:
                    continue
                user_email = user_row[0]

                cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s LIMIT 1", (user_id,))
                info_row = cursor.fetchone()
                user_name = to_clean_string(info_row[0]) if info_row and info_row[0] else "N/A"

                recognized_students.append({
                    "id": user_id,
                    "name": user_name,
                    "email": user_email
                })

                active_course_id = course_id or get_current_active_course_id(user_id)

                if active_course_id:
                    cursor.execute(
                        "SELECT 1 FROM attendance WHERE user_id = %s AND course_id = %s AND date(attendance_date) = %s LIMIT 1",
                        (user_id, active_course_id, today)
                    )
                else:
                    cursor.execute(
                        "SELECT 1 FROM attendance WHERE user_id = %s AND course_id IS NULL AND date(attendance_date) = %s LIMIT 1",
                        (user_id, today)
                    )

                if cursor.fetchone() is None:
                    today_datetime = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        "INSERT INTO attendance (user_id, course_id, attendance_date, status, created_at) VALUES (%s, %s, %s, TRUE, %s)",
                        (user_id, active_course_id, today_datetime, today_datetime)
                    )
                    logged_count += 1

            connection.commit()
            cursor.close()
            connection.close()

            if recognized_students:
                # Use the resolved active course ID for reporting
                first_course_id = course_id or (recognized_students[0].get('id') and get_current_active_course_id(recognized_students[0]['id']))
                import threading
                threading.Thread(
                    target=send_session_report_email,
                    args=(recognized_students, first_course_id),
                    daemon=True
                ).start()

            return jsonify({
                'success': True,
                'recognized': [s['name'] for s in recognized_students],
                'marked_present_count': logged_count,
                'message': f'Processed {len(recognized_students)} student(s). Marked {logged_count} new attendance. Session report sent.'
            }), 200

    return jsonify({
        'success': True,
        'recognized': [],
        'message': 'No known students recognized in frame.'
    }), 200


@app.route('/api/attendance/session', methods=['POST'])
def receive_session_attendance():
    """Receive student IDs from the AI stream server and mark them as present."""
    data = request.get_json() or {}
    student_keys = data.get('student_ids', [])
    course_id = to_int_value(data.get('course_id')) or None

    if not isinstance(student_keys, list):
        return jsonify({'success': False, 'message': 'Invalid data format'}), 400

    try:
        connection = get_db_connection()
        if connection is None:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = connection.cursor()
        today = get_local_now().strftime("%Y-%m-%d")

        logged_count = 0
        recognized_students = []
        for key in student_keys:
            # Parse user_id
            user_id = None
            if isinstance(key, int):
                user_id = key
            elif isinstance(key, str):
                if key.startswith("user_"):
                    try:
                        user_id = int(key.split("_")[1])
                    except (IndexError, ValueError):
                        continue
                else:
                    try:
                        user_id = int(key)
                    except ValueError:
                        continue

            if user_id is None:
                continue

            # Verify user exists in SQLite and get their email
            cursor.execute("SELECT email FROM users WHERE id = %s LIMIT 1", (user_id,))
            user_row = cursor.fetchone()
            if user_row is None:
                continue
            user_email = user_row[0]

            # Fetch first name or full name from user_additional_info
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s LIMIT 1", (user_id,))
            info_row = cursor.fetchone()
            user_name = to_clean_string(info_row[0]) if info_row and info_row[0] else "N/A"

            recognized_students.append({
                "id": user_id,
                "name": user_name,
                "email": user_email
            })

            # Check if already present today for this course to prevent duplicates
            today = get_local_now().strftime("%Y-%m-%d")
            if course_id:
                cursor.execute(
                    "SELECT 1 FROM attendance WHERE user_id = %s AND course_id = %s AND date(attendance_date) = %s LIMIT 1",
                    (user_id, course_id, today)
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM attendance WHERE user_id = %s AND course_id IS NULL AND date(attendance_date) = %s LIMIT 1",
                    (user_id, today)
                )

            if cursor.fetchone() is None:
                today_datetime = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO attendance (user_id, course_id, attendance_date, status, created_at) VALUES (%s, %s, %s, TRUE, %s)",
                    (user_id, course_id, today_datetime, today_datetime)
                )
                logged_count += 1

        connection.commit()
        cursor.close()
        connection.close()

        # Send report email in the background to avoid blocking API response
        if recognized_students:
            import threading
            threading.Thread(
                target=send_session_report_email,
                args=(recognized_students, course_id),
                daemon=True
            ).start()

        return jsonify({'success': True, 'message': f'Logged {logged_count} students successfully'}), 200

    except Exception as e:
        print(f"Error logging session attendance: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ================== TASKS ROUTE ==================

@app.route('/tasks')
@login_required
def tasks():
    """Tasks management page"""
    user_id = to_int_value(session.get('user_id'))
    email = session.get('email', '')
    username = email.split('@')[0].capitalize() if email else 'User'

    # Fetch real first name
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT first_name FROM user_additional_info WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                username = to_clean_string(result[0])
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching user name for tasks: {e}")

    profile_photo = _get_profile_photo(user_id)

    # Fetch user tasks grouped by date
    tasks_by_date = {}
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, task_text, is_completed, task_date, created_at FROM user_tasks WHERE user_id = %s ORDER BY task_date DESC, created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            for r in rows:
                tid, text, completed, tdate, created = r
                if not tdate:
                    if created:
                        try:
                            tdate = str(created).split(' ')[0]
                        except Exception:
                            tdate = datetime.now().strftime('%Y-%m-%d')
                    else:
                        tdate = datetime.now().strftime('%Y-%m-%d')
                
                if tdate not in tasks_by_date:
                    tasks_by_date[tdate] = []
                
                tasks_by_date[tdate].append({
                    'id': tid,
                    'text': text,
                    'completed': bool(completed)
                })
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error fetching tasks: {e}")

    # Ensure we always have today's card available
    today_str = datetime.now().strftime('%Y-%m-%d')
    if today_str not in tasks_by_date:
        tasks_by_date[today_str] = []

    cards = []
    # Sort dates descending
    for d_str in sorted(tasks_by_date.keys(), reverse=True):
        tasks = tasks_by_date[d_str]
        try:
            dt = datetime.strptime(d_str, '%Y-%m-%d')
            day_name = dt.strftime('%A')
            day_abbr = dt.strftime('%a')
            day_num = dt.strftime('%d')
            month_year = dt.strftime('%B %Y')
            formatted_date = dt.strftime('%B %d, %Y')
        except Exception:
            day_name = "Date"
            day_abbr = "Date"
            day_num = d_str
            month_year = ""
            formatted_date = d_str
            
        completed_count = sum(1 for t in tasks if t['completed'])
        total_count = len(tasks)
        progress_percent = round((completed_count / total_count) * 100) if total_count > 0 else 0
        
        cards.append({
            'date_str': d_str,
            'day_name': day_name,
            'day_abbr': day_abbr,
            'day_num': day_num,
            'month_year': month_year,
            'formatted_date': formatted_date,
            'tasks': tasks,
            'completed_count': completed_count,
            'total_count': total_count,
            'progress_percent': progress_percent
        })

    return render_template(
        'tasks.html',
        cards=cards,
        username=username,
        email=email,
        profile_photo=profile_photo
    )

@app.route('/tasks/add', methods=['POST'])
@login_required
def add_task():
    """Add a new task"""
    try:
        user_id = session.get('user_id')
        data = request.get_json() or {}
        task_text = to_clean_string(data.get('task_text', ''))
        task_date = to_clean_string(data.get('task_date', ''))
        
        if not task_date:
            task_date = datetime.now().strftime('%Y-%m-%d')
            
        if not task_text:
            return jsonify({'success': False, 'message': 'Task content cannot be empty'}), 400
            
        connection = get_db_connection()
        if connection is None:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
            
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO user_tasks (user_id, task_text, is_completed, task_date) VALUES (%s, %s, FALSE, %s)",
            (user_id, task_text, task_date)
        )
        task_id = cursor.lastrowid
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'task': {
                'id': task_id,
                'text': task_text,
                'completed': False,
                'date': task_date
            }
        }), 201
    except Exception as e:
        print(f"Error adding task: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/tasks/delete_day', methods=['POST'])
@login_required
def delete_day():
    """Delete all tasks for a specific date"""
    try:
        user_id = session.get('user_id')
        data = request.get_json() or {}
        task_date = to_clean_string(data.get('task_date', ''))
        
        if not task_date:
            return jsonify({'success': False, 'message': 'Date is required'}), 400
            
        connection = get_db_connection()
        if connection is None:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
            
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM user_tasks WHERE user_id = %s AND task_date = %s",
            (user_id, task_date)
        )
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting tasks for date: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/tasks/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    """Toggle a task's completion status"""
    try:
        user_id = session.get('user_id')
        
        connection = get_db_connection()
        if connection is None:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
            
        cursor = connection.cursor()
        
        # Verify the task belongs to the user
        cursor.execute("SELECT is_completed FROM user_tasks WHERE id = %s AND user_id = %s", (task_id, user_id))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Task not found'}), 404
            
        new_status = not bool(row[0])
        cursor.execute(
            "UPDATE user_tasks SET is_completed = %s WHERE id = %s AND user_id = %s",
            (new_status, task_id, user_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'completed': new_status
        })
    except Exception as e:
        print(f"Error toggling task: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    """Delete a task"""
    try:
        user_id = session.get('user_id')
        
        connection = get_db_connection()
        if connection is None:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
            
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM user_tasks WHERE id = %s AND user_id = %s",
            (task_id, user_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting task: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ================== ERROR HANDLERS ==================

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Page not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000, use_reloader=False)
