import streamlit as st
import PyPDF2
import re
from pdf2image import convert_from_bytes
from PIL import Image
import io
import zipfile
import pytesseract

st.set_page_config(page_title="FusionPDF", page_icon="📄", layout="wide")
st.title("📄 FusionPDF by Anna")
st.markdown("Compare and merge PDFs easily!")

# --- Sidebar ---
page = st.sidebar.radio("Navigation", ["Home", "Single Comparison", "Bulk Comparison", "Help"])

# --- OCR-based helper functions ---
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Try PyPDF2 first; fallback to OCR if text extraction is empty."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    except Exception:
        text = ""

    # If extraction failed or text too short, fallback to OCR
    if len(text.strip()) < 50:
        try:
            pages = convert_from_bytes(pdf_bytes, dpi=200)
            for page in pages:
                text += pytesseract.image_to_string(page, lang="eng") + "\n"
        except Exception as e:
            st.error(f"OCR extraction failed: {e}")
    return text


def extract_value(text: str, label: str) -> float:
    """Extract numeric value near a label (same or next line)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(re.escape(label), line, re.IGNORECASE):
            # Look for number on the same line
            match = re.search(r"(\d[\d.,]{2,})", line)
            # If not on same line, check next few lines
            if not match:
                for j in range(1, 3):
                    if i + j < len(lines):
                        match = re.search(r"(\d[\d.,]{2,})", lines[i + j])
                        if match:
                            break
            if match:
                num_str = re.sub(r"[^\d.,]", "", match.group(1))
                num_str = num_str.replace(".", "").replace(",", ".")
                try:
                    return float(num_str)
                except ValueError:
                    return None
    return None


def extract_value_from_pdf(pdf_bytes, label):
    text = extract_text_from_pdf(pdf_bytes)
    return extract_value(text, label)


def compare_values(val1, val2, tolerance=0.01):
    """Compare two float values within tolerance."""
    if val1 is None or val2 is None:
        return False
    if val2 == 0:
        return abs(val1 - val2) < tolerance
    diff_ratio = abs(val1 - val2) / val2
    return diff_ratio < 0.005  # within 0.5%


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
        col1.image(buf, width=300, caption="Invoice PDF")
    if facture_bytes:
        fac_img = convert_from_bytes(facture_bytes, dpi=100)[0]
        buf = io.BytesIO()
        fac_img.save(buf, format="PNG")
        col2.image(buf, width=300, caption="Facture PDF")


def display_extracted(invoice_data, facture_data):
    st.subheader("Extracted Values:")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Invoice**")
        st.json(invoice_data)
    with col2:
        st.markdown("**Facture**")
        st.json(facture_data)


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
        if not (invoice_pdf and facture_pdf):
            st.warning("Please upload both PDFs first.")
        else:
            inv_bytes = invoice_pdf.read()
            fac_bytes = facture_pdf.read()

            inv_text = extract_text_from_pdf(inv_bytes)
            fac_text = extract_text_from_pdf(fac_bytes)

            inv_values = {
                inv_kw1: extract_value(inv_text, inv_kw1),
                inv_kw2: extract_value(inv_text, inv_kw2),
            }
            fac_values = {
                fac_kw1: extract_value(fac_text, fac_kw1),
                fac_kw2: extract_value(fac_text, fac_kw2),
            }

            display_extracted(inv_values, fac_values)

            match1 = compare_values(inv_values[inv_kw1], fac_values[fac_kw1])
            match2 = compare_values(inv_values[inv_kw2], fac_values[fac_kw2])

            if match1 and match2:
                st.success("✅ Values match! Merged PDF is ready.")
                merged = merge_pdfs(inv_bytes, fac_bytes)
                st.download_button("Download Merged PDF", data=merged, file_name="merged.pdf", mime="application/pdf")
            else:
                st.error("❌ Values do NOT match!")
                st.markdown(f"**{inv_kw1} ↔ {fac_kw1}:** {'MATCH' if match1 else 'DIFF'}")
                st.markdown(f"**{inv_kw2} ↔ {fac_kw2}:** {'MATCH' if match2 else 'DIFF'}")

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
            facture_dict = {f.name: f for f in factures}
            successful, failed = [], []
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for invoice in invoices:
                    if invoice.name in facture_dict:
                        inv_bytes = invoice.read()
                        fac_bytes = facture_dict[invoice.name].read()

                        inv_text = extract_text_from_pdf(inv_bytes)
                        fac_text = extract_text_from_pdf(fac_bytes)

                        inv_values = {
                            inv_kw1: extract_value(inv_text, inv_kw1),
                            inv_kw2: extract_value(inv_text, inv_kw2),
                        }
                        fac_values = {
                            fac_kw1: extract_value(fac_text, fac_kw1),
                            fac_kw2: extract_value(fac_text, fac_kw2),
                        }

                        if (
                            compare_values(inv_values[inv_kw1], fac_values[fac_kw1])
                            and compare_values(inv_values[inv_kw2], fac_values[fac_kw2])
                        ):
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
    ### How to Use FusionPDF
    - **Single Comparison:** Upload one Invoice and one Facture PDF → Enter keywords → Compare → Download merged PDF.
    - **Bulk Comparison:** Upload multiple PDFs (filenames must match).
    - **Preview:** You can preview the first page of uploaded PDFs side by side.
    - **OCR Powered:** Automatically switches to OCR if text extraction fails.
    - **Tolerance:** Allows small numeric differences (rounding, commas, OCR noise).
    """)
