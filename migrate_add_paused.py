#!/usr/bin/env python3
"""
Migration script to add is_paused column to Monitor table
"""

import sqlite3
import os

def migrate_database():
    db_path = "instance/ripplememento.db"
    if not os.path.exists(db_path):
        print("Database not found, no migration needed.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if is_paused column already exists
        cursor.execute("PRAGMA table_info(monitor)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_paused' not in columns:
            print("Adding is_paused column to monitor table...")
            cursor.execute("ALTER TABLE monitor ADD COLUMN is_paused BOOLEAN DEFAULT 0")
            conn.commit()
            print("✅ Migration completed successfully!")
        else:
            print("✅ is_paused column already exists, no migration needed.")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()