import sqlite3
import os
from datetime import datetime
import pandas as pd

DB_DIR = r"C:\ameva\AMEVA-STT-Agent\db"
DB_PATH = os.path.join(DB_DIR, "ameva_stt.db")

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 작업 로그 테이블 (수동/자동 배치 및 비교 실행 기록)
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

    # 전사 데이터 테이블 (STT 청크)
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

    # 시스템 에러 로그 테이블
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

def log_batch(task_id, audio_path, model_used, language, processing_time, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO batch_logs (task_id, audio_path, model_used, language, processing_time, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (task_id, audio_path, model_used, language, processing_time, status))
    batch_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return batch_id

def log_transcriptions(batch_id, chunks):
    if not chunks:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for chunk in chunks:
        cursor.execute('''
            INSERT INTO transcriptions (batch_id, start_time, end_time, speaker, transcript_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (batch_id, chunk.get('start', 0), chunk.get('end', 0), chunk.get('speaker', 'Unknown'), chunk.get('text', '')))
    conn.commit()
    conn.close()

def log_error(context, error_message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO error_logs (context, error_message)
        VALUES (?, ?)
    ''', (context, str(error_message)))
    conn.commit()
    conn.close()

def get_table_df(table_name):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY id DESC", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

# 모듈 임포트 시 자동 초기화
init_db()
