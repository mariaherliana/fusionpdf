import streamlit as st
import PyPDF2
import re
from pdf2image import convert_from_bytes
from PIL import Image
import io
import tempfile
import os
import zipfile
import pytesseract

st.set_page_config(page_title="FusionPDF", page_icon="📄", layout="wide")

st.title("📄 FusionPDF by Anna")
st.markdown("Compare and merge PDFs easily!")

# --- Sidebar Navigation ---
page = st.sidebar.radio("Navigation", ["Home", "Single Comparison", "Bulk Comparison", "Help"])


# ============================================================
# ----------------- HELPER FUNCTIONS -------------------------
# ============================================================

def extract_text_from_pdf(pdf_bytes):
    """Try to extract text directly; fall back to OCR if blank or too short."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception:
        pass

    # If text extraction fails or is too short, fall back to OCR
    if len(text.strip()) < 100:
        try:
            pages = convert_from_bytes(pdf_bytes, dpi=200)
            ocr_text = ""
            for page in pages:
                ocr_text += pytesseract.image_to_string(page, lang="eng") + "\n"
            text = ocr_text
        except Exception as e:
            st.error(f"OCR failed: {e}")

    return text


def extract_value(text: str, label: str) -> float:
    """Extract numeric value after a given label using regex."""
    # Normalize decimal and thousand separators
    text_clean = text.replace('.', '').replace(',', '.')
    pattern = rf"{re.escape(label)}[^\d]*(\d+(?:\.\d+)?)"
    match = re.search(pattern, text_clean, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_pdf_values(pdf_bytes, keywords):
    """Extract multiple labeled values from one PDF."""
    text = extract_text_from_pdf(pdf_bytes)
    return {kw: extract_value(text, kw) for kw in keywords}


def compare_with_tolerance(val1, val2, tolerance=2.0):
    """Compare floats with tolerance to allow small OCR/extraction errors."""
    if val1 is None or val2 is None:
        return "MISSING"
    if abs(val1 - val2) <= tolerance:
        return "MATCH"
    else:
        return f"DIFF ({val1 - val2:+.2f})"


def merge_pdfs(pdf1_bytes, pdf2_bytes):
    writer = PyPDF2.PdfWriter()
    for pdf_bytes in [pdf1_bytes, pdf2_bytes]:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def preview_pdf_side_by_side(invoice_bytes, facture_bytes):
    col1, col2 = st.columns(2)
    if invoice_bytes:
        inv_img = convert_from_bytes(invoice_bytes, dpi=100)[0]
        buf = io.BytesIO()
        inv_img.save(buf, format="PNG")
        with col1:
            st.image(buf, width=300, caption="Invoice PDF")
    if facture_bytes:
        fac_img = convert_from_bytes(facture_bytes, dpi=100)[0]
        buf = io.BytesIO()
        fac_img.save(buf, format="PNG")
        with col2:
            st.image(buf, width=300, caption="Facture PDF")


# ============================================================
# ----------------- PAGE LOGIC -------------------------------
# ============================================================

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
        fac_kw2 = st.text_input("Facture Keyword 2", "Jumlah PPN")

    if invoice_pdf and facture_pdf:
        st.subheader("📑 Preview PDFs")
        preview_pdf_side_by_side(invoice_pdf.read(), facture_pdf.read())
        invoice_pdf.seek(0)
        facture_pdf.seek(0)

    if st.button("Start Comparison"):
        if not (invoice_pdf and facture_pdf):
            st.warning("Please upload both PDFs first.")
        else:
            invoice_bytes = invoice_pdf.read()
            facture_bytes = facture_pdf.read()

            # Extract values
            inv_vals = extract_pdf_values(invoice_bytes, [inv_kw1, inv_kw2])
            fac_vals = extract_pdf_values(facture_bytes, [fac_kw1, fac_kw2])

            # Compare
            result1 = compare_with_tolerance(inv_vals[inv_kw1], fac_vals[fac_kw1])
            result2 = compare_with_tolerance(inv_vals[inv_kw2], fac_vals[fac_kw2])

            st.write("### Extracted Values:")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Invoice**")
                st.json(inv_vals)
            with col2:
                st.write("**Facture**")
                st.json(fac_vals)

            if result1.startswith("MATCH") and result2.startswith("MATCH"):
                st.success("✅ Values match! Merged PDF is ready.")
                merged_pdf = merge_pdfs(invoice_bytes, facture_bytes)
                st.download_button("Download Merged PDF", data=merged_pdf, file_name="merged.pdf", mime="application/pdf")
            else:
                st.error("❌ Values do NOT match!")
                st.write(f"**{inv_kw1} ↔ {fac_kw1}:** {result1}")
                st.write(f"**{inv_kw2} ↔ {fac_kw2}:** {result2}")

elif page == "Bulk Comparison":
    st.subheader("📦 Bulk PDF Comparison")
    st.write("Upload multiple Invoice PDFs and Facture PDFs. Filenames should match.")

    invoices = st.file_uploader("Upload Invoice PDFs", type="pdf", accept_multiple_files=True)
    factures = st.file_uploader("Upload Facture PDFs", type="pdf", accept_multiple_files=True)

    inv_kw1 = st.text_input("Invoice Keyword 1", "Sub Total")
    inv_kw2 = st.text_input("Invoice Keyword 2", "VAT")
    fac_kw1 = st.text_input("Facture Keyword 1", "Harga Jual / Penggantian / Uang Muka / Termin")
    fac_kw2 = st.text_input("Facture Keyword 2", "Jumlah PPN")

    if st.button("Start Bulk Comparison"):
        if not (invoices and factures):
            st.warning("Please upload both invoice and facture PDFs.")
        else:
            facture_dict = {f.name: f for f in factures}
            successful, failed = [], []
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for invoice in invoices:
                    if invoice.name in facture_dict:
                        inv_bytes = invoice.read()
                        fac_bytes = facture_dict[invoice.name].read()

                        inv_vals = extract_pdf_values(inv_bytes, [inv_kw1, inv_kw2])
                        fac_vals = extract_pdf_values(fac_bytes, [fac_kw1, fac_kw2])

                        res1 = compare_with_tolerance(inv_vals[inv_kw1], fac_vals[fac_kw1])
                        res2 = compare_with_tolerance(inv_vals[inv_kw2], fac_vals[fac_kw2])

                        if res1.startswith("MATCH") and res2.startswith("MATCH"):
                            merged = merge_pdfs(inv_bytes, fac_bytes)
                            zf.writestr(invoice.name, merged.read())
                            successful.append(invoice.name)
                        else:
                            failed.append(invoice.name)

            zip_buffer.seek(0)
            st.success(f"✅ Success: {len(successful)}, ❌ Failed: {len(failed)}")
            if successful:
                st.download_button("Download Merged PDFs (ZIP)", data=zip_buffer, file_name="merged_pdfs.zip", mime="application/zip")
            if failed:
                st.warning(f"Failed files: {', '.join(failed)}")

elif page == "Help":
    st.subheader("📖 Help")
    st.markdown("""
    ### **How to Use FusionPDF**
    - Upload Invoice and Facture PDFs (single or bulk).
    - Keywords can be adjusted for different document layouts.
    - The app first tries direct text extraction; if that fails, OCR is used.
    - Small format differences (dots, commas) are automatically normalized.
    - A tolerance of ±2 in numeric comparison prevents false mismatches.
    """)
