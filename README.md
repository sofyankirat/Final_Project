<div align="center">
  <img src="front-end/app/static/images/banar.webp" alt="HAMAS Banner" width="100%" style="border-radius: 12px; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.15);">
  
  # HAMAS: Student Recommendation & Smart Attendance System
  
  **A comprehensive, AI-powered system integrating automated face recognition, a student analytics dashboard, personalized course recommendations, and an intelligent college advisor agent.**
</div>

---

## Project Overview

The project is structured into two core components:
1. **Front-End Web Application (`front-end/`)**: A Flask-based web application providing a student dashboard, theme switching, interactive course schedules, recommendations, help pages, and the user interface for face enrollment and recognition logs.
2. **Smart Attendance System (`Smart-Attendance-System/`)**: An offline/online AI pipeline leveraging **YOLOv8s-Face** and **ArcFace** models to detect and align classroom faces, compute embedding similarity, and log student presence.

---

## Main Features

The Student Attendance and Recommendation System offers the following features:

- **Secure Authentication & Onboarding**: Fully integrated user signup, email verification via token, and secure login, followed by a personalized profile setup collection (first name, program, level, GPA, etc.).
- **Interactive Analytics Dashboard**: Visual metrics representing weekly attendance, course-wise presence, performance analytics, and theme switching with dark mode optimization.
- **Smart Face Capture Studio**: Real-time BlazeFace-assisted camera client checking head orientation to capture multiple training positions.
- **Intelligent Course Advisor & Recommendations**: Customized course suggestions utilizing personal performance, GPA, program, failed subjects, and interest parameters.
- **Personalized AI Advisor Chat**: Conversational AI agent with persisted conversation histories, multi-chat controls, and image attachments.
- **Dynamic Course Scheduler**: Time conflict checking scheduler to register and manage weekly class slots.
- **Direct Support Contact System**: Standardized messaging contact form directly linked to administrators.

---

## Step-by-Step Local Setup Guide

Follow these steps to download the project, open it in your code editor, and run both the web dashboard and the AI backend on your local machine. The integrated SQLite database layer removes the need for external DB servers.

### Prerequisites
- **Python 3.11** (recommended for ML compatibility)
- **Webcam** or WiFi-connected IoT camera
- **Git** (optional, for cloning)

---

### A. Download the Code to your Local Machine

**Option A (Via Git Clone):** Open your computer's terminal, navigate to the folder where you want to store the project, and run:
```bash
git clone https://github.com/sofyankirat/Final_Project.git
```

**Option B (Direct ZIP Download):**
1. Go to the GitHub repository: https://github.com/sofyankirat/Final_Project.
2. Click the green **Code** button at the top right, then select **Download ZIP**.
3. Locate the downloaded file on your computer and extract (unzip) it to a folder.

### B. Open the Folder in Your Code Editor

1. Open your code editor (such as **Visual Studio Code**).
2. Go to **File** > **Open Folder...** and select the main extracted/cloned project folder (`Final_Project`).
3. Open a new terminal inside your editor (In VS Code, go to **Terminal** > **New Terminal** or press ``Ctrl + ` ``).

### C. Configure and Run the Web Server

#### 1. In `final_project` folder
Create and activate a virtual environment:

**Windows**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 2. Install all the requirements
```bash
pip install -r requirements.txt
```

#### 3. Navigate to the front-end folder:
```bash
cd front-end
```

#### 4. Launch the Flask web server:
```bash
python app.py
```

---

### Step 2 Configure and Run (Smart-Attendance-System/)

1. Open a new terminal window in your editor and navigate to the backend folder:
```bash
cd Smart-Attendance-System
```

**Run local scripts:**

2. **Enroll Students:**
```bash
python enroll.py
```
Enter the student's name and capture multiple head angles (press **SPACE** for each capture).

**Start Attendance Monitoring:**
```bash
python main.py
```
Press **Q** to exit the camera screen and log attendance to `logs/attendance_log.csv`.

---

### Live Online Demo

If you would like to try the AI system without running it locally, a live demonstration is hosted on Hugging Face:

**Live Demo:** https://huggingface.co/spaces/Haneen13/smart-attendance-system
