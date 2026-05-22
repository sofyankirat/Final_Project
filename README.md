<div align="center">
  <img src="front-end/app/static/images/Logo.jpg" alt="HAMAS Logo" width="420px" style="border-radius: 12px; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.15);">
  
  # HAMAS: Student Recommendation & Smart Attendance System
  
  **A comprehensive, AI-powered system integrating automated face recognition, a student analytics dashboard, personalized course recommendations, and an intelligent college advisor agent.**
</div>

---

## 🔍 Project Overview

The project is structured into two core components:
1. **🌐 Front-End Web Application (`front-end/`)**: A Flask-based web application providing a student dashboard, dark/light theme switching, interactive course schedules, recommendations, help pages, and the user interface for face enrollment and recognition logs.
2. **🧠 Smart Attendance System (`Smart-Attendance-System/`)**: An offline/online AI pipeline leveraging **YOLOv8s-Face** and **ArcFace** models to detect and align classroom faces, compute embedding similarity, and log student presence.

---

## ✨ Main Features

The Student Attendance and Recommendation System offers the following features:

* **🔒 Secure Authentication & Onboarding**: Fully integrated user signup, email verification via token, and secure login, followed by a personalized profile setup collection (First name, program, level, GPA, etc.).
* **📊 Interactive Analytics Dashboard**: Deep visual metrics representing weekly attendance, course-wise presence, performance analytics, and dynamic theme switching with dark mode optimization.
* **📷 Smart Face Capture Studio**: Real-time BlazeFace-assisted camera client checking head orientation to capture 5 training positions.
* **📈 Intelligent Course Advisor & Recommendations**: Customized machine learning-based course suggestions utilizing personal performance, GPA, program, failed subjects, and interest parameters.
* **💬 Personalized AI Advisor Chat**: Seamless, conversational AI agent with persisted conversation histories, multi-chat controls, and image attachments.
* **🗓️ Dynamic Course Scheduler**: Time conflict checking scheduler to register and manage weekly class slots.
* **✉️ Direct Support Contact System**: Standardized messaging contact form directly linked to administrators.

---

## 🚀 Step-by-Step Local Setup Guide

Follow these steps to download the project, open it in your code editor, and run both the web dashboard and the AI backend on your local machine. *Thanks to the integrated SQLite database layer, no complex MySQL or XAMPP setup is required!*

### 📋 Prerequisites
- **Python 3.11** (recommended version for machine learning compatibility)
- **Webcam** or WiFi-connected IoT camera
- **Git** (optional, for cloning)

---

### Step 1: Download the Project and Run the Web App (`front-end/`)

#### A. Download the Code to your Local Machine
* **Option A (Via Git Git Clone)**: Open your computer's terminal, navigate to the folder where you want to store the project, and run:
  ```bash
  git clone https://github.com/sofyankirat/Final_Project.git
  ```
* **Option B (Direct ZIP Download)**:
  1. Go to the GitHub repository: [https://github.com/sofyankirat/Final_Project](https://github.com/sofyankirat/Final_Project).
  2. Click the green **Code** button at the top right, then select **Download ZIP**.
  3. Locate the downloaded file on your computer and extract (unzip) it to a folder.

#### B. Open the Folder in Your Code Editor
1. Open your code editor (such as **Visual Studio Code**).
2. Go to **File** > **Open Folder...** and select the main extracted/cloned project folder (`Final_Project`).
3. Open a new terminal inside your editor (In VS Code, go to **Terminal** > **New Terminal** or press ``Ctrl + ` ``).

#### C. Configure and Run the Web Server
1. Navigate to the front-end folder:
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
   - Fill in your Gmail SMTP settings (used for verification emails):
     ```env
     SECRET_KEY=your_super_secret_key
     DB_NAME=student_system
     SMTP_SERVER=smtp.gmail.com
     SMTP_PORT=587
     EMAIL_ADDRESS=your_email@gmail.com
     EMAIL_PASSWORD=your_app_password
     HELP_RECEIVER_EMAIL=your_email@gmail.com
     ```
   - **💡 Easy Verification Shortcuts (No Inbox Needed)**:
     * **Auto-Verification Mode**: If you do not configure SMTP settings (or if email sending fails), the system will automatically verify newly registered users in the database so you can log in immediately.
     * **Developer Email Log**: When you register a user locally, the system writes the verification link directly to the local file `front-end/email_logs.txt`. You can just open this file, copy the verification link, and paste it into your browser to verify manually.
5. Launch the Flask web server:
   ```bash
   python app.py
   ```
   *The SQLite database file `student_system.db` and all required tables will be automatically created on its first run.* Open your browser to `http://127.0.0.1:5000`.

---

### Step 2: Configure and Run the AI Backend (Smart-Attendance-System/)

1. Open a new terminal window in your editor and navigate to the backend folder:
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

---

### 🌐 Live Online Demo
If you would like to try the AI system without running it locally, a live demonstration is hosted on Hugging Face:
🔗 **Live Demo**: [huggingface.co/spaces/Haneen13/smart-attendance-system](https://huggingface.co/spaces/Haneen13/smart-attendance-system)

