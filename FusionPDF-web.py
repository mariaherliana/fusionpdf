# FusionPDF-web.py — Natural Mocha v3
# Single-file Streamlit app with Single & Bulk Comparison

import streamlit as st
import tempfile
import os
import re
import PyPDF2
import pandas as pd
from io import BytesIO
from pdf2image import convert_from_path

# -------------------------
# Core Functions
# -------------------------

def extract_value_from_pdf(pdf_file_path: str, keyword: str) -> float:
    """Extract a numeric value from PDF based on a keyword.
    Returns -1 if not found or invalid.
    """
    if not os.path.exists(pdf_file_path):
        return -1

    try:
        with open(pdf_file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = "".join((page.extract_text() or "") for page in reader.pages)

        # normalize spaces
        text = re.sub(r'[\u00A0\u202F]', ' ', text)
        text = re.sub(r'\s+', ' ', text)

        if keyword.lower().strip() in ["vat", "v.a.t", "ppn"]:
            pattern = r"(?i)v[\s\u00A0\u202F\.\-]*a[\s\u00A0\u202F\.\-]*t[\s\u00A0\u202F\.\-]*[\s:\-\(\)%]*([\d]+(?:[.,]\d{3})*(?:[.,]\d{2})?)"
        else:
            pattern = rf"(?i){re.escape(keyword)}[\s:\-\(\)%]*([\d]+(?:[.,]\d{{3}})*(?:[.,]\d{{2}})?)"

        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
        elif keyword.lower().strip() in ["vat", "v.a.t", "ppn"]:
            sub = re.search(r"(?:Sub\s*Total|Subtotal)[^\d]{0,10}([\d]+(?:[.,]\d{3})*(?:[.,]\d{2})?)", text, re.IGNORECASE)
            if sub:
                subtotal = float(sub.group(1).replace('.', '').replace(',', '.'))
                return round(subtotal * 0.11, 2)
            else:
                return -1
        else:
            return -1

        return float(raw.replace('.', '').replace(',', '.'))
    except Exception:
        return -1

def compare_pdf_values(invoice_pdf: str, facture_pdf: str, keywords: dict) -> dict:
    """Compare extracted values between invoice and facture."""
    invoice_value1 = extract_value_from_pdf(invoice_pdf, keywords.get('invoice_k1', ''))
    invoice_value2 = extract_value_from_pdf(invoice_pdf, keywords.get('invoice_k2', ''))
    facture_value1 = extract_value_from_pdf(facture_pdf, keywords.get('facture_k1', ''))
    facture_value2 = extract_value_from_pdf(facture_pdf, keywords.get('facture_k2', ''))

    def almost_equal(a, b, tol=1.0):
        return a != -1 and b != -1 and abs(a - b) <= tol
    
    match = almost_equal(invoice_value1, facture_value1) and almost_equal(invoice_value2, facture_value2)
    return {
        'invoice_value1': invoice_value1,
        'invoice_value2': invoice_value2,
        'facture_value1': facture_value1,
        'facture_value2': facture_value2,
        'match': match,
    }


def merge_pdfs_bytes(pdf1_path: str, pdf2_path: str) -> bytes:
    """Merge two PDFs and return as bytes."""
    writer = PyPDF2.PdfWriter()
    with open(pdf1_path, 'rb') as f1, open(pdf2_path, 'rb') as f2:
        for p in PyPDF2.PdfReader(f1).pages:
            writer.add_page(p)
        for p in PyPDF2.PdfReader(f2).pages:
            writer.add_page(p)
    out = BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


def preview_pdf_first_page_as_image(pdf_path: str, dpi: int = 100) -> BytesIO:
    images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=1)
    bio = BytesIO()
    images[0].save(bio, format='PNG')
    bio.seek(0)
    return bio


# -------------------------
# Streamlit Setup
# -------------------------

st.set_page_config(page_title="FusionPDF — Mocha", layout="wide")

MOCHA_CSS = """
<style>
:root {
  --cream: #f6f0e9;
  --coffee: #3a2f2b;
  --card: #f1e6d8;
  --accent: #d4a373;
  --accent-rose: #e7a7a0;
  --accent-sage: #a6bba7;
  --muted: #8b817a;
}
html, body, [class*="stApp"] {
  background-color: var(--cream);
  color: var(--coffee);
  font-family: "Inter", sans-serif;
}
.app-card {
  background: var(--card);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 4px 12px rgba(58,47,43,0.15);
}
.section-title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 10px;
}
.small-muted { color: var(--muted); font-size: 13px; }
</style>
"""
st.markdown(MOCHA_CSS, unsafe_allow_html=True)

# -------------------------
# Sidebar navigation
# -------------------------

page = st.sidebar.radio("Navigation", ["Single Comparison", "Bulk Comparison"])
st.sidebar.markdown("<hr>", unsafe_allow_html=True)
force_merge = st.sidebar.checkbox("Force merge even if values don’t match", value=False)

# Keyword fields (shared)
st.sidebar.markdown("<div class='app-card'><div class='section-title'>Keywords</div>", unsafe_allow_html=True)
invoice_k1 = st.sidebar.text_input('Invoice keyword 1', value='Sub Total')
invoice_k2 = st.sidebar.text_input('Invoice keyword 2', value='VAT')
facture_k1 = st.sidebar.text_input('Facture keyword 1', value='Harga Jual / Penggantian / Uang Muka / Termin')
facture_k2 = st.sidebar.text_input('Facture keyword 2', value='Jumlah PPN (Pajak Pertambahan Nilai)')
st.sidebar.markdown("</div>", unsafe_allow_html=True)

def save_uploaded_to_temp(uploaded_file):
        if uploaded_file is None:
            return ''
        suffix = '.pdf'
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tf.write(uploaded_file.getbuffer())
        tf.flush()
        tf.close()
        return tf.name
    
# -------------------------
# Single Comparison Page
# -------------------------

if page == "Single Comparison":
    st.title("FusionPDF — Single Comparison")

    col1, col2 = st.columns(2)
    comparison_result = None

    with col1:
        st.markdown("<div class='app-card'><div class='section-title'>Upload PDFs</div>", unsafe_allow_html=True)
        invoice_file = st.file_uploader('Invoice PDF (drag & drop)', type=['pdf'])
        facture_file = st.file_uploader('Facture PDF (drag & drop)', type=['pdf'])
        st.markdown('</div>', unsafe_allow_html=True)

    invoice_path = save_uploaded_to_temp(invoice_file) if invoice_file else ''
    facture_path = save_uploaded_to_temp(facture_file) if facture_file else ''

    with col2:
        st.markdown("<div class='app-card'><div class='section-title'>Actions</div>", unsafe_allow_html=True)
        if st.button('Compare values', use_container_width=True):
            if not invoice_path or not facture_path:
                st.error('Upload both PDFs first.')
            else:
                with st.spinner('Comparing...'):
                    comparison_result = compare_pdf_values(invoice_path, facture_path, {
                        'invoice_k1': invoice_k1,
                        'invoice_k2': invoice_k2,
                        'facture_k1': facture_k1,
                        'facture_k2': facture_k2,
                    })
                if comparison_result['match']:
                    st.success('✅ Values match')
                else:
                    st.warning('⚠️ Values do not match')

                st.markdown(f"""
                **Invoice**  
                {comparison_result['invoice_value1']:.2f}  
                {comparison_result['invoice_value2']:.2f}  

                **Facture**  
                {comparison_result['facture_value1']:.2f}  
                {comparison_result['facture_value2']:.2f}
                """)

        if st.button('Preview PDFs', use_container_width=True):
            invoice_path = save_uploaded_to_temp(invoice_file) if invoice_file else ''
            facture_path = save_uploaded_to_temp(facture_file) if facture_file else ''
    
            if invoice_path:
                st.image(preview_pdf_first_page_as_image(invoice_path), caption='Invoice — First Page', use_container_width=True)
            if facture_path:
                st.image(preview_pdf_first_page_as_image(facture_path), caption='Facture — First Page', use_container_width=True)

        if st.button('Merge & Download', use_container_width=True, disabled=not (force_merge or comparison_result and comparison_result['match'])):
            if not invoice_path or not facture_path:
                st.error("Please upload both PDFs.")
            else:
                merged_bytes = merge_pdfs_bytes(invoice_path, facture_path)
                st.download_button('Download merged PDF', merged_bytes, file_name='merged.pdf', mime='application/pdf')

        st.markdown('</div>', unsafe_allow_html=True)


# -------------------------
# Bulk Comparison Page
# -------------------------

if page == "Bulk Comparison":
    st.title("FusionPDF — Bulk Comparison")

    col1, col2 = st.columns(2)
    with col1:
        invoice_files = st.file_uploader("Upload Invoice PDFs", type="pdf", accept_multiple_files=True)
    with col2:
        facture_files = st.file_uploader("Upload Facture PDFs", type="pdf", accept_multiple_files=True)

    if st.button("Run Bulk Comparison", use_container_width=True):
        if not invoice_files or not facture_files:
            st.error("Please upload both sets of PDFs.")
        else:
            tmp_dir = tempfile.mkdtemp()
            invoice_paths = {os.path.splitext(f.name)[0]: os.path.join(tmp_dir, f.name) for f in invoice_files}
            facture_paths = {os.path.splitext(f.name)[0]: os.path.join(tmp_dir, f.name) for f in facture_files}

            invoice_paths = {}
            facture_paths = {}
            
            for f in invoice_files:
                invoice_paths[os.path.splitext(f.name)[0]] = save_uploaded_to_temp(f)
            
            for f in facture_files:
                facture_paths[os.path.splitext(f.name)[0]] = save_uploaded_to_temp(f)

            common = sorted(set(invoice_paths.keys()) & set(facture_paths.keys()))
            results, merged_outputs = [], []

            for name in common:
                inv, fac = invoice_paths[name], facture_paths[name]
                comp = compare_pdf_values(inv, fac, {
                    'invoice_k1': invoice_k1, 'invoice_k2': invoice_k2,
                    'facture_k1': facture_k1, 'facture_k2': facture_k2
                })
                match = comp['match']
                status = "✅ Match" if match else ("⚠️ Forced" if force_merge else "❌ Mismatch")
                results.append({
                    "File": name,
                    "Invoice_1": comp["invoice_value1"],
                    "Invoice_2": comp["invoice_value2"],
                    "Facture_1": comp["facture_value1"],
                    "Facture_2": comp["facture_value2"],
                    "Status": status
                })
                if match or force_merge:
                    merged = merge_pdfs_bytes(inv, fac)
                    merged_outputs.append((name, merged))

            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download Summary CSV", csv, file_name="bulk_results.csv", mime="text/csv")

            st.markdown("### Download merged PDFs")
            for name, merged_bytes in merged_outputs:
                st.download_button(f"⬇️ Download {name}.pdf", merged_bytes, file_name=f"{name}_merged.pdf", mime="application/pdf")

st.markdown("<div class='small-muted'>FusionPDF — Natural Mocha v3. Supports single and bulk comparisons with force merge.</div>", unsafe_allow_html=True)
