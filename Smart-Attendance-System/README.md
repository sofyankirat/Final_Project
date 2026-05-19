# 🎓 Smart Attendance System

> **Automated Face Recognition Attendance using YOLOv8 + ArcFace**

Graduation Project , Faculty of Computers and Information Science, Mansoura University 2026

🌐 **Live Demo:** [huggingface.co/spaces/Haneen13/smart-attendance-system](https://huggingface.co/spaces/Haneen13/smart-attendance-system)

---

## 🔍 Overview

An AI-powered system that automatically marks student attendance by recognizing all faces in a classroom frame simultaneously. No manual roll call.

The project has two parts:

🖥️ **Local Script** runs on a laptop connected to a camera. It detects all faces at once, matches them against an enrolled database, and logs attendance to CSV.

🌐 **Web Application** (`Smart_Attendence_system_APP/`) is a Flask website deployed on Hugging Face Spaces with a live demo, enrollment interface, and REST API.

---

## ⚙️ Pipeline
```
Phase 1 — Offline Preprocessing (Google Colab)
──────────────────────────────────────────────
Raw Photos (classmates + LFW dataset)
    ↓
Data Cleaning
  → HEIC to JPG conversion
  → Uppercase extension fix
  → Fake JPG detection and fix
    ↓
YOLOv8s-Face → Detect faces (100% success rate)
    ↓
insightface buffalo_sc → Align faces to 112x112
    ↓
Data Augmentation → expand to 100 images/classmate
  (flip, brightness, rotation +-15 degrees, blur)
    ↓
ArcFace w600k_mbf → Extract 512-dim embeddings
    ↓
Average embeddings per person → Save database.pkl

Phase 2 — Real-Time Attendance (VS Code / Python)
──────────────────────────────────────────────────
Camera Frame
    ↓
YOLOv8s-Face → Detect ALL faces simultaneously
    ↓
Crop + Resize to 112x112
    ↓
ArcFace w600k_mbf → Extract 512-dim embedding
    ↓
Cosine Similarity vs database.pkl 
    ↓
Mark present + Log to CSV
```

---



---

## 📁 Project Structure

```
Smart-Attendance-System/
│
├──  Smart_Attendence_system_APP/    Web application (Hugging Face)
│   ├── templates/index.html           Website with embedded CSS and JS
│   ├── app.py                         Flask routes and REST API
│   ├── config.py                      Web app settings
│   ├── face_pipeline.py               AI pipeline for web
│   ├── Dockerfile                     Container for Hugging Face deployment
│   └── requirements.txt               Web app dependencies
│
│
├── config.py              # All settings in one place
├── face_pipeline.py       # Complete AI pipeline functions
├── main.py                # Real-time attendance camera loop
├── enroll.py              # Enroll new students (no retraining)
├── manage_database.py     # Add, delete, clear enrolled students
│
├── requirements.txt       # Python dependencies
├── .gitignore
├── README.md
│
├── models/                # Download separately (see below)
│   ├── yolov8s-face-lindevs.pt
│   └── w600k_mbf.onnx
│
├── database/              # private data or enroll.py
│   └── database.pkl
│
└── logs/                  # Created automatically when running
    └── attendance_log.csv
```
## 🗂️ File Descriptions

| File | Description |
|------|-------------|
| `config.py` | All tunable settings — only file you need to edit |
| `face_pipeline.py` | Core AI functions: detect, align, embed, match, log, draw |
| `main.py` | Real-time camera loop — runs the attendance system |
| `enroll.py` | Enrolls new students with face quality checks |
| `manage_database.py` | View, delete, or clear enrolled students |


> ⚠️ **Not in repo:** `Models/` (download separately), `database/` (private student data), `logs/` (private attendance records)

---

## 🚀 Installation — Local Script

**Requirements:** Python 3.11, webcam or IoT camera

```bash
git clone https://github.com/Haneenmohammed1311/Smart-Attendance-System.git
cd Smart-Attendance-System

py -3.11 -m venv venv
venv\Scripts\activate          # Windows


pip install -r requirements.txt
```

> 💡 If insightface fails: `pip install insightface --only-binary=:all:`

### 📥 Download Model Weights

```
🔷 YOLOv8s-Face (21 MB)
   Source  : https://github.com/lindevs/yolov8-face/releases
   Save to : models/yolov8s-face-lindevs.pt

🔷 ArcFace w600k_mbf (65 MB)
   Source  : https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip
   Extract : w600k_mbf.onnx
   Save to : models/w600k_mbf.onnx
```

---

## 🎯 Usage — Local Script

**👤 Enroll students**
```bash
python enroll.py
```
- Enter student full name
- Follow quality guide on screen (like Face ID):
  - Face must be centered in frame
  - Not too close or too far from camera
  - Look directly at camera
  - Hold still — no blur allowed
- Press SPACE 5 times to capture
- Student added to database instantly — no retraining needed

**📸 Run attendance**
```bash
python main.py
```
All faces in the frame are recognized simultaneously. Color code on screen: 
🟢 Green means just marked present, 
🟡 Yellow means already marked, 
🔴 Red means unknown. Press Q to quit and see session summary.

**🗃️ Manage database**
```bash
python manage_database.py
```

**🔧 Switch camera source** edit `config.py`:
```python
CAMERA_SOURCE = 0                              # Laptop webcam
CAMERA_SOURCE = "http://192.168.1.100/video"   # IoT camera via WiFi
```

---

## 🌐 Installation — Web Application

```bash
cd Smart_Attendence_system_APP

py -3.11 -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

python app.py
# Open: http://localhost:7860
```
---
## 🔧 Configuration

All settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `THRESHOLD` | `0.3` | Cosine similarity threshold |
| `CAMERA_SOURCE` | `0` | Camera input |
| `YOLO_PATH` | `models/yolov8s-face-lindevs.pt` | YOLOv8 weights path |
| `ARCFACE_PATH` | `models/w600k_mbf.onnx` | ArcFace weights path |
| `DATABASE_PATH` | `database/database.pkl` | Embeddings database path |
| `LOG_PATH` | `logs/attendance_log.csv` | Attendance output path |
| `PADDING` | `20` | Pixels added around detected face |
| `IMG_SIZE` | `112` | ArcFace input size (always 112) |
| `DETECTION_CONF` | `0.5` | Minimum YOLO confidence |
---

## 🔌 REST API

| Method | Endpoint | Description |
|---|---|---|
| POST | /recognize | Upload frame, detect all faces, return names and annotated image |
| POST | /enroll/capture | One capture per call, call 5 times with quality check |
| POST | /enroll/save | Average 5 embeddings and save to database |
| POST | /enroll/cancel | Clear incomplete enrollment buffer |
| GET | /attendance | Get today's attendance log |
| GET | /database | List all enrolled students |
| DELETE | /database/name | Remove a student from database |

---

## 🛠️ Technologies

| Component | Tool | Purpose |
|-----------|------|---------|
| Face Detection | YOLOv8s-Face (lindevs, 2023) | Detect faces in frame |
| Face Alignment | insightface buffalo_sc | Align to 112x112 (Colab preprocessing) |
| Face Embedding | ArcFace w600k_mbf (CVPR 2019) | Extract 512-dim identity vector |
| Similarity Matching | Cosine Similarity | Match query embedding vs database |
| Camera Interface | OpenCV VideoCapture | Read webcam or IoT camera frames |
| Model Runtime | ONNX Runtime | Run .onnx models on CPU |
| Preprocessing | Google Colab | Data pipeline and embedding extraction |
| Deployment | VS Code + Python 3.11 | Real-time attendance script |
|  Web Framework | Flask |
|  Deployment | Hugging Face Spaces + Docker |

---

## 📦 Deployment on Hugging Face

Flask on Hugging Face Spaces requires Docker. The `Dockerfile` is included in `Smart_Attendence_system_APP/`.

The app listens on port 7860. Model files are uploaded separately via the Hugging Face Files tab using Git LFS.

---

## 📚 Key Papers

| Paper | Authors | Venue |
|---|---|---|
| ArcFace: Additive Angular Margin Loss | Deng et al. | CVPR 2019 |
| YOLOv8 | Jocher, Chaurasia, Qiu | Ultralytics 2023 |

---


## 📄 License

Academic and research use only.
Model weights follow the [InsightFace non-commercial license](https://github.com/deepinsight/insightface)