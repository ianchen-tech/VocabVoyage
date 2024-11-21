import pypdf
from pdf2image import convert_from_path
import pytesseract

pdf_path = 'TOEIC.pdf'

# 直接提取文字
with open(pdf_path, 'rb') as file:
    reader = pypdf.PdfReader(file)
    text = ""
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text.strip():
            text += f"\n\n=== Page {i+1} ===\n{page_text}"

# 使用 OCR
images = convert_from_path(pdf_path)
text = ""
for i, image in enumerate(images):
    page_text = pytesseract.image_to_string(image, lang='chi_tra+eng')
    text += f"\n\n=== Page {i+1} ===\n{page_text}"

print()