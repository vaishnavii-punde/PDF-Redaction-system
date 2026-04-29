import fitz

def apply_redactions(input_path, output_path, findings, style='blackbar', custom_label='[REDACTED]'):
    doc = fitz.open(input_path)

    for finding in findings:
        page_num = finding.get('page', 0)
        if page_num >= len(doc):
            continue
        page = doc[page_num]

        bboxes = finding.get('words', [])
        if not bboxes:
            for inst in page.search_for(finding.get('text', '')):
                bboxes.append((inst.x0, inst.y0, inst.x1, inst.y1))

        for bbox in bboxes:
            rect = fitz.Rect(bbox)

            if style == 'blackbar':
                page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))

            elif style == 'text':
                font_size = rect.height * 0.75
                if font_size < 6: font_size = 6
                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                page.insert_text(
                    (rect.x0, rect.y1 - 1),
                    custom_label,
                    fontsize=font_size,
                    color=(0, 0, 0),
                    fontname='helv'
                )

            elif style == 'blur':
                # Simulate blur with overlapping semi-transparent rectangles
                page.draw_rect(rect, color=(0.5, 0.5, 0.5), fill=(0.8, 0.8, 0.8))
                small = 3
                for i in range(int(rect.width / small)):
                    for j in range(int(rect.height / small)):
                        import random
                        g = 0.6 + random.random() * 0.35
                        r2 = fitz.Rect(
                            rect.x0 + i*small, rect.y0 + j*small,
                            rect.x0 + (i+1)*small, rect.y0 + (j+1)*small
                        )
                        page.draw_rect(r2, color=(g,g,g), fill=(g,g,g))

            elif style == 'strikethrough':
                mid_y = (rect.y0 + rect.y1) / 2
                page.draw_line(
                    fitz.Point(rect.x0, mid_y),
                    fitz.Point(rect.x1, mid_y),
                    color=(1, 0, 0),
                    width=2
                )

        if style in ('blackbar', 'text', 'blur'):
            page.apply_redactions() if style != 'blur' else None

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f'Saved: {output_path}')
