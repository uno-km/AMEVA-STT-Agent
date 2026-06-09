import streamlit as st
import os
import time
import pandas as pd
import json
import plotly.express as px
import threading
from src.core.pipeline import STTPipeline
from src.core.settings_manager import settings_manager
from src.utils.report_generator import create_stt_report, create_comparison_report

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

tab_run, tab_compare, tab_explorer, tab_settings = st.tabs([
    "▶️ 작업 실행 (Batch & Auto)", 
    "⚖️ 모델 성능 비교", 
    "📁 데이터 및 결과 탐색기", 
    "⚙️ 시스템 고급 설정"
])

stt_settings = settings_manager.get("stt")
batch_settings = settings_manager.get("batch")

# Helper: Save chart safely
def safe_save_chart(fig, path):
    try:
        fig.write_image(path)
        return path
    except:
        return None

# --- TAB 4: ADVANCED SETTINGS ---
with tab_settings:
    st.header("⚙️ 엔터프라이즈급 STT 시스템 파라미터")
    with st.form("advanced_settings_form"):
        st.subheader("1. 모델 구성")
        col1, col2 = st.columns(2)
        with col1:
            models = ["tiny", "small", "medium", "large-v3-turbo", "large"]
            idx = models.index(stt_settings.get("model", "medium")) if stt_settings.get("model", "medium") in models else 2
            model_size = st.selectbox("Whisper 모델 사이즈", models, index=idx)
            custom_model_path = st.text_input("커스텀 모델 디렉터리 경로 (입력 시 우선 적용)", stt_settings.get("custom_model_path", ""))
        with col2:
            langs = ["auto", "ko", "en"]
            idx = langs.index(stt_settings.get("language", "ko")) if stt_settings.get("language", "ko") in langs else 1
            language = st.selectbox("언어 인식 설정", langs, index=idx)
            threads = st.number_input("사용할 CPU 스레드 수", min_value=1, max_value=32, value=int(stt_settings.get("threads", 4)))
            
        st.subheader("2. 화자 분리 및 오프셋(Diarization & Offset)")
        col3, col4 = st.columns(2)
        with col3:
            diarization_enabled = st.toggle("화자 분리(Diarization) 활성화", value=stt_settings.get("diarization_enabled", True))
            speakers = st.number_input("예상 화자 수 (0 = 자동)", min_value=0, max_value=20, value=int(stt_settings.get("speakers", 2)))
        with col4:
            max_offset = st.number_input("Max Offset (최대 허용 오차 초)", value=float(stt_settings.get("max_offset", 2.0)), step=0.1)
            max_len = st.number_input("Max Length (청크 최대 길이)", value=int(stt_settings.get("max_len", 20)))
            split_on_word = st.toggle("단어 단위 분할(Split on word)", value=stt_settings.get("split_on_word", True))
            
        st.subheader("3. VAD (음성 활동 감지) 제어")
        col5, col6 = st.columns(2)
        with col5:
            vad_enabled = st.toggle("VAD 활성화", value=stt_settings.get("vad_enabled", False))
        with col6:
            vad_max_speech = st.number_input("VAD Max Speech Duration (s)", value=int(stt_settings.get("vad_max_speech_duration", 5)))
            vad_min_silence = st.number_input("VAD Min Silence Duration (ms)", value=int(stt_settings.get("vad_min_silence_duration", 500)))

        st.subheader("4. 배치 및 디렉터리 설정")
        col7, col8 = st.columns(2)
        with col7:
            input_dir = st.text_input("입력 오디오 폴더 경로", batch_settings.get("input_dir", r"C:\ameva\input"))
            output_dir = st.text_input("출력 결과 폴더 경로", batch_settings.get("output_dir", r"C:\ameva\outputs"))
        with col8:
            interval_min = st.number_input("예약 배치 실행 간격(분)", min_value=1, value=int(batch_settings.get("interval_min", 1)))
            db_file = st.text_input("메인 DB 로그 경로 (CSV)", batch_settings.get("db_file", r"C:\ameva\db\stt_batch_log.csv"))
            exception_db_file = st.text_input("에러 DB 로그 경로 (CSV)", batch_settings.get("exception_db_file", r"C:\ameva\db\stt_exception_log.csv"))
            
        if st.form_submit_button("모든 설정 저장 및 적용", type="primary"):
            stt_settings.update({
                "model": model_size, "custom_model_path": custom_model_path, "language": language, "threads": threads,
                "diarization_enabled": diarization_enabled, "speakers": speakers, "max_offset": max_offset, "max_len": max_len,
                "split_on_word": split_on_word, "vad_enabled": vad_enabled, "vad_max_speech_duration": vad_max_speech,
                "vad_min_silence_duration": vad_min_silence
            })
            batch_settings.update({
                "input_dir": input_dir, "output_dir": output_dir, "interval_min": interval_min,
                "db_file": db_file, "exception_db_file": exception_db_file
            })
            settings_manager.set("stt", stt_settings)
            settings_manager.set("batch", batch_settings)
            st.success("✅ 엔터프라이즈 환경 설정이 성공적으로 저장되었습니다.")


# --- TAB 1: RUN BATCH & AUTO MODE ---
with tab_run:
    st.header("▶️ 파이프라인 제어 센터")
    col_mode1, col_mode2 = st.columns(2)
    with col_mode1:
        st.subheader("단일 / 매뉴얼 배치 실행")
        manual_path = st.text_input("분석할 개별 파일 또는 폴더 경로 (미입력시 기본 Input Directory 사용)", "")
        if st.button("수동 작업 즉시 시작 🚀", use_container_width=True, type="primary"):
            st.session_state["run_mode"] = "manual"
            st.session_state["target_path"] = manual_path if manual_path else batch_settings.get("input_dir", "")
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

        pipeline = STTPipeline()
        out_dir = batch_settings.get("output_dir", r"C:\ameva\outputs")
        os.makedirs(out_dir, exist_ok=True)
        
        if st.session_state["run_mode"] == "manual":
            target = st.session_state.get("target_path", "")
            if not os.path.exists(target):
                st.error("유효하지 않은 경로입니다.")
            else:
                with st.spinner("엔터프라이즈 파이프라인 가동 중..."):
                    start_t = time.time()
                    try:
                        final_json, pca_coords, labels, cluster_path, dia_texts, full_text = pipeline.execute(
                            audio_path=target, output_dir=out_dir, logger_callback=log_callback,
                            system_callback=sys_callback, task_id="MANUAL_BATCH",
                            diarization_enabled=stt_settings.get("diarization_enabled", True), batch_id="STT_ENT_BATCH"
                        )
                        proc_time = time.time() - start_t
                        st.success("✅ 수동 작업이 완료되었습니다.")
                        
                        # Load chunks for report
                        chunks_data = []
                        if os.path.exists(final_json):
                            with open(final_json, 'r', encoding='utf-8') as f:
                                chunks_data = json.load(f)
                                
                        st.session_state["last_json"] = final_json
                        st.session_state["last_cluster"] = cluster_path
                        st.session_state["last_stats"] = {
                            "processing_time_sec": proc_time,
                            "model": stt_settings.get("model", ""),
                            "language": stt_settings.get("language", "auto"),
                            "diarization_enabled": stt_settings.get("diarization_enabled", True)
                        }
                        st.session_state["last_text"] = full_text
                        st.session_state["last_audio"] = target
                        st.session_state["last_chunks"] = chunks_data
                        
                    except Exception as e:
                        st.error(f"❌ 작업 오류: {e}")
                st.session_state["run_mode"] = "none"
        
        elif st.session_state["run_mode"] == "auto":
            st.warning("🔄 자동 스케줄러가 활성화되었습니다.")
            input_d = batch_settings.get("input_dir", "")
            interval = int(batch_settings.get("interval_min", 1)) * 60
            with st.spinner("자동 감시 모드 작동 중... (취소하려면 상단의 중지 버튼 클릭)"):
                for _ in range(5):
                    if st.session_state.get("run_mode") != "auto": break
                    log_callback(f"[*] 오디오 폴더 스캔 중: {input_d}")
                    time.sleep(interval)
                    log_callback("[*] 대기 시간 종료, 다음 스캔을 시작합니다.")


# --- TAB 2: MODEL COMPARISON ---
with tab_compare:
    st.header("⚖️ 다중 모델 성능 비교")
    st.markdown("단일 오디오 파일을 대상으로 여러 모델을 순차적으로 실행하여 성능과 결과물을 정밀 비교합니다.")
    
    comp_audio_path = st.text_input("비교할 대상 오디오 파일 경로", "")
    
    builtin_models = st.multiselect("비교할 내장 모델 선택", ["tiny", "small", "medium", "large-v3-turbo", "large"], default=["small", "medium"])
    custom_models_str = st.text_input("커스텀 모델 경로들 (쉼표로 구분하여 여러 개 입력 가능)", "")
    
    if st.button("비교 시작 🏁", type="primary"):
        if not comp_audio_path or not os.path.exists(comp_audio_path):
            st.error("유효한 오디오 파일을 지정해주세요.")
        else:
            models_to_test = builtin_models.copy()
            if custom_models_str.strip():
                models_to_test.extend([m.strip() for m in custom_models_str.split(",") if m.strip()])
                
            if not models_to_test:
                st.warning("비교할 모델을 최소 하나 이상 선택하세요.")
            else:
                st.session_state["comp_models"] = models_to_test
                st.session_state["comp_results"] = {}
                st.session_state["comp_audio"] = comp_audio_path
                st.session_state["comp_status"] = {m: "pending" for m in models_to_test} # "pending", "running", "done", "error"

    # Status & Execution Area
    if "comp_models" in st.session_state and st.session_state["comp_models"]:
        st.markdown("### 🚦 비교 작업 상태 현황")
        models_to_test = st.session_state["comp_models"]
        
        status_cols = st.columns(len(models_to_test))
        for i, m in enumerate(models_to_test):
            status = st.session_state["comp_status"].get(m, "pending")
            icon = "🕒 대기중" if status == "pending" else "⏳ 진행중 (Spinner)" if status == "running" else "✅ 완료" if status == "done" else "❌ 에러"
            status_cols[i].info(f"**{m}**\n\n{icon}")
            
        # 순차 실행 로직
        pipeline = STTPipeline()
        out_dir = batch_settings.get("output_dir", r"C:\ameva\outputs")
        
        # Check if we need to run any pending model
        for idx, m in enumerate(models_to_test):
            if st.session_state["comp_status"].get(m) == "pending":
                st.session_state["comp_status"][m] = "running"
                st.rerun() # Refresh UI to show spinner
                
            if st.session_state["comp_status"].get(m) == "running":
                with st.spinner(f"[{m}] 모델 STT 분석 중... (이후 모델들은 순차 대기)"):
                    # 임시 설정 덮어쓰기 (메모리에서만)
                    orig_model = stt_settings.get("model")
                    orig_custom = stt_settings.get("custom_model_path")
                    if os.path.isabs(m): # 커스텀 경로인 경우
                        settings_manager.set("stt", {**stt_settings, "model": "medium", "custom_model_path": m})
                    else:
                        settings_manager.set("stt", {**stt_settings, "model": m, "custom_model_path": ""})
                    
                    start_t = time.time()
                    try:
                        final_json, pca_coords, labels, cluster_path, dia_texts, full_text = pipeline.execute(
                            audio_path=st.session_state["comp_audio"], output_dir=out_dir,
                            logger_callback=lambda x: None, system_callback=lambda x: None,
                            task_id=f"COMP_{m}", diarization_enabled=stt_settings.get("diarization_enabled", True), batch_id="COMP_BATCH"
                        )
                        proc_time = time.time() - start_t
                        
                        chunks_data = []
                        if os.path.exists(final_json):
                            with open(final_json, 'r', encoding='utf-8') as f:
                                chunks_data = json.load(f)
                                
                        # Save chart
                        chart_p = None
                        if cluster_path and os.path.exists(cluster_path):
                            with open(cluster_path, "r", encoding="utf-8") as f:
                                c_data = json.load(f)
                            if "embeddings" in c_data:
                                df_c = pd.DataFrame({
                                    "PCA1": [c[0] for c in c_data.get("embeddings", [])],
                                    "PCA2": [c[1] for c in c_data.get("embeddings", [])],
                                    "Speaker": [str(lbl) for lbl in c_data.get("labels", [])]
                                })
                                fig = px.scatter(df_c, x="PCA1", y="PCA2", color="Speaker", title=f"{m} Clustering")
                                chart_p = safe_save_chart(fig, os.path.join(out_dir, f"comp_chart_{m}.png"))
                        
                        st.session_state["comp_results"][m] = {
                            "stats": {
                                "processing_time_sec": proc_time, "model": m, 
                                "language": stt_settings.get("language", "auto"),
                                "diarization_enabled": stt_settings.get("diarization_enabled", True)
                            },
                            "chunks_data": chunks_data,
                            "chart_image_path": chart_p,
                            "full_text": full_text
                        }
                        st.session_state["comp_status"][m] = "done"
                    except Exception as e:
                        st.session_state["comp_status"][m] = "error"
                        st.error(f"[{m}] 모델 실행 실패: {e}")
                    
                    # 원래 설정 복원
                    settings_manager.set("stt", {**stt_settings, "model": orig_model, "custom_model_path": orig_custom})
                
                st.rerun() # Refresh UI to run next pending
                
        # 모든 작업이 완료된 후 결과 렌더링
        if all(s in ["done", "error"] for s in st.session_state["comp_status"].values()):
            st.success("🎉 모든 모델의 비교 분석이 완료되었습니다!")
            
            # 결과 비교표 출력
            res_list = []
            for m, data in st.session_state["comp_results"].items():
                res_list.append({
                    "모델 (Model)": m,
                    "소요 시간 (초)": round(data["stats"]["processing_time_sec"], 2),
                    "처리된 청크 수": len(data["chunks_data"]),
                    "결과 텍스트 길이": len(data["full_text"])
                })
            
            if res_list:
                df_comp = pd.DataFrame(res_list)
                st.table(df_comp)
                
                if st.button("📑 종합 비교 리포트(Word) 생성 및 다운로드", type="primary"):
                    with st.spinner("비교 리포트를 생성하고 있습니다..."):
                        audio_p = st.session_state["comp_audio"]
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
