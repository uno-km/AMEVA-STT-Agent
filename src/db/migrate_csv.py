import os
import csv
import json
import sqlite3
from datetime import datetime

DB_DIR = r"C:\ameva\AMEVA-STT-Agent\db"
DB_PATH = os.path.join(DB_DIR, "ameva_stt.db")

BATCH_LOG_CSV = r"C:\Users\ATSAdmin\Documents\UNO\small_prj\AMEVA-STT-Agent\stt_batch_log.csv"
EXCEPTION_LOG_CSV = r"C:\Users\ATSAdmin\Documents\UNO\small_prj\AMEVA-STT-Agent\stt_exception_log.csv"

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            audio_path TEXT,
            model_used TEXT,
            language TEXT,
            processing_time REAL,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transcriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            start_time REAL,
            end_time REAL,
            speaker TEXT,
            transcript_text TEXT,
            FOREIGN KEY(batch_id) REFERENCES batch_logs(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context TEXT,
            error_message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def migrate():
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("[*] Starting CSV data migration to SQLite...")

    # 1. Migrate stt_batch_log.csv
    if os.path.exists(BATCH_LOG_CSV):
        print(f"[*] Migrating {BATCH_LOG_CSV}...")
        with open(BATCH_LOG_CSV, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            batch_count = 0
            trans_count = 0
            for row in reader:
                # Insert into batch_logs
                cursor.execute('''
                    INSERT INTO batch_logs (task_id, audio_path, model_used, language, processing_time, status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row.get("task_id", "UNKNOWN"),
                    row.get("original_filename", ""),
                    row.get("model", ""),
                    row.get("language", ""),
                    float(row.get("duration", 0)) if row.get("duration") else 0.0,
                    row.get("status", "SUCCESS"),
                    row.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                ))
                new_batch_id = cursor.lastrowid
                batch_count += 1

                # Try to load chunks from the JSON output_filename
                json_path = row.get("output_filename", "")
                if json_path and os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as jf:
                            chunks = json.load(jf)
                            for chunk in chunks:
                                cursor.execute('''
                                    INSERT INTO transcriptions (batch_id, start_time, end_time, speaker, transcript_text)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (
                                    new_batch_id,
                                    chunk.get("start", 0.0),
                                    chunk.get("end", 0.0),
                                    chunk.get("speaker", "Unknown"),
                                    chunk.get("text", "")
                                ))
                                trans_count += 1
                    except Exception as je:
                        print(f"[Warning] Failed to read JSON at {json_path}: {je}")
            
            print(f"[OK] Migrated {batch_count} batch logs and {trans_count} transcription chunks.")
    else:
        print("[Info] stt_batch_log.csv not found.")

    # 2. Migrate stt_exception_log.csv
    if os.path.exists(EXCEPTION_LOG_CSV):
        print(f"[*] Migrating {EXCEPTION_LOG_CSV}...")
        with open(EXCEPTION_LOG_CSV, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            error_count = 0
            for row in reader:
                context = f"Migrated - Batch: {row.get('batch_id', '')} File: {row.get('original_filename', '')}"
                cursor.execute('''
                    INSERT INTO error_logs (context, error_message, timestamp)
                    VALUES (?, ?, ?)
                ''', (
                    context,
                    row.get("error", ""),
                    row.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                ))
                error_count += 1
            print(f"[OK] Migrated {error_count} error logs.")
    else:
        print("[Info] stt_exception_log.csv not found.")

    conn.commit()
    conn.close()
    print("[*] Migration completed successfully.")

if __name__ == "__main__":
    migrate()
