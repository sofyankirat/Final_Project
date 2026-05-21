<div align="center">
  <img src="front-end/app/static/images/Logo.jpg" alt="HAMAS Logo" width="220px" style="border-radius: 12px; margin-bottom: 20px;">
  
  # HAMAS: Student Recommendation & Smart Attendance System
  
  **A comprehensive, AI-powered system integrating automated face recognition, a student analytics dashboard, personalized course recommendations, and an intelligent college advisor agent.**
</div>

---

## 🔍 Project Overview

The project is structured into two core components:
1. **🌐 Front-End Web Application (`front-end/`)**: A Flask-based web application providing a student dashboard, dark/light theme switching, interactive course schedules, recommendations, help pages, and the user interface for face enrollment and recognition logs.
2. **🧠 Smart Attendance System (`Smart-Attendance-System/`)**: An offline/online AI pipeline leveraging **YOLOv8s-Face** and **ArcFace** models to detect and align classroom faces, compute embedding similarity, and log student presence.

---

## ✨ Features Added & System Refinements

The following enhancements, visual optimizations, and bug fixes were added to the codebase:

### 1. 🎨 Premium Redesign & Theme Harmonization
- **Theme Consistency**: Applied a global cohesive color palette. Dark mode icons and badges across the **Student Recommendation** page now match the primary brand color.
- **Improved Layouts & Typography**:
  - Refactored form fields on the **Recommendations** and **Help (Contact Us)** pages to ensure user inputs do not touch the boundaries (added proper inner padding).
  - Designed responsive card layouts with dynamic hover animations.
- **Interactive Team Visualizations**: Implemented canvas-based S-curve interactive animated connectors on the **Our Team** page to link team members dynamically to the central brand logo.
- **AI Agent Chat Cursor**: Replaced the basic image hover magnifying cursor on the **AI Agent** chat page with a more creative and professional custom preview interface.

### 2. 🛡️ Robust Face Capture & Overwriting Logic
- **Embeddings Overwrite on Re-Enrollment**: Updated `enroll.py` and front-end endpoints so that re-enrolling a student with 5 new face positions successfully replaces the existing embeddings in `database.pkl` instead of generating conflicts.
- **Client-Side Face Validation**: Embedded a client-side BlazeFace model to validate the student's face angle and orientation before capturing each frame.
- **Fixed Infinite Reload Loops**: Solved front-end script race conditions on the attendance dashboard.

### 3. 🧹 Clean Syntax & Validation Fixes
- **Zero ESLint Warnings**: Removed all unused JavaScript variables and bound global event handlers to the `window` object in `attendance.html` to ensure perfect lint checks.
- **Standardized Attributes**: Moved dynamic Jinja tags out of HTML `style="..."` attributes and into standard `class` names and `data-*` properties to prevent VS Code compiler warnings.
- **Pyright Type Checking Fixes**: Solved all python static analysis type issues on OpenCV constants (`cv2.CV_64F`) and dynamically imported models.

---

## 🚀 Step-by-Step Local Setup Guide

Follow these steps to run both the web dashboard and the AI backend on your local machine:

### 📋 Prerequisites
- **Python 3.11** (recommended version for machine learning compatibility)
- **MySQL Server** (local server instance or via XAMPP)
- **Webcam** or WiFi-connected IoT camera

---

### Step 1: Set Up MySQL Database
Create a database named `student_system`.
- **Using local MySQL Command Line**:
  ```sql
  CREATE DATABASE student_system;
  ```
- **Using XAMPP (phpMyAdmin)**:
  1. Start the **MySQL** module from the XAMPP Control Panel.
  2. Open `http://localhost/phpmyadmin` in your browser.
  3. Create a new database named `student_system`.

---

### Step 2: Configure and Run the Web App (`front-end/`)

1. Open your terminal and navigate to the front-end folder:
   ```bash
   cd front-end
   ```
2. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the web dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create your configuration `.env` file:
   - Copy `.env.example` to `.env`
   - Fill in your MySQL credentials and Gmail SMTP settings:
     ```env
     SECRET_KEY=your_super_secret_key
     DB_HOST=localhost
     DB_USER=root
     DB_PASSWORD=your_mysql_password
     DB_NAME=student_system
     SMTP_SERVER=smtp.gmail.com
     SMTP_PORT=587
     EMAIL_ADDRESS=your_email@gmail.com
     EMAIL_PASSWORD=your_app_password
     HELP_RECEIVER_EMAIL=your_email@gmail.com
     ```
5. Launch the Flask web server:
   ```bash
   python app.py
   ```
   *The application will automatically create the necessary database tables on its first run.* Open your browser to `http://127.0.0.1:5000`.

---

### Step 3: Configure and Run the AI Backend (`Smart-Attendance-System/`)

1. Open a new terminal and navigate to the backend folder:
   ```bash
   cd Smart-Attendance-System
   ```
2. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the AI dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: If `insightface` installation fails, run: `pip install insightface --only-binary=:all:`*

4. Download the Model Weights:
   Download the following model files and place them inside the `Smart-Attendance-System/models/` folder:
   - **YOLOv8s-Face**: Download `yolov8s-face-lindevs.pt` from [lindevs releases](https://github.com/lindevs/yolov8-face/releases).
   - **ArcFace**: Download `buffalo_sc.zip` from [insightface releases](https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip), extract it, and place `w600k_mbf.onnx` inside the models folder.

5. Run local scripts:
   - **Enroll Students**:
     ```bash
     python enroll.py
     ```
     Enter the student's name and capture 5 different head angles (press SPACE for each capture).
   - **Start Attendance Monitoring**:
     ```bash
     python main.py
     ```
     Press `Q` to exit the camera screen and log attendance to `logs/attendance_log.csv`.
