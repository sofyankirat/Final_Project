-- Initial migration: create application schema
-- Generated from migration/supabase_schema.sql

-- enable pgvector when available (no-op if already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Users
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  is_verified BOOLEAN DEFAULT FALSE,
  verification_token TEXT,
  token_expiry TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_additional_info (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
  student_id TEXT,
  first_name TEXT NOT NULL,
  age INTEGER NOT NULL,
  program TEXT NOT NULL,
  gender TEXT NOT NULL,
  level INTEGER NOT NULL,
  is_working BOOLEAN DEFAULT FALSE,
  failed_subjects INTEGER DEFAULT 0,
  discipline_score INTEGER,
  analytical_score INTEGER,
  practical_score INTEGER,
  gpa NUMERIC(4, 2) NOT NULL,
  screen_hours NUMERIC(4, 1) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_course_schedule (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  course_name TEXT NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  days TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_recommendation_history (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  course_name TEXT NOT NULL,
  professor_name TEXT NOT NULL,
  study_hours NUMERIC(5, 2) NOT NULL,
  attendance_count INTEGER NOT NULL,
  score NUMERIC NOT NULL,
  recommended BOOLEAN NOT NULL,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS help_requests (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_tasks (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  task_text TEXT NOT NULL,
  is_completed BOOLEAN NOT NULL DEFAULT FALSE,
  task_date TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attendance (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  course_id INTEGER,
  attendance_date DATE,
  status BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS courses (
  course_id INTEGER PRIMARY KEY,
  course_name TEXT NOT NULL,
  course_code TEXT UNIQUE,
  professor TEXT,
  department TEXT,
  description TEXT,
  course_category TEXT,
  course_level INTEGER,
  course_difficulty INTEGER,
  course_credit_hours INTEGER,
  is_required BOOLEAN,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS professors (
  professor_id INTEGER PRIMARY KEY,
  professor_name TEXT NOT NULL,
  professor_program TEXT,
  professor_academic_rank TEXT,
  professor_specialization TEXT,
  professor_avg_teaching_score INTEGER,
  professor_avg_pass_percentage INTEGER,
  created_at TIMESTAMPTZ DEFAULT now()
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    CREATE TABLE IF NOT EXISTS embeddings (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      metadata JSONB,
      embedding vector(512),
      created_at TIMESTAMPTZ DEFAULT now()
    );
  ELSE
    CREATE TABLE IF NOT EXISTS embeddings_json (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      metadata JSONB,
      embedding JSONB,
      created_at TIMESTAMPTZ DEFAULT now()
    );
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_user_email ON users (lower(email));
CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance (user_id, attendance_date);
CREATE INDEX IF NOT EXISTS idx_course_code ON courses (course_code);
CREATE INDEX IF NOT EXISTS idx_user_course_schedule_user ON user_course_schedule (user_id);
CREATE INDEX IF NOT EXISTS idx_help_requests_user_created ON help_requests (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_user_tasks_user ON user_tasks (user_id);
