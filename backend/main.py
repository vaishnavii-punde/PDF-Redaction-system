from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import List
import uuid, os, zipfile, io, tempfile
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
    allow_origins=['*'],
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
    file_id = str(uuid.uuid4())
    input_path = f'{UPLOAD_DIR}/{file_id}.pdf'
    with open(input_path, 'wb') as f: f.write(await file.read())
    pages = extract_text_and_positions(input_path)
    if not any(p['text'].strip() for p in pages):
        pages = ocr_if_needed(input_path)
    cats = [c.strip() for c in categories.split(',') if c.strip()]
    words = [w.strip() for w in custom_words.split(',') if w.strip()]
    findings = detect_sensitive(pages, cats, words, min_confidence=min_confidence)
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
    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
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
    pages = [{'page':0,'text':full_text,
              'words':[{'text':c['text'],'bbox':(c['col']*100,c['row']*20,c['col']*100+90,c['row']*20+18),'page':0} for c in cells],
              'width':800,'height':600}]
    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
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
        return Response(status_code=404, content='Session not found')
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

    with tempfile.NamedTemporaryFile(suffix=output_ext, delete=False) as tmp:
        output_path = tmp.name

    if file_type == 'pdf':
        apply_redactions(session['input_path'], output_path, findings, style=style, custom_label=custom_label)
        media_type = 'application/pdf'
    elif file_type == 'image':
        redact_image(session['input_path'], output_path, findings, style=style)
        media_type = 'image/png'
    elif file_type == 'excel':
        redact_excel(session['input_path'], output_path, findings, style=style)
        media_type = 'application/octet-stream'

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

                if is_image:
                    import pytesseract
                    from PIL import Image
                    img = Image.open(input_path)
                    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    word_list = [{'text':t,'bbox':(data['left'][j],data['top'][j],data['left'][j]+data['width'][j],data['top'][j]+data['height'][j]),'page':0} for j,t in enumerate(data['text']) if t.strip()]
                    full_text = ' '.join(w['text'] for w in word_list)
                    pages = [{'page':0,'text':full_text,'words':word_list,'width':img.width,'height':img.height}]
                    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
                    redact_image(input_path, output_path, findings, style=style)
                elif is_excel:
                    df, cells, full_text = analyze_excel(input_path, [])
                    pages = [{'page':0,'text':full_text,'words':[{'text':c['text'],'bbox':(c['col']*100,c['row']*20,c['col']*100+90,c['row']*20+18),'page':0} for c in cells],'width':800,'height':600}]
                    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
                    redact_excel(input_path, output_path, findings, style=style)
                else:
                    pages = extract_text_and_positions(input_path)
                    if not any(p['text'].strip() for p in pages):
                        pages = ocr_if_needed(input_path)
                    findings = detect_sensitive(pages, cats, words_list, min_confidence=min_confidence)
                    apply_redactions(input_path, output_path, findings, style=style, custom_label=custom_label)

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
        headers={'Content-Disposition':'attachment; filename=redacted_batch.zip',
                 'X-Results': str(results)}
    )

@app.get('/audit')
def get_audit_log():
    from audit import get_all_logs
    return get_all_logs()

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run('main:app', host='0.0.0.0', port=port)
