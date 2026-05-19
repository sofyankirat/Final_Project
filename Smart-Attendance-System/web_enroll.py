# web_enroll_camera.py
# ============================================================
# Smart Attendance System — Web-triggered Enrollment
# Launched by the Flask app as a subprocess.
# Opens the native OpenCV camera window with the same quality
# checks, progress bar, and SPACE-to-capture flow as enroll.py.
#
# Usage:  python web_enroll_camera.py "Student Name"
# Exit codes:
#   0 = enrolled successfully
#   1 = cancelled / error
# Stdout last line on success: JSON with result details
# ============================================================

import cv2
import numpy as np
import pickle
import os
import sys
import json

# Resolve paths relative to this script's directory
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

import config
import onnxruntime as ort
from ultralytics import YOLO

# ============================================================
# LOAD MODELS
# ============================================================
def _resolve(path):
    """Make config paths absolute relative to this script's dir."""
    if os.path.isabs(path):
        return path
    return os.path.join(_DIR, path)

print("Loading models...\n")
yolo_model = YOLO(_resolve(config.YOLO_PATH))
session    = ort.InferenceSession(
    _resolve(config.ARCFACE_PATH),
    providers=['CPUExecutionProvider']
)
input_name = session.get_inputs()[0].name
print("✅ Models loaded\n")

# ============================================================
# HELPER FUNCTIONS  (identical to enroll.py)
# ============================================================

def extract_embedding(face_img):
    """Extract 512-dim ArcFace embedding from 112x112 face"""
    img = face_img[:, :, ::-1].astype(np.float32)
    img = (img - 127.5) / 127.5
    img = np.transpose(img, (2, 0, 1))
    img = np.expand_dims(img, axis=0)
    output = session.run(None, {input_name: img})
    return output[0][0]


def check_face_quality(frame, box):
    """
    Checks face quality before accepting capture.
    Returns (is_good, message).
    """
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
    conf            = float(box.conf[0])
    h_frame, w_frame = frame.shape[:2]

    face_w = x2 - x1
    face_h = y2 - y1

    min_face_size = min(w_frame, h_frame) * 0.2
    if face_w < min_face_size or face_h < min_face_size:
        return False, "Move closer to camera"

    max_face_size = min(w_frame, h_frame) * 0.9
    if face_w > max_face_size or face_h > max_face_size:
        return False, "Move farther from camera"

    margin = 0.1
    if (x1 < w_frame * margin or
        x2 > w_frame * (1 - margin) or
        y1 < h_frame * margin or
        y2 > h_frame * (1 - margin)):
        return False, "Center your face"

    if conf < 0.75:
        return False, "Look directly at camera"

    face_crop  = frame[y1:y2, x1:x2]
    gray       = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < 50:
        return False, "Hold still — image blurry"

    return True, "✅ Good — press SPACE"


def detect_and_crop(frame):
    """Detect face in frame and return 112x112 crop + box"""
    results = yolo_model(frame, verbose=False)
    boxes   = results[0].boxes

    if boxes is None or len(boxes) == 0:
        return None, None

    areas    = [(float(b.xyxy[0][2]) - float(b.xyxy[0][0])) *
                (float(b.xyxy[0][3]) - float(b.xyxy[0][1]))
                for b in boxes]
    best_box = boxes[areas.index(max(areas))]

    x1, y1, x2, y2 = map(int, best_box.xyxy[0].tolist())
    h, w            = frame.shape[:2]
    x1p = max(0, x1 - config.PADDING)
    y1p = max(0, y1 - config.PADDING)
    x2p = min(w, x2 + config.PADDING)
    y2p = min(h, y2 + config.PADDING)

    face = frame[y1p:y2p, x1p:x2p]
    if face.size == 0:
        return None, None

    return cv2.resize(face, (config.IMG_SIZE, config.IMG_SIZE)), best_box


def load_database():
    """Load existing database or create empty one"""
    db_path = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        with open(db_path, "rb") as f:
            return pickle.load(f)
    return {}


def save_database(database):
    """Save updated database to disk"""
    db_path = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(db_path, "wb") as f:
        pickle.dump(database, f)


# ============================================================
# ENROLLMENT PROCESS  (no stdin — name from CLI argument)
# ============================================================
def enroll_student(name):
    """
    Run the full enrollment with OpenCV camera window.
    Returns a dict with the result (printed as JSON on stdout).
    """
    database = load_database()

    # Auto-overwrite if name exists (no interactive prompt)
    overwritten = name in database

    # Open camera
    cap = cv2.VideoCapture(config.CAMERA_SOURCE)
    if not cap.isOpened():
        return {"success": False, "message": "Cannot open camera"}

    print(f"\nEnrolling: {name}")
    print("Instructions:")
    print("  → Look directly at camera")
    print("  → Keep face centered")
    print("  → Stay at arm's length distance")
    print("  → Press SPACE when quality is good")
    print("  → Press Q to cancel\n")

    captured_embeddings = []
    needed              = 5
    last_quality_msg    = ""

    positions = [
        "Look straight ahead",
        "Turn slightly LEFT",
        "Turn slightly RIGHT",
        "Look slightly UP",
        "Look slightly DOWN",
    ]

    while len(captured_embeddings) < needed:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()
        current_pos = positions[len(captured_embeddings)]

        # Detect face
        face, box = detect_and_crop(frame)

        if box is not None:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            is_good, quality_msg = check_face_quality(frame, box)
            last_quality_msg     = quality_msg

            color = (0, 255, 0) if is_good else (0, 165, 255)
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

            cv2.putText(display, quality_msg,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, color, 2)
        else:
            cv2.putText(display, "No face detected — look at camera",
                        (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 0, 255), 2)

        # Draw name and progress
        cv2.putText(display,
                    f"Enrolling: {name}",
                    (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (255, 255, 255), 2)

        cv2.putText(display,
                    f"Captured: {len(captured_embeddings)}/{needed}",
                    (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 255, 255), 2)

        # Current position instruction
        cv2.putText(display,
                    f"Position: {current_pos}",
                    (10, 105),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 200, 100), 2)

        # Draw progress bar
        bar_width  = 300
        bar_filled = int(bar_width * len(captured_embeddings) / needed)
        cv2.rectangle(display, (10, 140), (10 + bar_width, 160),
                      (100, 100, 100), -1)
        cv2.rectangle(display, (10, 140), (10 + bar_filled, 160),
                      (0, 255, 0), -1)

        cv2.imshow("Enrollment — Press SPACE to capture, Q to cancel",
                   display)

        key = cv2.waitKey(1) & 0xFF

        # SPACE to capture
        if key == ord(' '):
            if face is None:
                print("  ❌ No face detected — try again")
            elif not check_face_quality(frame, box)[0]:
                print(f"  ❌ Quality check failed: {last_quality_msg}")
            else:
                emb = extract_embedding(face)
                captured_embeddings.append(emb)
                print(f"  ✅ Capture {len(captured_embeddings)}/{needed} accepted — {current_pos}")

                # Flash green to confirm capture
                flash = frame.copy()
                cv2.rectangle(flash, (0, 0),
                              (flash.shape[1], flash.shape[0]),
                              (0, 255, 0), 20)
                cv2.imshow("Enrollment — Press SPACE to capture, Q to cancel",
                           flash)
                cv2.waitKey(300)

        # Q to cancel
        elif key == ord('q'):
            print("\nEnrollment cancelled.")
            cap.release()
            cv2.destroyAllWindows()
            return {"success": False, "message": "Enrollment cancelled by user"}

    cap.release()
    cv2.destroyAllWindows()

    if len(captured_embeddings) < needed:
        return {
            "success": False,
            "message": f"Only {len(captured_embeddings)}/{needed} captures taken. Camera may have disconnected.",
        }

    # Average + normalize embeddings
    avg_embedding = np.mean(captured_embeddings, axis=0)
    avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

    # Save to database
    database[name] = avg_embedding
    save_database(database)

    action = "updated" if overwritten else "enrolled"
    result = {
        "success": True,
        "message": f"'{name}' {action} successfully with {needed} captures. Database now has {len(database)} person(s).",
        "details": {
            "name": name,
            "captures_used": needed,
            "database_size": len(database),
            "overwritten": overwritten,
        }
    }

    print(f"\n{'='*50}")
    print(f"✅ '{name}' {action} successfully!")
    print(f"   Captures used : {needed}")
    print(f"   Database size : {len(database)} persons")
    print(f"   Saved to      : {_resolve(config.DATABASE_PATH)}")
    print(f"{'='*50}\n")

    return result


# ============================================================
# MAIN — receive student name from CLI argument
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(json.dumps({"success": False, "message": "Student name is required. Usage: python web_enroll_camera.py \"Name\""}))
        sys.exit(1)

    student_name = sys.argv[1].strip()
    result = enroll_student(student_name)

    # Print JSON result as the LAST line of stdout for the Flask app to parse
    print("__RESULT_JSON__" + json.dumps(result))
    sys.exit(0 if result.get("success") else 1)
