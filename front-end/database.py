"""
Database Configuration and Helper Functions using SQLite
"""

import sqlite3
from sqlite3 import Error
from dotenv import load_dotenv  # type: ignore[import]
import os

load_dotenv()

# Database Configuration (for compatibility)
DB_CONFIG = {
    'database': os.getenv('DB_NAME', 'student_system'),
}

class User:
    """User model"""
    def __init__(self, email, password):
        self.email = email
        self.password = password

class SQLiteCursorWrapper:
    """Wrapper to map %s parameters to SQLite's ? parameters"""
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        if query:
            query = query.replace('%s', '?')
        if params is not None:
            if isinstance(params, list):
                params = tuple(params)
            return self.cursor.execute(query, params)
        else:
            return self.cursor.execute(query)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        self.cursor.close()

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    @property
    def description(self):
        return self.cursor.description

class SQLiteConnectionWrapper:
    """Wrapper for SQLite connection"""
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return SQLiteCursorWrapper(self.connection.cursor())

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

class PostgresCursorWrapper:
    """Wrapper to map insert results and translate schema SQL for Postgres"""
    def __init__(self, cursor):
        self.cursor = cursor
        self._lastrowid = None

    def execute(self, query, params=None):
        if not query:
            return self.cursor.execute(query, params)
            
        # Translate SQLite-specific table creation queries to PostgreSQL
        query_upper = query.upper()
        if "CREATE TABLE" in query_upper:
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            query = query.replace("LONGTEXT", "TEXT")
            query = query.replace("DATETIME", "TIMESTAMP")
            
        q_strip = query.strip()
        is_insert = q_strip.upper().startswith("INSERT")
        
        if is_insert and "RETURNING" not in q_strip.upper():
            if q_strip.endswith(";"):
                q_strip = q_strip[:-1]
            q_strip += " RETURNING id"
            res = self.cursor.execute(q_strip, params)
            try:
                row = self.cursor.fetchone()
                if row:
                    self._lastrowid = row[0]
            except Exception:
                pass
            return res
        else:
            return self.cursor.execute(query, params)

    @property
    def lastrowid(self):
        return self._lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        self.cursor.close()

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def description(self):
        return self.cursor.description


class PostgresConnectionWrapper:
    """Wrapper for PostgreSQL connection"""
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return PostgresCursorWrapper(self.connection.cursor())

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def get_db_connection():
    """Create and return a database connection (Supabase PostgreSQL or SQLite fallback)"""
    supabase_url = os.getenv('SUPABASE_URL')
    supa_pass = os.getenv('SUPA_PASS')
    
    if supabase_url and supa_pass:
        try:
            # Extract reference ID from https://ref_id.supabase.co
            cleaned = supabase_url.replace("https://", "").replace("http://", "")
            ref_id = cleaned.split('.')[0]
            host = f"db.{ref_id}.supabase.co"
            
            import psycopg2
            connection = psycopg2.connect(
                host=host,
                database="postgres",
                user="postgres",
                password=supa_pass,
                port="5432",
                connect_timeout=10
            )
            return PostgresConnectionWrapper(connection)
        except Exception as e:
            print(f"Failed to connect to Supabase PostgreSQL: {e}. Falling back to SQLite.")

    # SQLite Fallback
    try:
        db_name = DB_CONFIG['database']
        db_file = f"{db_name}.db"
        
        # Support SQLITE_DB_DIR env var for persistent storage (e.g. Railway volume mounts)
        db_dir = os.getenv('SQLITE_DB_DIR')
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, db_file)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, db_file)
        
        connection = sqlite3.connect(db_path, timeout=30.0)
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.execute("PRAGMA journal_mode = WAL;")
        
        return SQLiteConnectionWrapper(connection)
    except Error as e:
        print(f"Error while connecting to SQLite: {e}")
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            is_verified BOOLEAN DEFAULT FALSE,
            verification_token VARCHAR(255),
            token_expiry DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_users_table)
        
        # Create attendance table
        create_attendance_table = """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            student_id VARCHAR(100),
            first_name VARCHAR(100) NOT NULL,
            age INTEGER NOT NULL,
            program VARCHAR(255) NOT NULL,
            gender VARCHAR(50) NOT NULL,
            level INTEGER NOT NULL,
            is_working BOOLEAN NOT NULL DEFAULT FALSE,
            failed_subjects INTEGER NOT NULL DEFAULT 0,
            discipline_score INTEGER NOT NULL,
            analytical_score INTEGER NOT NULL,
            practical_score INTEGER NOT NULL,
            gpa DECIMAL(4,2) NOT NULL,
            screen_hours DECIMAL(4,1) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_user_additional_info_table)

        # Check if student_id column exists, if not, add it (for existing databases)
        is_postgres = isinstance(connection, PostgresConnectionWrapper)
        if not is_postgres:
            try:
                cursor.execute("SELECT student_id FROM user_additional_info LIMIT 1")
            except Exception:
                try:
                    cursor.execute("ALTER TABLE user_additional_info ADD COLUMN student_id VARCHAR(100)")
                except Exception as ae:
                    print(f"Error migrating student_id: {ae}")

        # Create AI chat state table (persisted conversation history per user)
        create_ai_chat_state_table = """
        CREATE TABLE IF NOT EXISTS user_ai_chat_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            chat_data LONGTEXT NOT NULL,
            chat_counter INTEGER NOT NULL DEFAULT 1,
            current_chat_id VARCHAR(100) NOT NULL DEFAULT 'chat_1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_ai_chat_state_table)

        # Create recommendation history table (persisted recommendation runs per user)
        create_recommendation_history_table = """
        CREATE TABLE IF NOT EXISTS user_recommendation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title VARCHAR(500) NOT NULL,
            course_name VARCHAR(255) NOT NULL,
            professor_name VARCHAR(255) NOT NULL,
            study_hours DECIMAL(5,2) NOT NULL,
            attendance_count INTEGER NOT NULL,
            score FLOAT NOT NULL,
            recommended BOOLEAN NOT NULL,
            reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_recommendation_history_table)
        
        # Create separate index for recommendation history
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_hist_user_created ON user_recommendation_history (user_id, created_at)")

        # Create help requests table (messages from Help page)
        create_help_requests_table = """
        CREATE TABLE IF NOT EXISTS help_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email VARCHAR(255) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_help_requests_table)
        
        # Create separate index for help requests
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_help_req_user_created ON help_requests (user_id, created_at)")

        # Create user course schedule table
        create_course_schedule_table = """
        CREATE TABLE IF NOT EXISTS user_course_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_name VARCHAR(255) NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            days VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_course_schedule_table)
        
        # Create separate index for course schedule
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_course_sched_user ON user_course_schedule (user_id)")

        # Create user tasks table
        create_user_tasks_table = """
        CREATE TABLE IF NOT EXISTS user_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            is_completed BOOLEAN NOT NULL DEFAULT FALSE,
            task_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        cursor.execute(create_user_tasks_table)
        
        # Add task_date column if it doesn't exist (backward compatibility)
        if not is_postgres:
            try:
                cursor.execute("ALTER TABLE user_tasks ADD COLUMN task_date TEXT")
            except Exception:
                pass
        
        # Create separate index for user tasks
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_user ON user_tasks (user_id)")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("Database initialized successfully")
        return True
    
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

def create_database_if_not_exists():
    """For SQLite, database file is created automatically on connect."""
    pass

# Create database on import
create_database_if_not_exists()
