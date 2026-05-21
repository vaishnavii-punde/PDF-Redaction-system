from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List
import uuid, os, zipfile, io, tempfile

app = FastAPI(title='PDF Redactor API')
app.add_middleware(CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

UPLOAD_DIR = 'uploads'
OUTPUT_DIR = 'output'
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

sessions = {}

# Safe imports — app won't crash if optional libraries missing
try:
    from parser_pdf import extract_text_and_positions
    PDF_AVAILABLE = True
except Exception as ex:
    print(f'parser_pdf not available: {ex}')
    PDF_AVAILABLE = False

try:
    from ocr import ocr_if_needed
    OCR_AVAILABLE = True
except Exception as ex:
    print(f'OCR not available: {ex}')
    OCR_AVAILABLE = False

try:
    from detector import detect_sensitive
    DETECTOR_AVAILABLE = True
except Exception as ex:
    print(f'detector not available: {ex}')
    DETECTOR_AVAILABLE = False

try:
    from redactor import apply_redactions
    REDACTOR_AVAILABLE = True
except Exception as ex:
    print(f'redactor not available: {ex}')
    REDACTOR_AVAILABLE = False

try:
    from preview import get_preview_pages
    PREVIEW_AVAILABLE = True
except Exception as ex:
    print(f'preview not available: {ex}')
    PREVIEW_AVAILABLE = False

try:
    from profiles import load_profiles, add_profile, delete_profile
    PROFILES_AVAILABLE = True
except Exception as ex:
    print(f'profiles not available: {ex}')
    PROFILES_AVAILABLE = False
    def load_profiles(): return {}
    def add_profile(n,c,w): return {}
    def delete_profile(n): return {}

try:
    from audit import log_redaction, get_all_logs
    AUDIT_AVAILABLE = True
except Exception as ex:
    print(f'audit not available: {ex}')
    AUDIT_AVAILABLE = False
    def log_redaction(*a): pass
    def get_all_logs(): return []

try:
    from image_handler import redact_image
    IMAGE_AVAILABLE = True
except Exception as ex:
    print(f'image_handler not available: {ex}')
    IMAGE_AVAILABLE = False

try:
    from excel_handler import analyze_excel, redact_excel
    EXCEL_AVAILABLE = True
except Exception as ex:
    print(f'excel_handler not available: {ex}')
    EXCEL_AVAILABLE = False

class ProfileRequest(BaseModel):
    name: str
    categories: List[str]
    custom_words: List[str]

@app.get('/health')
def health():
    return {
        'status': 'ok',
        'pdf': PDF_AVAILABLE,
        'ocr': OCR_AVAILABLE,
        'detector': DETECTOR_AVAILABLE,
        'redactor': REDACTOR_AVAILABLE,
        'preview': PREVIEW_AVAILABLE,
    }

@app.get('/profiles')
def get_profiles(): return load_profiles()

@app.post('/profiles')
def create_profile(req: ProfileRequest):
    return add_profile(req.name, req.categories, req.custom_words)

@app.delete('/profiles/{name}')
def remove_profile(name: str): return delete_profile(name)

@app.post('/analyze')
async def analyze(
    file: UploadFile = File(...),
    categories: str = Form(default=''),
    custom_words: str = Form(default=''),
    min_confidence: float = Form(default=0.0)
):
    if not PDF_AVAILABLE or not DETECTOR_AVAILABLE:
        return {'error': 'PDF processing not available'}

    file_id = str(uuid.uuid4())
    input_path = f'{UPLOAD_DIR}/{file_id}.pdf'
    with open(input_path, 'wb') as f: f.write(await file.read())

    pages = extract_text_and_positions(input_path)
    if not any(p['text'].strip() for p in pages) and OCR_AVAILABLE:
        pages = ocr_if_needed(input_path)

    cats = [c.strip() for c in categories.split(',') if c.strip()]
    words = [w.strip() for w in custom_words.split(',') if w.strip()]
    findings = detect_sensitive(pages, cats, words, min_confidence=min_confidence)

    preview_pages = []
    if PREVIEW_AVAILABLE:
        preview_pages = get_preview_pages(input_path, findings)

    sessions[file_id] = {
        'input_path': input_path,
        'findings': findings,
        'filename': file.filename,
        'type': 'pdf'
    }
    return {
        'file_id': file_id,
        'findings': findings,
        'count': len(findings),
        'original_filename': file.filename,
        'preview_pages': preview_pages
    }

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

    try:
        import pytesseract
        from PIL import Image
        import base64
        img = Image.open(input_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        word_list = []
        for j, text in enumerate(data['text']):
            if text.strip():
                word_list.append({'text': text,
                    'bbox': (data['left'][j], data['top'][j],
                             data['left'][j]+data['width'][j],
                             data['top'][j]+data['height'][j]),
                    'page': 0})
        full_text = ' '.join(w['text'] for w in word_list)
        pages = [{'page':0,'text':full_text,'words':word_list,'width':img.width,'height':img.height}]
        findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence) if DETECTOR_AVAILABLE else []
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        highlights = []
        for fi in findings:
            for bbox in fi.get('words', []):
                highlights.append({'x':bbox[0],'y':bbox[1],'w':bbox[2]-bbox[0],'h':bbox[3]-bbox[1],'type':fi['type'],'text':fi['text']})
        sessions[file_id] = {'input_path':input_path,'findings':findings,'filename':file.filename,'type':'image','ext':ext}
        return {'file_id':file_id,'findings':findings,'count':len(findings),
                'original_filename':file.filename,
                'preview_pages':[{'page_num':0,'image':img_b64,'width':img.width,'height':img.height,'highlights':highlights}]}
    except Exception as ex:
        return {'error': f'Image processing failed: {str(ex)}'}

@app.post('/analyze-excel')
async def analyze_excel_route(
    file: UploadFile = File(...),
    categories: str = Form(default=''),
    custom_words: str = Form(default=''),
    min_confidence: float = Form(default=0.0)
):
    if not EXCEL_AVAILABLE:
        return {'error': 'Excel processing not available'}
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = f'{UPLOAD_DIR}/{file_id}{ext}'
    with open(input_path, 'wb') as f: f.write(await file.read())
    cats = [c.strip() for c in categories.split(',') if c.strip()]
    words_list = [w.strip() for w in custom_words.split(',') if w.strip()]
    df, cells, full_text = analyze_excel(input_path, [])
    pages = [{'page':0,'text':full_text,
              'words':[{'text':c['text'],'bbox':(c['col']*100,c['row']*20,c['col']*100+90,c['row']*20+18),'page':0} for c in cells],
              'width':800,'height':600}]
    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence) if DETECTOR_AVAILABLE else []
    sessions[file_id] = {'input_path':input_path,'findings':findings,'filename':file.filename,'type':'excel','ext':ext}
    return {'file_id':file_id,'findings':findings,'count':len(findings),'original_filename':file.filename,'preview_pages':[]}

@app.post('/confirm/{file_id}')
def confirm_redaction(
    file_id: str,
    style: str = Query(default='blackbar'),
    custom_label: str = Query(default='[REDACTED]'),
    removed_indices: str = Query(default='')
):
    if file_id not in sessions:
        return {'error': 'Session not found or expired'}

    session = sessions[file_id]
    findings = session['findings']

    if removed_indices:
        try:
            removed = set(int(i) for i in removed_indices.split(',') if i.strip())
            findings = [f for i,f in enumerate(findings) if i not in removed]
        except: pass

    file_type = session.get('type','pdf')
    ext = session.get('ext','.pdf')
    output_ext = ext if file_type != 'pdf' else '.pdf'

    try:
        with tempfile.NamedTemporaryFile(suffix=output_ext, delete=False) as tmp:
            output_path = tmp.name

        if file_type == 'pdf' and REDACTOR_AVAILABLE:
            apply_redactions(session['input_path'], output_path, findings, style=style, custom_label=custom_label)
            media_type = 'application/pdf'
        elif file_type == 'image' and IMAGE_AVAILABLE:
            redact_image(session['input_path'], output_path, findings, style=style)
            media_type = 'image/png'
        elif file_type == 'excel' and EXCEL_AVAILABLE:
            redact_excel(session['input_path'], output_path, findings, style=style)
            media_type = 'application/octet-stream'
        else:
            return {'error': 'Processing not available for this file type'}

        log_redaction(file_id, session['filename'], findings)

        if os.path.exists(session['input_path']):
            os.remove(session['input_path'])
        del sessions[file_id]

        with open(output_path, 'rb') as f:
            content = f.read()
        os.remove(output_path)

        return Response(
            content=content,
            media_type=media_type,
            headers={'Content-Disposition': f'attachment; filename=redacted{output_ext}'}
        )
    except Exception as ex:
        return {'error': f'Redaction failed: {str(ex)}'}

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
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1].lower()
            input_path = f'{UPLOAD_DIR}/{file_id}{ext}'
            is_image = ext in ['.png','.jpg','.jpeg','.webp']
            is_excel = ext in ['.xlsx','.xls','.csv']
            try:
                with open(input_path,'wb') as f: f.write(await file.read())
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    output_path = tmp.name

                if is_excel and EXCEL_AVAILABLE:
                    df, cells, full_text = analyze_excel(input_path, [])
                    pages = [{'page':0,'text':full_text,'words':[{'text':c['text'],'bbox':(c['col']*100,c['row']*20,c['col']*100+90,c['row']*20+18),'page':0} for c in cells],'width':800,'height':600}]
                    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence) if DETECTOR_AVAILABLE else []
                    redact_excel(input_path, output_path, findings, style=style)
                elif PDF_AVAILABLE and REDACTOR_AVAILABLE:
                    pages = extract_text_and_positions(input_path)
                    if not any(p['text'].strip() for p in pages) and OCR_AVAILABLE:
                        pages = ocr_if_needed(input_path)
                    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence) if DETECTOR_AVAILABLE else []
                    apply_redactions(input_path, output_path, findings, style=style, custom_label=custom_label)
                else:
                    findings = []

                log_redaction(file_id, file.filename, findings)
                if os.path.exists(input_path): os.remove(input_path)

                with open(output_path,'rb') as f:
                    zf.writestr('redacted_'+file.filename, f.read())
                os.remove(output_path)
                results.append({'filename':file.filename,'count':len(findings),'status':'done'})
            except Exception as ex:
                results.append({'filename':file.filename,'count':0,'status':'error','error':str(ex)})

    return Response(
        content=zip_buffer.getvalue(),
        media_type='application/zip',
        headers={
            'Content-Disposition': 'attachment; filename=redacted_batch.zip',
            'X-Batch-Results': str(len([r for r in results if r['status']=='done'])) + ' succeeded'
        }
    )

@app.get('/audit')
def get_audit_log():
    return get_all_logs()

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 10000))
    uvicorn.run('main:app', host='0.0.0.0', port=port)
