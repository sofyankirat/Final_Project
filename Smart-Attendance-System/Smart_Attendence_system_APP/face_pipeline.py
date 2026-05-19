# Contains all functions 
# Load Models , Detection , Aligment , Embedding , Match , log , Draw
# ---------------------------------------------------

# IMPORT LIBRARIES 
#------------------

import cv2
import numpy as np
import pickle
import csv
import os
import onnxruntime as ort
from datetime import datetime
from ultralytics import YOLO
# from insightface.app import FaceAnalysis
import config
#------------------
#ARCFACE ONNX CLASS
#------------------
class ArcFaceONNX:
    """
    - Loads ArcFace model directly via ONNX.
    - Bypasses FaceAnalysis to avoid 'AssertionError' and installation issues.
    """
    def __init__(self, model_path):
        self.session = ort.InferenceSession(
            model_path, 
            providers=['CPUExecutionProvider']
        )
        self.input_name = self.session.get_inputs()[0].name
        print(f"  ✅ ArcFace ONNX loaded from {model_path}")

    def get_feat(self, img):
        # 1. BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 2. Normalize to [-1, 1]
        img = img.astype(np.float32)
        img = (img - 127.5) / 127.5

        # 3. HWC to CHW and add Batch dimension
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)

        # 4. Run Inference
        output = self.session.run(None, {self.input_name: img})
        return output[0].flatten()

#------------
# LOAD MODEL
#------------
"""
returns yolo_model (for ace detection) , face_app(for embedding) and the database
"""
def load_models():
    yolo_detection_model = YOLO(config.YOLO_PATH)      #  Load YOLOv8 face detector 
    print("  ✅ YOLOv8s-Face loaded")

    face_app_embedding = ArcFaceONNX(config.ARCFACE_PATH)
    # face_app_embedding = FaceAnalysis(name='buffalo_sc')
    # face_app_embedding.prepare(ctx_id=0, det_size=(112, 112),
    #                         providers=['CPUExecutionProvider'])   # Load ArcFace embedding model
    # print("  ✅ ArcFace (buffalo_sc) loaded")

 
    with open(config.DATABASE_PATH, "rb") as f:
        database = pickle.load(f)
    database = {name: np.array(emb).flatten() for name, emb in database.items()}
    print(f"  ✅ Database loaded → {len(database)} persons") # Load embedding database

    return yolo_detection_model, face_app_embedding, database
#--------------
#FACE DETECTION
#--------------

def detect_faces(frame, yolo_detection_model):
    """
    Runs YOLOv8 on full camera frame
    Detects ALL faces by confidence threshold

    """
    results = yolo_detection_model(frame, verbose=False)
    boxes   = results[0].boxes

    if boxes is None or len(boxes) == 0:
        return []

    # Filter by minimum confidence
    valid_boxes = [box for box in boxes
                   if float(box.conf[0]) >= config.DETECTION_CONF]

    return valid_boxes
#-------------
#FACE ALIGMENT
#-------------

def align_face(frame, box):
    """
    -Crops detected face from frame
    -Adds padding around bounding box
    -Resizes to 112x112 (ArcFace standard)

    """
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
    h, w            = frame.shape[:2]

    # Add padding — prevents cutting face edges
    x1 = max(0, x1 - config.PADDING)
    y1 = max(0, y1 - config.PADDING)
    x2 = min(w, x2 + config.PADDING)
    y2 = min(h, y2 + config.PADDING)

    # Crop face region
    face_crop = frame[y1:y2, x1:x2]

    # Check crop is valid
    if face_crop.size == 0:
        return None, (x1, y1, x2, y2)

    # Resize to ArcFace standard input size
    face_aligned = cv2.resize(face_crop,
                              (config.IMG_SIZE, config.IMG_SIZE))

    return face_aligned, (x1, y1, x2, y2)
# -----------------
# EXTRACT EMBEDDING
#------------------
def extract_embedding(face_img, face_app_embedding):
    """
    -Runs ArcFace on aligned 112x112 face
    -Returns 512-dimensional identity vector
    -Returns: numpy array of shape (512,)
    """
    emb = face_app_embedding.get_feat(face_img)
    return emb  # shape (512,)

# ----------
# FIND MATCH
# ----------
def find_match(query_embedding, database):
    """
    - Compares query embedding with all database embeddings
    - Uses cosine similarity

    """
    best_match = "Unknown"
    best_score = -1

    # Normalize query to unit length
    query = query_embedding / np.linalg.norm(query_embedding)

    for person, stored_emb in database.items():
        # Cosine similarity = dot product of unit vectors
        stored_emb = stored_emb.flatten()
        similarity = np.dot(query, stored_emb)
        if isinstance(similarity, np.ndarray):
            similarity = similarity.item()

        if similarity > best_score:
            best_score = similarity
            best_match = person

    # Reject if below threshold
    if best_score < config.THRESHOLD:
        return "Unknown", best_score

    return best_match, best_score
#---------------
# LOG ATTENDANCE
#---------------
def log_attendance(name, score, attendance_logged):
    """
    - Logs attendance to CSV file
    - Each person logged ONCE per session only
    - Skips Unknown persons

    """
    # Skip unknown or already logged
    if name == "Unknown" or name in attendance_logged:
        return False

    # Create logs folder if not exists
    os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)

    # Write to CSV
    now          = datetime.now()
    file_exists  = os.path.exists(config.LOG_PATH)

    with open(config.LOG_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Name", "Date", "Time", "Confidence"])
        writer.writerow([
            name,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            f"{score:.3f}"
        ])
    # Add to logged set
    attendance_logged.add(name)
    print(f"  ✅ Marked present: {name} (confidence: {score:.3f})")
    return True
#--------------
# DRAW ON FRAME
# -------------
def draw_on_frame(frame, x1, y1, x2, y2, name, score, newly_logged, attendance_logged):
    """
    - Draws bounding box and name label on frame

      Green  → recognized + just marked present
      Yellow → recognized + already marked before
      Red    → unknown person
    """
    # Choose color based on status
    if name == "Unknown":
        color = config.COLOR_UNKNOWN    # Red
    elif newly_logged:
        color = config.COLOR_NEW        # Green
    else:
        color = config.COLOR_REPEAT     # Yellow

    # Draw bounding box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # Prepare label text
    first_name = name.split()[0] if name != "Unknown" else "Unknown"
    label      = f"{first_name} ({score:.2f})"

    # Draw label background for readability
    text_size = cv2.getTextSize(label,
                                config.FONT,
                                config.FONT_SCALE,
                                config.FONT_THICKNESS)[0]

    cv2.rectangle(frame,
                  (x1, y1 - text_size[1] - 12),
                  (x1 + text_size[0] + 4, y1),
                  color, -1)

    # Draw label text in black
    cv2.putText(frame, label,
                (x1 + 2, y1 - 6),
                config.FONT,
                config.FONT_SCALE,
                (0, 0, 0),
                config.FONT_THICKNESS)

    return frame
#-------------
# PRINT SUMMARY
# -------------
def print_summary(attendance_logged, all_persons):
    """
    Prints final session summary:
      → list of present students
      → list of absent students
      → path to attendance log
    """
    print(f"\n{'-'*53}")
    print(f"  SESSION SUMMARY")
    print(f"{'-'*53}")

    print(f"\n  Present ({len(attendance_logged)}):")
    for name in sorted(attendance_logged):
        print(f"    ✅ {name}")

    absent = [p for p in sorted(all_persons)
              if p not in attendance_logged]

    print(f"\n  Absent ({len(absent)}):")
    for name in absent:
        print(f"    ❌ {name}")

    print(f"\n  Log saved → {config.LOG_PATH}")
    print(f"{'-'*53}\n")
