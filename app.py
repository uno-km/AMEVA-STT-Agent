import streamlit as st
import os
import time
import pandas as pd
import json
import plotly.express as px
import threading
import tkinter as tk
from tkinter import filedialog
from src.core.pipeline import STTPipeline
from src.core.settings_manager import settings_manager
from src.utils.report_generator import create_stt_report, create_comparison_report
from src.db.db_manager import log_batch, log_transcriptions, log_error, get_table_df

st.set_page_config(page_title="AMEVA Hybrid STT Enterprise", layout="wide", page_icon="🎙️")

st.markdown("""
<style>
    .stCodeBlock { border-radius: 8px !important; }
    .stButton>button { border-radius: 6px; font-weight: bold; }
    .metric-box { padding: 15px; border-radius: 8px; background-color: #1E1E1E; border: 1px solid #333; margin-bottom: 10px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #4CAF50; }
    .metric-label { font-size: 14px; color: #AAA; }
</style>
""", unsafe_allow_html=True)

st.title("🎙️ AMEVA STT Enterprise Dashboard")
st.markdown("**(Professional Edition with Advanced Configuration & Reporting)**")

stt_settings = settings_manager.get("stt")
batch_settings = settings_manager.get("batch")

# Helper: Save chart safely
def safe_save_chart(fig, path):
    try:
        fig.write_image(path)
        return path
    except:
        return None

# Tkinter File Dialogs
def ask_directory():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(master=root)
    root.destroy()
    return folder

def ask_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(master=root, filetypes=[("Audio/Media Files", "*.wav *.mp3 *.m4a *.flac *.mp4 *.avi *.mkv"), ("All Files", "*.*")])
    root.destroy()
    return file_path

# State initialization for UI fields
if "ui_custom_model" not in st.session_state: st.session_state["ui_custom_model"] = stt_settings.get("custom_model_path", "")
if "ui_input_dir" not in st.session_state: st.session_state["ui_input_dir"] = batch_settings.get("input_dir", r"C:\ameva\input")
if "ui_output_dir" not in st.session_state: st.session_state["ui_output_dir"] = batch_settings.get("output_dir", r"C:\ameva\outputs")
if "ui_manual_path" not in st.session_state: st.session_state["ui_manual_path"] = ""
if "ui_comp_path" not in st.session_state: st.session_state["ui_comp_path"] = ""

# --- SIDEBAR: ADVANCED SETTINGS ---
st.sidebar.header("⚙️ 시스템 고급 설정")

st.sidebar.subheader("1. 모델 구성")
models = ["tiny", "small", "medium", "large-v3-turbo", "large"]
idx = models.index(stt_settings.get("model", "medium")) if stt_settings.get("model", "medium") in models else 2
model_size = st.sidebar.selectbox("Whisper 모델 사이즈", models, index=idx)

st.sidebar.markdown("**커스텀 모델 경로**")
col1, col2 = st.sidebar.columns([4, 1])
with col1: custom_model_path = st.text_input("커스텀 모델 경로", st.session_state["ui_custom_model"], key="cm_in", label_visibility="collapsed")
with col2:
    if st.button("📁", key="btn_cm"):
        d = ask_directory()
        if d: 
            st.session_state["ui_custom_model"] = d
            st.rerun()

langs = ["auto", "ko", "en"]
lang_idx = langs.index(stt_settings.get("language", "ko")) if stt_settings.get("language", "ko") in langs else 1
language = st.sidebar.selectbox("언어 인식 설정", langs, index=lang_idx)
threads = st.sidebar.number_input("사용할 CPU 스레드 수", min_value=1, max_value=32, value=int(stt_settings.get("threads", 4)))

st.sidebar.markdown("---")
st.sidebar.subheader("2. 화자 분리 및 오프셋")
diarization_enabled = st.sidebar.toggle("화자 분리 활성화", value=stt_settings.get("diarization_enabled", True))
speakers = st.sidebar.number_input("예상 화자 수 (0=자동)", min_value=0, max_value=20, value=int(stt_settings.get("speakers", 2)))
max_offset = st.sidebar.number_input("Max Offset", value=float(stt_settings.get("max_offset", 2.0)), step=0.1)
max_len = st.sidebar.number_input("Max Length", value=int(stt_settings.get("max_len", 20)))
split_on_word = st.sidebar.toggle("단어 단위 분할", value=stt_settings.get("split_on_word", True))

st.sidebar.markdown("---")
st.sidebar.subheader("3. VAD 제어")
vad_enabled = st.sidebar.toggle("VAD 활성화", value=stt_settings.get("vad_enabled", False))
vad_max_speech = st.sidebar.number_input("VAD Max Speech (s)", value=int(stt_settings.get("vad_max_speech_duration", 5)))
vad_min_silence = st.sidebar.number_input("VAD Min Silence (ms)", value=int(stt_settings.get("vad_min_silence_duration", 500)))

st.sidebar.markdown("---")
st.sidebar.subheader("4. 경로 및 배치 설정")

st.sidebar.markdown("**입력 오디오 폴더**")
col3, col4 = st.sidebar.columns([4, 1])
with col3: input_dir = st.text_input("입력 오디오 폴더", st.session_state["ui_input_dir"], label_visibility="collapsed")
with col4:
    if st.button("📁", key="btn_in"):
        d = ask_directory()
        if d: st.session_state["ui_input_dir"] = d; st.rerun()

st.sidebar.markdown("**출력 결과 폴더**")
col5, col6 = st.sidebar.columns([4, 1])
with col5: output_dir = st.text_input("출력 결과 폴더", st.session_state["ui_output_dir"], label_visibility="collapsed")
with col6:
    if st.button("📁", key="btn_out"):
        d = ask_directory()
        if d: st.session_state["ui_output_dir"] = d; st.rerun()

interval_min = st.sidebar.number_input("예약 실행 간격(분)", min_value=1, value=int(batch_settings.get("interval_min", 1)))

if st.sidebar.button("설정 저장 및 적용", type="primary", use_container_width=True):
    stt_settings.update({
        "model": model_size, "custom_model_path": custom_model_path, "language": language, "threads": threads,
        "diarization_enabled": diarization_enabled, "speakers": speakers, "max_offset": max_offset, "max_len": max_len,
        "split_on_word": split_on_word, "vad_enabled": vad_enabled, "vad_max_speech_duration": vad_max_speech,
        "vad_min_silence_duration": vad_min_silence
    })
    batch_settings.update({
        "input_dir": input_dir, "output_dir": output_dir, "interval_min": interval_min
    })
    settings_manager.set("stt", stt_settings)
    settings_manager.set("batch", batch_settings)
    st.sidebar.success("설정이 저장되었습니다.")

# TABS
tab_run, tab_compare, tab_explorer, tab_db = st.tabs([
    "▶️ 작업 실행 (Batch & Auto)", 
    "⚖️ 모델 성능 비교", 
    "📁 데이터 및 결과 탐색기",
    "📊 데이터베이스 및 시스템 로그"
])

# --- TAB 1: RUN BATCH & AUTO MODE ---
with tab_run:
    st.header("▶️ 파이프라인 제어 센터")
    col_mode1, col_mode2 = st.columns(2)
    with col_mode1:
        st.subheader("단일 오디오/디렉터리 수동 실행")
        uploaded_file = st.file_uploader("웹 업로드 (오디오 파일 끌어다 놓기)", type=["wav", "mp3", "m4a", "flac"])
        
        st.markdown("**또는 직접 경로 (파일/폴더)**")
        col_m1, col_m2, col_m3 = st.columns([6, 1, 1])
        with col_m1: manual_path = st.text_input("직접 경로", st.session_state["ui_manual_path"], key="m_in", label_visibility="collapsed")
        with col_m2:
            if st.button("📁", key="m_btn_d"):
                d = ask_directory()
                if d: st.session_state["ui_manual_path"] = d; st.rerun()
        with col_m3:
            if st.button("📄", key="m_btn_f"):
                f = ask_file()
                if f: st.session_state["ui_manual_path"] = f; st.rerun()
                
        if st.button("수동 작업 즉시 시작 🚀", use_container_width=True, type="primary"):
            target_p = ""
            if uploaded_file is not None:
                os.makedirs(batch_settings.get("input_dir", r"C:\ameva\input"), exist_ok=True)
                target_p = os.path.join(batch_settings.get("input_dir", r"C:\ameva\input"), uploaded_file.name)
                with open(target_p, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            elif manual_path.strip():
                target_p = manual_path.strip()
            else:
                target_p = batch_settings.get("input_dir", "")
                
            st.session_state["run_mode"] = "manual"
            st.session_state["target_path"] = target_p
            
    with col_mode2:
        st.subheader("자동 감시 및 스케줄링 (Auto Mode)")
        st.info(f"현재 설정된 간격: {batch_settings.get('interval_min', 1)}분")
        if st.button("자동 스케줄러 가동 🔄", use_container_width=True):
            st.session_state["run_mode"] = "auto"
    
    if st.button("작업 중지 / 리셋 🛑"):
        st.session_state["run_mode"] = "none"
        
    st.markdown("---")
    
    if st.session_state.get("run_mode") in ["manual", "auto"]:
        log_container = st.empty()
        log_text = []
        
        def log_callback(msg):
            log_text.append(msg)
            display_text = "\n".join(log_text[-50:])
            log_container.code(display_text, language="text")
            
        def sys_callback(msg):
            log_text.append(f"[SYSTEM] {msg}")
            display_text = "\n".join(log_text[-50:])
            log_container.code(display_text, language="text")
            if "error" in msg.lower() or "fail" in msg.lower() or "❌" in msg:
                log_error("Pipeline System", msg)

        pipeline = STTPipeline()
        out_dir = batch_settings.get("output_dir", r"C:\ameva\outputs")
        os.makedirs(out_dir, exist_ok=True)
        
        if st.session_state["run_mode"] == "manual":
            target = st.session_state.get("target_path", "")
            if not os.path.exists(target):
                st.error("유효하지 않은 경로입니다.")
            else:
                with st.spinner("엔터프라이즈 파이프라인 가동 중..."):
                    try:
                        targets = []
                        if os.path.isdir(target):
                            for f in os.listdir(target):
                                if f.lower().endswith(('.wav', '.mp3', '.m4a', '.flac', '.mp4', '.mkv', '.avi')):
                                    targets.append(os.path.join(target, f))
                        else:
                            targets = [target]
                        
                        log_callback(f"[Batch] 총 {len(targets)}개의 파일을 처리합니다.")
                        
                        for i, t in enumerate(targets):
                            log_callback(f"\n[Batch] {i+1}/{len(targets)} 처리 시작: {os.path.basename(t)}")
                            start_t = time.time()
                            final_json, pca_coords, labels, cluster_path, dia_texts, full_text = pipeline.execute(
                                audio_path=t, output_dir=out_dir, logger_callback=log_callback,
                                system_callback=sys_callback, task_id="MANUAL_BATCH",
                                diarization_enabled=stt_settings.get("diarization_enabled", True), batch_id="STT_ENT_BATCH"
                            )
                            proc_time = time.time() - start_t
                            
                            chunks_data = []
                            if final_json and os.path.exists(final_json):
                                with open(final_json, 'r', encoding='utf-8') as f:
                                    chunks_data = json.load(f)
                                    
                            # DB Log
                            batch_id = log_batch("MANUAL_BATCH", t, stt_settings.get("model", ""), stt_settings.get("language", "auto"), proc_time, "SUCCESS")
                            log_transcriptions(batch_id, chunks_data)
                                    
                            st.session_state["last_json"] = final_json
                            st.session_state["last_cluster"] = cluster_path
                            st.session_state["last_stats"] = {
                                "processing_time_sec": proc_time,
                                "model": stt_settings.get("model", ""),
                                "language": stt_settings.get("language", "auto"),
                                "diarization_enabled": stt_settings.get("diarization_enabled", True)
                            }
                            st.session_state["last_text"] = full_text
                            st.session_state["last_audio"] = t
                            st.session_state["last_chunks"] = chunks_data
                            
                        st.success("✅ 수동 작업이 모두 완료되었습니다.")
                    except Exception as e:
                        st.error(f"❌ 작업 오류: {e}")
                        log_error("Manual Batch Process", str(e))
                st.session_state["run_mode"] = "none"
        
        elif st.session_state["run_mode"] == "auto":
            st.warning("🔄 자동 스케줄러가 활성화되었습니다.")
            input_d = batch_settings.get("input_dir", "")
            interval = int(batch_settings.get("interval_min", 1)) * 60
            with st.spinner("자동 감시 모드 작동 중... (취소하려면 상단의 중지 버튼 클릭)"):
                for _ in range(5):
                    if st.session_state.get("run_mode") != "auto": break
                    log_callback(f"[*] 오디오 폴더 스캔 중: {input_d}")
                    if os.path.exists(input_d):
                        for f in os.listdir(input_d):
                            if f.lower().endswith(('.wav', '.mp3', '.m4a', '.flac')):
                                p = os.path.join(input_d, f)
                                log_callback(f"[Auto] 새로운 파일 감지: {f}")
                                try:
                                    start_t = time.time()
                                    final_json, pca_coords, labels, cluster_path, dia_texts, full_text = pipeline.execute(
                                        audio_path=p, output_dir=out_dir, logger_callback=log_callback,
                                        system_callback=sys_callback, task_id="AUTO",
                                        diarization_enabled=stt_settings.get("diarization_enabled", True), batch_id="AUTO_BATCH"
                                    )
                                    proc_time = time.time() - start_t
                                    
                                    chunks_data = []
                                    if final_json and os.path.exists(final_json):
                                        with open(final_json, 'r', encoding='utf-8') as jsf:
                                            chunks_data = json.load(jsf)
                                    
                                    batch_id = log_batch("AUTO", p, stt_settings.get("model", ""), stt_settings.get("language", "auto"), proc_time, "SUCCESS")
                                    log_transcriptions(batch_id, chunks_data)
                                    
                                    os.rename(p, p + ".done")
                                except Exception as auto_e:
                                    log_error("Auto Loop Process", str(auto_e))
                    time.sleep(interval)
                    log_callback("[*] 대기 시간 종료, 다음 스캔을 시작합니다.")


# --- TAB 2: MODEL COMPARISON ---
with tab_compare:
    st.header("⚖️ 다중 모델 성능 비교")
    st.markdown("단일 오디오/디렉터리를 대상으로 여러 모델을 순차적으로 실행하고 성능을 비교합니다.")
    
    st.markdown("**비교할 대상 (파일 또는 폴더)**")
    col_c1, col_c2, col_c3 = st.columns([6, 1, 1])
    with col_c1: comp_audio_path = st.text_input("비교할 대상", st.session_state["ui_comp_path"], key="c_in", label_visibility="collapsed")
    with col_c2:
        if st.button("📁", key="c_btn_d"):
            d = ask_directory()
            if d: st.session_state["ui_comp_path"] = d; st.rerun()
    with col_c3:
        if st.button("📄", key="c_btn_f"):
            f = ask_file()
            if f: st.session_state["ui_comp_path"] = f; st.rerun()
    
    builtin_models = st.multiselect("비교할 내장 모델 선택", ["tiny", "small", "medium", "large-v3-turbo", "large"], default=["small", "medium"])
    
    st.markdown("**커스텀 모델 경로들 (쉼표로 구분하여 여러 개 입력 가능)**")
    col_m1, col_m2 = st.columns([6, 1])
    with col_m1: custom_models_str = st.text_input("커스텀 모델 경로들", "", key="c_models_str", label_visibility="collapsed")
    with col_m2:
        if st.button("📁추가", key="c_btn_cust"):
            d = ask_directory()
            if d: 
                # Append to existing
                cur = custom_models_str.strip()
                new_val = f"{cur}, {d}" if cur else d
                st.session_state["custom_models_str"] = new_val
                st.success(f"경로를 복사하여 텍스트 상자에 붙여넣으세요:\n{d}")
    
    if st.button("비교 시작 🏁", type="primary"):
        target_p = comp_audio_path.strip()
            
        if not target_p or not os.path.exists(target_p):
            st.error("유효한 오디오 파일 또는 폴더 경로를 지정해주세요.")
        else:
            models_to_test = builtin_models.copy()
            if custom_models_str.strip():
                models_to_test.extend([m.strip() for m in custom_models_str.split(",") if m.strip()])
                
            if not models_to_test:
                st.warning("비교할 모델을 최소 하나 이상 선택하세요.")
            else:
                targets = []
                if os.path.isdir(target_p):
                    for f in os.listdir(target_p):
                        if f.lower().endswith(('.wav', '.mp3', '.m4a', '.flac', '.mp4', '.mkv', '.avi')):
                            targets.append(os.path.join(target_p, f))
                else:
                    targets = [target_p]
                    
                st.session_state["comp_models"] = models_to_test
                st.session_state["comp_targets"] = targets
                st.session_state["comp_results"] = {}
                st.session_state["comp_status"] = {m: "pending" for m in models_to_test}

    if "comp_models" in st.session_state and st.session_state["comp_models"]:
        st.markdown("### 🚦 비교 작업 상태 현황")
        models_to_test = st.session_state["comp_models"]
        targets = st.session_state["comp_targets"]
        
        st.info(f"총 {len(targets)}개의 미디어 파일에 대해 {len(models_to_test)}개 모델을 테스트합니다.")
        
        status_cols = st.columns(len(models_to_test))
        for i, m in enumerate(models_to_test):
            status = st.session_state["comp_status"].get(m, "pending")
            icon = "🕒 대기중" if status == "pending" else "⏳ 진행중" if status == "running" else "✅ 완료" if status == "done" else "❌ 에러"
            status_cols[i].info(f"**{os.path.basename(m) if os.path.isabs(m) else m}**\n\n{icon}")
            
        pipeline = STTPipeline()
        out_dir = batch_settings.get("output_dir", r"C:\ameva\outputs")
        
        for idx, m in enumerate(models_to_test):
            if st.session_state["comp_status"].get(m) == "pending":
                st.session_state["comp_status"][m] = "running"
                st.rerun()
                
            if st.session_state["comp_status"].get(m) == "running":
                with st.spinner(f"[{m}] 모델 STT 분석 중... (이후 모델들은 순차 대기)"):
                    orig_model = stt_settings.get("model")
                    orig_custom = stt_settings.get("custom_model_path")
                    if os.path.isabs(m):
                        settings_manager.set("stt", {**stt_settings, "model": "medium", "custom_model_path": m})
                    else:
                        settings_manager.set("stt", {**stt_settings, "model": m, "custom_model_path": ""})
                    
                    try:
                        total_time = 0
                        all_chunks = []
                        all_text = ""
                        chart_p = None
                        
                        for t in targets:
                            start_t = time.time()
                            final_json, pca_coords, labels, cluster_path, dia_texts, full_text = pipeline.execute(
                                audio_path=t, output_dir=out_dir,
                                logger_callback=lambda x: None, system_callback=lambda x: None,
                                task_id=f"COMP_{os.path.basename(m) if os.path.isabs(m) else m}", 
                                diarization_enabled=stt_settings.get("diarization_enabled", True), batch_id="COMP_BATCH"
                            )
                            proc_time = time.time() - start_t
                            total_time += proc_time
                            all_text += full_text + "\n"
                            
                            file_chunks = []
                            if final_json and os.path.exists(final_json):
                                with open(final_json, 'r', encoding='utf-8') as f:
                                    file_chunks = json.load(f)
                                    all_chunks.extend(file_chunks)
                                    
                            batch_id = log_batch("COMPARE_MODE", t, os.path.basename(m) if os.path.isabs(m) else m, stt_settings.get("language", "auto"), proc_time, "SUCCESS")
                            log_transcriptions(batch_id, file_chunks)
                                    
                            if not chart_p and cluster_path and os.path.exists(cluster_path):
                                with open(cluster_path, "r", encoding="utf-8") as f:
                                    c_data = json.load(f)
                                if "embeddings" in c_data:
                                    df_c = pd.DataFrame({
                                        "PCA1": [c[0] for c in c_data.get("embeddings", [])],
                                        "PCA2": [c[1] for c in c_data.get("embeddings", [])],
                                        "Speaker": [str(lbl) for lbl in c_data.get("labels", [])]
                                    })
                                    fig = px.scatter(df_c, x="PCA1", y="PCA2", color="Speaker", title=f"Sample Clustering")
                                    chart_p = safe_save_chart(fig, os.path.join(out_dir, f"comp_chart_sample.png"))
                        
                        st.session_state["comp_results"][m] = {
                            "stats": {
                                "processing_time_sec": total_time, "model": os.path.basename(m) if os.path.isabs(m) else m, 
                                "language": stt_settings.get("language", "auto"),
                                "diarization_enabled": stt_settings.get("diarization_enabled", True)
                            },
                            "chunks_data": all_chunks,
                            "chart_image_path": chart_p,
                            "full_text": all_text
                        }
                        st.session_state["comp_status"][m] = "done"
                    except Exception as e:
                        st.session_state["comp_status"][m] = "error"
                        st.error(f"[{m}] 모델 실행 실패: {e}")
                        log_error(f"Compare Batch - {m}", str(e))
                    
                    settings_manager.set("stt", {**stt_settings, "model": orig_model, "custom_model_path": orig_custom})
                
                st.rerun()
                
        if all(s in ["done", "error"] for s in st.session_state["comp_status"].values()):
            st.success("🎉 모든 모델의 비교 분석이 완료되었습니다!")
            
            res_list = []
            for m, data in st.session_state["comp_results"].items():
                res_list.append({
                    "모델 (Model)": os.path.basename(m) if os.path.isabs(m) else m,
                    "총 소요 시간 (초)": round(data["stats"]["processing_time_sec"], 2),
                    "처리된 총 청크 수": len(data["chunks_data"]),
                    "결과 텍스트 길이": len(data["full_text"])
                })
            
            if res_list:
                df_comp = pd.DataFrame(res_list)
                st.table(df_comp)
                
                if st.button("📑 종합 비교 리포트(Word) 생성 및 다운로드", type="primary"):
                    with st.spinner("비교 리포트를 생성하고 있습니다..."):
                        audio_p = st.session_state["comp_targets"][0] if st.session_state["comp_targets"] else "Multiple_Files"
                        r_path = create_comparison_report(audio_p, out_dir, st.session_state["comp_results"], task_id="Comparison")
                        with open(r_path, "rb") as f:
                            st.download_button(
                                label="⬇️ 비교 리포트 다운로드 (DOCX)", data=f, 
                                file_name=os.path.basename(r_path), 
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )


# --- TAB 3: EXPLORER & REPORT ---
with tab_explorer:
    st.header("📁 로컬 파일 탐색기 & 개별 결과 리포트")
    
    col_exp1, col_exp2 = st.columns([1, 2])
    with col_exp1:
        st.subheader("서버 디렉터리 구조 트리")
        base_path = batch_settings.get("output_dir", r"C:\ameva\outputs")
        
        if os.path.exists(base_path):
            def build_tree(path):
                items = os.listdir(path)
                for item in items:
                    full_p = os.path.join(path, item)
                    if os.path.isdir(full_p):
                        with st.expander(f"📂 {item}"):
                            build_tree(full_p)
                    else:
                        if st.button(f"📄 {item}", key=full_p):
                            st.session_state["selected_file"] = full_p
            build_tree(base_path)
        else:
            st.warning("출력 디렉터리가 아직 존재하지 않습니다.")
            
    with col_exp2:
        st.subheader("결과 상세 분석 및 다운로드")
        selected = st.session_state.get("selected_file", "")
        if selected:
            st.info(f"선택된 파일: {selected}")
            if selected.endswith(".json"):
                with open(selected, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if "embeddings" in data:  # It's a cluster file
                    coords = data.get("embeddings", [])
                    labels = data.get("labels", [])
                    texts = data.get("texts", [])
                    df_cluster = pd.DataFrame({
                        "PCA1": [c[0] for c in coords], "PCA2": [c[1] for c in coords],
                        "Speaker": [f"Speaker {lbl}" for lbl in labels], "Text": texts
                    })
                    fig = px.scatter(df_cluster, x="PCA1", y="PCA2", color="Speaker", hover_data=["Text"], title="Speaker Clustering")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if st.button("📝 이 파일의 엔터프라이즈 Word 리포트 생성", type="primary"):
                        with st.spinner("리포트를 생성 중입니다..."):
                            chart_path = safe_save_chart(fig, os.path.join(base_path, "temp_chart.png"))
                            stats = st.session_state.get("last_stats", {})
                            chunks_data = st.session_state.get("last_chunks", [])
                            audio = st.session_state.get("last_audio", selected)
                            
                            report_path = create_stt_report(audio, base_path, stats, chunks_data, chart_path, task_id="Explorer")
                            
                            with open(report_path, "rb") as f:
                                st.download_button(
                                    label="⬇️ 리포트 다운로드 (DOCX)", data=f, 
                                    file_name=os.path.basename(report_path), 
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                else: # chunk data file
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)
            elif selected.endswith(".csv"):
                df = pd.read_csv(selected)
                st.dataframe(df, use_container_width=True)
            else:
                st.write("미리보기를 지원하지 않는 형식입니다.")
        else:
            st.write("왼쪽 트리에서 파싱된 결과를 선택하면 표, 차트, 리포트 생성 기능이 나타납니다.")


# --- TAB 4: DATABASE & LOG VIEWER ---
with tab_db:
    st.header("📊 데이터베이스 및 시스템 로그 뷰어")
    st.markdown("SQLite 데이터베이스(`db/ameva_stt.db`)에 누적된 작업 내역과 시스템 에러 로그를 실시간으로 조회합니다.")

    if st.button("🔄 새로고침", type="primary"):
        st.rerun()

    db_tab1, db_tab2, db_tab3 = st.tabs(["작업 히스토리 (Batch Logs)", "청크 전사 데이터 (Transcriptions)", "시스템 예외 로그 (Error Logs)"])
    
    with db_tab1:
        st.subheader("모든 작업 이력")
        df_batch = get_table_df("batch_logs")
        if not df_batch.empty:
            st.dataframe(df_batch, use_container_width=True)
        else:
            st.info("기록된 작업이 없습니다.")

    with db_tab2:
        st.subheader("상세 전사 데이터 조회")
        df_trans = get_table_df("transcriptions")
        if not df_trans.empty:
            st.dataframe(df_trans, use_container_width=True)
        else:
            st.info("기록된 전사 데이터가 없습니다.")

    with db_tab3:
        st.subheader("예외 발생 추적")
        df_err = get_table_df("error_logs")
        if not df_err.empty:
            st.dataframe(df_err, use_container_width=True)
        else:
            st.success("발생한 에러가 없습니다!")
