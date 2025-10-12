# app.py
import streamlit as st
from io import BytesIO
import re
import os
import zipfile
from typing import Tuple, Dict, List
import logging

# Extraction and merging libs
import pdfplumber
import PyPDF2

# Optional nicer PDF viewer
try:
    from streamlit_pdf_viewer import pdf_viewer
    HAVE_PDF_VIEWER = True
except Exception:
    HAVE_PDF_VIEWER = False

logging.basicConfig(level=logging.INFO)

# Defaults (from your original script)
DEFAULT_INVOICE_KW1 = "Sub Total"
DEFAULT_INVOICE_KW2 = "VAT"
DEFAULT_FACTURE_KW1 = "Harga Jual / Penggantian / Uang Muka / Termin"
DEFAULT_FACTURE_KW2 = "Jumlah PPN (Pajak Pertambahan Nilai)"

st.set_page_config(page_title="FusionPDF (Streamlit)", layout="wide")

# --- Extraction / Comparison / Merge (kept behaviorally equivalent) ---
def extract_text_with_pdfplumber(pdf_bytes: bytes) -> str:
    """Return concatenated page text using pdfplumber (visually ordered)."""
    text_parts = []
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    text_parts.append(t)
    except Exception as e:
        logging.exception("pdfplumber failed to open PDF: %s", e)
    return "\n".join(text_parts)


def extract_value_from_text(text: str, keyword: str) -> float:
    """
    Use a pattern equivalent to the original:
      rf"{re.escape(keyword)}\s*(\d+(?:[.,]\d{3})*(?:[.,]\d{2}))"
    Slight improvement: allow non-digit separators (like 'Rp', ':' or spaces) between keyword and number.
    Returns -1.0 if not found.
    """
    if not keyword:
        return -1.0
    # Escape keyword (same as re.escape in original)
    esc = re.escape(keyword)
    # allow any non-digit characters (including currency symbols) between keyword & number
    pattern = rf"{esc}[^\d\-]*?(\d+(?:[.,]\d{{3}})*(?:[.,]\d{{2}}))"
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return -1.0
    raw = m.group(1)
    cleaned = raw.replace(".", "").replace(",", "").strip()
    try:
        val = int(cleaned)
    except ValueError:
        val = float(re.sub(r"[^\d.,]", "", raw).replace(",", "."))
    return val


def extract_value_from_pdf_bytes(pdf_bytes: bytes, keyword: str) -> float:
    text = extract_text_with_pdfplumber(pdf_bytes)
    return extract_value_from_text(text, keyword)


def compare_pdf_values_bytes(invoice_bytes: bytes, facture_bytes: bytes,
                             invoice_kw1: str, invoice_kw2: str,
                             facture_kw1: str, facture_kw2: str) -> Tuple[bool, Dict]:
    inv1 = extract_value_from_pdf_bytes(invoice_bytes, invoice_kw1)
    inv2 = extract_value_from_pdf_bytes(invoice_bytes, invoice_kw2)
    fac1 = extract_value_from_pdf_bytes(facture_bytes, facture_kw1)
    fac2 = extract_value_from_pdf_bytes(facture_bytes, facture_kw2)
    match = (inv1 == fac1 and inv2 == fac2)  # strict equality, as requested
    info = {
        "invoice": {invoice_kw1: inv1, invoice_kw2: inv2},
        "facture": {facture_kw1: fac1, facture_kw2: fac2},
    }
    return match, info


def merge_pdfs_bytes(pdf1_bytes: bytes, pdf2_bytes: bytes) -> bytes:
    writer = PyPDF2.PdfWriter()
    r1 = PyPDF2.PdfReader(BytesIO(pdf1_bytes))
    r2 = PyPDF2.PdfReader(BytesIO(pdf2_bytes))
    for p in r1.pages:
        writer.add_page(p)
    for p in r2.pages:
        writer.add_page(p)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


# --- UI ---
st.title("FusionPDF — Invoice vs Facture")
st.write("Single comparison (separate Invoice & Facture upload) or Bulk (many files). Keywords are editable in the sidebar.")

# Sidebar: keywords and options
st.sidebar.header("Extraction keywords (exact text expected)")
invoice_kw1 = st.sidebar.text_input("Invoice keyword 1", value=DEFAULT_INVOICE_KW1)
invoice_kw2 = st.sidebar.text_input("Invoice keyword 2", value=DEFAULT_INVOICE_KW2)
facture_kw1 = st.sidebar.text_input("Facture keyword 1", value=DEFAULT_FACTURE_KW1)
facture_kw2 = st.sidebar.text_input("Facture keyword 2", value=DEFAULT_FACTURE_KW2)

st.sidebar.markdown("---")
st.sidebar.write("Comparison: strict equality (default) — change logic in code to allow tolerance if desired.")

mode = st.radio("Mode", options=["Single (explicit Invoice + Facture upload)", "Bulk (multiple files)"])

if mode.startswith("Single"):
    st.header("Single comparison (preview)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Invoice (left)")
        uploaded_invoice = st.file_uploader("Upload Invoice PDF", type="pdf", key="inv_single")
        if uploaded_invoice:
            inv_bytes = uploaded_invoice.read()
            # preview
            if HAVE_PDF_VIEWER:
                pdf_viewer(inv_bytes, height=600, key="inv_view")
            else:
                # safe iframe fallback (serve as base64 but in small iframe; Chrome may block data:urls in some contexts)
                import base64, streamlit.components.v1 as components
                b64 = base64.b64encode(inv_bytes).decode("utf-8")
                iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600px"></iframe>'
                components.html(iframe, height=600)

    with col2:
        st.subheader("Facture (right)")
        uploaded_facture = st.file_uploader("Upload Facture PDF", type="pdf", key="fac_single")
        if uploaded_facture:
            fac_bytes = uploaded_facture.read()
            if HAVE_PDF_VIEWER:
                pdf_viewer(fac_bytes, height=600, key="fac_view")
            else:
                import base64, streamlit.components.v1 as components
                b64 = base64.b64encode(fac_bytes).decode("utf-8")
                iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600px"></iframe>'
                components.html(iframe, height=600)

    if st.button("Compare uploaded Invoice and Facture"):
        if not (uploaded_invoice and uploaded_facture):
            st.warning("Please upload both Invoice and Facture PDFs.")
        else:
            with st.spinner("Extracting numbers and comparing..."):
                match, info = compare_pdf_values_bytes(inv_bytes, fac_bytes, invoice_kw1, invoice_kw2, facture_kw1, facture_kw2)
            st.markdown("### Extraction")
            st.json(info)
            if match:
                st.success("Values match (strict equality).")
                merged = merge_pdfs_bytes(inv_bytes, fac_bytes)
                st.download_button("Download merged PDF", data=merged,
                                   file_name=f"merged_{os.path.splitext(uploaded_invoice.name)[0]}_{os.path.splitext(uploaded_facture.name)[0]}.pdf",
                                   mime="application/pdf")
            else:
                st.error("Values do NOT match (strict equality).")
                st.caption("You can force-merge if you want:")
                if st.button("Force merge and download anyway"):
                    merged = merge_pdfs_bytes(inv_bytes, fac_bytes)
                    st.download_button("Download merged PDF (forced)", data=merged,
                                       file_name=f"merged_forced_{os.path.splitext(uploaded_invoice.name)[0]}_{os.path.splitext(uploaded_facture.name)[0]}.pdf",
                                       mime="application/pdf")

else:
    # Bulk
    st.header("Bulk comparison")
    st.write("Upload many PDFs. Files will be grouped by basename; the first two files with the same basename are taken as a pair.")
    uploaded = st.file_uploader("Upload multiple PDFs (bulk)", type="pdf", accept_multiple_files=True, key="bulk_files")
    if not uploaded:
        st.info("Upload PDFs for bulk comparison.")
        st.stop()

    files = [(f.name, f.read()) for f in uploaded]

    # group by basename (filename without extension)
    from collections import defaultdict
    grouped = defaultdict(list)
    for name, b in files:
        base = os.path.splitext(os.path.basename(name))[0]
        grouped[base].append((name, b))

    # Prepare pairs and unmatched
    pairs = []
    unmatched = []
    for base, arr in grouped.items():
        if len(arr) >= 2:
            # take first two as pair
            pairs.append((arr[0], arr[1]))
        else:
            unmatched.append(arr[0][0])

    st.write(f"Found {len(pairs)} pair(s). Unmatched files: {len(unmatched)}")
    if unmatched:
        st.warning("Unmatched (no pair): " + ", ".join(unmatched[:10]) + ("..." if len(unmatched) > 10 else ""))

    if st.button("Run bulk comparison"):
        results = []
        successful = []
        progress = st.progress(0)
        total = len(pairs) or 1
        for i, ((n1, b1), (n2, b2)) in enumerate(pairs):
            match, info = compare_pdf_values_bytes(b1, b2, invoice_kw1, invoice_kw2, facture_kw1, facture_kw2)
            result = {
                "invoice_name": n1,
                "facture_name": n2,
                "match": match,
                "invoice_val_1": info["invoice"].get(invoice_kw1),
                "invoice_val_2": info["invoice"].get(invoice_kw2),
                "facture_val_1": info["facture"].get(facture_kw1),
                "facture_val_2": info["facture"].get(facture_kw2),
            }
            # try merging only on match (same behavior as original)
            if match:
                try:
                    merged = merge_pdfs_bytes(b1, b2)
                    successful.append((f"merged_{os.path.splitext(n1)[0]}_{os.path.splitext(n2)[0]}.pdf", merged))
                    result["merged"] = True
                except Exception as e:
                    result["merged"] = False
                    result["merge_error"] = str(e)
            else:
                result["merged"] = False
            results.append(result)
            progress.progress((i + 1) / total)

        # show table
        import pandas as pd
        df = pd.DataFrame(results)
        st.subheader("Bulk results")
        st.dataframe(df)

        # download buttons for successful merges
        if successful:
            st.subheader("Successful merged PDFs")
            for fname, b in successful:
                st.download_button(f"Download {fname}", data=b, file_name=fname, mime="application/pdf")
            if len(successful) > 1:
                # create zip
                zip_io = BytesIO()
                with zipfile.ZipFile(zip_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for fname, b in successful:
                        zf.writestr(fname, b)
                zip_io.seek(0)
                st.download_button("Download all merged PDFs (zip)", data=zip_io.getvalue(), file_name="merged_pdfs.zip", mime="application/zip")
        else:
            st.warning("No successful merged PDFs (no exact matches found).")

