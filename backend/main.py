from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import uuid, os, zipfile
from parser_pdf import extract_text_and_positions
from ocr import ocr_if_needed
from detector import detect_sensitive
from redactor import apply_redactions
from audit import log_redaction
from preview import get_preview_pages
from profiles import load_profiles, add_profile, delete_profile
from image_handler import redact_image
from excel_handler import analyze_excel, redact_excel

app = FastAPI(title='PDF Redactor API')
app.add_middleware(CORSMiddleware,
    allow_origins=['http://localhost:5173','http://localhost:3000'],
    allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

UPLOAD_DIR = 'uploads'
OUTPUT_DIR = 'output'
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

sessions = {}

class ProfileRequest(BaseModel):
    name: str
    categories: List[str]
    custom_words: List[str]

@app.get('/health')
def health(): return {'status': 'ok'}

@app.get('/profiles')
def get_profiles(): return load_profiles()

@app.post('/profiles')
def create_profile(req: ProfileRequest): return add_profile(req.name, req.categories, req.custom_words)

@app.delete('/profiles/{name}')
def remove_profile(name: str): return delete_profile(name)

@app.post('/analyze')
async def analyze(
    file: UploadFile = File(...),
    categories: str = Form(default=''),
    custom_words: str = Form(default=''),
    min_confidence: float = Form(default=0.0)
):
    file_id = str(uuid.uuid4())
    input_path = f'{UPLOAD_DIR}/{file_id}.pdf'
    with open(input_path, 'wb') as f: f.write(await file.read())
    pages = extract_text_and_positions(input_path)
    if not any(p['text'].strip() for p in pages): pages = ocr_if_needed(input_path)
    cats = [c.strip() for c in categories.split(',') if c.strip()]
    words = [w.strip() for w in custom_words.split(',') if w.strip()]
    findings = detect_sensitive(pages, cats, words, min_confidence=min_confidence)
    preview_pages = get_preview_pages(input_path, findings)
    sessions[file_id] = {'input_path': input_path, 'findings': findings, 'filename': file.filename, 'type': 'pdf'}
    return {'file_id': file_id, 'findings': findings, 'count': len(findings),
            'original_filename': file.filename, 'preview_pages': preview_pages}

@app.post('/analyze-image')
async def analyze_image_route(
    file: UploadFile = File(...),
    categories: str = Form(default=''),
    custom_words: str = Form(default=''),
    min_confidence: float = Form(default=0.0)
):
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = f'{UPLOAD_DIR}/{file_id}{ext}'
    with open(input_path, 'wb') as f: f.write(await file.read())
    cats = [c.strip() for c in categories.split(',') if c.strip()]
    words_list = [w.strip() for w in custom_words.split(',') if w.strip()]
    import pytesseract
    from PIL import Image
    import base64, io
    img = Image.open(input_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    word_list = []
    for j, text in enumerate(data['text']):
        if text.strip():
            word_list.append({'text': text, 'bbox': (data['left'][j], data['top'][j],
                data['left'][j]+data['width'][j], data['top'][j]+data['height'][j]), 'page': 0})
    full_text = ' '.join(w['text'] for w in word_list)
    pages = [{'page': 0, 'text': full_text, 'words': word_list, 'width': img.width, 'height': img.height}]
    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    highlights = []
    for fi in findings:
        for bbox in fi.get('words', []):
            highlights.append({'x': bbox[0], 'y': bbox[1], 'w': bbox[2]-bbox[0], 'h': bbox[3]-bbox[1], 'type': fi['type'], 'text': fi['text']})
    preview_pages = [{'page_num': 0, 'image': img_b64, 'width': img.width, 'height': img.height, 'highlights': highlights}]
    sessions[file_id] = {'input_path': input_path, 'findings': findings, 'filename': file.filename, 'type': 'image', 'ext': ext}
    return {'file_id': file_id, 'findings': findings, 'count': len(findings), 'original_filename': file.filename, 'preview_pages': preview_pages}

@app.post('/analyze-excel')
async def analyze_excel_route(
    file: UploadFile = File(...),
    categories: str = Form(default=''),
    custom_words: str = Form(default=''),
    min_confidence: float = Form(default=0.0)
):
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = f'{UPLOAD_DIR}/{file_id}{ext}'
    with open(input_path, 'wb') as f: f.write(await file.read())
    cats = [c.strip() for c in categories.split(',') if c.strip()]
    words_list = [w.strip() for w in custom_words.split(',') if w.strip()]
    df, cells, full_text = analyze_excel(input_path, [])
    pages = [{'page': 0, 'text': full_text,
              'words': [{'text': c['text'], 'bbox': (c['col']*100, c['row']*20, c['col']*100+90, c['row']*20+18), 'page': 0} for c in cells],
              'width': 800, 'height': 600}]
    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
    sessions[file_id] = {'input_path': input_path, 'findings': findings, 'filename': file.filename, 'type': 'excel', 'ext': ext}
    return {'file_id': file_id, 'findings': findings, 'count': len(findings), 'original_filename': file.filename, 'preview_pages': []}

@app.post('/confirm/{file_id}')
def confirm_redaction(
    file_id: str,
    style: str = Query(default='blackbar'),
    custom_label: str = Query(default='[REDACTED]'),
    removed_indices: str = Query(default='')
):
    if file_id not in sessions: return {'error': 'Session not found'}
    session = sessions[file_id]

    # Filter out items the user removed
    findings = session['findings']
    if removed_indices:
        try:
            removed = set(int(i) for i in removed_indices.split(',') if i.strip())
            findings = [f for i, f in enumerate(findings) if i not in removed]
        except: pass

    file_type = session.get('type', 'pdf')
    ext = session.get('ext', '.pdf')
    output_ext = ext if file_type != 'pdf' else '.pdf'
    output_path = f'{OUTPUT_DIR}/{file_id}_redacted{output_ext}'

    if file_type == 'pdf':
        apply_redactions(session['input_path'], output_path, findings, style=style, custom_label=custom_label)
    elif file_type == 'image':
        redact_image(session['input_path'], output_path, findings, style=style)
    elif file_type == 'excel':
        redact_excel(session['input_path'], output_path, findings, style=style)

    log_redaction(file_id, session['filename'], findings)
    if os.path.exists(session['input_path']): os.remove(session['input_path'])
    del sessions[file_id]
    return {'file_id': file_id, 'status': 'done', 'ext': output_ext}

@app.post('/batch')
async def batch_redact(
    files: List[UploadFile] = File(...),
    categories: str = Form(default=''),
    custom_words: str = Form(default=''),
    style: str = Form(default='blackbar'),
    custom_label: str = Form(default='[REDACTED]'),
    min_confidence: float = Form(default=0.0)
):
    cats = [c.strip() for c in categories.split(',') if c.strip()]
    words_list = [w.strip() for w in custom_words.split(',') if w.strip()]
    results = []
    output_files = []
    for file in files:
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1].lower()
        input_path = f'{UPLOAD_DIR}/{file_id}{ext}'
        is_image = ext in ['.png','.jpg','.jpeg','.webp']
        is_excel = ext in ['.xlsx','.xls','.csv']
        output_path = f'{OUTPUT_DIR}/{file_id}_redacted{ext}'
        try:
            with open(input_path, 'wb') as f: f.write(await file.read())
            if is_image:
                import pytesseract
                from PIL import Image
                img = Image.open(input_path)
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                word_list = [{'text': t, 'bbox': (data['left'][j], data['top'][j], data['left'][j]+data['width'][j], data['top'][j]+data['height'][j]), 'page': 0} for j, t in enumerate(data['text']) if t.strip()]
                full_text = ' '.join(w['text'] for w in word_list)
                pages = [{'page': 0, 'text': full_text, 'words': word_list, 'width': img.width, 'height': img.height}]
                findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
                redact_image(input_path, output_path, findings, style=style)
            elif is_excel:
                df, cells, full_text = analyze_excel(input_path, [])
                pages = [{'page': 0, 'text': full_text, 'words': [{'text': c['text'], 'bbox': (c['col']*100, c['row']*20, c['col']*100+90, c['row']*20+18), 'page': 0} for c in cells], 'width': 800, 'height': 600}]
                findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
                redact_excel(input_path, output_path, findings, style=style)
            else:
                pages = extract_text_and_positions(input_path)
                if not any(p['text'].strip() for p in pages): pages = ocr_if_needed(input_path)
                findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
                apply_redactions(input_path, output_path, findings, style=style, custom_label=custom_label)
            log_redaction(file_id, file.filename, findings)
            if os.path.exists(input_path): os.remove(input_path)
            results.append({'file_id': file_id, 'filename': file.filename, 'count': len(findings), 'status': 'done'})
            output_files.append((output_path, 'redacted_' + file.filename))
        except Exception as ex:
            results.append({'file_id': file_id, 'filename': file.filename, 'count': 0, 'status': 'error', 'error': str(ex)})
    batch_id = str(uuid.uuid4())
    zip_path = f'{OUTPUT_DIR}/{batch_id}_batch.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for op, an in output_files:
            if os.path.exists(op): zf.write(op, an)
    return {'batch_id': batch_id, 'results': results, 'total': len(files),
            'success': len([r for r in results if r['status']=='done']),
            'failed': len([r for r in results if r['status']=='error'])}

@app.get('/download/{file_id}')
def download(file_id: str):
    for ext in ['.pdf','.png','.jpg','.jpeg','.webp','.xlsx','.xls','.csv']:
        path = f'{OUTPUT_DIR}/{file_id}_redacted{ext}'
        if os.path.exists(path):
            mt = 'application/pdf' if ext=='.pdf' else 'image/png' if ext in ['.png','.jpg','.jpeg','.webp'] else 'application/octet-stream'
            return FileResponse(path, media_type=mt, filename='redacted'+ext)
    return {'error': 'File not found'}

@app.get('/download-batch/{batch_id}')
def download_batch(batch_id: str):
    path = f'{OUTPUT_DIR}/{batch_id}_batch.zip'
    if not os.path.exists(path): return {'error': 'Batch not found'}
    return FileResponse(path, media_type='application/zip', filename='redacted_batch.zip')

@app.get('/audit')
def get_audit_log():
    from audit import get_all_logs
    return get_all_logs()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)
