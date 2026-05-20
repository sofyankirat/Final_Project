# Student Recommendation and Attendance System

A comprehensive web-based system to help students with course recommendations, attendance tracking, and an AI assistant for college information.

## Features

### 1. **User Authentication System**
   - User registration with email verification
# Student Recommendation and Attendance System

A Flask web app for student dashboarding, course recommendations, attendance insights, an AI Agent, and a Help contact page.

## Main features

- User registration and email verification
- Dashboard with overview cards and analytics placeholders
- Recommendation system with history
- Attendance visualizations
- AI Agent chat interface
- Help page with feature guide and contact form

## Local setup

### 1) Clone the project

```bash
git clone https://github.com/your-username/your-repository-name.git
cd your-repository-name
```

Or open the project folder directly in VS Code if you already have it on your machine.

### 2) Create a virtual environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Create a `.env` file

Copy `.env.example` to `.env` and fill in your own values.

```env
SECRET_KEY=replace-with-a-strong-secret-key
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=student_system
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password
HELP_RECEIVER_EMAIL=www.sofyankirat123@gmail.com
```

### 5) Start MySQL

Make sure MySQL Server is running. The app creates the database tables automatically on first launch.

## If MySQL is not installed on the machine

This project needs MySQL to run fully. If MySQL is missing, follow these steps:

### Option A: Install MySQL Community Server

1. Download MySQL Community Server from:
   https://dev.mysql.com/downloads/mysql/
2. Install it on the machine.
3. During setup, choose a root password and keep it safe.
4. Make sure the MySQL service is running.
5. Open MySQL Workbench or the MySQL command line.
6. Create the database if needed:

```sql
CREATE DATABASE student_system;
```

7. Update the `.env` file with the correct MySQL details:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=student_system
```

8. Run the project:

```bash
python app.py
```

### Option B: Install XAMPP and use its MySQL

1. Download XAMPP from:
   https://www.apachefriends.org/
2. Install XAMPP.
3. Open the XAMPP Control Panel.
4. Start **MySQL**.
5. Open phpMyAdmin in the browser:

```text
http://localhost/phpmyadmin
```

6. Create the database `student_system`.
7. Put the XAMPP MySQL settings into `.env`.
8. Run the Flask app with `python app.py`.

### Option C: If you do not want to install MySQL at all

The project will not work fully without a database server. In that case, the code must be converted from MySQL to SQLite before it can run on a machine with no MySQL installation.

SQLite is easier for beginners because:

- it does not need a separate server
- it works with built-in Python tools
- it is easier to run on any machine

If you want the project to work without MySQL, the database layer must be changed first.

### 6) Run the app

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

## Important project files

- `app.py` — Flask routes and email logic
- `database.py` — database connection and table creation
- `app/templates/` — HTML pages
- `app/static/css/` — styles
- `app/static/js/` — browser scripts

## How to upload to GitHub

### 1) Initialize Git

```bash
git init
git add .
git commit -m "Initial commit"
```

### 2) Create a repository on GitHub

Create a new empty repository on GitHub. Do not add a README from GitHub if this project already has one locally.

### 3) Connect and push

```bash
git branch -M main
git remote add origin https://github.com/your-username/your-repository-name.git
git push -u origin main
```

If the remote already exists, use:

```bash
git remote set-url origin https://github.com/your-username/your-repository-name.git
git push -u origin main
```

## Notes

- Do not upload `.env` to GitHub.
- Keep your Gmail app password private.
- Use a strong `SECRET_KEY`.

## License

Educational use only.
