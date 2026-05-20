import pickle
import os

db_path = 'd:/Final_Project/Smart-Attendance-System/database/database.pkl'
if not os.path.exists(db_path):
    print("Database file database.pkl does not exist yet. Please enroll a user first.")
else:
    with open(db_path, 'rb') as f:
        db = pickle.load(f)
    print(f"Total Enrolled Users: {len(db)}")
    print("-" * 50)
    for name, emb in db.items():
        if hasattr(emb, 'shape'):
            shape_str = f"numpy array of shape {emb.shape}"
        else:
            shape_str = f"type {type(emb)}"
        print(f"User: {name}")
        print(f"  Embedding details: {shape_str}")
        print(f"  First 5 values: {emb[:5]}")
        print("-" * 50)