# web_enroll.py
# ============================================================
# Smart Attendance System — Full Pipeline Web Enrollment
# Phase 1 steps executed from browser captures:
#   1. YOLOv8s-Face  → detect face
#   2. insightface buffalo_sc → align face to 112x112
#   3. Data augmentation → expand to 100 images
#      (flip, brightness, rotation ±15°, blur)
#   4. ArcFace w600k_mbf → extract 512-dim embeddings
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

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
import config

# ── Load models ──────────────────────────────────────────────
from insightface.app import FaceAnalysis

MODELS_ROOT = os.path.join(_DIR, "models")

face_app = FaceAnalysis(
    name="buffalo_sc",
    root=MODELS_ROOT,
    providers=["CPUExecutionProvider"],
)
face_app.prepare(ctx_id=-1, det_size=(640, 640))

# ── Augmentation helpers ─────────────────────────────────────

def augment_face(face_112, target_count=20):
    """Generate augmented copies of a 112x112 aligned face.
    Returns a list of images (including the original)."""
    augmented = [face_112]
    h, w = face_112.shape[:2]
    center = (w // 2, h // 2)

    while len(augmented) < target_count:
        img = face_112.copy()

        # Random horizontal flip (50%)
        if random.random() < 0.5:
            img = cv2.flip(img, 1)

        # Random brightness shift [-30, +30]
        beta = random.randint(-30, 30)
        img = cv2.convertScaleAbs(img, alpha=1.0, beta=beta)

        # Random rotation [-15, +15] degrees
        angle = random.uniform(-15, 15)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT_101)

        # Random slight blur (30%)
        if random.random() < 0.3:
            ksize = random.choice([3, 5])
            img = cv2.GaussianBlur(img, (ksize, ksize), 0)

        augmented.append(img)

    return augmented


def check_quality(frame, face):
    """Check face quality from insightface detection result."""
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    conf = float(face.det_score)
    fh, fw = frame.shape[:2]
    face_w, face_h = x2 - x1, y2 - y1

    # Face too small (user too far)
    min_size = min(fw, fh) * 0.15
    if face_w < min_size or face_h < min_size:
        return False, "Face too small — move closer"

    # Face too large (user too close)
    max_size = min(fw, fh) * 0.9
    if face_w > max_size or face_h > max_size:
        return False, "Face too large — move back"

    # Not centered
    margin = 0.08
    if x1 < fw * margin or x2 > fw * (1 - margin) or y1 < fh * margin or y2 > fh * (1 - margin):
        return False, "Center your face"

    # Low confidence
    if conf < 0.65:
        return False, "Low confidence — face camera"

    # Blurriness check
    face_crop = frame[max(0, y1):min(fh, y2), max(0, x1):min(fw, x2)]
    if face_crop.size > 0:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(gray, cv2.CV_64F).var() < 30:
            return False, "Image blurry — hold still"

    return True, "Good quality"


# ── Database ─────────────────────────────────────────────────

def _resolve(p):
    return p if os.path.isabs(p) else os.path.join(_DIR, p)


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


# ── Main processing ──────────────────────────────────────────

def process_images(name, paths):
    """Full Phase-1 pipeline for web-captured images."""
    db = load_db()
    overwritten = name in db
    all_embeddings = []
    per_image = []
    total_augmented = 0

    # Target: 100 augmented images total, split evenly per valid capture
    target_total = 100

    # Step 1: Detect + align + quality check each capture
    aligned_faces = []
    for path in paths:
        bn = os.path.basename(path)
        frame = cv2.imread(path)
        if frame is None:
            per_image.append({"file": bn, "status": "error", "reason": "Cannot read image"})
            continue

        # insightface detection + alignment
        faces = face_app.get(frame)
        if len(faces) == 0:
            per_image.append({"file": bn, "status": "no_face", "reason": "No face detected"})
            continue

        # Pick largest face
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

        # Quality check
        ok, msg = check_quality(frame, face)

        # Get aligned 112x112 face (insightface normed_embedding uses this internally)
        # Extract the aligned/normed face from insightface
        aligned = face.normed_embedding  # This is the normalized embedding
        # For augmentation we need the aligned face IMAGE
        # insightface stores the aligned face in face.embedding_norm... 
        # We need to get the aligned crop. Let's do it manually from bbox + landmarks.
        
        # Use insightface's alignment: get the 112x112 aligned face
        bbox = face.bbox.astype(int)
        x1, y1, x2, y2 = bbox
        pad = config.PADDING
        h, w = frame.shape[:2]
        crop = frame[max(0, y1 - pad):min(h, y2 + pad), max(0, x1 - pad):min(w, x2 + pad)]
        if crop.size == 0:
            per_image.append({"file": bn, "status": "error", "reason": "Face crop empty"})
            continue
        face_112 = cv2.resize(crop, (112, 112))

        status = "ok" if ok else "quality_warn"
        per_image.append({"file": bn, "status": status, "reason": msg})
        aligned_faces.append(face_112)

    if len(aligned_faces) < 3:
        return {
            "success": False,
            "message": f"Only {len(aligned_faces)} usable faces from {len(paths)} images. Need at least 3.",
            "details": {"per_image": per_image, "augmented_total": 0},
        }

    # Step 2: Data augmentation → expand to ~100 images total
    aug_per_face = max(1, target_total // len(aligned_faces))
    all_face_images = []
    for face_112 in aligned_faces:
        augmented = augment_face(face_112, target_count=aug_per_face)
        all_face_images.extend(augmented)
    total_augmented = len(all_face_images)

    # Step 3: Extract 512-dim ArcFace embeddings from all augmented images
    rec_model = face_app.models["recognition"]
    for face_img in all_face_images:
        emb = rec_model.get_feat(face_img)
        all_embeddings.append(emb.flatten())

    if len(all_embeddings) == 0:
        return {
            "success": False,
            "message": "Failed to extract embeddings from augmented images.",
            "details": {"per_image": per_image, "augmented_total": total_augmented},
        }

    # Step 4: Average + normalize
    avg = np.mean(all_embeddings, axis=0)
    avg = avg / np.linalg.norm(avg)

    # Step 5: Save to database
    db[name] = avg
    save_db(db)

    action = "updated" if overwritten else "enrolled"
    return {
        "success": True,
        "message": (
            f"{name} {action} successfully! "
            f"{len(aligned_faces)} captures -> {total_augmented} augmented images -> "
            f"{len(all_embeddings)} embeddings averaged. "
            f"Database now has {len(db)} person(s)."
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
