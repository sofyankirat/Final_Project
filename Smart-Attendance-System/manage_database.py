# manage_database.py
# ============================================================
# Smart Attendance System — Database Manager
# Manage enrolled students:
#   [d] Delete a student
#   [c] Clear all students
#   [l] List all students
#   [q] Quit
# ============================================================

import pickle
import os
import config

def manage_db():
    # Check database exists
    if not os.path.exists(config.DATABASE_PATH):
        print(f"❌ Database not found at: {config.DATABASE_PATH}")
        print("   Run enroll.py first to create a database.")
        return

    # Load database
    with open(config.DATABASE_PATH, "rb") as f:
        database = pickle.load(f)

    while True:
        print("\n" + "="*50)
        print("  DATABASE MANAGER")
        print("="*50)
        print(f"  Total enrolled: {len(database)} persons")
        print("-"*50)

        # List all names
        if not database:
            print("  Database is empty.")
        else:
            names = sorted(database.keys())
            for i, name in enumerate(names, 1):
                print(f"  {i:2d}. {name}")

        print("-"*50)
        print("  [d] Delete a student")
        print("  [c] Clear all students")
        print("  [q] Quit")
        print("-"*50)

        choice = input("  Select option: ").lower().strip()

        # ── Delete one student ──
        if choice == 'd':
            target = input("  Enter exact name to delete: ").strip()
            if target in database:
                confirm = input(f"  Delete '{target}'? (y/n): ").strip()
                if confirm.lower() == 'y':
                    del database[target]
                    with open(config.DATABASE_PATH, "wb") as f:
                        pickle.dump(database, f)
                    print(f"  ✅ '{target}' deleted successfully.")
                else:
                    print("  Cancelled.")
            else:
                print(f"  ❌ '{target}' not found.")
                print("     Check spelling and capitalization.")

        # ── Clear all ──
        elif choice == 'c':
            confirm = input("  ⚠️  Delete ALL students? (y/n): ").strip()
            if confirm.lower() == 'y':
                database = {}
                with open(config.DATABASE_PATH, "wb") as f:
                    pickle.dump(database, f)
                print("  ✅ Database cleared.")
            else:
                print("  Cancelled.")

        # ── Quit ──
        elif choice == 'q':
            print("  Goodbye! 👋")
            break

        else:
            print("  ❌ Invalid option. Choose d, c, or q.")


if __name__ == "__main__":
    manage_db()