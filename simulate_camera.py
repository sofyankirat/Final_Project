import os
import requests

# URL of your live Railway server
URL = 'https://finalproject-production-aa41.up.railway.app/stream/frame'

# Path to your face photo (put your photo here)
IMAGE_PATH = 'my_face.jpg'

def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Could not find '{IMAGE_PATH}' in the project folder.")
        print("Please copy a photo of your face to this directory and rename it to 'my_face.jpg'.")
        return

    print(f"Sending '{IMAGE_PATH}' to the attendance server...")
    try:
        with open(IMAGE_PATH, 'rb') as fh:
            files = {'file': fh}
            response = requests.post(URL, files=files)
            
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
        print(f"Make sure the server at {URL} is running.")

if __name__ == '__main__':
    main()
