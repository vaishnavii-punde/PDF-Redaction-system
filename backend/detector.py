import re
import os

# On cloud deployment, use regex only (no spacy/presidio - too heavy)
# On local machine, presidio is used automatically
NLP_AVAILABLE = False
IS_CLOUD = os.environ.get('RENDER', False) or os.environ.get('CLOUD', False)

if not IS_CLOUD:
    try:
        from presidio_analyzer import AnalyzerEngine
        analyzer = AnalyzerEngine()
        NLP_AVAILABLE = True
        print('Presidio NLP loaded successfully')
    except Exception as ex:
        print(f'Presidio not available, using regex only: {ex}')

REGEX_PATTERNS = {
    'phone':      r'(\+?\d[\d\s\-().]{7,}\d)',
    'email':      r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    'dob':        r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b',
    'pan':        r'\b[A-Z]{5}\d{4}[A-Z]\b',
    'aadhaar':    r'\b\d{4}\s\d{4}\s\d{4}\b',
    'ssn':        r'\b\d{3}-\d{2}-\d{4}\b',
    'passport':   r'\b[A-Z]\d{7}\b',
    'credit':     r'\b(?:\d{4}[\s\-]?){3}\d{4}\b',
    'ip':         r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    'voter_id':   r'\b[A-Z]{3}\d{7}\b',
    'driving_licence': r'\b[A-Z]{2}\d{2}\s?\d{11}\b',
    'epic':       r'\b[A-Z]{3}[0-9]{7}\b',
    'ifsc':       r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
    'gst':        r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b',
    'uan':        r'\b\d{12}\b',
}

FALSE_POSITIVE_PERSONS = {
    'django','flask','react','angular','vue','node','nodejs',
    'python','java','kotlin','swift','ruby','rails','golang',
    'jupyter','claude','gemini','copilot','chatgpt','openai',
    'tensorflow','pytorch','keras','sklearn','pandas','numpy',
    'docker','kubernetes','github','gitlab','aws','azure',
    'google','microsoft','apple','amazon','linux','ubuntu',
    'windows','macos','android','ios','html','css','sql',
    'mysql','postgres','mongodb','redis','fastapi','express',
    'streamlit','gradio','tableau','powerbi','git','rest','api',
}

BLOCKED_ENTITY_TYPES = {'URL', 'NRP', 'DATE_TIME'}

def is_false_positive(text, entity_type):
    cleaned = text.strip().lower()
    if entity_type == 'PERSON' and cleaned in FALSE_POSITIVE_PERSONS:
        return True
    if entity_type == 'PERSON' and len(cleaned) <= 3:
        return True
    if entity_type in BLOCKED_ENTITY_TYPES:
        return True
    if entity_type == 'PERSON' and text.isupper() and len(text) <= 5:
        return True
    return False

def detect_sensitive(pages, categories, custom_words, min_confidence=0.0):
    findings = []
    person_enabled = 'person' in [c.lower() for c in categories]

    for pg in pages:
        text = pg['text']
        words = pg['words']

        # NLP detection (local only)
        if NLP_AVAILABLE:
            try:
                results = analyzer.analyze(text=text, language='en')
                for r in results:
                    matched = text[r.start:r.end]
                    if r.entity_type == 'PERSON' and not person_enabled:
                        continue
                    if is_false_positive(matched, r.entity_type):
                        continue
                    if r.score < min_confidence:
                        continue
                    findings.append({
                        'text': matched,
                        'type': r.entity_type,
                        'score': round(r.score, 2),
                        'page': pg['page'],
                        'words': find_word_bboxes(matched, words)
                    })
            except Exception as ex:
                print(f'Presidio error: {ex}')

        # Regex detection (always runs)
        for cat, pattern in REGEX_PATTERNS.items():
            if categories and cat not in categories:
                continue
            for m in re.finditer(pattern, text, re.IGNORECASE):
                findings.append({
                    'text': m.group(),
                    'type': cat,
                    'score': 1.0,
                    'page': pg['page'],
                    'words': find_word_bboxes(m.group(), words)
                })

        # Custom words
        for word in custom_words:
            if not word.strip():
                continue
            for m in re.finditer(re.escape(word.strip()), text, re.IGNORECASE):
                findings.append({
                    'text': m.group(),
                    'type': 'custom',
                    'score': 1.0,
                    'page': pg['page'],
                    'words': find_word_bboxes(m.group(), words)
                })

    seen = set()
    unique = []
    for f in findings:
        key = (f['text'].lower().strip(), f['page'])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique

def find_word_bboxes(matched_text, words):
    result = []
    tokens = matched_text.lower().split()
    for w in words:
        if w['text'].lower() in tokens:
            result.append(w['bbox'])
    return result
