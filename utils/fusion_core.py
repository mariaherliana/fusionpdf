import os, re
import PyPDF2
from io import BytesIO

def extract_value_from_pdf(pdf_file_path: str, keyword: str) -> float:
    if not os.path.exists(pdf_file_path) or not pdf_file_path.lower().endswith('.pdf'):
        return -1

    try:
        with open(pdf_file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = "".join((page.extract_text() or "") for page in reader.pages)

        text = re.sub(r'[\u00A0\u202F]', ' ', text)
        text = re.sub(r'\s+', ' ', text)

        if keyword.lower().strip() in ["vat", "v.a.t", "ppn"]:
            pattern = r"(?i)v[\s\u00A0\u202F\.\-]*a[\s\u00A0\u202F\.\-]*t[\s\u00A0\u202F\.\-]*[\s:\-\(\)%]*([\d]+(?:[.,]\d{3})*(?:[.,]\d{2})?)"
        else:
            pattern = rf"(?i){re.escape(keyword)}[\s:\-\(\)%]*([\d]+(?:[.,]\d{{3}})*(?:[.,]\d{{2}})?)"

        value_match = re.search(pattern, text)
        if value_match:
            raw = value_match.group(1)
        elif keyword.lower().strip() in ["vat", "v.a.t", "ppn"]:
            sub_match = re.search(r"(?:Sub\s*Total|Subtotal)[^\d]{0,10}([\d]+(?:[.,]\d{3})*(?:[.,]\d{2})?)", text, re.IGNORECASE)
            if sub_match:
                raw_sub = sub_match.group(1)
                subtotal = float(raw_sub.replace('.', '').replace(',', '.'))
                return round(subtotal * 0.11, 2)
            return -1
        else:
            return -1

        return float(raw.replace('.', '').replace(',', '.'))
    except Exception:
        return -1


def compare_pdf_values(invoice_pdf: str, facture_pdf: str, keywords: dict) -> dict:
    invoice_value1 = extract_value_from_pdf(invoice_pdf, keywords.get('invoice_k1', ''))
    invoice_value2 = extract_value_from_pdf(invoice_pdf, keywords.get('invoice_k2', ''))
    facture_value1 = extract_value_from_pdf(facture_pdf, keywords.get('facture_k1', ''))
    facture_value2 = extract_value_from_pdf(facture_pdf, keywords.get('facture_k2', ''))
    match = (invoice_value1 == facture_value1) and (invoice_value2 == facture_value2)
    return {
        'invoice_value1': invoice_value1,
        'invoice_value2': invoice_value2,
        'facture_value1': facture_value1,
        'facture_value2': facture_value2,
        'match': match,
    }


def merge_pdfs_bytes(pdf1_path: str, pdf2_path: str) -> bytes:
    pdf_writer = PyPDF2.PdfWriter()
    with open(pdf1_path, 'rb') as f1, open(pdf2_path, 'rb') as f2:
        r1 = PyPDF2.PdfReader(f1)
        r2 = PyPDF2.PdfReader(f2)
        for p in r1.pages:
            pdf_writer.add_page(p)
        for p in r2.pages:
            pdf_writer.add_page(p)
    out_io = BytesIO()
    pdf_writer.write(out_io)
    out_io.seek(0)
    return out_io.read()
