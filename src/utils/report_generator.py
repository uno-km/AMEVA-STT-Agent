import os
import json
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def format_time(seconds):
    """초 단위 시간을 HH:MM:SS 형태로 변환"""
    if seconds is None:
        return "00:00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def add_transcription_table(doc, chunks_data):
    """청크(시간/화자/텍스트) 리스트를 표 형태로 문서에 삽입"""
    if not chunks_data:
        doc.add_paragraph("No transcription data available.")
        return
        
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Time'
    hdr_cells[1].text = 'Speaker'
    hdr_cells[2].text = 'Text'
    
    # 헤더 스타일 지정
    for cell in hdr_cells:
        for p in cell.paragraphs:
            p.runs[0].font.bold = True
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
    for chunk in chunks_data:
        row_cells = table.add_row().cells
        
        # 시간 추출 (start ~ end)
        start_t = chunk.get('start', 0)
        end_t = chunk.get('end', 0)
        time_str = f"{format_time(start_t)} - {format_time(end_t)}"
        
        # 화자 추출 (diarization 결과가 있으면 'speaker', 없으면 '-')
        speaker = chunk.get('speaker', '-')
        text = chunk.get('text', '').strip()
        
        row_cells[0].text = time_str
        row_cells[1].text = str(speaker)
        row_cells[2].text = text

def create_stt_report(audio_path, output_dir, stats, chunks_data, chart_image_path=None, task_id="Report"):
    """
    STT 및 화자 분리 결과에 대한 단일 파일 엔터프라이즈급 Word 리포트 생성
    """
    doc = Document()
    
    # Title
    title = doc.add_heading(f'Enterprise STT & Diarization Report', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Task ID: {task_id}\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}").alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 1. Audio & Processing Meta Information
    doc.add_heading('1. Processing Statistics', level=1)
    
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Property'
    hdr_cells[1].text = 'Value'
    
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024) if os.path.exists(audio_path) else 0
    
    stats_data = [
        ("File Path", os.path.basename(audio_path)),
        ("File Size", f"{file_size_mb:.2f} MB"),
        ("Processing Time", f"{stats.get('processing_time_sec', 0):.2f} sec"),
        ("Model", stats.get('model', 'Unknown')),
        ("Language", stats.get('language', 'auto')),
        ("Diarization", str(stats.get('diarization_enabled', False))),
        ("Total Chunks", str(len(chunks_data) if chunks_data else 0))
    ]
        
    for k, v in stats_data:
        row_cells = table.add_row().cells
        row_cells[0].text = k
        row_cells[1].text = str(v)
        
    doc.add_paragraph()
        
    # 2. Clustering Chart
    if chart_image_path and os.path.exists(chart_image_path):
        doc.add_heading('2. Speaker Clustering Visualization', level=1)
        doc.add_paragraph("PCA-reduced embeddings of speaker segments:")
        doc.add_picture(chart_image_path, width=Inches(6.0))
        doc.add_paragraph()
        
    # 3. Full Transcription Table
    doc.add_heading('3. Transcription Result (Timestamped)', level=1)
    add_transcription_table(doc, chunks_data)
                
    # Save the document
    os.makedirs(output_dir, exist_ok=True)
    report_filename = f"{task_id}_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    report_path = os.path.join(output_dir, report_filename)
    doc.save(report_path)
    
    return report_path


def create_comparison_report(audio_path, output_dir, models_data, task_id="Compare"):
    """
    여러 모델의 결과를 비교하는 엔터프라이즈급 Word 리포트 생성
    models_data: dict, 키는 모델명, 값은 { 'stats': {}, 'chunks_data': [], 'chart_image_path': str }
    """
    doc = Document()
    
    title = doc.add_heading(f'Enterprise STT Model Comparison Report', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Target Audio: {os.path.basename(audio_path)}\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()
    
    # Executive Summary (표 형태)
    doc.add_heading('Executive Summary: Performance Comparison', level=1)
    
    summary_table = doc.add_table(rows=1, cols=4)
    summary_table.style = 'Table Grid'
    hdr = summary_table.rows[0].cells
    hdr[0].text = 'Model'
    hdr[1].text = 'Proc. Time (sec)'
    hdr[2].text = 'Chunks'
    hdr[3].text = 'Length (Chars)'
    
    for model_name, data in models_data.items():
        stats = data.get('stats', {})
        chunks = data.get('chunks_data', [])
        total_len = sum([len(c.get('text', '')) for c in chunks])
        
        row = summary_table.add_row().cells
        row[0].text = model_name
        row[1].text = f"{stats.get('processing_time_sec', 0):.2f}"
        row[2].text = str(len(chunks))
        row[3].text = str(total_len)
        
    doc.add_page_break()
    
    # Detailed Results per Model
    for model_name, data in models_data.items():
        doc.add_heading(f'Model Result: {model_name}', level=1)
        stats = data.get('stats', {})
        chunks = data.get('chunks_data', [])
        chart_image_path = data.get('chart_image_path', None)
        
        doc.add_paragraph(f"Processing Time: {stats.get('processing_time_sec', 0):.2f} sec")
        
        if chart_image_path and os.path.exists(chart_image_path):
            doc.add_heading('Clustering Visualization', level=2)
            doc.add_picture(chart_image_path, width=Inches(5.0))
            
        doc.add_heading('Transcription (Timestamped)', level=2)
        add_transcription_table(doc, chunks)
        doc.add_page_break()
        
    os.makedirs(output_dir, exist_ok=True)
    report_filename = f"Comparison_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    report_path = os.path.join(output_dir, report_filename)
    doc.save(report_path)
    
    return report_path
