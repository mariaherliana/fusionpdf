# streamlit_fusion_pdf_app.py
# Streamlit adaptation of FusionPDF.py (originally a Tkinter app)
# Kept the core logic (keyword extraction, comparison, merging) intact
# Adds a modern "mocha"-themed custom CSS and a sidebar for keywords.

import streamlit as st
import tempfile
import os
import re
import PyPDF2
from io import BytesIO
from pdf2image import convert_from_path

# -------------------------
# Utility functions (core logic preserved/adapted)
# -------------------------

def extract_value_from_pdf(pdf_file_path: str, keyword: str) -> float:
    """Extract a numeric value from PDF based on a keyword.
    Returns -1 on failure or if no value found. Keeps same regex logic as original.
    """
    if not os.path.exists(pdf_file_path) or not pdf_file_path.lower().endswith('.pdf'):
        return -1

    try:
        with open(pdf_file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = "".join((page.extract_text() or "") for page in reader.pages)

        # original regex pattern: keyword followed by a number (supporting '.' and ',' thousand/decimal)
        pattern = rf"{re.escape(keyword)}\s*(\d+(?:[.,]\d{{3}})*(?:[.,]\d{{2}}))"
        value_match = re.search(pattern, text)
        if value_match:
            raw = value_match.group(1)
            # normalize thousand separators and decimal comma
            value = float(raw.replace('.', '').replace(',', '.'))
            return value
        return -1
    except Exception as e:
        # In Streamlit we will show errors in the UI; return -1 so caller knows
        return -1


def compare_pdf_values(invoice_pdf: str, facture_pdf: str, keywords: dict) -> dict:
    """Compare values between invoice and facture PDFs.
    keywords: dict with keys invoice_k1, invoice_k2, facture_k1, facture_k2
    Returns a dict with extracted values and a boolean match flag.
    """
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
    """Merge two PDFs and return result as bytes.
    Preserves original merge order (pdf1 then pdf2).
    """
    pdf_writer = PyPDF2.PdfWriter()
    try:
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
    except Exception as e:
        raise


def preview_pdf_first_page_as_image(pdf_path: str, dpi: int = 100) -> BytesIO:
    """Convert first page of PDF to PNG bytes (via pdf2image). Returns BytesIO or raises."""
    images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=1)
    if not images:
        raise RuntimeError('No images rendered from PDF')
    img = images[0]
    bio = BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio


# -------------------------
# Streamlit UI
# -------------------------

st.set_page_config(page_title='FusionPDF — Streamlit', layout='wide')

# Custom Mocha-like CSS (rounded, soft shadows, subtle pastel accents)
MOCHA_CSS = r"""
<style>
:root{
  --bg:#111010;
  --panel:#171617;
  --muted:#a3a09a;
  --accent:#c7a9ff;
  --accent-2:#ffb5cf;
  --card:#1f1e1b;
}
html,body,#root, .stApp {
  background: linear-gradient(180deg, #0f0f10 0%, #141312 100%);
  color: #e6e1dc;
}
.section-title{font-size:20px;font-weight:700;margin-bottom:8px}
.app-card{background:var(--card);border-radius:14px;padding:18px;box-shadow: 0 6px 18px rgba(0,0,0,0.45);}
.small-muted{color:var(--muted);font-size:13px}
.btn-cute{background:linear-gradient(90deg,var(--accent),var(--accent-2));border:none;padding:8px 14px;border-radius:12px;color:#111;font-weight:700}
.sidebar .stFileUploader{min-height:60px}
</style>
"""

st.markdown(MOCHA_CSS, unsafe_allow_html=True)

# Layout: sidebar for keywords; main area for uploaders and controls
with st.sidebar:
    st.markdown("<div class='app-card'><div class='section-title'>Keywords</div>", unsafe_allow_html=True)
    invoice_k1 = st.text_input('Invoice keyword 1', value='Sub Total')
    invoice_k2 = st.text_input('Invoice keyword 2', value='VAT')
    facture_k1 = st.text_input('Facture keyword 1', value='Harga Jual / Penggantian / Uang Muka / Termin')
    facture_k2 = st.text_input('Facture keyword 2', value='Jumlah PPN (Pajak Pertambahan Nilai)')
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>These values are used by the extractor to find numeric values following the keyword. Leave blank to skip.</div></div>", unsafe_allow_html=True)

# Main area
st.markdown("<div style='display:flex;gap:20px'>", unsafe_allow_html=True)
col1, col2 = st.columns([1,1])

with col1:
    st.markdown("<div class='app-card'><div class='section-title'>Upload PDFs</div>", unsafe_allow_html=True)
    invoice_file = st.file_uploader('Upload Invoice PDF (drag & drop)', type=['pdf'], key='invoice_uploader')
    facture_file = st.file_uploader('Upload Facture PDF (drag & drop)', type=['pdf'], key='facture_uploader')
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown("<div class='app-card'><div class='section-title'>Preview & Actions</div>", unsafe_allow_html=True)
    col_actions = st.container()
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Action area below
st.markdown("<div class='app-card' style='margin-top:18px'><div class='section-title'>Operations</div>", unsafe_allow_html=True)
col_a, col_b, col_c = st.columns([1,1,1])

keywords = {
    'invoice_k1': invoice_k1,
    'invoice_k2': invoice_k2,
    'facture_k1': facture_k1,
    'facture_k2': facture_k2,
}

# save uploaded files to temporary files for downstream processing
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

with col_a:
    if st.button('Compare values'):
        if not invoice_path or not facture_path:
            st.error('Please upload both PDFs before comparing.')
        else:
            with st.spinner('Extracting and comparing...'):
                result = compare_pdf_values(invoice_path, facture_path, keywords)
            st.write('**Invoice values**: ', result['invoice_value1'], result['invoice_value2'])
            st.write('**Facture values**: ', result['facture_value1'], result['facture_value2'])
            if result['match']:
                st.success('Values match ✅')
            else:
                st.warning('Values do NOT match ⚠️')

with col_b:
    if st.button('Merge and download'):
        if not invoice_path or not facture_path:
            st.error('Please upload both PDFs before merging.')
        else:
            try:
                merged_bytes = merge_pdfs_bytes(invoice_path, facture_path)
                st.success('PDFs merged — download below')
                st.download_button('Download merged PDF', merged_bytes, file_name='merged.pdf', mime='application/pdf')
            except Exception as e:
                st.error(f'Failed to merge PDFs: {e}')

with col_c:
    if st.button('Preview first pages'):
        if not invoice_path and not facture_path:
            st.error('Upload at least one PDF to preview')
        else:
            if invoice_path:
                try:
                    img_io = preview_pdf_first_page_as_image(invoice_path)
                    st.image(img_io, caption='Invoice — first page', use_column_width=True)
                except Exception as e:
                    st.error(f'Failed to render invoice preview: {e}')
            if facture_path:
                try:
                    img_io2 = preview_pdf_first_page_as_image(facture_path)
                    st.image(img_io2, caption='Facture — first page', use_column_width=True)
                except Exception as e:
                    st.error(f'Failed to render facture preview: {e}')

st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("<div style='margin-top:18px' class='small-muted'>FusionPDF — Streamlit port. Keywords are used as-is by the regex extractor. If extraction fails, try different keywords or check PDF text extraction compatibility.</div>", unsafe_allow_html=True)

# Cleanup: remove temp files on rerun? Streamlit doesn't give a direct hook; we'll attempt to remove when app stops by registering atexit if present.
try:
    import atexit
    def _cleanup():
        for p in [invoice_path, facture_path]:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
    atexit.register(_cleanup)
except Exception:
    pass
