import cv2
import requests
import time
import sys

URL = 'https://finalproject-production-aa41.up.railway.app/stream/frame'

def main():
    print("\n--- Live Webcam ESP32-CAM Stream Simulator ---")
    print(f"Streaming to: {URL}")
    print("Press Ctrl+C to quit.")
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open laptop webcam.")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame.")
                break
                
            # Encode frame as JPEG
            _, img_encoded = cv2.imencode('.jpg', frame)
            img_bytes = img_encoded.tobytes()
            
            # Send HTTP POST request with raw binary frame bytes
            try:
                response = requests.post(URL, data=img_bytes, headers={'Content-Type': 'image/jpeg'}, timeout=2.0)
                if response.status_code == 200:
                    msg = response.json().get('message', '')
                    print(f"[Live Stream] Sent frame. Response: {msg}")
                else:
                    print(f"[Error] Server returned status: {response.status_code}")
            except Exception as e:
                print(f"[Error] Connection error: {e}")
                
            # Sleep 200ms (5 frames per second) to mimic ESP32-CAM stream rate
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\nStopping stream...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam released. Done.")

if __name__ == '__main__':
    main()
