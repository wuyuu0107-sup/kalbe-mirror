import io, re, os
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
import pytesseract

# -------- Tesseract binary path (macOS/Win/Linux) --------
TESS_CANDIDATES = [
    os.getenv("TESSERACT_CMD"),
    "/opt/homebrew/bin/tesseract",   # macOS Apple Silicon (brew)
    "/usr/local/bin/tesseract",      # macOS Intel (brew)
    "tesseract",                     # PATH fallback (Linux/Windows if added)
]
for p in TESS_CANDIDATES:
    if p and os.path.exists(p):
        pytesseract.pytesseract.tesseract_cmd = p
        break

# -------- Optional: TrOCR (for handwriting/digits). Can be heavy. --------
# Comment these 3 lines if you don't want TrOCR right now.
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
_processor = None
_model = None

def get_trocr():
    global _processor, _model
    if _processor is None or _model is None:
        name = "microsoft/trocr-small-handwritten"
        _processor = TrOCRProcessor.from_pretrained(name)
        _model = VisionEncoderDecoderModel.from_pretrained(name)
        _model.eval()
    return _processor, _model

# -------- PDF support (render first page) --------
# Requires: pip install pdf2image  AND  poppler installed (brew install poppler)
from pdf2image import convert_from_bytes

def load_image_or_pdf(file_bytes: bytes, filename: str) -> Image.Image:
    """
    Return a PIL Image from bytes. If it's a PDF, render the first page.
    """
    if filename.lower().endswith(".pdf"):
        pages = convert_from_bytes(file_bytes)
        if not pages:
            raise ValueError("PDF has no pages.")
        im = pages[0]
        if im.mode != "RGB":
            im = im.convert("RGB")
        return im
    # else: assume image
    try:
        im = Image.open(io.BytesIO(file_bytes))
        if im.mode != "RGB":
            im = im.convert("RGB")
        return im
    except UnidentifiedImageError:
        raise ValueError("Unsupported file type. Upload PNG/JPG or PDF.")

# -------- Preprocess & OCR --------
def preprocess_pil(im: Image.Image) -> Image.Image:
    # Grayscale + Otsu threshold, small opening: good for forms
    arr = np.array(im.convert("L"))
    _, th = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k)
    return Image.fromarray(th)

def tesseract_text(im: Image.Image) -> str:
    # PSM 6 treats the image as a block of text, good for forms
    return pytesseract.image_to_string(im, config="--psm 6")

def trocr_text(im: Image.Image) -> str:
    # Use sparingly (heavier); great for handwriting/digits
    processor, model = get_trocr()
    pixel_values = processor(images=im, return_tensors="pt").pixel_values
    out_ids = model.generate(pixel_values, max_length=128)
    return processor.batch_decode(out_ids, skip_special_tokens=True)[0]

# -------- Field extraction tuned to your dummy layout --------
DATE_ALPH = (
    r"(?:\d{2}\s*[\/-]?\s*[A-Z]{3}\s*[\/-]?\s*\d{4})"
    r"|\d{2}[\/-]\d{2}[\/-]\d{4}"
    r"|\d{2}\s*[A-Z]{3}\s*\d{4}"
)

def extract_fields(full_text: str):
    text = re.sub(r"[^\S\r\n]+", " ", full_text)  # collapse spaces
    fields = {}

    # Header-ish
    m = re.search(r"Study\s*Drug\s*:\s*([^\n\r]+)", text, re.I)
    if m: fields["study_drug"] = m.group(1).strip()

    m = re.search(r"Study\s*No\.\s*:\s*([A-Z0-9\/-]+)", text, re.I)
    if m: fields["study_no"] = m.group(1).strip()

    # Demography
    fields["sex"] = (
        "Female" if re.search(r"\bFemale\b|\[.?x.?]\s*Female", text, re.I)
        else ("Male" if re.search(r"\bMale\b", text, re.I) else None)
    )
    m = re.search(r"Date of birth\s*:\s*(" + DATE_ALPH + r")", text, re.I)
    if m: fields["dob"] = m.group(1)
    m = re.search(r"\bAge\s*:\s*(\d+)", text, re.I)
    if m: fields["age"] = int(m.group(1))
    m = re.search(r"\bWeight\s*:\s*(\d+)\s*Kg?", text, re.I)
    if m: fields["weight_kg"] = int(m.group(1))
    m = re.search(r"\bHeight\s*:\s*(\d+)\s*cm", text, re.I)
    if m: fields["height_cm"] = int(m.group(1))
    m = re.search(r"Body\s*Mass\s*Index\s*:\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m: fields["bmi"] = float(m.group(1))

    # Smoking / Alcohol / COVID
    fields["smoking"] = (
        "Yes" if re.search(r"Smoking.*Yes", text, re.I | re.S)
        else "No" if re.search(r"Smoking.*No", text, re.I | re.S)
        else None
    )
    fields["alcohol"] = (
        "Yes" if re.search(r"Alcohol.*Yes", text, re.I | re.S)
        else "No" if re.search(r"Alcohol.*No", text, re.I | re.S)
        else None
    )
    fields["covid_exposure_14d"] = (
        "Yes" if re.search(r"history.*14\s*days.*Yes", text, re.I | re.S)
        else "No" if re.search(r"history.*14\s*days.*No", text, re.I | re.S)
        else None
    )

    # Vitals
    m = re.search(r"Body\s*Temperature\s*:\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m: fields["temp_c"] = float(m.group(1))
    m = re.search(r"Blood pressure\s*\(Systolic\/ Diastolic\)\s*:\s*(\d+)\s*[\/:\-]\s*(\d+)", text, re.I)
    if m: fields["bp"] = {"sys": int(m.group(1)), "dia": int(m.group(2))}
    m = re.search(r"Heart rate\s*:\s*(\d+)", text, re.I)
    if m: fields["hr_bpm"] = int(m.group(1))
    m = re.search(r"Respiration rate\s*:\s*(\d+)", text, re.I)
    if m: fields["rr_min"] = int(m.group(1))
    m = re.search(r"ECG.*Result Assessment\s*:\s*(Normal|Abnormal)", text, re.I | re.S)
    if m: fields["ecg"] = m.group(1).title()

    # Serology
    def yesno(name):
        m_ = re.search(rf"\b{name}\b.*?(Negative|Positive)", text, re.I | re.S)
        return m_.group(1).title() if m_ else None
    fields["HBsAg"] = yesno("HBsAg")
    fields["HCV"]   = yesno("HCV")
    fields["HIV"]   = yesno("HIV")
    fields["covid_rapid"] = (
        "Negative" if re.search(r"COVID-19 RAPID TEST RESULT.*?Negative", text, re.I | re.S)
        else None
    )

    return fields

# -------- Pipeline (bytes + filename) -> JSON --------
def run_ocr_pipeline(file_bytes: bytes, filename: str):
    """
    Load page (image or first page of PDF) -> preprocess -> OCR -> parse fields.
    """
    im = load_image_or_pdf(file_bytes, filename)
    im = preprocess_pil(im)

    text_tess = tesseract_text(im)

    # TrOCR is optional; if it fails (e.g., no GPU/torch), we continue with Tesseract result.
    try:
        text_hand = trocr_text(im)
    except Exception:
        text_hand = ""

    full_text = (text_tess + "\n" + text_hand).strip()
    return {
        "fields": extract_fields(full_text),
        "raw_text": full_text
    }
