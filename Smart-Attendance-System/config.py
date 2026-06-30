# Smart Attendance System — Configuration
# All tunable parameters in one place

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CAMERA_SOURCE = 0
# 0           = laptop built-in webcam
# 1           = external USB webcam
# "http://192.168.1.100/video" = ESP32-CAM IoT camera
# "rtsp://192.168.1.100:554"   = IP camera

YOLO_PATH = os.path.join(BASE_DIR, "models", "yolov8s-face-lindevs.pt")
ARCFACE_PATH = os.path.join(BASE_DIR, "models", "w600k_mbf.onnx")
# Support persistent storage directory (e.g. Railway volume mounts)
db_dir = os.getenv('SQLITE_DB_DIR')
if db_dir:
    DATABASE_PATH = os.path.join(db_dir, "database.pkl")
else:
    DATABASE_PATH = os.path.join(BASE_DIR, "database", "database.pkl")
LOG_PATH = os.path.join(BASE_DIR, "logs", "attendance_log.csv") # Output path

# RECOGNETION
THRESHOLD = 0.15

#Face_processing 
PADDING = 20    # pixels added around detected face bounding box
IMG_SIZE = 112   # ArcFace standard input size

#DETECTION 
DETECTION_CONF = 0.5    # minimum YOLO confidence to accept a detection

#DISPLAY 
COLOR_NEW      = (0, 255, 0)    # Green  → just marked present
COLOR_REPEAT   = (0, 255, 255)  # Yellow → already marked
COLOR_UNKNOWN  = (0, 0, 255)    # Red    → not recognized
FONT           = 0              # cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE     = 0.6
FONT_THICKNESS = 2