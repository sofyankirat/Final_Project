# web_enroll.py
# ============================================================
# Smart Attendance System — Web Enrollment Bridge
# Called by the Flask front-end to process captured images
# through the same YOLO + ArcFace pipeline used by enroll.py.
# ============================================================

import cv2
import numpy as np
import pickle
import os
import sys

# Resolve paths relative to this file's directory
_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Lazy-loaded singletons so the heavy model import happens only once per
# process lifetime.
# ---------------------------------------------------------------------------
_yolo_model = None
_arcface_session = None
_arcface_input_name = None


def _ensure_models():
    """Load YOLO + ArcFace exactly once (lazy singleton)."""
    global _yolo_model, _arcface_session, _arcface_input_name

    if _yolo_model is not None:
        return

    # Import config relative to Smart-Attendance-System directory
    sys.path.insert(0, _DIR)
    import config as sa_config

    # Resolve model paths relative to the Smart-Attendance-System folder
    yolo_path = sa_config.YOLO_PATH
    if not os.path.isabs(yolo_path):
        yolo_path = os.path.join(_DIR, yolo_path)

    arcface_path = sa_config.ARCFACE_PATH
    if not os.path.isabs(arcface_path):
        arcface_path = os.path.join(_DIR, arcface_path)

    if not os.path.exists(yolo_path):
        raise FileNotFoundError(f"YOLO model not found: {yolo_path}")
    if not os.path.exists(arcface_path):
        raise FileNotFoundError(f"ArcFace model not found: {arcface_path}")

    from ultralytics import YOLO  # type: ignore[import]
    import onnxruntime as ort  # type: ignore[import]

    _yolo_model = YOLO(yolo_path)
    _arcface_session = ort.InferenceSession(
        arcface_path, providers=['CPUExecutionProvider']
    )
    _arcface_input_name = _arcface_session.get_inputs()[0].name
    print("✅ [web_enroll] Models loaded")


def _get_config():
    """Return the Smart-Attendance-System config module."""
    sys.path.insert(0, _DIR)
    import config as sa_config
    return sa_config


# ---------------------------------------------------------------------------
# Core helpers (mirror logic from enroll.py / face_pipeline.py)
# ---------------------------------------------------------------------------

def _extract_embedding(face_img: np.ndarray) -> np.ndarray:
    """Extract 512-dim ArcFace embedding from a 112×112 face crop."""
    img = face_img[:, :, ::-1].astype(np.float32)   # BGR → RGB
    img = (img - 127.5) / 127.5
    img = np.transpose(img, (2, 0, 1))               # HWC → CHW
    img = np.expand_dims(img, axis=0)                 # add batch
    output = _arcface_session.run(None, {_arcface_input_name: img})
    return output[0][0]


def _detect_and_crop(frame: np.ndarray, padding: int = 20, img_size: int = 112):
    """Detect the largest face in *frame* and return a 112×112 crop."""
    results = _yolo_model(frame, verbose=False)
    boxes = results[0].boxes

    if boxes is None or len(boxes) == 0:
        return None

    # Pick the largest detected face
    areas = [
        (float(b.xyxy[0][2]) - float(b.xyxy[0][0])) *
        (float(b.xyxy[0][3]) - float(b.xyxy[0][1]))
        for b in boxes
    ]
    best_box = boxes[areas.index(max(areas))]
    x1, y1, x2, y2 = map(int, best_box.xyxy[0].tolist())
    h, w = frame.shape[:2]

    x1p = max(0, x1 - padding)
    y1p = max(0, y1 - padding)
    x2p = min(w, x2 + padding)
    y2p = min(h, y2 + padding)

    face = frame[y1p:y2p, x1p:x2p]
    if face.size == 0:
        return None

    return cv2.resize(face, (img_size, img_size))


# ---------------------------------------------------------------------------
# Public API used by the Flask route
# ---------------------------------------------------------------------------

def enroll_from_images(
    image_paths: list[str],
    student_name: str,
) -> dict:
    """
    Process a list of captured JPEG paths through the face pipeline,
    compute an averaged embedding, and save it into the attendance
    database pickle.

    Returns a dict: {'success': bool, 'message': str, 'details': {...}}
    """
    _ensure_models()
    cfg = _get_config()

    if not image_paths:
        return {'success': False, 'message': 'No images provided.', 'details': {}}

    embeddings: list[np.ndarray] = []
    per_image_results: list[dict] = []

    for path in image_paths:
        basename = os.path.basename(path)
        frame = cv2.imread(path)
        if frame is None:
            per_image_results.append({
                'file': basename,
                'status': 'error',
                'reason': 'Could not read image',
            })
            continue

        face = _detect_and_crop(frame, padding=cfg.PADDING, img_size=cfg.IMG_SIZE)
        if face is None:
            per_image_results.append({
                'file': basename,
                'status': 'no_face',
                'reason': 'No face detected in this image',
            })
            continue

        emb = _extract_embedding(face)
        embeddings.append(emb)
        per_image_results.append({
            'file': basename,
            'status': 'ok',
            'reason': 'Face detected and embedding extracted',
        })

    if len(embeddings) < 3:
        return {
            'success': False,
            'message': (
                f'Only {len(embeddings)} out of {len(image_paths)} images '
                f'had a detectable face. At least 3 are required.'
            ),
            'details': {'per_image': per_image_results},
        }

    # Average + L2-normalize
    avg_embedding = np.mean(embeddings, axis=0)
    avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

    # Load or create the pickle database
    db_path = cfg.DATABASE_PATH
    if not os.path.isabs(db_path):
        db_path = os.path.join(_DIR, db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    database: dict = {}
    if os.path.exists(db_path):
        with open(db_path, 'rb') as f:
            database = pickle.load(f)

    overwritten = student_name in database
    database[student_name] = avg_embedding

    with open(db_path, 'wb') as f:
        pickle.dump(database, f)

    action = 'updated' if overwritten else 'enrolled'
    return {
        'success': True,
        'message': (
            f"'{student_name}' {action} successfully with "
            f"{len(embeddings)}/{len(image_paths)} captures. "
            f"Database now has {len(database)} person(s)."
        ),
        'details': {
            'per_image': per_image_results,
            'embeddings_used': len(embeddings),
            'total_captures': len(image_paths),
            'database_size': len(database),
            'overwritten': overwritten,
        },
    }
