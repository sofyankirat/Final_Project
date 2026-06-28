# web_enroll.py
# ============================================================
# Smart Attendance System — Full Pipeline Web Enrollment
# Uses the EXACT same pipeline as enroll.py for consistent embeddings:
#   1. YOLOv8s-Face  → detect face  (same model)
#   2. Bbox crop + padding → resize to 112x112  (same logic)
#   3. Data augmentation → expand to ~100 images
#   4. ArcFace w600k_mbf ONNX → extract 512-dim embeddings  (same model+preprocessing)
#   5. Average embeddings → save to database.pkl
#
# Usage: python web_enroll.py "Student Name" img1.jpg img2.jpg ...
# ============================================================

import cv2
import numpy as np
import pickle
import os
import sys
import json
import random
import onnxruntime as ort
from ultralytics import YOLO

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
import config
from db_sync import save_embedding_to_db


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


# ── Load SAME models as enroll.py ────────────────────────────
yolo_model = YOLO(_resolve(config.YOLO_PATH))
arcface_session = ort.InferenceSession(
    _resolve(config.ARCFACE_PATH), providers=["CPUExecutionProvider"]
)
arcface_input = arcface_session.get_inputs()[0].name


# ── SAME extract_embedding as enroll.py ──────────────────────
def extract_embedding(face_img):
    """Extract 512-dim ArcFace embedding from 112x112 face.
    Identical to enroll.py: BGR→RGB, (x-127.5)/127.5, HWC→CHW."""
    img = face_img[:, :, ::-1].astype(np.float32)
    img = (img - 127.5) / 127.5
    img = np.transpose(img, (2, 0, 1))
    img = np.expand_dims(img, axis=0)
    return arcface_session.run(None, {arcface_input: img})[0][0]


# ── SAME detect_and_crop as enroll.py ────────────────────────
def detect_and_crop(frame, path=None):
    """Detect face and return 112x112 crop + box.
    Identical to enroll.py: YOLO detect → bbox + padding → resize."""
    source = path if path is not None else frame
    results = yolo_model(source, verbose=False)
    boxes = results[0].boxes

    if boxes is None or len(boxes) == 0:
        return None, None

    areas = [
        (float(b.xyxy[0][2]) - float(b.xyxy[0][0]))
        * (float(b.xyxy[0][3]) - float(b.xyxy[0][1]))
        for b in boxes
    ]
    best_box = boxes[areas.index(max(areas))]

    x1, y1, x2, y2 = map(int, best_box.xyxy[0].tolist())
    h, w = frame.shape[:2]
    x1p = max(0, x1 - config.PADDING)
    y1p = max(0, y1 - config.PADDING)
    x2p = min(w, x2 + config.PADDING)
    y2p = min(h, y2 + config.PADDING)

    face = frame[y1p:y2p, x1p:x2p]
    if face.size == 0:
        return None, None

    return cv2.resize(face, (config.IMG_SIZE, config.IMG_SIZE)), best_box


# ── SAME check_face_quality as enroll.py ─────────────────────
def check_face_quality(frame, box):
    """Quality checks identical to enroll.py."""
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
    conf = float(box.conf[0])
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
    if (x1 < w_frame * margin or x2 > w_frame * (1 - margin) or
            y1 < h_frame * margin or y2 > h_frame * (1 - margin)):
        return False, "Center your face"

    if conf < 0.75:
        return False, "Look directly at camera"

    face_crop = frame[y1:y2, x1:x2]
    if face_crop.size > 0:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        blur_score = np.var(cv2.Laplacian(gray, getattr(cv2, 'CV_64F', 6)))
        if blur_score < 50:
            return False, "Hold still — image blurry"

    return True, "Good quality"


# ── Data augmentation ────────────────────────────────────────
def augment_face(face_112, target_count=20):
    """Generate augmented copies of a 112x112 face crop."""
    augmented = [face_112]
    h, w = face_112.shape[:2]
    center = (w // 2, h // 2)

    while len(augmented) < target_count:
        img = face_112.copy()

        if random.random() < 0.5:
            img = cv2.flip(img, 1)

        beta = random.randint(-30, 30)
        img = cv2.convertScaleAbs(img, alpha=1.0, beta=beta)

        angle = random.uniform(-15, 15)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT_101)

        if random.random() < 0.3:
            ksize = random.choice([3, 5])
            img = cv2.GaussianBlur(img, (ksize, ksize), 0)

        augmented.append(img)

    return augmented


# ── Database ─────────────────────────────────────────────────
def load_db():
    p = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                db = pickle.load(f)
            return {name: np.array(emb, dtype=np.float32) for name, emb in db.items()}
        except Exception as e:
            print(f"⚠️  Error reading database.pkl: {e}. Trying backup...")
            backup = p + ".bak"
            if os.path.exists(backup):
                try:
                    with open(backup, "rb") as f:
                        bdb = pickle.load(f)
                    return {name: np.array(emb, dtype=np.float32) for name, emb in bdb.items()}
                except Exception:
                    pass
            return {}
    return {}


def save_db(db):
    p = _resolve(config.DATABASE_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    # Convert numpy arrays to lists before saving
    serializable = {}
    for name, emb in db.items():
        if hasattr(emb, 'tolist'):
            serializable[name] = emb.tolist()
        else:
            serializable[name] = list(emb)
            
    # Save a backup of the current database before overwriting
    if os.path.exists(p):
        backup = p + ".bak"
        try:
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(p, backup)
        except OSError:
            pass

    with open(p, "wb") as f:
        pickle.dump(serializable, f)


# ── Main processing ──────────────────────────────────────────
def process_images(name, paths):
    """Full pipeline — identical detection/embedding to enroll.py + augmentation."""
    db = load_db()
    overwritten = name in db
    all_embeddings = []
    per_image = []
    target_total = 100

    aligned_faces = []
    for path in paths:
        bn = os.path.basename(path)
        frame = cv2.imread(path)
        print(f"DEBUG: path={path}, type={type(frame)}, hasattr_shape={hasattr(frame, 'shape')}", file=sys.stderr)
        if frame is not None and hasattr(frame, 'shape'):
            print(f"DEBUG: shape={frame.shape}, dtype={frame.dtype}", file=sys.stderr)
        if frame is None:
            per_image.append({"file": bn, "status": "error", "reason": f"Cannot read image (frame is None)"})
            continue

        face, box = detect_and_crop(frame, path)
        if face is None:
            per_image.append({"file": bn, "status": "no_face", "reason": "No face detected"})
            continue

        ok, msg = check_face_quality(frame, box)
        per_image.append({
            "file": bn,
            "status": "ok" if ok else "quality_warn",
            "reason": msg,
        })
        aligned_faces.append(face)

    # ── Fail if ANY photo has issues (no face, quality problem, read error) ──
    bad_images = [r for r in per_image if r["status"] != "ok"]
    if bad_images:
        pos_labels = ["Front", "Left", "Right", "Up", "Down"]
        summary_parts = []
        for i, r in enumerate(per_image):
            label = pos_labels[i] if i < len(pos_labels) else f"Photo {i+1}"
            if r["status"] == "ok":
                summary_parts.append(f"{label}: Passed")
            else:
                summary_parts.append(f"{label}: Failed — {r['reason']}")
        summary = " | ".join(summary_parts)
        return {
            "success": False,
            "message": f"Enrollment failed — {len(bad_images)} of {len(paths)} photos did not pass quality checks. Please ensure your face is clearly visible and centered in every position.",
            "details": {"per_image": per_image, "augmented_total": 0, "summary": summary},
        }

    if len(aligned_faces) < 3:
        return {
            "success": False,
            "message": f"Only {len(aligned_faces)} usable faces from {len(paths)} images. Need at least 3.",
            "details": {"per_image": per_image, "augmented_total": 0},
        }

    # Augment to ~100 images total
    aug_per_face = max(1, target_total // len(aligned_faces))
    all_face_images = []
    for face_112 in aligned_faces:
        augmented = augment_face(face_112, target_count=aug_per_face)
        all_face_images.extend(augmented)
    total_augmented = len(all_face_images)

    # Extract embeddings from ALL augmented images
    for face_img in all_face_images:
        emb = extract_embedding(face_img)
        all_embeddings.append(emb)

    if len(all_embeddings) == 0:
        return {
            "success": False,
            "message": "Failed to extract embeddings.",
            "details": {"per_image": per_image, "augmented_total": total_augmented},
        }

    # Average + normalize
    avg = np.mean(all_embeddings, axis=0)
    avg = avg / np.linalg.norm(avg)

    db[name] = avg
    save_db(db)
    
    # Sync with Supabase database
    save_embedding_to_db(name, avg)

    action = "updated" if overwritten else "enrolled"
    return {
        "success": True,
        "message": (
            f"{name} {action} successfully! "
            f"{len(aligned_faces)} captures -> {total_augmented} augmented -> "
            f"{len(all_embeddings)} embeddings averaged. "
            f"DB now has {len(db)} person(s)."
        ),
        "details": {
            "per_image": per_image,
            "aligned_faces": len(aligned_faces),
            "augmented_total": total_augmented,
            "embeddings_extracted": len(all_embeddings),
            "database_size": len(db),
            "overwritten": overwritten,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("__RESULT_JSON__" + json.dumps({
            "success": False,
            "message": "Usage: python web_enroll.py Name img1.jpg ..."
        }))
        sys.exit(1)

    student_name = sys.argv[1]
    image_files = sys.argv[2:]
    result = process_images(student_name, image_files)
    print("__RESULT_JSON__" + json.dumps(result))
    sys.exit(0 if result.get("success") else 1)
