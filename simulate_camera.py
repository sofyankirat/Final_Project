import os
import requests
import sqlite3

# URL of your local or live server
DEFAULT_URL = 'http://localhost:5000/stream/frame'

# Path to your face photo (put your photo here)
IMAGE_PATH = 'my_face.jpg'

def get_db_connection():
    """Get database connection (Supabase or SQLite fallback)"""
    import os
    import sqlite3
    
    supabase_url = os.getenv('SUPABASE_URL')
    supa_pass = os.getenv('SUPA_PASS')
    
    if supabase_url and supa_pass:
        try:
            import psycopg2
            cleaned = supabase_url.replace("https://", "").replace("http://", "")
            ref_id = cleaned.split('.')[0]
            host = "aws-0-eu-west-1.pooler.supabase.com"
            conn = psycopg2.connect(
                host=host,
                database="postgres",
                user=f"postgres.{ref_id}",
                password=supa_pass,
                port="5432",
                connect_timeout=5
            )
            return conn
        except Exception:
            pass

    # SQLite fallback
    db_paths = [
        os.path.join('front-end', 'student_system.db'),
        'student_system.db'
    ]
    for db_path in db_paths:
        if os.path.exists(db_path):
            try:
                return sqlite3.connect(db_path)
            except Exception:
                pass
    return None

def get_registered_users():
    """Fetch users from database (Supabase or SQLite fallback)."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email FROM users ORDER BY id ASC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception:
        return []

def get_user_courses(user_id):
    """Fetch course schedules for a user from database."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        # Handle SQLite (?) vs Postgres (%s) placeholder format
        is_postgres = not hasattr(conn, 'execute') or "psycopg2" in str(type(conn))
        placeholder = "%s" if is_postgres else "?"
        cursor.execute(f"SELECT id, course_name, days, start_time, end_time FROM user_course_schedule WHERE user_id = {placeholder} ORDER BY course_name", (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception:
        return []

def get_matching_datetime(days_str, start_time_str):
    """
    Finds a recent or current-week datetime matching the schedule.
    - days_str: e.g. 'Monday, Wednesday'
    - start_time_str: e.g. '10:00:00' or '10:00'
    """
    import datetime as dt
    
    # Map weekdays
    weekday_map = {
        'monday': 0, 'mon': 0,
        'tuesday': 1, 'tue': 1,
        'wednesday': 2, 'wed': 2,
        'thursday': 3, 'thu': 3,
        'friday': 4, 'fri': 4,
        'saturday': 5, 'sat': 5,
        'sunday': 6, 'sun': 6
    }
    
    weekdays = []
    cleaned = str(days_str).lower()
    for name, idx in weekday_map.items():
        if name in cleaned:
            if idx not in weekdays:
                weekdays.append(idx)
    
    if not weekdays:
        weekdays = [0] # default to Monday if not parsed
        
    # Find a date in the current week (or last few days) that matches one of the weekdays
    now = dt.datetime.now()
    target_date = now.date()
    
    # Check the last 7 days starting from today to find a matching weekday
    for i in range(7):
        candidate = now - dt.timedelta(days=i)
        if candidate.weekday() in weekdays:
            target_date = candidate.date()
            break
            
    # Parse start time and add 15 minutes to be safely inside the course range
    time_parts = str(start_time_str).split(':')
    try:
        h = int(time_parts[0])
        m = int(time_parts[1])
    except (IndexError, ValueError):
        h, m = 10, 0
        
    # Add 15 minutes
    m = (m + 15)
    if m >= 60:
        h = (h + 1) % 24
        m = m - 60
        
    simulated_time = dt.time(h, m)
    simulated_dt = dt.datetime.combine(target_date, simulated_time)
    return simulated_dt.strftime("%Y-%m-%d %H:%M:%S")

def send_frame(request_url, image_path):
    print(f"Sending '{image_path}' to {request_url}...")
    try:
        with open(image_path, 'rb') as fh:
            files = {'file': fh}
            try:
                response = requests.post(request_url, files=files)
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as ssl_err:
                print(f"  SSL/Connection issue ({ssl_err}), retrying with verify=False...")
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                try:
                    response = requests.post(request_url, files=files, verify=False, timeout=15)
                except Exception as fallback_err:
                    if request_url.startswith("https://"):
                        http_url = request_url.replace("https://", "http://")
                        print(f"  Retrying over HTTP: {http_url}")
                        response = requests.post(http_url, files=files, timeout=15)
                    else:
                        raise fallback_err
            
        if response.status_code == 200:
            result = response.json()
            print("  Server Response:")
            print(f"    Success: {result.get('success')}")
            print(f"    Recognized Students: {result.get('recognized')}")
            print(f"    Marked Present: {result.get('marked_present_count')} new record(s)")
            print(f"    Message: {result.get('message')}")
        else:
            print(f"  Server returned error status code: {response.status_code}")
            print(f"  {response.text}")
            
    except Exception as e:
        print(f"  Connection error: {e}")

def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Could not find '{IMAGE_PATH}' in the project folder.")
        print("Please copy a photo of your face to this directory and rename it to 'my_face.jpg'.")
        return

    # Try to load environment variables from dotenv if available
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join('front-end', '.env'))
        load_dotenv('.env')
    except Exception:
        pass

    url = "https://finalproject-production-aa41.up.railway.app/stream/frame"
    print("\n--- Smart Attendance Simulator ---")
    print(f"Target Server URL: {url}")

    users = get_registered_users()
    test_user_id = None

    if users:
        print("\nSelect which registered user to simulate attendance for:")
        for idx, (uid, email) in enumerate(users):
            print(f"[{idx + 1}] {email} (ID: {uid})")
        print(f"[{len(users) + 1}] Do not override (use face recognition name directly)")
        
        try:
            choice = input(f"\nEnter choice [1-{len(users) + 1}] (default: 1): ").strip()
            if not choice:
                choice = "1"
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(users):
                test_user_id = users[choice_idx][0]
                print(f"Simulating attendance for: {users[choice_idx][1]} (ID: {test_user_id})")
            else:
                print("Using standard face recognition name matching.")
        except Exception:
            print("Using standard face recognition name matching.")
    else:
        print("\nNote: Local database not found or empty. Using standard face recognition matching.")

    # Construct and send request(s) automatically
    if test_user_id:
        courses = get_user_courses(test_user_id)
        if courses:
            print(f"\nFound {len(courses)} course schedule(s) for user ID {test_user_id}.")
            print("Automatically simulating attendance for each schedule...")
            for idx, item in enumerate(courses):
                cid = item[0]
                course_name = item[1]
                days = item[2] if len(item) > 2 else "Monday"
                start_time = item[3] if len(item) > 3 else "10:00:00"
                end_time = item[4] if len(item) > 4 else "11:30:00"
                
                custom_time = get_matching_datetime(days, start_time)
                print(f"\n[{idx + 1}/{len(courses)}] Course: {course_name} (Schedule: {days} {start_time}-{end_time})")
                print(f"  Simulating active time inside schedule range: {custom_time}")
                
                params = [f"test_user_id={test_user_id}", f"custom_time={custom_time}"]
                request_url = f"{url}?{'&'.join(params)}"
                send_frame(request_url, IMAGE_PATH)
        else:
            print(f"\nNo course schedules found for user ID {test_user_id}. Simulating general class attendance.")
            request_url = f"{url}?test_user_id={test_user_id}"
            send_frame(request_url, IMAGE_PATH)
    else:
        print("\nUsing standard face recognition name matching (no user override).")
        send_frame(url, IMAGE_PATH)

if __name__ == '__main__':
    main()
