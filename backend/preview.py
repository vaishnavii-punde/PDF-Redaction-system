import fitz
import base64

def get_preview_pages(pdf_path, findings):
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(1.5, 1.5)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes('png')
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        page_findings = [f for f in findings if f.get('page') == page_num]
        highlights = []
        for f in page_findings:
            for bbox in f.get('words', []):
                highlights.append({
                    'x': bbox[0] * 1.5,
                    'y': bbox[1] * 1.5,
                    'w': (bbox[2] - bbox[0]) * 1.5,
                    'h': (bbox[3] - bbox[1]) * 1.5,
                    'type': f['type'],
                    'text': f['text']
                })
            if not f.get('words'):
                instances = page.search_for(f.get('text', ''))
                for inst in instances:
                    highlights.append({
                        'x': inst.x0 * 1.5,
                        'y': inst.y0 * 1.5,
                        'w': (inst.x1 - inst.x0) * 1.5,
                        'h': (inst.y1 - inst.y0) * 1.5,
                        'type': f['type'],
                        'text': f['text']
                    })
        pages.append({
            'page_num': page_num,
            'image': img_b64,
            'width': pix.width,
            'height': pix.height,
            'highlights': highlights
        })
    doc.close()
    return pages
