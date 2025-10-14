# streamlit_fusion_pdf_app.py
# Streamlit adaptation of FusionPDF.py — Natural Mocha v2
# Adds value preview card, modern UI, and force-merge control.

import streamlit as st
import tempfile
import os
import re
import PyPDF2
from io import BytesIO
from pdf2image import convert_from_path

# -------------------------
# Utility functions (core logic preserved)
# -------------------------

def extract_value_from_pdf(pdf_file_path: str, keyword: str) -> float:
    """Extract a numeric value from PDF based on a keyword.
    Returns -1 on failure or if no value found.
    """
    if not os.path.exists(pdf_file_path) or not pdf_file_path.lower().endswith('.pdf'):
        return -1

    try:
        with open(pdf_file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = "".join((page.extract_text() or "") for page in reader.pages)

        # normalize spaces
        text = re.sub(r'[\u00A0\u202F]', ' ', text)
        text = re.sub(r'\s+', ' ', text)

        # smarter VAT handling
        if keyword.lower().strip() in ["vat", "v.a.t", "ppn"]:
            pattern = r"(?i)v[\s\u00A0\u202F\.\-]*a[\s\u00A0\u202F\.\-]*t[\s\u00A0\u202F\.\-]*[\s:\-\(\)%]*([\d]+(?:[.,]\d{3})*(?:[.,]\d{2})?)"
        else:
            pattern = rf"(?i){re.escape(keyword)}[\s:\-\(\)%]*([\d]+(?:[.,]\d{{3}})*(?:[.,]\d{{2}})?)"

        value_match = re.search(pattern, text)

        if value_match:
            raw = value_match.group(1)
        elif keyword.lower().strip() in ["vat", "v.a.t", "ppn"]:
            # Fallback: look for "Stamp Duty" or "Total" followed by a smaller number
            alt_match = re.search(
                r"(?:Stamp\s*Duty\s*Total|Total\s*(?:Amount)?)[^\d]{0,10}([\d]+(?:[.,]\d{3})*(?:[.,]\d{2})?)",
                text, re.IGNORECASE
            )
            if alt_match:
                raw = alt_match.group(1)
            else:
                return -1
        else:
            return -1

        value = float(raw.replace('.', '').replace(',', '.'))
        return value

    except Exception as e:
        return -1


def compare_pdf_values(invoice_pdf: str, facture_pdf: str, keywords: dict) -> dict:
    """Compare extracted values between invoice and facture."""
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
    """Merge two PDFs and return as bytes."""
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


def preview_pdf_first_page_as_image(pdf_path: str, dpi: int = 100) -> BytesIO:
    """Convert first page of PDF to image (BytesIO)."""
    images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=1)
    if not images:
        raise RuntimeError('No images rendered')
    bio = BytesIO()
    images[0].save(bio, format='PNG')
    bio.seek(0)
    return bio


# -------------------------
# Streamlit UI Setup
# -------------------------

st.set_page_config(page_title='FusionPDF — Mocha', layout='wide')

MOCHA_CSS = r"""
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
.section-title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 10px;
}
.app-card {
  background: var(--card);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 4px 12px rgba(58,47,43,0.15);
}
.small-muted {
  color: var(--muted);
  font-size: 13px;
}
.btn-cute {
  background-color: var(--accent);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-cute:hover {
  background-color: var(--accent-rose);
}
.success-box {
  background-color: var(--accent-sage);
  color: var(--coffee);
  padding: 10px;
  border-radius: 8px;
  margin-top: 10px;
}
.warning-box {
  background-color: var(--accent-rose);
  color: var(--coffee);
  padding: 10px;
  border-radius: 8px;
  margin-top: 10px;
}
.value-table {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  background-color: #f9f3eb;
  border-radius: 10px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(58,47,43,0.1);
}
.value-column {
  flex: 1;
  text-align: right;
  font-family: "Courier New", monospace;
  font-size: 14px;
  color: var(--coffee);
}
.value-header {
  text-align: right;
  font-weight: 600;
  color: var(--accent);
  font-size: 15px;
  margin-bottom: 4px;
}
.value-divider {
  width: 1px;
  background-color: #d9cbbb;
  margin: 0 12px;
}
</style>
"""

st.markdown(MOCHA_CSS, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("<div class='app-card'><div class='section-title'>Keywords</div>", unsafe_allow_html=True)
    invoice_k1 = st.text_input('Invoice keyword 1', value='Sub Total')
    invoice_k2 = st.text_input('Invoice keyword 2', value='VAT')
    facture_k1 = st.text_input('Facture keyword 1', value='Harga Jual / Penggantian / Uang Muka / Termin')
    facture_k2 = st.text_input('Facture keyword 2', value='Jumlah PPN (Pajak Pertambahan Nilai)')
    st.markdown("<hr>", unsafe_allow_html=True)
    force_merge = st.checkbox('Force merge even if values don’t match', value=False)
    st.markdown("<div class='small-muted'>Used to extract and compare numeric values following these keywords.</div></div>", unsafe_allow_html=True)

# Layout
col1, col2 = st.columns(2)
comparison_result = None

with col1:
    st.markdown("<div class='app-card'><div class='section-title'>Upload PDFs</div>", unsafe_allow_html=True)
    invoice_file = st.file_uploader('Invoice PDF (drag & drop)', type=['pdf'])
    facture_file = st.file_uploader('Facture PDF (drag & drop)', type=['pdf'])
    st.markdown('</div>', unsafe_allow_html=True)

def save_uploaded_to_temp(uploaded_file) -> str:
    if uploaded_file is None:
        return ''
    suffix = '.pdf'
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tf.write(uploaded_file.getbuffer())
    tf.flush()
    tf.close()
    return tf.name

invoice_path = save_uploaded_to_temp(invoice_file) if invoice_file else ''
facture_path = save_uploaded_to_temp(facture_file) if facture_file else ''

with col2:
    st.markdown("<div class='app-card'><div class='section-title'>Actions</div>", unsafe_allow_html=True)
    if st.button('Compare values', key='compare', use_container_width=True):
        if not invoice_path or not facture_path:
            st.error('Please upload both PDFs first.')
        else:
            with st.spinner('Comparing...'):
                comparison_result = compare_pdf_values(invoice_path, facture_path, {
                    'invoice_k1': invoice_k1,
                    'invoice_k2': invoice_k2,
                    'facture_k1': facture_k1,
                    'facture_k2': facture_k2,
                })
            if comparison_result['match']:
                st.markdown("<div class='success-box'>Values match ✅</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='warning-box'>Values do not match ⚠️</div>", unsafe_allow_html=True)

            # --- Value display table ---
            st.markdown("""
            <div class='value-table'>
                <div class='value-column'>
                    <div class='value-header'>Invoice</div>
                    <div>{:.2f}</div>
                    <div>{:.2f}</div>
                </div>
                <div class='value-divider'></div>
                <div class='value-column'>
                    <div class='value-header'>Facture</div>
                    <div>{:.2f}</div>
                    <div>{:.2f}</div>
                </div>
            </div>
            """.format(
                comparison_result['invoice_value1'],
                comparison_result['invoice_value2'],
                comparison_result['facture_value1'],
                comparison_result['facture_value2']
            ), unsafe_allow_html=True)

    if st.button('Preview PDFs', key='preview', use_container_width=True):
        if invoice_path:
            try:
                st.image(preview_pdf_first_page_as_image(invoice_path), caption='Invoice — First Page', use_container_width=True)
            except Exception as e:
                st.error(f'Invoice preview failed: {e}')
        if facture_path:
            try:
                st.image(preview_pdf_first_page_as_image(facture_path), caption='Facture — First Page', use_container_width=True)
            except Exception as e:
                st.error(f'Facture preview failed: {e}')
    st.markdown('</div>', unsafe_allow_html=True)

# Merge Section
st.markdown("<div class='app-card' style='margin-top:18px'><div class='section-title'>Merge PDFs</div>", unsafe_allow_html=True)

can_merge = False
if comparison_result:
    can_merge = comparison_result['match'] or force_merge
elif force_merge:
    can_merge = True

merge_button = st.button('Merge & Download', key='merge', use_container_width=True, disabled=not can_merge)

if merge_button:
    if not invoice_path or not facture_path:
        st.error('Please upload both PDFs.')
    else:
        try:
            merged_bytes = merge_pdfs_bytes(invoice_path, facture_path)
            st.success('Merged successfully!')
            st.download_button('Download merged PDF', merged_bytes, file_name='merged.pdf', mime='application/pdf')
        except Exception as e:
            st.error(f'Merge failed: {e}')

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div class='small-muted' style='margin-top:12px;'>FusionPDF — Natural Mocha version. Values must match exactly unless “Force merge” is checked.</div>", unsafe_allow_html=True)
