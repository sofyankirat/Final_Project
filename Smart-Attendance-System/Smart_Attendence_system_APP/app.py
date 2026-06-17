# app.py
# ============================================================
# Smart Attendance System — FastAPI Web Application
# ============================================================

from fastapi import FastAPI, Request, File, UploadFile, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import numpy as np
import pickle
import cv2
import os
import csv
import base64
import onnxruntime as ort
from ultralytics import YOLO
from datetime import datetime
import config
import httpx
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

def _resolve_model_path(path):
    if os.path.exists(path):
        return path

    candidate_names = [os.path.basename(path), path]
    candidate_roots = [
        os.path.dirname(os.path.abspath(__file__)),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"),
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)),
        os.path.join(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)), "models"),
    ]
    for root in candidate_roots:
        for name in candidate_names:
            candidate = os.path.join(root, name)
            if os.path.exists(candidate):
                return candidate
    return path

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))

# ============================================================
# LOAD MODELS
# ============================================================
print("Loading models...")

yolo_model = YOLO(_resolve_model_path(config.YOLO_PATH))
session    = ort.InferenceSession(
                _resolve_model_path(config.ARCFACE_PATH),
                providers=['CPUExecutionProvider'])
input_name = session.get_inputs()[0].name


def load_database():
    if os.path.exists(config.DATABASE_PATH):
        with open(config.DATABASE_PATH, "rb") as f:
            return pickle.load(f)
    return {}


database          = load_database()
enrollment_buffer = {}   # { name: [emb1, emb2, ...] }

print(f"Ready — {len(database)} persons enrolled")

# ============================================================
# HELPERS
# ============================================================

def extract_embedding(face_img):
    img = face_img[:, :, ::-1].astype(np.float32)
    img = (img - 127.5) / 127.5
    img = np.transpose(img, (2, 0, 1))
    img = np.expand_dims(img, axis=0)
    return session.run(None, {input_name: img})[0][0]


def detect_all_faces(frame):
    """Detect ALL faces — for recognition"""
    results = yolo_model(frame, verbose=False)
    boxes   = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return []
    faces = []
    h, w  = frame.shape[:2]
    for box in boxes:
        conf = float(box.conf[0])
        if conf < config.DETECTION_CONF:
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        x1p = max(0, x1 - config.PADDING)
        y1p = max(0, y1 - config.PADDING)
        x2p = min(w, x2 + config.PADDING)
        y2p = min(h, y2 + config.PADDING)
        crop = frame[y1p:y2p, x1p:x2p]
        if crop.size == 0:
            continue
        face = cv2.resize(crop, (config.IMG_SIZE, config.IMG_SIZE))
        faces.append((face, (x1, y1, x2, y2), conf))
    return faces


def detect_best_face(frame):
    """Detect largest face only — for enrollment"""
    results = yolo_model(frame, verbose=False)
    boxes   = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None, None
    areas    = [(float(b.xyxy[0][2]) - float(b.xyxy[0][0])) *
                (float(b.xyxy[0][3]) - float(b.xyxy[0][1]))
                for b in boxes]
    best_box = boxes[areas.index(max(areas))]
    conf     = float(best_box.conf[0])
    if conf < 0.5:
        return None, None
    x1, y1, x2, y2 = map(int, best_box.xyxy[0].tolist())
    h, w = frame.shape[:2]
    x1p = max(0, x1 - config.PADDING)
    y1p = max(0, y1 - config.PADDING)
    x2p = min(w, x2 + config.PADDING)
    y2p = min(h, y2 + config.PADDING)
    face = frame[y1p:y2p, x1p:x2p]
    if face.size == 0:
        return None, None
    return cv2.resize(face, (config.IMG_SIZE, config.IMG_SIZE)), (x1, y1, x2, y2)


def find_match(query_embedding):
    if not database:
        return "Unknown", 0.0
    best_match, best_score = "Unknown", -1
    query = query_embedding / np.linalg.norm(query_embedding)
    for person, stored_emb in database.items():
        sim = np.dot(query, stored_emb)
        if sim > best_score:
            best_score, best_match = sim, person
    if best_score < config.THRESHOLD:
        return "Unknown", float(best_score)
    return best_match, float(best_score)


def log_attendance(name, score):
    os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)
    now         = datetime.now()
    file_exists = os.path.exists(config.LOG_PATH)
    with open(config.LOG_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Name", "Date", "Time", "Confidence"])
        writer.writerow([name, now.strftime("%Y-%m-%d"),
                         now.strftime("%H:%M:%S"), f"{score:.3f}"])


def draw_all_results(frame, results):
    for item in results:
        name  = item['name']
        score = item['confidence']
        x1, y1, x2, y2 = item['box']
        color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label    = f"{name.split()[0]} {score:.2f}"
        font     = cv2.FONT_HERSHEY_SIMPLEX
        txt_size = cv2.getTextSize(label, font, 0.6, 2)[0]
        cv2.rectangle(frame, (x1, y1 - txt_size[1] - 12),
                      (x1 + txt_size[0] + 4, y1), color, -1)
        cv2.putText(frame, label, (x1 + 2, y1 - 5), font, 0.6, (0, 0, 0), 2)
    _, buf = cv2.imencode('.jpg', frame)
    return base64.b64encode(buf).decode('utf-8')


async def report_attendance_session(student_ids: List[str], course_id: Optional[str]):
    url = os.environ.get("FLASK_BACKEND_URL", "http://localhost:5000/api/attendance/session")
    payload = {
        "student_ids": student_ids,
        "course_id": course_id
    }
    print(f"Sending session attendance to backend webhook ({url}): {payload}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            print(f"Backend webhook response: status={response.status_code}, body={response.text}")
        except Exception as e:
            print(f"Error calling backend webhook: {e}")

# ============================================================
# WEBSITE
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "total_persons": len(database),
        "persons": sorted(database.keys())
    })

# ============================================================
# RECOGNIZE — ALL FACES
# ============================================================

@app.post("/recognize")
async def recognize_face(file: UploadFile = File(...)):
    contents = await file.read()
    nparr    = np.frombuffer(contents, np.uint8)
    frame    = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return JSONResponse({"error": "Invalid image"}, status_code=400)

    faces = detect_all_faces(frame)
    if not faces:
        return {
            "total_faces": 0,
            "results": [],
            "annotated": None,
            "message": "No faces detected"
        }

    results, logged = [], set()
    for face_img, (x1, y1, x2, y2), conf in faces:
        embedding   = extract_embedding(face_img)
        name, score = find_match(embedding)
        if name != "Unknown" and name not in logged:
            log_attendance(name, score)
            logged.add(name)
        results.append({"name":name,"confidence":round(score,3),
                        "status":"present" if name!="Unknown" else "unknown",
                        "box":[x1,y1,x2,y2]})

    annotated = draw_all_results(frame.copy(), results)
    clean     = [{"name":r["name"],"confidence":r["confidence"],
                  "status":r["status"]} for r in results]

    return {
        "total_faces": len(results),
        "results": clean,
        "annotated": annotated,
        "message": f"Detected {len(results)} face(s)"
    }

# ============================================================
# ENROLL — 5-CAPTURE FLOW
# ============================================================

@app.post("/enroll/capture")
async def enroll_capture(name: str = Form(...), file: UploadFile = File(...)):
    global enrollment_buffer
    name = name.strip()
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)

    contents = await file.read()
    nparr    = np.frombuffer(contents, np.uint8)
    frame    = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return JSONResponse({"error": "Invalid image"}, status_code=400)

    face, box = detect_best_face(frame)
    current   = len(enrollment_buffer.get(name, []))

    if face is None:
        return {
            "success": False,
            "message": "No face detected — look directly at the camera",
            "captured": current
        }

    gray       = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < 30:
        return {
            "success": False,
            "message": "Image too blurry — hold still",
            "captured": current
        }

    embedding = extract_embedding(face)
    if name not in enrollment_buffer:
        enrollment_buffer[name] = []
    enrollment_buffer[name].append(embedding)

    captured = len(enrollment_buffer[name])
    needed   = 5

    return {
        "success": True,
        "captured": captured,
        "needed": needed,
        "done": captured >= needed,
        "message": f"Capture {captured}/{needed} accepted" if captured < needed else "All 5 captures done"
    }


@app.post("/enroll/save")
async def enroll_save(request: Request, name: Optional[str] = Form(None)):
    global database, enrollment_buffer

    if name is None:
        try:
            data = await request.json()
            name = (data.get('name', '') if data else '').strip()
        except Exception:
            name = ''
    else:
        name = name.strip()

    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)

    captures = enrollment_buffer.get(name, [])
    if len(captures) < 5:
        return JSONResponse({
            "error": f"Need 5 captures, only have {len(captures)}"
        }, status_code=400)

    avg = np.mean(captures, axis=0)
    avg = avg / np.linalg.norm(avg)

    database[name] = avg
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    with open(config.DATABASE_PATH, "wb") as f:
        pickle.dump(database, f)

    if name in enrollment_buffer:
        del enrollment_buffer[name]

    return {
        "success": True,
        "message": f"'{name}' enrolled successfully!",
        "total_enrolled": len(database)
    }


@app.post("/enroll/cancel")
async def enroll_cancel(request: Request, name: Optional[str] = Form(None)):
    global enrollment_buffer
    if name is None:
        try:
            data = await request.json()
            name = (data.get('name', '') if data else '').strip()
        except Exception:
            name = ''
    else:
        name = name.strip()

    if name in enrollment_buffer:
        del enrollment_buffer[name]
    return {"success": True}

# ============================================================
# REAL-TIME WEBSOCKET CAMERA STREAM
# ============================================================

@app.websocket("/ws/camera-stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[SUCCESS] Camera streaming WebSocket connected")
    
    course_id = websocket.query_params.get("course_id")
    session_attended_ids = set()
    
    try:
        while True:
            # Receive binary frame (JPEG bytes)
            frame_bytes = await websocket.receive_bytes()
            
            # Decode JPEG bytes to OpenCV frame
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                faces = detect_all_faces(frame)
                for face_img, _, _ in faces:
                    embedding = extract_embedding(face_img)
                    name, score = find_match(embedding)
                    
                    if name != "Unknown":
                        session_attended_ids.add(name)
                        print(f"Recognized: {name} (score: {score:.3f})")
                        
    except WebSocketDisconnect:
        print("[DISCONNECT] Camera streaming WebSocket disconnected")
        if session_attended_ids:
            print(f"Reporting attendance for session: {list(session_attended_ids)}")
            await report_attendance_session(list(session_attended_ids), course_id)

# ============================================================
# OTHER ROUTES
# ============================================================

@app.get("/attendance")
async def get_attendance():
    if not os.path.exists(config.LOG_PATH):
        return {"date": datetime.now().strftime("%Y-%m-%d"), "records": [], "total": 0}
    today, records = datetime.now().strftime("%Y-%m-%d"), []
    with open(config.LOG_PATH, 'r') as f:
        for row in csv.DictReader(f):
            if row.get("Date") == today:
                records.append(row)
    return {"date": today, "records": records, "total": len(records)}


@app.get("/database")
async def get_database_students():
    return {"total": len(database), "students": sorted(database.keys())}


@app.delete("/database/{name}")
async def delete_student(name: str):
    global database
    if name not in database:
        raise HTTPException(status_code=404, detail=f"'{name}' not found")
    del database[name]
    with open(config.DATABASE_PATH, "wb") as f:
        pickle.dump(database, f)
    return {
        "success": True,
        "message": f"'{name}' deleted",
        "remaining": len(database)
    }

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host='0.0.0.0', port=port)