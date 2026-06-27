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
                    res_json = response.json()
                    msg = res_json.get('message', '')
                    print(f"[Live Stream] Sent frame. Response: {msg}")
                    
                    # Draw bounding boxes returned by the server on our local frame!
                    faces = res_json.get('faces', [])
                    for face in faces:
                        bbox = face.get('bbox', [])
                        name = face.get('name', 'Unknown')
                        conf = face.get('confidence', 0.0)
                        
                        if len(bbox) == 4:
                            x1, y1, x2, y2 = bbox
                            # Draw green for recognized student, red for Unknown
                            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(frame, f"{name} ({conf:.2f})", (x1, y1 - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                else:
                    print(f"[Error] Server returned status: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[Error] Connection error: {e}")
                
            # Display the frame in a local window!
            cv2.imshow('ESP32-CAM Simulator Feed (Press Q to Quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            # Sleep 150ms (mimic stream rate)
            time.sleep(0.15)
            
    except KeyboardInterrupt:
        print("\nStopping stream...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam released. Done.")

if __name__ == '__main__':
    main()
