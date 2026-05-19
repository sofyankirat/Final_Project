# web_enroll.py
# ============================================================
# Smart Attendance System  -  Web Enrollment Processor
# Accepts image file paths on the command line, runs
# YOLO face detection + ArcFace embedding, saves to the
# attendance database pickle.
#
# Usage:
#   python web_enroll.py "Student Name" img1.jpg img2.jpg ...
#
# Exit codes:  0 = success, 1 = failure
# The last stdout line prefixed with __RESULT_JSON__ is the
# machine-readable result for the Flask backend.
# ============================================================

import cv2
import numpy as np
import pickle
import os
import sys
import json

# Resolve paths relative to this script
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

import config  # type: ignore[import]

# ── Helpers ──────────────────────────────────────────────────

def _resolve(path):
    return path if os.path.isabs(path) else os.path.join(_DIR, path)


def load_models():
    """Load YOLO + ArcFace once."""
    from ultralytics import YOLO  # type: ignore[import]
    import onnxruntime as ort      # type: ignore[import]

    yolo = YOLO(_resolve(config.YOLO_PATH))
    sess = ort.InferenceSession(
        _resolve(config.ARCFACE_PATH),
        providers=['CPUExecutionProvider'],
    )
    return yolo, sess, sess.get_inputs()[0].name


def extract_embedding(face_img, session, input_name):
    img = face_img[:, :, ::-1].astype(np.float32)
    img = (img - 127.5) / 127.5
    img = np.transpose(img, (2, 0, 1))
    img = np.expand_dims(img, axis=0)
    return session.run(None, {input_name: img})[0][0]


def detect_and_crop(frame, yolo, padding=None, img_size=None):
    padding  = padding  or config.PADDING
    img_size = img_size or config.IMG_SIZE

    results = yolo(frame, verbose=False)
    boxes   = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None

    areas    = [
        (float(b.xyxy[0][2]) - float(b.xyxy[0][0])) *
        (float(b.xyxy[0][3]) - float(b.xyxy[0][1]))
        for b in boxes
    ]
    best = boxes[areas.index(max(areas))]
    x1, y1, x2, y2 = map(int, best.xyxy[0].tolist())
    h, w = frame.shape[:2]

    face = frame[
        max(0, y1 - padding): min(h, y2 + padding),
        max(0, x1 - padding): min(w, x2 + padding),
    ]
    if face.size == 0:
        return None
    return cv2.resize(face, (img_size, img_size))


def load_database():
    db_path = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        with open(db_path, "rb") as f:
            return pickle.load(f)
    return {}


def save_database(database):
    db_path = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(db_path, "wb") as f:
        pickle.dump(database, f)


# ── Main ─────────────────────────────────────────────────────

def process_images(name, image_paths):
    """Process saved image files and enroll into the database."""
    print("Loading AI models...")
    yolo, session, input_name = load_models()
    print("Models loaded.")

    embeddings   = []
    per_image    = []

    for path in image_paths:
        basename = os.path.basename(path)
        frame = cv2.imread(path)
        if frame is None:
            per_image.append({"file": basename, "status": "error", "reason": "Could not read image"})
            continue

        face = detect_and_crop(frame, yolo)
        if face is None:
            per_image.append({"file": basename, "status": "no_face", "reason": "No face detected"})
            continue

        emb = extract_embedding(face, session, input_name)
        embeddings.append(emb)
        per_image.append({"file": basename, "status": "ok", "reason": "Face detected"})

    if len(embeddings) < 3:
        return {
            "success": False,
            "message": f"Only {len(embeddings)}/{len(image_paths)} images had a detectable face. Need at least 3.",
            "details": {"per_image": per_image},
        }

    avg = np.mean(embeddings, axis=0)
    avg = avg / np.linalg.norm(avg)

    database    = load_database()
    overwritten = name in database
    database[name] = avg
    save_database(database)

    action = "updated" if overwritten else "enrolled"
    return {
        "success": True,
        "message": f"'{name}' {action} successfully with {len(embeddings)}/{len(image_paths)} captures. Database now has {len(database)} person(s).",
        "details": {
            "per_image": per_image,
            "embeddings_used": len(embeddings),
            "database_size": len(database),
            "overwritten": overwritten,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        r = {"success": False, "message": "Usage: python web_enroll.py \"Name\" img1.jpg img2.jpg ..."}
        print("__RESULT_JSON__" + json.dumps(r))
        sys.exit(1)

    student_name = sys.argv[1].strip()
    paths        = sys.argv[2:]

    result = process_images(student_name, paths)
    print("__RESULT_JSON__" + json.dumps(result))
    sys.exit(0 if result.get("success") else 1)
