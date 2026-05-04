import os
import csv
import sys
import time
import subprocess
from datetime import datetime

# 작업 폴더 및 DB 파일 경로
INPUT_DIR = "./input_audios"
OUTPUT_DIR = "./output_results"
BATCH_DB_FILE = "stt_batch_log.csv"
EXCEPTION_DB_FILE = "stt_exception_log.csv"

# 지원할 오디오 확장자
AUDIO_EXTENSIONS = (".wav", ".m4a", ".mp3", ".flac", ".aac", ".ogg", ".opus")


def ensure_directories():
    """입력/출력 폴더가 없으면 생성합니다."""
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def scan_audio_files():
    """INPUT_DIR에서 지원되는 오디오 파일 목록을 스캔합니다."""
    files = []
    for root, _, filenames in os.walk(INPUT_DIR):
        for fname in filenames:
            if fname.lower().endswith(AUDIO_EXTENSIONS):
                full_path = os.path.abspath(os.path.join(root, fname))
                rel_path = os.path.relpath(full_path, INPUT_DIR)
                files.append((rel_path, full_path))
    return sorted(files)


def load_batch_db():
    """기존 CSV DB 파일을 읽어 옵니다."""
    rows = []
    if not os.path.exists(BATCH_DB_FILE):
        return rows

    with open(BATCH_DB_FILE, "r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(row)
    return rows


def write_batch_db(rows):
    """CSV 파일 전체를 재작성합니다."""
    fieldnames = [
        "id",
        "original_filename",
        "output_filename",
        "start_time",
        "batch_id",
        "duration",
        "status",
        "completion_time",
        "exception_time",
        "exception_message",
    ]
    with open(BATCH_DB_FILE, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_batch_row(row):
    """CSV 파일 끝에 새로운 레코드를 추가합니다."""
    file_exists = os.path.exists(BATCH_DB_FILE)
    fieldnames = [
        "id",
        "original_filename",
        "output_filename",
        "start_time",
        "batch_id",
        "duration",
        "status",
        "completion_time",
        "exception_time",
        "exception_message",
    ]
    with open(BATCH_DB_FILE, "a", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def log_exception_to_csv(original_filename, batch_id, exception_time, exception_message):
    """예외 발생 시 별도의 예외 기록 CSV 파일에 상세 내용을 추가합니다."""
    file_exists = os.path.exists(EXCEPTION_DB_FILE)
    fieldnames = [
        "log_timestamp",
        "batch_id",
        "original_filename",
        "exception_time",
        "exception_message"
    ]
    with open(EXCEPTION_DB_FILE, "a", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "log_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "batch_id": batch_id,
            "original_filename": original_filename,
            "exception_time": exception_time,
            "exception_message": exception_message
        })


def get_next_id(rows):
    """CSV DB에 있는 마지막 id 값 다음 숫자를 반환합니다."""
    max_id = 0
    for row in rows:
        try:
            row_id = int(row.get("id", "0") or "0")
            if row_id > max_id:
                max_id = row_id
        except ValueError:
            continue
    return max_id + 1


def select_work_queue(audio_files, rows):
    """처리할 대상 파일 큐를 구성합니다."""
    success_files = {
        row["original_filename"]
        for row in rows
        if row.get("status", "").upper() == "SUCCESS"
    }

    queue = []
    for rel_path, full_path in audio_files:
        if rel_path not in success_files:
            queue.append((rel_path, full_path))
    return queue


def create_batch_id():
    """현재 배치 실행을 식별할 batch_id 생성."""
    return datetime.now().strftime("%Y%m%d_%H%M")


def run_ameva_for_file(original_filename, audio_path, batch_id, next_id):
    """ameva_hybrid.py를 subprocess로 실행하고 결과를 기록할 준비를 합니다."""
    output_prefix = os.path.join(
        os.path.abspath(OUTPUT_DIR),
        f"{os.path.splitext(os.path.basename(original_filename))[0]}_{batch_id}",
    )

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_row = {
        "id": str(next_id),
        "original_filename": original_filename,
        "output_filename": output_prefix,
        "start_time": start_time,
        "batch_id": batch_id,
        "duration": "",
        "status": "PROCESSING",
        "completion_time": "",
        "exception_time": "",
        "exception_message": "",
    }
    append_batch_row(output_row)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    ameva_script = os.path.join(script_dir, "ameva_hybrid.py")

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "."

    command = [
        sys.executable,
        ameva_script,
        "-f",
        audio_path,
        "--ko",
        "--medium",
        "--output",
        output_prefix,
    ]

    start_ts = time.time()
    exception_time = ""
    exception_message = ""
    status = "FAIL"

    try:
        result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration = time.time() - start_ts
        completion_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result.returncode == 0:
            status = "SUCCESS"
        else:
            status = "FAIL"
            exception_time = completion_time
            exception_message = (
                f"returncode={result.returncode} stderr={result.stderr.strip()}"
            )
            log_exception_to_csv(original_filename, batch_id, exception_time, exception_message)
    except Exception as exc:
        duration = time.time() - start_ts
        completion_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exception_time = completion_time
        exception_message = f"{type(exc).__name__}: {str(exc)}"
        status = "FAIL"
        log_exception_to_csv(original_filename, batch_id, exception_time, exception_message)

    output_row.update(
        {
            "duration": f"{duration:.2f}",
            "status": status,
            "completion_time": completion_time,
            "exception_time": exception_time,
            "exception_message": exception_message,
        }
    )
    return output_row


def update_batch_record(rows, updated_row):
    """처리된 레코드를 찾아 최신 정보로 덮어씁니다."""
    for row in rows:
        if row.get("id") == updated_row.get("id"):
            row.update(updated_row)
            break
    return rows


def main():
    ensure_directories()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[BATCH MANAGER] 실행 시간: {current_time}")

    audio_files = scan_audio_files()
    print(f"[BATCH MANAGER] INPUT_DIR 스캔 결과: {len(audio_files)}개 파일 발견")

    existing_rows = load_batch_db()
    work_queue = select_work_queue(audio_files, existing_rows)

    if not work_queue:
        print("[BATCH MANAGER] 처리할 대상이 없습니다.")
        return

    print(f"[BATCH MANAGER] 처리 대상 개수: {len(work_queue)}개")
    batch_id = create_batch_id()

    rows = load_batch_db()
    next_id = get_next_id(rows)

    for rel_path, full_path in work_queue:
        print(f"[BATCH MANAGER] 처리 시작: {rel_path}")

        try:
            updated_row = run_ameva_for_file(rel_path, full_path, batch_id, next_id)
            next_id += 1
        except Exception as exc:
            exc_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            exc_msg = f"{type(exc).__name__}: {str(exc)}"
            updated_row = {
                "id": str(next_id),
                "original_filename": rel_path,
                "output_filename": "",
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "batch_id": batch_id,
                "duration": "",
                "status": "FAIL",
                "completion_time": exc_time,
                "exception_time": exc_time,
                "exception_message": exc_msg,
            }
            append_batch_row(updated_row)
            log_exception_to_csv(rel_path, batch_id, exc_time, exc_msg)
            next_id += 1
            print(f"[BATCH MANAGER] 예외 발생: {updated_row['exception_message']}")
            continue

        # DB 전체를 다시 로드하여 최신 상태로 업데이트
        rows = load_batch_db()
        rows = update_batch_record(rows, updated_row)
        write_batch_db(rows)

        print(f"[BATCH MANAGER] 완료: {rel_path} -> {updated_row['status']} (소요: {updated_row['duration']}초)")

    print("[BATCH MANAGER] 배치 처리 종료")


if __name__ == "__main__":
    main()