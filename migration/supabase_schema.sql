-- Supabase/Postgres schema for the app (adapted from existing SQLite schema)
-- Optional: enable pgvector for embeddings (requires service role)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS users (
  id serial PRIMARY KEY,
  email text UNIQUE NOT NULL,
  password text NOT NULL,
  is_verified boolean DEFAULT false,
  verification_token text,
  token_expiry timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS user_additional_info (
  id serial PRIMARY KEY,
  user_id integer REFERENCES users(id) ON DELETE CASCADE,
  student_id text,
  first_name text NOT NULL,
  age integer NOT NULL,
  program text NOT NULL,
  gender text NOT NULL,
  level integer NOT NULL,
  is_working boolean DEFAULT false,
  failed_subjects integer DEFAULT 0,
  discipline_score integer,
  analytical_score integer,
  practical_score integer,
  gpa numeric(4, 2) NOT NULL,
  screen_hours numeric(4, 1) NOT NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS user_course_schedule (
  id serial PRIMARY KEY,
  user_id integer REFERENCES users(id) ON DELETE CASCADE,
  course_name text NOT NULL,
  start_time time NOT NULL,
  end_time time NOT NULL,
  days text NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS user_recommendation_history (
  id serial PRIMARY KEY,
  user_id integer REFERENCES users(id) ON DELETE CASCADE,
  title text NOT NULL,
  course_name text NOT NULL,
  professor_name text NOT NULL,
  study_hours numeric(5, 2) NOT NULL,
  attendance_count integer NOT NULL,
  score numeric NOT NULL,
  recommended boolean NOT NULL,
  reason text NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS help_requests (
  id serial PRIMARY KEY,
  user_id integer REFERENCES users(id) ON DELETE CASCADE,
  email text NOT NULL,
  subject text NOT NULL,
  message text NOT NULL,
  status text NOT NULL DEFAULT 'new',
  created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS user_tasks (
  id serial PRIMARY KEY,
  user_id integer REFERENCES users(id) ON DELETE CASCADE,
  task_text text NOT NULL,
  is_completed boolean NOT NULL DEFAULT false,
  task_date text,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS attendance (
  id serial PRIMARY KEY,
  user_id integer REFERENCES users(id) ON DELETE CASCADE,
  course_id integer,
  attendance_date date,
  status boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);
-- Store raw courses table (from CSV)
CREATE TABLE IF NOT EXISTS courses (
  course_id integer PRIMARY KEY,
  course_name text NOT NULL,
  course_code text UNIQUE,
  professor text,
  department text,
  description text,
  course_category text,
  course_level integer,
  course_difficulty integer,
  course_credit_hours integer,
  is_required boolean,
  created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS professors (
  professor_id integer PRIMARY KEY,
  professor_name text NOT NULL,
  professor_program text,
  professor_academic_rank text,
  professor_specialization text,
  professor_avg_teaching_score integer,
  professor_avg_pass_percentage integer,
  created_at timestamptz DEFAULT now()
);
-- Embeddings table (pgvector extension required for vector type)
-- If pgvector is not available, you can store embeddings as jsonb in a separate column.
DO $$ BEGIN IF EXISTS (
  SELECT 1
  FROM pg_extension
  WHERE extname = 'vector'
) THEN CREATE TABLE IF NOT EXISTS embeddings (
  id serial PRIMARY KEY,
  name text NOT NULL,
  metadata jsonb,
  embedding vector(512),
  created_at timestamptz DEFAULT now()
);
ELSE CREATE TABLE IF NOT EXISTS embeddings_json (
  id serial PRIMARY KEY,
  name text NOT NULL,
  metadata jsonb,
  embedding jsonb,
  created_at timestamptz DEFAULT now()
);
END IF;
END $$;