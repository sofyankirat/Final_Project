import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
import joblib
import os

def train_and_save_models():
    print("Starting ML Model training...")
    
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "..", "Recommendation_System_Data", "Enrollments.csv")
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    # Load data
    df = pd.read_csv(data_path)
    
    # Subsample data to prevent CPU starvation and timeouts on shared cloud resources
    if len(df) > 10000:
        df = df.sample(n=10000, random_state=42)
    
    # Create classification target (Recommended = 1 if subject_score >= 75 else 0)
    df['recommended'] = (df['subject_score'] >= 75).astype(int)
    
    # Define feature groups
    categorical_features = [
        'student_gender', 'student_program', 'course_name', 'course_category',
        'is_required', 'professor_name', 'professor_program',
        'professor_academic_rank', 'professor_specialization'
    ]

    numeric_features = [
        'student_age', 'student_level', 'GPA', 'is_employed',
        'total_failed_subjects', 'discipline_score', 'analytical_score',
        'practical_score', 'avg_screen_hours', 'course_level',
        'course_difficulty', 'course_credit_hours', 'professor_avg_teaching_score',
        'professor_avg_pass_percentage', 'student_attendance_percentage_subject',
        'weekly_avg_study_hours_subject'
    ]

    all_features = categorical_features + numeric_features

    X = df[all_features]
    y_score = df['subject_score']
    y_rec = df['recommended']
    
    # Preprocessor
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numeric_features),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
        ]
    )

    # Regressor Pipeline
    reg_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1))
    ])

    # Classifier Pipeline
    clf_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1))
    ])
    
    print("Fitting Regressor model...")
    reg_pipeline.fit(X, y_score)
    reg_model_path = os.path.join(models_dir, "recommendation_regressor.joblib")
    joblib.dump(reg_pipeline, reg_model_path)
    print(f"Regressor model saved to {reg_model_path}")
    
    print("Fitting Classifier model...")
    clf_pipeline.fit(X, y_rec)
    clf_model_path = os.path.join(models_dir, "recommendation_classifier.joblib")
    joblib.dump(clf_pipeline, clf_model_path)
    print(f"Classifier model saved to {clf_model_path}")
    
    print("ML Model training completed successfully!")

if __name__ == "__main__":
    train_and_save_models()
