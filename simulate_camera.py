import os
import requests
import sqlite3

# URL of your local or live server
DEFAULT_URL = 'http://localhost:5000/stream/frame'

# Path to your face photo (put your photo here)
IMAGE_PATH = 'my_face.jpg'

def get_registered_users():
    """Fetch users from local SQLite database if available."""
    db_paths = [
        os.path.join('front-end', 'student_system.db'),
        'student_system.db'
    ]
    for db_path in db_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id, email FROM users ORDER BY id ASC")
                rows = cursor.fetchall()
                conn.close()
                return rows
            except Exception:
                pass
    return []

def get_user_courses(user_id):
    """Fetch course schedules for a user from local SQLite database."""
    db_paths = [
        os.path.join('front-end', 'student_system.db'),
        'student_system.db'
    ]
    for db_path in db_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id, course_name FROM user_course_schedule WHERE user_id = ? ORDER BY course_name", (user_id,))
                rows = cursor.fetchall()
                conn.close()
                return rows
            except Exception:
                pass
    return []

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

    # Construct request URL and select course if student is selected
    test_course_id = None
    if test_user_id:
        courses = get_user_courses(test_user_id)
        if courses:
            print("\nSelect which course schedule to mark attendance for:")
            for idx, (cid, course_name) in enumerate(courses):
                print(f"[{idx + 1}] {course_name} (ID: {cid})")
            print(f"[{len(courses) + 1}] General/No specific course")
            
            try:
                choice = input(f"\nEnter choice [1-{len(courses) + 1}] (default: {len(courses) + 1}): ").strip()
                if choice:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(courses):
                        test_course_id = courses[choice_idx][0]
                        print(f"Marking attendance for course: {courses[choice_idx][1]} (ID: {test_course_id})")
                    else:
                        print("Using general class attendance.")
                else:
                    print("Using general class attendance.")
            except Exception:
                print("Using general class attendance.")

    params = []
    if test_user_id:
        params.append(f"test_user_id={test_user_id}")
    if test_course_id:
        params.append(f"course_id={test_course_id}")

    request_url = url
    if params:
        request_url = f"{url}?{'&'.join(params)}"

    print(f"\nSending '{IMAGE_PATH}' to {request_url}...")
    try:
        with open(IMAGE_PATH, 'rb') as fh:
            files = {'file': fh}
            try:
                response = requests.post(request_url, files=files)
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as ssl_err:
                print(f"SSL/Connection issue ({ssl_err}), retrying with verify=False...")
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                try:
                    response = requests.post(request_url, files=files, verify=False, timeout=15)
                except Exception as fallback_err:
                    if request_url.startswith("https://"):
                        http_url = request_url.replace("https://", "http://")
                        print(f"Retrying over HTTP: {http_url}")
                        response = requests.post(http_url, files=files, timeout=15)
                    else:
                        raise fallback_err
            
        if response.status_code == 200:
            result = response.json()
            print("\nServer Response:")
            print(f"Success: {result.get('success')}")
            print(f"Recognized Students: {result.get('recognized')}")
            print(f"Marked Present: {result.get('marked_present_count')} new record(s)")
            print(f"Message: {result.get('message')}")
        else:
            print(f"Server returned error status code: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Connection error: {e}")
        print(f"Make sure the server at {url} is running.")

if __name__ == '__main__':
    main()
