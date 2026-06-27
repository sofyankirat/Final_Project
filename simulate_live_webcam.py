import cv2
import requests
import time
import sys
import threading

URL = 'https://finalproject-production-aa41.up.railway.app/stream/frame'

# Shared thread-safe variables
latest_frame_to_send = None
latest_frame_lock = threading.Lock()
latest_faces = []
latest_faces_lock = threading.Lock()
running = True

def sender_thread():
    global latest_faces, running
    print("[Sender Thread] Started background frame transmitter.")
    while running:
        frame_bytes = None
        with latest_frame_lock:
            if latest_frame_to_send is not None:
                frame_bytes = latest_frame_to_send
        
        if frame_bytes is not None:
            try:
                response = requests.post(URL, data=frame_bytes, headers={'Content-Type': 'image/jpeg'}, timeout=2.5)
                if response.status_code == 200:
                    res_json = response.json()
                    msg = res_json.get('message', '')
                    faces = res_json.get('faces', [])
                    print(f"[Live Stream] Sent frame. Server response: {msg}")
                    with latest_faces_lock:
                        latest_faces = faces
                else:
                    print(f"[Error] Server returned status: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[Error] Connection error: {e}")
                
        # Send ~5 frames per second to not overload network/server
        time.sleep(0.18)

def main():
    global latest_frame_to_send, running
    print("\n--- Threaded Live Webcam ESP32-CAM Stream Simulator ---")
    print(f"Streaming to: {URL}")
    print("Press Q in the webcam window to quit.")
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open laptop webcam.")
        return

    # Start background sender thread
    t = threading.Thread(target=sender_thread)
    t.daemon = True
    t.start()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame.")
                break
                
            # Encode frame as JPEG for the background sender thread
            _, img_encoded = cv2.imencode('.jpg', frame)
            img_bytes = img_encoded.tobytes()
            
            with latest_frame_lock:
                latest_frame_to_send = img_bytes
                
            # Draw latest bounding boxes returned from server
            with latest_faces_lock:
                faces = list(latest_faces)
                
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
            
            # Display frame instantly in local window (smooth 30 FPS)
            cv2.imshow('ESP32-CAM Simulator Feed (Press Q to Quit)', frame)
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam released. Done.")

if __name__ == '__main__':
    main()
