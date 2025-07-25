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

# --- Sidebar for Navigation ---
page = st.sidebar.radio("Navigation", ["Home", "Single Comparison", "Bulk Comparison", "Help"])

# --- OCR-based Helper Functions ---
def extract_value_from_pdf(pdf_bytes, keyword: str) -> float:
    """Extract numeric value after a given keyword using OCR."""
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=200)
        ocr_text = ""
        for page in pages:
            ocr_text += pytesseract.image_to_string(page, lang="eng") + "\n"

        # Normalize text: unify formats like 1.000.000 -> 1000000, 1,000.00 -> 1000.00
        text_clean = ocr_text.replace(".", "").replace(",", ".")
        
        # Flexible pattern: keyword followed by a number (supports floats)
        pattern = rf"{re.escape(keyword)}[^\d]*(\d+(?:\.\d+)?)"
        value_match = re.search(pattern, text_clean, re.IGNORECASE)
        
        if value_match:
            value = float(value_match.group(1))
            return value

    except Exception as e:
        st.error(f"Error extracting value (OCR): {e}")
    return -1

def compare_pdf_values(invoice_bytes, facture_bytes, inv_kw1, inv_kw2, fac_kw1, fac_kw2):
    invoice_value1 = extract_value_from_pdf(invoice_bytes, inv_kw1)
    invoice_value2 = extract_value_from_pdf(invoice_bytes, inv_kw2)
    facture_value1 = extract_value_from_pdf(facture_bytes, fac_kw1)
    facture_value2 = extract_value_from_pdf(facture_bytes, fac_kw2)
    return invoice_value1 == facture_value1 and invoice_value2 == facture_value2

def merge_pdfs(pdf1_bytes, pdf2_bytes):
    pdf_writer = PyPDF2.PdfWriter()
    pdf_reader1 = PyPDF2.PdfReader(io.BytesIO(pdf1_bytes))
    pdf_reader2 = PyPDF2.PdfReader(io.BytesIO(pdf2_bytes))
    for page in pdf_reader1.pages:
        pdf_writer.add_page(page)
    for page in pdf_reader2.pages:
        pdf_writer.add_page(page)
    output_stream = io.BytesIO()
    pdf_writer.write(output_stream)
    output_stream.seek(0)
    return output_stream

def preview_pdf_side_by_side(invoice_bytes, facture_bytes):
    """Preview first page of both PDFs side by side."""
    col1, col2 = st.columns(2)
    if invoice_bytes:
        pages = convert_from_bytes(invoice_bytes, dpi=100)
        img_buffer = io.BytesIO()
        pages[0].save(img_buffer, format="PNG")
        with col1:
            st.image(img_buffer, width=300, caption="Invoice PDF")
    if facture_bytes:
        pages = convert_from_bytes(facture_bytes, dpi=100)
        img_buffer = io.BytesIO()
        pages[0].save(img_buffer, format="PNG")
        with col2:
            st.image(img_buffer, width=300, caption="Facture PDF")

# --- Pages ---
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

    if invoice_pdf and facture_pdf:
        st.subheader("📑 Preview PDFs")
        preview_pdf_side_by_side(invoice_pdf.read(), facture_pdf.read())
        invoice_pdf.seek(0)
        facture_pdf.seek(0)

    if st.button("Start Comparison"):
        if invoice_pdf and facture_pdf:
            invoice_bytes = invoice_pdf.read()
            facture_bytes = facture_pdf.read()
            if compare_pdf_values(invoice_bytes, facture_bytes, inv_kw1, inv_kw2, fac_kw1, fac_kw2):
                st.success("✅ Values match! Merged PDF is ready.")
                merged_pdf = merge_pdfs(invoice_bytes, facture_bytes)
                st.download_button("Download Merged PDF", data=merged_pdf, file_name="merged.pdf", mime="application/pdf")
            else:
                st.error("❌ Values do NOT match!")
        else:
            st.warning("Please upload both PDFs first.")

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
        if invoices and factures:
            facture_dict = {f.name: f for f in factures}
            successful, failed = [], []
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for invoice in invoices:
                    if invoice.name in facture_dict:
                        inv_bytes = invoice.read()
                        fac_bytes = facture_dict[invoice.name].read()
                        if compare_pdf_values(inv_bytes, fac_bytes, inv_kw1, inv_kw2, fac_kw1, fac_kw2):
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
        else:
            st.warning("Please upload both invoice and facture PDFs.")

elif page == "Help":
    st.subheader("📖 Help")
    st.markdown("""
    ### **How to Use FusionPDF**
    - **Single Comparison:** Upload one Invoice and one Facture PDF → Enter keywords → Compare → Download merged PDF.
    - **Bulk Comparison:** Upload multiple PDFs (filenames must match).
    - **Preview:** You can preview the first page of uploaded PDFs side by side.
    - **OCR Powered:** Extracted values are now based on what you visually see in the PDF.
    - **Results:** Success → merged PDF, Failure → mismatch warning.
    """)
