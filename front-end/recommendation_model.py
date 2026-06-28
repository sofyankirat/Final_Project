import os
import pandas as pd
import numpy as np
import joblib
import requests

# Cache for loaded resources
_courses_map = None
_professors_map = None
_regressor_model = None
_classifier_model = None

def normalize_name(name):
    """Normalize names to prevent punctuation and casing mismatches."""
    if not name:
        return ""
    return "".join(c.lower() for c in name if c.isalnum())

def _load_resources():
    global _courses_map, _professors_map, _regressor_model, _classifier_model
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Load Courses
    if _courses_map is None:
        courses_path = os.path.join(base_dir, "..", "Recommendation_System_Data", "Courses.csv")
        if os.path.exists(courses_path):
            courses_df = pd.read_csv(courses_path)
            _courses_map = {}
            for _, row in courses_df.iterrows():
                norm = normalize_name(row['course_name'])
                _courses_map[norm] = {
                    'course_id': row['course_id'],
                    'course_name': row['course_name'],
                    'course_category': row['course_category'],
                    'course_level': int(row['course_level']),
                    'course_difficulty': int(row['course_difficulty']),
                    'course_credit_hours': int(row['course_credit_hours']),
                    'is_required': row['is_required']
                }
        else:
            _courses_map = {}

    # Load Professors
    if _professors_map is None:
        professors_path = os.path.join(base_dir, "..", "Recommendation_System_Data", "Professors.csv")
        if os.path.exists(professors_path):
            professors_df = pd.read_csv(professors_path)
            _professors_map = {}
            for _, row in professors_df.iterrows():
                norm = normalize_name(row['professor_name'])
                _professors_map[norm] = {
                    'professor_id': int(row['professor_id']),
                    'professor_name': row['professor_name'],
                    'professor_program': row['professor_program'],
                    'professor_academic_rank': row['professor_academic_rank'],
                    'professor_specialization': row['professor_specialization'],
                    'professor_avg_teaching_score': int(row['professor_avg_teaching_score']),
                    'professor_avg_pass_percentage': int(row['professor_avg_pass_percentage'])
                }
        else:
            _professors_map = {}

    # Load Models
    import sys
    if _regressor_model is None:
        model_path = os.path.join(base_dir, "models", "recommendation_regressor.joblib")
        if os.path.exists(model_path):
            try:
                _regressor_model = joblib.load(model_path)
            except Exception as e:
                import traceback
                print(f"DEBUG ERROR: Failed to load regressor model: {e}", file=sys.stderr)
                traceback.print_exc()
            
    if _classifier_model is None:
        model_path = os.path.join(base_dir, "models", "recommendation_classifier.joblib")
        if os.path.exists(model_path):
            try:
                _classifier_model = joblib.load(model_path)
            except Exception as e:
                import traceback
                print(f"DEBUG ERROR: Failed to load classifier model: {e}", file=sys.stderr)
                traceback.print_exc()

def get_course_details(course_name):
    _load_resources()
    norm = normalize_name(course_name)
    return _courses_map.get(norm, None)

def get_professor_details(professor_name):
    _load_resources()
    norm = normalize_name(professor_name)
    return _professors_map.get(norm, None)

def predict_recommendation(student_info, course_name, professor_name, study_hours, attendance_percentage):
    """
    Run predictions for score and recommendation label.
    student_info: dict containing age, gender, level, program, gpa, is_working, 
                  failed_subjects, discipline_score, analytical_score, practical_score, screen_hours
    """
    _load_resources()
    
    # 1. Look up course and professor properties
    course_details = get_course_details(course_name)
    prof_details = get_professor_details(professor_name)
    
    if not course_details:
        raise ValueError(f"Course '{course_name}' details could not be found.")
    if not prof_details:
        raise ValueError(f"Professor '{professor_name}' details could not be found.")
        
    # 2. Construct the single prediction row dataframe
    input_data = {
        'student_gender': student_info['gender'],
        'student_program': student_info['program'],
        'course_name': course_details['course_name'],
        'course_category': course_details['course_category'],
        'is_required': course_details['is_required'],
        'professor_name': prof_details['professor_name'],
        'professor_program': prof_details['professor_program'],
        'professor_academic_rank': prof_details['professor_academic_rank'],
        'professor_specialization': prof_details['professor_specialization'],
        'student_age': int(student_info['age']),
        'student_level': int(student_info['level']),
        'GPA': float(student_info['gpa']),
        'is_employed': int(student_info['is_working']),
        'total_failed_subjects': int(student_info['failed_subjects']),
        'discipline_score': int(student_info['discipline_score']),
        'analytical_score': int(student_info['analytical_score']),
        'practical_score': int(student_info['practical_score']),
        'avg_screen_hours': float(student_info['screen_hours']),
        'course_level': int(course_details['course_level']),
        'course_difficulty': int(course_details['course_difficulty']),
        'course_credit_hours': int(course_details['course_credit_hours']),
        'professor_avg_teaching_score': int(prof_details['professor_avg_teaching_score']),
        'professor_avg_pass_percentage': int(prof_details['professor_avg_pass_percentage']),
        'student_attendance_percentage_subject': int(attendance_percentage),
        'weekly_avg_study_hours_subject': float(study_hours)
    }
    
    df_input = pd.DataFrame([input_data])
    
    # 3. Predict continuous score (Model A)
    try:
        if _regressor_model:
            pred_score = float(_regressor_model.predict(df_input)[0])
        else:
            # Fallback heuristic
            pred_score = 70.0 + (float(student_info['gpa']) * 5.0) + (float(study_hours) * 1.5)
    except Exception as model_err:
        print(f"ML Regressor predict error, using fallback heuristic: {model_err}")
        pred_score = 70.0 + (float(student_info['gpa']) * 5.0) + (float(study_hours) * 1.5)
        
    # Apply weights / adjustment to make study hours, attendance, and difficulty highly dynamic
    attendance = float(attendance_percentage)
    hours = float(study_hours)
    difficulty = float(course_details['course_difficulty'])
    
    # Reference points
    attendance_ref = 85.0
    hours_ref = 6.0
    difficulty_ref = 3.0  # Medium difficulty
    
    # Adjustments (highly responsive)
    attendance_adj = (attendance - attendance_ref) * 0.6
    hours_adj = (hours - hours_ref) * 2.5
    difficulty_adj = (difficulty_ref - difficulty) * 2.5  # harder courses drop score, easier ones raise it
    
    pred_score = pred_score + attendance_adj + hours_adj + difficulty_adj
    pred_score = max(0.0, min(100.0, pred_score))
    
    # 4. Predict recommended label (Model B)
    # To prevent conflicting results and ensure the recommendation matches the adjusted performance score,
    # we determine recommendation status directly based on the adjusted score (threshold of 75.0).
    pred_rec = pred_score >= 75.0
        
    return {
        'score': pred_score,
        'recommended': pred_rec,
        'features': input_data
    }

def generate_llm_reasoning(prediction_results):
    """
    Generate natural language reasoning explaining the recommendation.
    """
    features = prediction_results['features']
    score = prediction_results['score']
    recommended = prediction_results['recommended']
    
    rec_str = "Recommended" if recommended else "Not Recommended"
    
    # Map numeric difficulty to descriptive text
    difficulty_map = {
        1: "very easy",
        2: "easy",
        3: "medium",
        4: "hard",
        5: "very hard"
    }
    course_diff_val = int(features.get('course_difficulty', 3))
    course_diff_str = difficulty_map.get(course_diff_val, "medium")
    
    # Build structured prompt
    prompt = f"""
As a human university academic advisor, write a supportive, professional, and personalized recommendation summary for a student.

Student details:
- Academic Program: {features['student_program']} (Level {features['student_level']})
- GPA: {features['GPA']}
- Analytical Score: {features['analytical_score']}/10
- Practical Score: {features['practical_score']}/10
- Failed subjects count: {features['total_failed_subjects']}
- Employed status: {"Yes" if features['is_employed'] == 1 else "No"}

Course details:
- Course name: {features['course_name']} ({features['course_category']})
- Course difficulty: {course_diff_str}
- Credit hours: {features['course_credit_hours']} hrs
- Status: {features['is_required']}

Professor details:
- Professor name: {features['professor_name']}
- Average Teaching rating: {features['professor_avg_teaching_score']}/10
- Historical class pass rate: {features['professor_avg_pass_percentage']}%

Planned inputs:
- Planned weekly study hours: {features['weekly_avg_study_hours_subject']} hrs
- Planned class attendance: {features['student_attendance_percentage_subject']}%

Outcome to justify:
- Estimated course performance score: {score:.1f}%
- Advisor Recommendation status: {rec_str}

Please write a concise 2-3 sentence reasoning summary. Make sure to:
1. Talk directly to the student as their advisor (use "you" and "your").
2. Explain how their profile (e.g. GPA, analytical/practical scores, study hours, attendance) aligns with this advisor recommendation status.
3. CRITICAL: Do NOT mention "machine learning", "model", "algorithm", "AI system", "predictive analysis", "data analysis", "training", or similar terms. Write the recommendation as if you are a human academic advisor giving direct feedback.
4. CRITICAL: Do NOT say "Based on the analysis" or "Our system predicts". Start directly or with advisor feedback.
5. CRITICAL: Use the descriptive difficulty level "{course_diff_str}" (do NOT use numbers like "3/5" or "1/5" for difficulty).
6. Keep the output as a single paragraph of plain text (no markdown formatting, bolding, or lists).
"""

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Try loading from local environment/dotenv
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        
    if api_key:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": "You are a university academic advisor. Keep responses short (under 75 words), direct, and positive without markdown bolding or styling."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.5,
                "max_tokens": 150
            }
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=8.0)
            if response.status_code == 200:
                data = response.json()
                reasoning = data['choices'][0]['message']['content'].strip()
                if reasoning:
                    return reasoning
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            
    # Fallback reasoning generator
    if recommended:
        reasoning = (
            f"You are estimated to perform excellently in {features['course_name']} with an expected score of {score:.1f}%. "
            f"Your solid GPA ({features['GPA']:.2f}) and strong analytical score ({features['analytical_score']}/10) make you well-prepared for this course, which has a {course_diff_str} difficulty level. "
            f"Your commitment to {features['student_attendance_percentage_subject']}% attendance and {features['weekly_avg_study_hours_subject']:g} study hours per week with Professor {features['professor_name']} will position you for success."
        )
    else:
        reasoning = (
            f"You might face some challenges in {features['course_name']} with an estimated score of {score:.1f}%. "
            f"Given that this course has a {course_diff_str} difficulty level and Professor {features['professor_name']}'s historical class pass rate is {features['professor_avg_pass_percentage']}%, "
            f"we advise increasing your planned study hours beyond {features['weekly_avg_study_hours_subject']:g} hours per week and utilizing tutoring resources to support your performance."
        )
        
    return reasoning
