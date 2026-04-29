import pytesseract
from pdf2image import convert_from_path

def ocr_if_needed(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        print(f"pdf2image error: {e}")
        return []
    pages = []
    for i, img in enumerate(images):
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words = []
        for j, text in enumerate(data["text"]):
            if text.strip():
                words.append({"text": text,
                    "bbox": (data["left"][j], data["top"][j],
                             data["left"][j]+data["width"][j],
                             data["top"][j]+data["height"][j]),
                    "page": i})
        pages.append({"page": i, "text": " ".join(w["text"] for w in words),
                       "words": words, "width": img.width, "height": img.height})
    return pages
