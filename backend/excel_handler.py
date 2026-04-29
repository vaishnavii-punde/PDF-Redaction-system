import pandas as pd
import os

def analyze_excel(file_path, findings):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.csv':
        df = pd.read_csv(file_path, dtype=str).fillna('')
    else:
        df = pd.read_excel(file_path, dtype=str).fillna('')

    full_text = df.to_string()
    cells = []
    for row_idx, row in df.iterrows():
        for col_idx, val in enumerate(row):
            if str(val).strip():
                cells.append({'text': str(val), 'row': row_idx, 'col': col_idx})

    return df, cells, full_text

def redact_excel(file_path, output_path, findings, style='blackbar'):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.csv':
        df = pd.read_csv(file_path, dtype=str).fillna('')
    else:
        df = pd.read_excel(file_path, dtype=str).fillna('')

    sensitive_values = set(f['text'].lower().strip() for f in findings)

    def redact_cell(val):
        v = str(val)
        for s in sensitive_values:
            if s and s in v.lower():
                v = '[REDACTED]' if style == 'text' else 'XXXXXXXX'
        return v

    redacted_df = df.applymap(redact_cell)

    if ext == '.csv':
        redacted_df.to_csv(output_path, index=False)
    else:
        redacted_df.to_excel(output_path, index=False)
