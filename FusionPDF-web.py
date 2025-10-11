# FusionPDF-Web.py (PyMuPDF version, robust extraction & comparison)
import streamlit as st
import fitz  # PyMuPDF
import re
import io
import zipfile
import PyPDF2
from pdf2image import convert_from_bytes

st.set_page_config(page_title="FusionPDF", page_icon="📄", layout="wide")
st.title("📄 FusionPDF by Anna — PyMuPDF extraction")
st.markdown("Text-based extraction (no OCR). Shows debug output to help tune keywords.")

# ----------------- Utilities -----------------
def normalize_number_token(token: str):
    """Convert a numeric token with ., and , in various formats to float, or None."""
    if not token:
        return None
    s = token.strip()
    # Keep only digits, dots, commas, minus
    s = re.sub(r'[^\d\.,\-]', '', s)
    if s == "":
        return None
    # If both separators exist, decide decimal by rightmost
    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'):
            # comma decimal, dot thousands
            s = s.replace('.', '')
            s = s.replace(',', '.')
        else:
            # dot decimal, comma thousands
            s = s.replace(',', '')
    else:
        # only dots
        if s.count('.') > 1:
            # likely thousand separators
            s = s.replace('.', '')
        elif s.count('.') == 1:
            # ambiguous; leave as is (dot is decimal)
            pass
        # only commas
        if s.count(',') > 1:
            s = s.replace(',', '')
        elif s.count(',') == 1:
            # if comma is thousand sep (three digits) -> remove, else treat as decimal
            if re.search(r',\d{3}$', s):
                s = s.replace(',', '')
            else:
                s = s.replace(',', '.')
    s = re.sub(r'[^\d\.\-]', '', s)
    try:
        return float(s)
    except Exception:
        return None

def pdf_text_pages(pdf_bytes: bytes):
    """Return list of page text strings using PyMuPDF."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = [page.get_text("text") for page in doc]
        return pages
    except Exception as e:
        st.error(f"PyMuPDF extraction error: {e}")
        return []

def find_label_line_indices(page_text: str, label: str):
    """Return indices of lines where label appears (case-insensitive)."""
    lines = page_text.splitlines()
    idxs = [i for i, ln in enumerate(lines) if re.search(re.escape(label), ln, re.IGNORECASE)]
    return lines, idxs

def find_rightmost_number_on_line(line: str):
    """Return rightmost numeric-like token on the line, more likely to be an amount."""
    # numeric tokens that look like money: 1.234.567, 1234.56, 1,234, etc.
    tokens = re.findall(r'(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?|\d+[.,]\d{2}|\d+)', line)
    if not tokens:
        return None
    return tokens[-1]

def extract_value_from_pdf(pdf_file: str, keyword: str) -> float:
    logging.info(f"Extracting value from {pdf_file} with keyword '{keyword}'")
    if not os.path.exists(pdf_file) or not pdf_file.lower().endswith('.pdf'):
        return -1

    try:
        with open(pdf_file, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "".join(page.extract_text() for page in reader.pages)

        # Extract the paragraph/line that contains the keyword
        lines = text.splitlines()
        matching_lines = [line for line in lines if keyword.lower() in line.lower()]
        if not matching_lines:
            return -1

        for line in matching_lines:
            # Find all numbers in that line
            candidates = re.findall(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+)", line)
            numbers = []
            for c in candidates:
                try:
                    num = float(c.replace(".", "").replace(",", "."))
                    numbers.append(num)
                except:
                    pass
            # Filter out small values (e.g. percentages, penalties)
            numbers = [n for n in numbers if n > 1000]
            if numbers:
                # Pick the *largest* number near that keyword (most likely the amount)
                return max(numbers)

        # fallback: last resort regex on the whole text
        all_numbers = re.findall(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+)", text)
        return max([float(n.replace(".", "").replace(",", ".")) for n in all_numbers if float(n.replace(".", "").replace(",", ".")) > 1000], default=-1)

    except Exception as e:
        logging.error(f"Error extracting value: {e}")
        return -1

def compare_values_with_tolerance(a, b, rel_tol=0.005, abs_tol=1.0):
    """Return dict with match boolean and reason."""
    if a is None or b is None:
        return {"match": False, "reason": "MISSING", "a": a, "b": b}
    if abs(a - b) <= abs_tol:
        return {"match": True, "reason": f"ABS within {abs_tol}", "a": a, "b": b}
    denom = max(abs(b), 1.0)
    if abs(a - b) / denom <= rel_tol:
        return {"match": True, "reason": f"REL within {rel_tol*100:.2f}%", "a": a, "b": b}
    return {"match": False, "reason": f"DIFF {a - b:+.2f}", "a": a, "b": b}

def merge_pdfs_bytes(pdf1_bytes: bytes, pdf2_bytes: bytes):
    writer = PyPDF2.PdfWriter()
    for b in (pdf1_bytes, pdf2_bytes):
        reader = PyPDF2.PdfReader(io.BytesIO(b))
        for p in reader.pages:
            writer.add_page(p)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out

def preview_first_page(invoice_bytes: bytes, facture_bytes: bytes):
    col1, col2 = st.columns(2)
    if invoice_bytes:
        pages = convert_from_bytes(invoice_bytes, dpi=100)
        buf = io.BytesIO()
        pages[0].save(buf, format="PNG")
        col1.image(buf, caption="Invoice (first page)", use_column_width=True)
    if facture_bytes:
        pages = convert_from_bytes(facture_bytes, dpi=100)
        buf = io.BytesIO()
        pages[0].save(buf, format="PNG")
        col2.image(buf, caption="Facture (first page)", use_column_width=True)

# ----------------- Streamlit UI -----------------
page = st.sidebar.radio("Navigation", ["Home", "Single Comparison", "Bulk Comparison", "Help"])

if page == "Home":
    st.subheader("Welcome — use the sidebar to choose an action.")
    st.write("This app extracts values using PyMuPDF. If PDFs are scans, consider OCR fallback.")

elif page == "Single Comparison":
    st.subheader("Single Comparison")
    inv_file = st.file_uploader("Upload Invoice PDF", type="pdf")
    fac_file = st.file_uploader("Upload Facture PDF", type="pdf")
    c1, c2 = st.columns(2)
    with c1:
        inv_kw1 = st.text_input("Invoice Keyword 1", "Sub Total")
        inv_kw2 = st.text_input("Invoice Keyword 2", "VAT")
    with c2:
        fac_kw1 = st.text_input("Facture Keyword 1", "Harga Jual / Penggantian / Uang Muka / Termin")
        fac_kw2 = st.text_input("Facture Keyword 2", "Jumlah PPN (Pajak Pertambahan Nilai)")
    show_raw = st.checkbox("Show extracted raw page text (debug)", value=False)

    if inv_file and fac_file:
        inv_bytes = inv_file.read()
        fac_bytes = fac_file.read()
        st.subheader("Preview")
        preview_first_page(inv_bytes, fac_bytes)

        if show_raw:
            st.write("---- Invoice raw page text (page 1) ----")
            pages = pdf_text_pages(inv_bytes)
            if pages:
                st.text_area("Invoice page 1 text", pages[0][:20000], height=240)
            st.write("---- Facture raw page text (page 1) ----")
            pages = pdf_text_pages(fac_bytes)
            if pages:
                st.text_area("Facture page 1 text", pages[0][:20000], height=240)

        if st.button("Start Comparison"):
            inv_v1 = extract_value_from_pdf_text(inv_bytes, inv_kw1)
            inv_v2 = extract_value_from_pdf_text(inv_bytes, inv_kw2)
            fac_v1 = extract_value_from_pdf_text(fac_bytes, fac_kw1)
            fac_v2 = extract_value_from_pdf_text(fac_bytes, fac_kw2)

            st.subheader("Extracted Values")
            colA, colB = st.columns(2)
            with colA:
                st.write("Invoice")
                st.json({inv_kw1: inv_v1, inv_kw2: inv_v2})
            with colB:
                st.write("Facture")
                st.json({fac_kw1: fac_v1, fac_kw2: fac_v2})

            cmp1 = compare_values_with_tolerance(inv_v1, fac_v1)
            cmp2 = compare_values_with_tolerance(inv_v2, fac_v2)

            ok = cmp1["match"] and cmp2["match"]
            if ok:
                st.success("✅ Values match (within tolerance). You can download merged PDF.")
                merged = merge_pdfs_bytes(inv_bytes, fac_bytes)
                st.download_button("Download merged PDF", merged, file_name="merged.pdf", mime="application/pdf")
            else:
                st.error("❌ Values do NOT match.")
                st.markdown(f"**{inv_kw1} ↔ {fac_kw1}:** {cmp1['reason']}")
                st.markdown(f"**{inv_kw2} ↔ {fac_kw2}:** {cmp2['reason']}")

elif page == "Bulk Comparison":
    st.subheader("Bulk Comparison")
    inv_files = st.file_uploader("Upload Invoice PDFs (multiple)", type="pdf", accept_multiple_files=True)
    fac_files = st.file_uploader("Upload Facture PDFs (multiple)", type="pdf", accept_multiple_files=True)
    inv_kw1 = st.text_input("Invoice Keyword 1 (bulk)", "Sub Total")
    inv_kw2 = st.text_input("Invoice Keyword 2 (bulk)", "VAT")
    fac_kw1 = st.text_input("Facture Keyword 1 (bulk)", "Harga Jual / Penggantian / Uang Muka / Termin")
    fac_kw2 = st.text_input("Facture Keyword 2 (bulk)", "Jumlah PPN (Pajak Pertambahan Nilai)")

    if st.button("Start Bulk Compare"):
        if not inv_files or not fac_files:
            st.warning("Upload both sets of PDFs.")
        else:
            fac_map = {f.name: f for f in fac_files}
            success, failed = [], []
            zip_out = io.BytesIO()
            with zipfile.ZipFile(zip_out, "w") as zf:
                for inv in inv_files:
                    if inv.name not in fac_map:
                        failed.append(inv.name + " (no matching facture file)")
                        continue
                    inv_b = inv.read()
                    fac_b = fac_map[inv.name].read()
                    inv_v1 = extract_value_from_pdf_text(inv_b, inv_kw1)
                    inv_v2 = extract_value_from_pdf_text(inv_b, inv_kw2)
                    fac_v1 = extract_value_from_pdf_text(fac_b, fac_kw1)
                    fac_v2 = extract_value_from_pdf_text(fac_b, fac_kw2)
                    cmp1 = compare_values_with_tolerance(inv_v1, fac_v1)
                    cmp2 = compare_values_with_tolerance(inv_v2, fac_v2)
                    if cmp1["match"] and cmp2["match"]:
                        merged = merge_pdfs_bytes(inv_b, fac_b)
                        zf.writestr(inv.name, merged.read())
                        success.append(inv.name)
                    else:
                        failed.append(inv.name)
            zip_out.seek(0)
            st.success(f"Done. Success: {len(success)}, Failed: {len(failed)}")
            if success:
                st.download_button("Download matched merged PDFs (zip)", zip_out, "merged_pdfs.zip", "application/zip")
            if failed:
                st.warning("Failed: " + ", ".join(failed))

elif page == "Help":
    st.subheader("Help & Tips")
    st.markdown("""
    - This uses PyMuPDF (fitz) for text extraction — no OCR.
    - If PDFs are scanned images, extraction will fail; consider OCR fallback.
    - Use the debug 'Show extracted raw page text' to inspect what text was read.
    - If values are still mismatched, paste the 'Invoice page 1 text' and 'Facture page 1 text' and I will point to the problem token.
    - Install PyMuPDF: `pip install PyMuPDF`
    """)

