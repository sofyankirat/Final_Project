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

    # Construct request URL
    request_url = url
    if test_user_id:
        request_url = f"{url}?test_user_id={test_user_id}"

    print(f"\nSending '{IMAGE_PATH}' to {request_url}...")
    try:
        with open(IMAGE_PATH, 'rb') as fh:
            files = {'file': fh}
            response = requests.post(request_url, files=files)
            
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
