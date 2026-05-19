# web_enroll.py
# ============================================================
# Smart Attendance System - Web Enrollment Bridge
# Processes captured images from the web UI through YOLO+ArcFace.
# Usage: python web_enroll.py "Student Name" img1.jpg img2.jpg ...
# ============================================================

import cv2
import numpy as np
import pickle
import os
import sys
import json

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
import config
import onnxruntime as ort
from ultralytics import YOLO


def _resolve(p):
    return p if os.path.isabs(p) else os.path.join(_DIR, p)


# Load models once
yolo_model = YOLO(_resolve(config.YOLO_PATH))
arcface_session = ort.InferenceSession(
    _resolve(config.ARCFACE_PATH), providers=["CPUExecutionProvider"]
)
arcface_input = arcface_session.get_inputs()[0].name


def extract_embedding(face_img):
    img = face_img[:, :, ::-1].astype(np.float32)
    img = (img - 127.5) / 127.5
    img = np.transpose(img, (2, 0, 1))[np.newaxis]
    return arcface_session.run(None, {arcface_input: img})[0][0]


def detect_and_crop(frame):
    results = yolo_model(frame, verbose=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None, None
    areas = [
        (float(b.xyxy[0][2]) - float(b.xyxy[0][0]))
        * (float(b.xyxy[0][3]) - float(b.xyxy[0][1]))
        for b in boxes
    ]
    best = boxes[areas.index(max(areas))]
    x1, y1, x2, y2 = map(int, best.xyxy[0].tolist())
    h, w = frame.shape[:2]
    pad = config.PADDING
    face = frame[max(0, y1 - pad) : min(h, y2 + pad), max(0, x1 - pad) : min(w, x2 + pad)]
    if face.size == 0:
        return None, None
    return cv2.resize(face, (config.IMG_SIZE, config.IMG_SIZE)), best


def check_quality(frame, box):
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
    conf = float(box.conf[0])
    fh, fw = frame.shape[:2]
    face_w, face_h = x2 - x1, y2 - y1
    mn = min(fw, fh) * 0.15
    if face_w < mn or face_h < mn:
        return False, "Face too small"
    if conf < 0.6:
        return False, "Low confidence"
    gray = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 30:
        return False, "Image blurry"
    return True, "Good"


def load_db():
    p = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return pickle.load(f)
    return {}


def save_db(db):
    p = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        pickle.dump(db, f)


def process_images(name, paths):
    db = load_db()
    overwritten = name in db
    embeddings, per_image = [], []

    for path in paths:
        bn = os.path.basename(path)
        frame = cv2.imread(path)
        if frame is None:
            per_image.append({"file": bn, "status": "error", "reason": "Cannot read image"})
            continue
        face, box = detect_and_crop(frame)
        if face is None:
            per_image.append({"file": bn, "status": "no_face", "reason": "No face detected"})
            continue
        ok, msg = check_quality(frame, box)
        per_image.append({
            "file": bn,
            "status": "ok" if ok else "quality_warn",
            "reason": msg,
        })
        embeddings.append(extract_embedding(face))

    if len(embeddings) < 3:
        return {
            "success": False,
            "message": f"Only {len(embeddings)} usable faces from {len(paths)} images. Need at least 3.",
            "details": {"per_image": per_image},
        }

    avg = np.mean(embeddings, axis=0)
    avg = avg / np.linalg.norm(avg)
    db[name] = avg
    save_db(db)

    action = "updated" if overwritten else "enrolled"
    return {
        "success": True,
        "message": f"{name} {action} successfully with {len(embeddings)}/{len(paths)} captures. Database has {len(db)} person(s).",
        "details": {
            "per_image": per_image,
            "embeddings_used": len(embeddings),
            "database_size": len(db),
            "overwritten": overwritten,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("__RESULT_JSON__" + json.dumps({"success": False, "message": "Usage: python web_enroll.py Name img1.jpg ..."}))
        sys.exit(1)

    student_name = sys.argv[1]
    image_files = sys.argv[2:]
    result = process_images(student_name, image_files)
    print("__RESULT_JSON__" + json.dumps(result))
    sys.exit(0 if result.get("success") else 1)
