# app.py
import streamlit as st
from io import BytesIO
import re
import os
import zipfile
from typing import Tuple, Dict, List
import PyPDF2
import logging

logging.basicConfig(level=logging.INFO)

# Default keywords copied from your original GUI defaults
DEFAULT_INVOICE_KW1 = "Sub Total"
DEFAULT_INVOICE_KW2 = "VAT"
DEFAULT_FACTURE_KW1 = "Harga Jual / Penggantian / Uang Muka / Termin"
DEFAULT_FACTURE_KW2 = "Jumlah PPN (Pajak Pertambahan Nilai)"

st.set_page_config(page_title="FusionPDF (Streamlit)", layout="wide")


# --- Core logic (kept functionally equivalent to your original code) ---
def extract_value_from_pdf_bytes(pdf_bytes: bytes, keyword: str) -> float:
    """
    Extract numeric value following the literal keyword using the same regex
    pattern your original script used:
      rf"{re.escape(keyword)}\s*(\d+(?:[.,]\d{3})*(?:[.,]\d{2}))"
    Returns float value or -1 if not found / error.
    """
    try:
        reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        text = "".join((page.extract_text() or "") for page in reader.pages)

        pattern = rf"{re.escape(keyword)}\s*(\d+(?:[.,]\d{3})*(?:[.,]\d{2}))"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1)
            # match original behaviour: remove thousands dots, swap comma -> dot
            val = float(raw.replace(".", "").replace(",", "."))
            return val
    except Exception as e:
        logging.error(f"extract_value_from_pdf_bytes error: {e}")
    return -1.0


def compare_pdf_values_bytes(invoice_bytes: bytes, facture_bytes: bytes,
                             invoice_kw1: str, invoice_kw2: str,
                             facture_kw1: str, facture_kw2: str) -> Tuple[bool, Dict]:
    """
    Runs extraction for the two keywords on both PDFs and compares them
    using strict equality (exact behavior of your original script).
    Returns (match_bool, info_dict)
    """
    inv1 = extract_value_from_pdf_bytes(invoice_bytes, invoice_kw1)
    inv2 = extract_value_from_pdf_bytes(invoice_bytes, invoice_kw2)
    fac1 = extract_value_from_pdf_bytes(facture_bytes, facture_kw1)
    fac2 = extract_value_from_pdf_bytes(facture_bytes, facture_kw2)

    match = (inv1 == fac1 and inv2 == fac2)
    info = {
        "invoice": {invoice_kw1: inv1, invoice_kw2: inv2},
        "facture": {facture_kw1: fac1, facture_kw2: fac2},
    }
    return match, info


def merge_pdfs_bytes(pdf1_bytes: bytes, pdf2_bytes: bytes) -> bytes:
    """
    Sequentially append pages from pdf1 then pdf2 (same as original merge_pdfs).
    Returns merged PDF bytes.
    """
    writer = PyPDF2.PdfWriter()
    try:
        r1 = PyPDF2.PdfReader(BytesIO(pdf1_bytes))
        r2 = PyPDF2.PdfReader(BytesIO(pdf2_bytes))
        for p in r1.pages:
            writer.add_page(p)
        for p in r2.pages:
            writer.add_page(p)
        out = BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as e:
        logging.error(f"merge_pdfs_bytes error: {e}")
        raise


# --- UI / Flow ---

st.title("FusionPDF — Invoice vs Facture (Streamlit)")
st.markdown(
    "Upload two PDFs for a single comparison (side-by-side preview) or upload many PDFs for bulk comparison. "
    "Bulk pairs are matched by **filename basename** (exact match)."
)

# Sidebar for keywords (kept default values from original)
st.sidebar.header("Keywords (use exact text as in PDFs)")
invoice_kw1 = st.sidebar.text_input("Invoice Keyword 1", value=DEFAULT_INVOICE_KW1)
invoice_kw2 = st.sidebar.text_input("Invoice Keyword 2", value=DEFAULT_INVOICE_KW2)
facture_kw1 = st.sidebar.text_input("Facture Keyword 1", value=DEFAULT_FACTURE_KW1)
facture_kw2 = st.sidebar.text_input("Facture Keyword 2", value=DEFAULT_FACTURE_KW2)

uploaded_files = st.file_uploader("Upload PDF(s) — single pair (2 files) or multiple for bulk", type=["pdf"], accept_multiple_files=True)

if not uploaded_files:
    st.info("Upload one pair (2 PDFs) for single comparison (preview available), or upload many for bulk mode.")
    st.stop()

# Convert Streamlit UploadedFile objects to (filename, bytes)
files = [(f.name, f.read()) for f in uploaded_files]

if len(files) == 2:
    # Single comparison with PDF preview
    st.subheader("Single comparison (preview)")
    col1, col2 = st.columns(2)
    fname1, b1 = files[0]
    fname2, b2 = files[1]

    with col1:
        st.markdown(f"**Left: {fname1}**")
        # embed PDF in iframe using base64
        pdf_b64 = b1.encode("base64") if False else None  # placeholder (we'll use other method below)

        # Using HTML iframe with base64 data
        import base64
        b64 = base64.b64encode(b1).decode("utf-8")
        iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600px"></iframe>'
        st.components.v1.html(iframe, height=600)

    with col2:
        st.markdown(f"**Right: {fname2}**")
        import base64
        b64 = base64.b64encode(b2).decode("utf-8")
        iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600px"></iframe>'
        st.components.v1.html(iframe, height=600)

    if st.button("Compare these two PDFs"):
        with st.spinner("Extracting and comparing..."):
            match, info = compare_pdf_values_bytes(b1, b2, invoice_kw1, invoice_kw2, facture_kw1, facture_kw2)

        st.markdown("### Comparison Result")
        st.json(info)
        if match:
            st.success("Values match (strict equality). Merging PDFs...")
            try:
                merged_bytes = merge_pdfs_bytes(b1, b2)
                st.download_button("Download merged PDF", data=merged_bytes, file_name=f"merged_{os.path.splitext(fname1)[0]}_{os.path.splitext(fname2)[0]}.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"Failed to merge PDFs: {e}")
        else:
            st.error("Values do NOT match. No merged PDF will be produced by default.")
            # Still offer merge if user insists
            if st.button("Force merge and download anyway"):
                try:
                    merged_bytes = merge_pdfs_bytes(b1, b2)
                    st.download_button("Download merged PDF (forced)", data=merged_bytes, file_name=f"merged_{os.path.splitext(fname1)[0]}_{os.path.splitext(fname2)[0]}.pdf", mime="application/pdf")
                except Exception as e:
                    st.error(f"Failed to merge PDFs: {e}")

else:
    # Bulk mode: match files by basename
    st.subheader("Bulk comparison")
    st.info("Files will be grouped by filename (basename). For each basename with two PDFs present, we'll compare and attempt to merge on success.")

    # Build mapping basename -> list of (name, bytes)
    from collections import defaultdict
    by_base = defaultdict(list)
    for name, b in files:
        base = os.path.basename(name)
        by_base[base].append((name, b))

    pairs = []
    missing = []
    for base, arr in by_base.items():
        if len(arr) >= 2:
            # take first two as pair (mimics earlier logic that relied on folders)
            pairs.append((arr[0], arr[1]))
        else:
            missing.append(base)

    st.write(f"Found {len(pairs)} pair(s) and {len(missing)} unmatched filename(s).")
    if missing:
        st.warning(f"Unmatched (no pair): {', '.join(missing[:10])}{'...' if len(missing)>10 else ''}")

    if st.button("Run bulk comparison"):
        results = []
        successful_merged = []
        prog = st.progress(0)
        total = len(pairs)
        for i, ((n1, b1), (n2, b2)) in enumerate(pairs):
            # run same compare logic
            match, info = compare_pdf_values_bytes(b1, b2, invoice_kw1, invoice_kw2, facture_kw1, facture_kw2)
            result = {
                "invoice_name": n1,
                "facture_name": n2,
                "match": match,
                "info": info
            }
            if match:
                # merge and collect bytes for download/zip
                try:
                    merged = merge_pdfs_bytes(b1, b2)
                    result["merged_bytes"] = merged
                    successful_merged.append((f"merged_{os.path.splitext(n1)[0]}_{os.path.splitext(n2)[0]}.pdf", merged))
                except Exception as e:
                    result["merge_error"] = str(e)
            results.append(result)
            prog.progress((i + 1) / max(1, total))
        st.success("Bulk comparison finished.")

        # Show results table (brief)
        import pandas as pd
        rows = []
        for r in results:
            rows.append({
                "invoice": r["invoice_name"],
                "facture": r["facture_name"],
                "match": r["match"],
                "invoice_val_1": r["info"]["invoice"].get(invoice_kw1),
                "invoice_val_2": r["info"]["invoice"].get(invoice_kw2),
                "facture_val_1": r["info"]["facture"].get(facture_kw1),
                "facture_val_2": r["info"]["facture"].get(facture_kw2),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df)

        # Allow downloading individual merged PDFs (successful) and zip all
        if successful_merged:
            st.markdown("### Successful merged PDFs")
            for fname, b in successful_merged:
                st.download_button(f"Download {fname}", data=b, file_name=fname, mime="application/pdf")
            # offer single zip download
            if len(successful_merged) > 1:
                zip_io = BytesIO()
                with zipfile.ZipFile(zip_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for fname, b in successful_merged:
                        zf.writestr(fname, b)
                zip_io.seek(0)
                st.download_button("Download all merged PDFs (zip)", data=zip_io.getvalue(), file_name="merged_pdfs.zip", mime="application/zip")
        else:
            st.warning("No successful merges produced (probably no matches).")
