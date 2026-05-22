"""
web_recognize.py — Test recognition against the enrolled database.
Uses the same YOLO + ArcFace pipeline as face_pipeline.py.

Usage:
    python web_recognize.py <image_path>

Outputs JSON result via __RESULT_JSON__ prefix.
"""

import sys, os, json, pickle
import numpy as np
import cv2
import onnxruntime as ort

# ── Paths ────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
import config

def _resolve(p):
    candidates = []
    if p:
        candidates.append(p)
        if not os.path.isabs(p):
            candidates.append(os.path.join(_DIR, p))
    base_name = os.path.basename(p) if p else ""
    for root in (_DIR, os.path.join(_DIR, "models"), os.path.abspath(os.path.join(_DIR, os.pardir)), os.path.join(os.path.abspath(os.path.join(_DIR, os.pardir)), "models")):
        if base_name:
            candidates.append(os.path.join(root, base_name))
        if p:
            candidates.append(os.path.join(root, p))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return p

import typing

# ── Load models (same as face_pipeline.py) ───────────────────
yolo_model: typing.Any = None
arc_session: typing.Any = None
arc_input: typing.Any = None

def _load_models():
    global yolo_model, arc_session, arc_input
    from ultralytics import YOLO
    yolo_model = YOLO(_resolve(config.YOLO_PATH))
    arc_session = ort.InferenceSession(
        _resolve(config.ARCFACE_PATH),
        providers=['CPUExecutionProvider']
    )
    arc_input = arc_session.get_inputs()[0].name

def _extract_embedding(face_112):
    img = cv2.cvtColor(face_112, cv2.COLOR_BGR2RGB).astype(np.float32)
    img = (img - 127.5) / 127.5
    img = np.transpose(img, (2, 0, 1))[np.newaxis, ...]
    return arc_session.run(None, {arc_input: img})[0].flatten()

def _load_db():
    p = _resolve(config.DATABASE_PATH)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "rb") as f:
            db = pickle.load(f)
        return {name: np.array(emb, dtype=np.float32).flatten() for name, emb in db.items()}
    except Exception as e:
        print(f"⚠️ Error loading database in recognize: {e}")
        backup = p + ".bak"
        if os.path.exists(backup):
            try:
                with open(backup, "rb") as f:
                    bdb = pickle.load(f)
                return {name: np.array(emb, dtype=np.float32).flatten() for name, emb in bdb.items()}
            except Exception:
                pass
        return {}

def _find_match(query_emb, database):
    query = query_emb / np.linalg.norm(query_emb)
    best_match, best_score = "Unknown", -1
    for person, stored_emb in database.items():
        sim = float(np.dot(query, stored_emb.flatten()))
        if sim > best_score:
            best_score = sim
            best_match = person
    if best_score < getattr(config, 'THRESHOLD', 0.4):
        return "Unknown", best_score
    return best_match, best_score


def recognize(image_path):
    _load_models()
    database = _load_db()

    if not database:
        return {"success": False, "message": "No enrolled users in the database yet."}

    frame = cv2.imread(image_path)
    if frame is None:
        return {"success": False, "message": "Could not read the uploaded image."}

    # Detect faces
    results = yolo_model(frame, verbose=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return {"success": False, "message": "No face detected in the image. Please try a clearer photo."}

    faces_found = []
    pad = getattr(config, 'PADDING', 20)

    for box in boxes:
        conf = float(box.conf[0])
        if conf < getattr(config, 'DETECTION_CONF', 0.5):
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        face_112 = cv2.resize(crop, (112, 112))
        emb = _extract_embedding(face_112)
        match_name, score = _find_match(emb, database)
        faces_found.append({
            "name": match_name,
            "confidence": round(score * 100, 1),
            "bbox": [x1, y1, x2, y2],
        })

    if not faces_found:
        return {"success": False, "message": "Face detected but could not extract features."}

    recognized = [f for f in faces_found if f["name"] != "Unknown"]
    return {
        "success": True,
        "faces": faces_found,
        "recognized_count": len(recognized),
        "total_faces": len(faces_found),
        "message": f"Found {len(faces_found)} face(s). {len(recognized)} recognized."
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python web_recognize.py <image_path>")
        sys.exit(1)
    result = recognize(sys.argv[1])
    print("__RESULT_JSON__" + json.dumps(result))
