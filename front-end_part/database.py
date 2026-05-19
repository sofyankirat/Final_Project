"""
Database Configuration and Helper Functions
"""

import mysql.connector  # type: ignore[import]
from mysql.connector import Error  # type: ignore[import]
from dotenv import load_dotenv  # type: ignore[import]
import os

load_dotenv()

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'student_system'),
}

class User:
    """User model"""
    def __init__(self, email, password):
        self.email = email
        self.password = password

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print("Database connection successful")
            return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

def init_db():
    """Initialize database and create tables"""
    try:
        connection = get_db_connection()
        if connection is None:
            print("Could not connect to database")
            return False
        
        cursor = connection.cursor()
        
        # Create users table
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            is_verified BOOLEAN DEFAULT FALSE,
            verification_token VARCHAR(255),
            token_expiry DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_users_table)
        
        # Create attendance table
        create_attendance_table = """
        CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            course_id INT,
            attendance_date DATE,
            status BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_attendance_table)
        
        # Create courses table
        create_courses_table = """
        CREATE TABLE IF NOT EXISTS courses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_name VARCHAR(255) NOT NULL,
            course_code VARCHAR(50) UNIQUE NOT NULL,
            professor VARCHAR(255),
            department VARCHAR(255),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_courses_table)
        
        # Create recommendations table
        create_recommendations_table = """
        CREATE TABLE IF NOT EXISTS recommendations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            course_id INT NOT NULL,
            recommendation_score FLOAT,
            recommendation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_recommendations_table)

        # Create additional user profile info table
        create_user_additional_info_table = """
        CREATE TABLE IF NOT EXISTS user_additional_info (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            first_name VARCHAR(100) NOT NULL,
            age INT NOT NULL,
            program VARCHAR(255) NOT NULL,
            gender VARCHAR(50) NOT NULL,
            level INT NOT NULL,
            is_working BOOLEAN NOT NULL DEFAULT FALSE,
            failed_subjects INT NOT NULL DEFAULT 0,
            discipline_score INT NOT NULL,
            analytical_score INT NOT NULL,
            practical_score INT NOT NULL,
            gpa DECIMAL(4,2) NOT NULL,
            screen_hours DECIMAL(4,1) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_user_additional_info_table)

        # Create AI chat state table (persisted conversation history per user)
        create_ai_chat_state_table = """
        CREATE TABLE IF NOT EXISTS user_ai_chat_state (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            chat_data LONGTEXT NOT NULL,
            chat_counter INT NOT NULL DEFAULT 1,
            current_chat_id VARCHAR(100) NOT NULL DEFAULT 'chat_1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_ai_chat_state_table)

        # Create recommendation history table (persisted recommendation runs per user)
        create_recommendation_history_table = """
        CREATE TABLE IF NOT EXISTS user_recommendation_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(500) NOT NULL,
            course_name VARCHAR(255) NOT NULL,
            professor_name VARCHAR(255) NOT NULL,
            study_hours DECIMAL(5,2) NOT NULL,
            attendance_count INT NOT NULL,
            score FLOAT NOT NULL,
            recommended BOOLEAN NOT NULL,
            reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_recommendation_history_user_created (user_id, created_at)
        )
        """
        cursor.execute(create_recommendation_history_table)

        # Create help requests table (messages from Help page)
        create_help_requests_table = """
        CREATE TABLE IF NOT EXISTS help_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            email VARCHAR(255) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_help_requests_user_created (user_id, created_at)
        )
        """
        cursor.execute(create_help_requests_table)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("Database initialized successfully")
        return True
    
    except Error as e:
        print(f"Error initializing database: {e}")
        return False

def create_database_if_not_exists():
    """Create database if it doesn't exist"""
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.close()
        connection.close()
        print(f"Database '{DB_CONFIG['database']}' created or already exists")
    except Error as e:
        print(f"Error creating database: {e}")

# Create database on import
create_database_if_not_exists()
