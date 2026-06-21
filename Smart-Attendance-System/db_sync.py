# db_sync.py
# ============================================================
# Smart Attendance System — Supabase Embeddings Synchronization
# ============================================================

import os
import sys
import pickle
import numpy as np
import psycopg2
from urllib.parse import urlparse

# Add parent directory to path to make sure we can import config
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
import config

def get_supabase_connection():
    """Establish and return connection to Supabase PostgreSQL database."""
    supabase_url = os.getenv('SUPABASE_URL')
    supa_pass = os.getenv('SUPA_PASS')

    if not supabase_url or not supa_pass:
        # Try loading from .env files
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_DIR, '.env'))
        load_dotenv(os.path.join(_DIR, '..', '.env'))
        load_dotenv(os.path.join(_DIR, '..', 'front-end', '.env'))
        supabase_url = os.getenv('SUPABASE_URL')
        supa_pass = os.getenv('SUPA_PASS')

    if not supabase_url or not supa_pass:
        print("[!] Supabase credentials not found in environment or .env files.")
        return None

    try:
        host = os.getenv('SUPABASE_HOST')
        port = os.getenv('SUPABASE_PORT', '5432')
        if not host:
            # Extract reference ID from URL: https://ref_id.supabase.co
            cleaned = supabase_url.replace("https://", "").replace("http://", "")
            ref_id = cleaned.split('.')[0]
            host = f"db.{ref_id}.supabase.co"

        conn = psycopg2.connect(
            host=host,
            database="postgres",
            user="postgres",
            password=supa_pass,
            port=port,
            connect_timeout=5
        )
        return conn
    except Exception as e:
        print(f"[!] Failed to connect to Supabase PostgreSQL: {e}")
        return None

def save_embedding_to_db(name, embedding):
    """Insert or update a face embedding in Supabase."""
    conn = get_supabase_connection()
    if not conn:
        print("[!] Skipping Supabase save: Database connection failed.")
        return False
    try:
        cur = conn.cursor()
        
        # Convert numpy array/list to string format '[v1,v2,...]' for pgvector
        if hasattr(embedding, 'tolist'):
            emb_list = embedding.tolist()
        else:
            emb_list = list(embedding)
        vector_str = "[" + ",".join(map(str, emb_list)) + "]"
        
        # Check if row already exists
        cur.execute("SELECT 1 FROM embeddings WHERE name = %s LIMIT 1", (name,))
        exists = cur.fetchone() is not None
        
        if exists:
            cur.execute(
                "UPDATE embeddings SET embedding = %s, created_at = now() WHERE name = %s",
                (vector_str, name)
            )
            print(f"[OK] Updated embedding for '{name}' in Supabase.")
        else:
            cur.execute(
                "INSERT INTO embeddings (name, embedding, metadata) VALUES (%s, %s, %s)",
                (name, vector_str, '{}')
            )
            print(f"[OK] Inserted embedding for '{name}' into Supabase.")
            
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[!] Error saving embedding for '{name}' to Supabase: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False

def fetch_embeddings_from_db():
    """Retrieve all face embeddings from Supabase."""
    conn = get_supabase_connection()
    if not conn:
        print("[!] Skipping Supabase fetch: Database connection failed.")
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, embedding FROM embeddings")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        db_embeddings = {}
        for name, emb_data in rows:
            if not emb_data:
                continue
            # Parse vector representation
            if isinstance(emb_data, str):
                cleaned = emb_data.strip('[]')
                emb_array = np.fromstring(cleaned, sep=',')
            elif isinstance(emb_data, (list, tuple)):
                emb_array = np.array(emb_data, dtype=np.float32)
            else:
                # Fallback
                emb_array = np.array(list(emb_data), dtype=np.float32)
            
            db_embeddings[name] = emb_array.flatten()
            
        return db_embeddings
    except Exception as e:
        print(f"[!] Error fetching embeddings from Supabase: {e}")
        return None

def load_db_with_sync():
    """Load embeddings, syncing with Supabase (write to local cache if database is reachable)."""
    # 1. Try to fetch from Supabase first
    db = fetch_embeddings_from_db()
    if db is not None:
        # Successfully fetched from Supabase, update the local pkl cache
        try:
            p = config.DATABASE_PATH
            os.makedirs(os.path.dirname(p), exist_ok=True)
            serializable = {name: emb.tolist() for name, emb in db.items()}
            with open(p, "wb") as f:
                pickle.dump(serializable, f)
            print(f"[SYNC] Synced local database.pkl cache with Supabase ({len(db)} records)")
        except Exception as e:
            print(f"[!] Error updating local database.pkl cache: {e}")
        return db
    
    # 2. Fallback to local pickle if database connection fails
    p = config.DATABASE_PATH
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                local_db = pickle.load(f)
            print(f"[LOAD] Loaded face embeddings from local database.pkl cache ({len(local_db)} records)")
            return {name: np.array(emb, dtype=np.float32).flatten() for name, emb in local_db.items()}
        except Exception as e:
            print(f"[!] Error loading local database.pkl: {e}")
            backup = p + ".bak"
            if os.path.exists(backup):
                try:
                    with open(backup, "rb") as f:
                        bdb = pickle.load(f)
                    return {name: np.array(emb, dtype=np.float32).flatten() for name, emb in bdb.items()}
                except Exception:
                    pass
    return {}

def delete_embedding_from_db(name):
    """Delete a student embedding from Supabase."""
    conn = get_supabase_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM embeddings WHERE name = %s", (name,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DEL] Deleted embedding for '{name}' from Supabase.")
        return True
    except Exception as e:
        print(f"[!] Error deleting embedding for '{name}' from Supabase: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False

def clear_all_embeddings_from_db():
    """Clear all embeddings from Supabase."""
    conn = get_supabase_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE embeddings")
        conn.commit()
        cur.close()
        conn.close()
        print("[DEL] Cleared all embeddings from Supabase.")
        return True
    except Exception as e:
        print(f"[!] Error clearing embeddings from Supabase: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
