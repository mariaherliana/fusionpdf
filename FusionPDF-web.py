# FusionPDF-Web.py (patched)
import streamlit as st
import PyPDF2
import re
from pdf2image import convert_from_bytes
import io
import zipfile
import pytesseract

st.set_page_config(page_title="FusionPDF", page_icon="📄", layout="wide")
st.title("📄 FusionPDF by Anna")
st.markdown("Compare and merge PDFs easily!")

# --- Sidebar ---
page = st.sidebar.radio("Navigation", ["Home", "Single Comparison", "Bulk Comparison", "Help"])


# -------------------------
# Utility / extraction
# -------------------------
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Try direct text extraction; if it's very short, fallback to OCR."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    except Exception:
        text = ""

    if len(text.strip()) < 80:  # heuristic: if little text, use OCR
        try:
            pages = convert_from_bytes(pdf_bytes, dpi=200)
            ocr_text = ""
            for page in pages:
                # Try english; if you have Indonesian language pack, consider 'eng+ind'
                try:
                    ocr_text += pytesseract.image_to_string(page, lang="eng") + "\n"
                except Exception:
                    ocr_text += pytesseract.image_to_string(page) + "\n"
            text = (text + "\n" + ocr_text).strip()
        except Exception as e:
            st.error(f"OCR failed: {e}")
    return text


def parse_number_string(s: str):
    """Robustly parse a numeric token with possible ., and , as thousands/decimals."""
    if not s:
        return None
    s = s.strip()
    s = re.sub(r'[^\d\.,\-]', '', s)  # keep digits, dot, comma, minus

    if s == "":
        return None

    # If both separators present: decide which is decimal by rightmost separator
    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'):
            # comma likely decimal, dot thousand
            s = s.replace('.', '')
            s = s.replace(',', '.')
        else:
            # dot likely decimal, comma thousand
            s = s.replace(',', '')
    else:
        # only dots
        if s.count('.') > 1:
            # likely dot as thousand sep
            s = s.replace('.', '')
        elif s.count('.') == 1:
            # if 3 digits after dot -> thousand, else decimal
            if re.search(r'\.\d{3}$', s):
                s = s.replace('.', '')
            # else leave as is (decimal)
        # only commas
        if s.count(',') > 1:
            s = s.replace(',', '')
        elif s.count(',') == 1:
            # if comma three-digit grouping
            if re.search(r',\d{3}$', s):
                s = s.replace(',', '')
            else:
                s = s.replace(',', '.')

    s = re.sub(r'[^\d\.\-]', '', s)
    try:
        return float(s)
    except Exception:
        return None


def find_number_candidates_near_label(text: str, label: str, lines_down=3):
    """Scan the line containing label and next few lines for monetary-like tokens."""
    candidates = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(re.escape(label), line, re.IGNORECASE):
            # search same line, then next few lines
            for j in range(0, lines_down + 1):
                if i + j >= len(lines):
                    break
                target_line = lines[i + j]
                # Capture tokens that look like numbers with potential separators:
                for m in re.finditer(r'(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?|\d+[.,]\d{2}|\d+)', target_line):
                    token = m.group(1)
                    # Reject if this token context includes '%' (it's likely a percent)
                    pos = m.start(1)
                    context = target_line[max(0, pos - 4): pos + len(token) + 4]
                    if '%' in context or 'percent' in context.lower():
                        continue
                    candidates.append((token, i + j, pos, target_line.strip()))
    return candidates


def select_best_candidate(tokens):
    """
    tokens: list of (token_str, line_idx, pos, line_text)
    choose by: (1) longest digit-length, (2) numeric value (bigger wins)
    """
    parsed = []
    for token, ln, pos, line_text in tokens:
        num = parse_number_string(token)
        if num is None:
            continue
        digits_count = len(re.sub(r'\D', '', token))
        parsed.append((token, num, digits_count, ln, pos, line_text))
    if not parsed:
        return None
    # sort by digits_count desc, then numeric value desc
    parsed.sort(key=lambda x: (x[2], x[1]), reverse=True)
    return parsed[0][1]  # return numeric value


def extract_best_value_for_label(text: str, label: str):
    """
    Returns the chosen numeric value near the label, or None.
    This is the improved extractor that avoids grabbing '1' from dates, etc.
    """
    candidates = find_number_candidates_near_label(text, label, lines_down=3)
    if not candidates:
        return None
    return select_best_candidate(candidates)


# -------------------------
# Comparison / PDF ops
# -------------------------
def compare_values(val1, val2, rel_tol=0.005, abs_tol=1.0):
    """Compare numbers: either relative tolerance (0.5% default) or small absolute tolerance."""
    if val1 is None or val2 is None:
        return {"match": False, "reason": "MISSING", "val1": val1, "val2": val2}
    # absolute check
    if abs(val1 - val2) <= abs_tol:
        return {"match": True, "reason": "ABS within tol", "val1": val1, "val2": val2}
    # relative check
    denom = max(abs(val2), 1.0)
    if abs(val1 - val2) / denom <= rel_tol:
        return {"match": True, "reason": f"REL within {rel_tol*100:.2f}%", "val1": val1, "val2": val2}
    return {"match": False, "reason": f"DIFF {val1 - val2:+.2f}", "val1": val1, "val2": val2}


def merge_pdfs(pdf1_bytes, pdf2_bytes):
    writer = PyPDF2.PdfWriter()
    for pdf_bytes in (pdf1_bytes, pdf2_bytes):
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


def preview_pdf_side_by_side(invoice_bytes, facture_bytes):
    col1, col2 = st.columns([1, 1])
    if invoice_bytes:
        inv_img = convert_from_bytes(invoice_bytes, dpi=100)[0]
        buf = io.BytesIO()
        inv_img.save(buf, format="PNG")
        col1.image(buf, width=360, caption="Invoice PDF")
    if facture_bytes:
        fac_img = convert_from_bytes(facture_bytes, dpi=100)[0]
        buf = io.BytesIO()
        fac_img.save(buf, format="PNG")
        col2.image(buf, width=360, caption="Facture PDF")


# -------------------------
# Pages
# -------------------------
if page == "Home":
    st.subheader("Welcome to FusionPDF!")
    st.write("Choose an option from the sidebar to get started.")

elif page == "Single Comparison":
    st.subheader("🔍 Single PDF Comparison")

    invoice_pdf = st.file_uploader("Upload Invoice PDF", type="pdf")
    facture_pdf = st.file_uploader("Upload Facture PDF", type="pdf")

    col1, col2 = st.columns(2)
    with col1:
        inv_kw1 = st.text_input("Invoice Keyword 1", "Sub Total")
        inv_kw2 = st.text_input("Invoice Keyword 2", "VAT")
    with col2:
        fac_kw1 = st.text_input("Facture Keyword 1", "Harga Jual / Penggantian / Uang Muka / Termin")
        fac_kw2 = st.text_input("Facture Keyword 2", "Jumlah PPN (Pajak Pertambahan Nilai)")

    show_raw = st.checkbox("Show raw extracted text (debug)", value=False)

    if invoice_pdf and facture_pdf:
        st.subheader("📑 Preview PDFs")
        preview_pdf_side_by_side(invoice_pdf.read(), facture_pdf.read())
        invoice_pdf.seek(0)
        facture_pdf.seek(0)

    if st.button("Start Comparison"):
        if not (invoice_pdf and facture_pdf):
            st.warning("Please upload both PDFs first.")
        else:
            inv_bytes = invoice_pdf.read()
            fac_bytes = facture_pdf.read()

            inv_text = extract_text_from_pdf(inv_bytes)
            fac_text = extract_text_from_pdf(fac_bytes)

            if show_raw:
                st.subheader("Raw extracted text (Invoice)")
                st.text_area("Invoice raw text", inv_text[:20000], height=240)
                st.subheader("Raw extracted text (Facture)")
                st.text_area("Facture raw text", fac_text[:20000], height=240)

            # extract best numeric values near labels
            inv_val1 = extract_best_value_for_label(inv_text, inv_kw1)
            inv_val2 = extract_best_value_for_label(inv_text, inv_kw2)

            fac_val1 = extract_best_value_for_label(fac_text, fac_kw1)
            fac_val2 = extract_best_value_for_label(fac_text, fac_kw2)

            st.subheader("Extracted Values")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Invoice**")
                st.write({inv_kw1: inv_val1, inv_kw2: inv_val2})
            with col_b:
                st.markdown("**Facture**")
                st.write({fac_kw1: fac_val1, fac_kw2: fac_val2})

            cmp1 = compare_values(inv_val1, fac_val1)
            cmp2 = compare_values(inv_val2, fac_val2)

            if cmp1["match"] and cmp2["match"]:
                st.success("✅ Values match! Merged PDF is ready.")
                merged = merge_pdfs(inv_bytes, fac_bytes)
                st.download_button("Download Merged PDF", data=merged, file_name="merged.pdf", mime="application/pdf")
            else:
                st.error("❌ Values do NOT match!")
                st.markdown(f"**{inv_kw1} ↔ {fac_kw1}:** {cmp1['reason']}")
                st.markdown(f"**{inv_kw2} ↔ {fac_kw2}:** {cmp2['reason']}")

elif page == "Bulk Comparison":
    st.subheader("📦 Bulk PDF Comparison")
    st.write("Upload multiple Invoice PDFs and Facture PDFs. Filenames should match.")

    invoices = st.file_uploader("Upload Invoice PDFs", type="pdf", accept_multiple_files=True)
    factures = st.file_uploader("Upload Facture PDFs", type="pdf", accept_multiple_files=True)

    inv_kw1 = st.text_input("Invoice Keyword 1", "Sub Total")
    inv_kw2 = st.text_input("Invoice Keyword 2", "VAT")
    fac_kw1 = st.text_input("Facture Keyword 1", "Harga Jual / Penggantian / Uang Muka / Termin")
    fac_kw2 = st.text_input("Facture Keyword 2", "Jumlah PPN (Pajak Pertambahan Nilai)")

    if st.button("Start Bulk Comparison"):
        if not (invoices and factures):
            st.warning("Please upload both invoice and facture PDFs.")
        else:
            facture_map = {f.name: f for f in factures}
            success, failed = [], []
            zipbuf = io.BytesIO()
            with zipfile.ZipFile(zipbuf, "w") as zf:
                for inv in invoices:
                    if inv.name in facture_map:
                        inv_bytes = inv.read()
                        fac_bytes = facture_map[inv.name].read()

                        inv_text = extract_text_from_pdf(inv_bytes)
                        fac_text = extract_text_from_pdf(fac_bytes)

                        inv_val1 = extract_best_value_for_label(inv_text, inv_kw1)
                        inv_val2 = extract_best_value_for_label(inv_text, inv_kw2)
                        fac_val1 = extract_best_value_for_label(fac_text, fac_kw1)
                        fac_val2 = extract_best_value_for_label(fac_text, fac_kw2)

                        cmp1 = compare_values(inv_val1, fac_val1)
                        cmp2 = compare_values(inv_val2, fac_val2)

                        if cmp1["match"] and cmp2["match"]:
                            merged = merge_pdfs(inv_bytes, fac_bytes)
                            zf.writestr(inv.name, merged.read())
                            success.append(inv.name)
                        else:
                            failed.append(inv.name)
            zipbuf.seek(0)
            st.success(f"✅ Success: {len(success)}, ❌ Failed: {len(failed)}")
            if success:
                st.download_button("Download Merged PDFs (ZIP)", data=zipbuf, file_name="merged_pdfs.zip", mime="application/zip")
            if failed:
                st.warning(f"Failed files: {', '.join(failed)}")

elif page == "Help":
    st.subheader("📖 Help")
    st.markdown("""
    **Notes & tips**
    - Toggle 'Show raw extracted text' to see what text extraction / OCR read from each PDF.  
    - This extractor finds monetary tokens near the label, favors tokens with more digits (so it ignores dates like '1' or '30').  
    - If you still get wrong results: enable the raw text debug, paste a snippet here, and I'll point to the misread token.
    - If your invoices always use a nonstandard language or formatting, installing a matching tesseract language pack (e.g., 'ind' for Indonesian) helps OCR.
    """)

