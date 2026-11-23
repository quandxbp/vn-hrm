"""Cheap visual signals per sampled frame: brightness, change vs previous frame, OCR text.

No face recognition. Students are matched only by the names written on screen (participant tiles).
"""
import re


def analyse_frames(frames, interval, settings):
    import numpy as np
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = settings.tesseract

    rows, previous = [], None
    for index, path in enumerate(frames):
        with Image.open(path) as image:
            gray = image.convert('L')
            small = np.asarray(gray.resize((160, 90)), dtype=np.float32)
            brightness = float(small.mean())
            change = float(np.abs(small - previous).mean()) if previous is not None else None
            previous = small
            text = pytesseract.image_to_string(gray, lang=settings.ocr_langs, config='--psm 11',
                                               timeout=30) if brightness > 12 else ''
        text = re.sub(r'\s+', ' ', text).strip()
        rows.append({'t': index * interval, 'brightness': round(brightness, 1),
                     'change': None if change is None else round(change, 2), 'text': text[:2000]})
    return {'interval': interval, 'frames': rows}
