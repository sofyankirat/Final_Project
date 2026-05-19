print("Start Running ..........")
#------------------------------------------
# Runs the real-time attendance camera loop
#------------------------------------------

import cv2
import config
from face_pipeline import (
    load_models,
    detect_faces,
    align_face,
    extract_embedding,
    find_match,
    log_attendance,
    draw_on_frame,
    print_summary
)

# ---------------
# LOAD ALL MODELS
# ---------------
yolo_detection_model, face_app_embedding, database = load_models()

#  Track who is marked present this session
attendance_logged = set() # using set() so when the student already marked skip

# -----------
# OPEN CAMERA
#------------
cap = cv2.VideoCapture(config.CAMERA_SOURCE)

if not cap.isOpened():
    print("❌ Cannot open camera — check CAMERA_SOURCE in config.py")
    exit()

print("✅ Camera opened")
print("Press Q to quit and see session summary\n")

# ---------------------
#  processes every frame
# ---------------------
while True:

    # Read frame from camera 
    ret, frame = cap.read()
    if not ret:
        print("❌ Cannot read frame — camera disconnected")
        break

    #  Step 1: Detect all faces in frame 
    boxes = detect_faces(frame, yolo_detection_model)

    # Process each detected face 
    for box in boxes:

        #  Step 2: Align face to 112x112 
        face, (x1, y1, x2, y2) = align_face(frame, box)
        if face is None:
            continue

        #  Step 3: Extract ArcFace embedding 
        embedding = extract_embedding(face, face_app_embedding)

        # Step 4: Match against database
        name, score = find_match(embedding, database)

        # Step 5: Log attendance
        newly_logged = log_attendance(name, score, attendance_logged)

        #  Step 6: Draw result on frame
        frame = draw_on_frame(frame,
                              x1, y1, x2, y2,
                              name, score,
                              newly_logged,
                              attendance_logged)

    # Show attendance counter on screen
    counter_text = f"Present: {len(attendance_logged)}/{len(database)}"
    cv2.putText(frame, counter_text,
                (10, 35),
                config.FONT, 0.9,
                (255, 255, 255), 2)

    # Display the frame
    cv2.imshow("Smart Attendance System", frame)

    # ── Press Q to quit ──
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

#-------
#SUMMARY
#-------
cap.release()
cv2.destroyAllWindows()
print_summary(attendance_logged, database.keys())
