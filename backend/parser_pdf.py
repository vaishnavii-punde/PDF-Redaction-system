import fitz

def extract_text_and_positions(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for page_num, page in enumerate(doc):
        words_raw = page.get_text("words")
        words = [{"text": w[4], "bbox": (w[0],w[1],w[2],w[3]), "page": page_num} for w in words_raw]
        full_text = " ".join(w["text"] for w in words)
        pages.append({"page": page_num, "text": full_text, "words": words,
                       "width": page.rect.width, "height": page.rect.height})
    doc.close()
    return pages
