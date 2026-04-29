import pytesseract
import base64
import io
from PIL import Image, ImageDraw

def redact_image(image_path, output_path, findings, style='blackbar'):
    img = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(img)

    for finding in findings:
        for bbox in finding.get('words', []):
            x0, y0, x1, y1 = bbox
            if style == 'blackbar':
                draw.rectangle([x0, y0, x1, y1], fill='black')
            else:
                draw.rectangle([x0, y0, x1, y1], fill='white')
                draw.text((x0+2, y0+1), '[REDACTED]', fill='black')

    img.save(output_path)

def image_to_base64(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')
