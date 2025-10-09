import streamlit as st
import fitz  # PyMuPDF
import re
import io
import zipfile
import PyPDF2
from pdf2image import convert_from_bytes

st.set_page_config(page_title="FusionPDF", page_icon="📄", layout="wide")

st.title("📄 FusionPDF by Anna")
st.markdown("Compare and merge PDFs accurately — now with PyMuPDF text extraction.")

# ----------------- HELPER FUNCTIONS -----------------

def normalize_number(num_str: str) -> float:
    """Normalize and convert number string to float."""
    num_str = num_str.strip()
    num_str = re.sub(r"[^\d,.-]", "", num_str)
    num_str = num_str.replace(".", "").replace(",", ".")
    try:
        return float(num_str)
    except ValueError:
        return None


def extract_value_from_pdf_text(pdf_bytes, keyword: str) -> float:
    """Extract numeric value near a keyword using PyMuPDF (no OCR)."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(page.get_text("text") for page in doc)
        lines = text.splitlines()

        for i, line in enumerate(lines):
            if re.search(re.escape(keyword), line, re.IGNORECASE):
                # Look for numbers on same or next line
                candidate_lines = [line]
                if i + 1 < len(lines):
                    candidate_lines.append(lines[i + 1])
                for l in candidate_lines:
                    numbers = re.findall(r"(\d[\d.,]*)", l)
                    if numbers:
                        val = normalize_number(numbers[-1])
                        if val is not None:
                            return val
        return None
    except Exception as e:
        st.error(f"Extraction error: {e}")
        return None


def compare_pdf_values(invoice_bytes, facture_bytes, inv_kw1, inv_kw2, fac_kw1, fac_kw2):
    """Extract and compare values."""
    invoice_values = {
        inv_kw1: extract_value_from_pdf_text(invoice_bytes, inv_kw1),
        inv_kw2: extract_value_from_pdf_text(invoice_bytes, inv_kw2)
    }

    facture_values = {
        fac_kw1: extract_value_from_pdf_text(facture_bytes, fac_kw1),
        fac_kw2: extract_value_from_pdf_text(facture_bytes, fac_kw2)
    }

    return invoice_values, facture_values


def merge_pdfs(pdf1_bytes, pdf2_bytes):
    """Merge two PDFs into one."""
    pdf_writer = PyPDF2.PdfWriter()
    for pdf_bytes in [pdf1_bytes, pdf2_bytes]:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            pdf_writer.add_page(page)
    output = io.BytesIO()
    pdf_writer.write(output)
    output.seek(0)
    return output


def preview_pdf_side_by_side(invoice_bytes, facture_bytes):
    """Preview first pages side by side."""
    col1, col2 = st.columns(2)
    if invoice_bytes:
        pages = convert_from_bytes(invoice_bytes, dpi=120)
        img_buf = io.BytesIO()
        pages[0].save(img_buf, format="PNG")
        with col1:
            st.image(img_buf, caption="Invoice PDF", width=350)
    if facture_bytes:
        pages = convert_from_bytes(facture_bytes, dpi=120)
        img_buf = io.BytesIO()
        pages[0].save(img_buf, format="PNG")
        with col2:
            st.image(img_buf, caption="Facture PDF", width=350)

# ----------------- APP LAYOUT -----------------

page = st.sidebar.radio("Navigation", ["Home", "Single Comparison", "Bulk Comparison", "Help"])

if page == "Home":
    st.subheader("Welcome to FusionPDF!")
    st.write("This version uses text-based extraction via PyMuPDF — faster and more precise than OCR.")

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
        invoice_bytes = invoice_pdf.read()
        facture_bytes = facture_pdf.read()

        st.subheader("📑 Preview PDFs")
        preview_pdf_side_by_side(invoice_bytes, facture_bytes)

        if st.button("Start Comparison"):
            invoice_values, facture_values = compare_pdf_values(
                invoice_bytes, facture_bytes, inv_kw1, inv_kw2, fac_kw1, fac_kw2
            )

            st.subheader("Extracted Values:")
            colA, colB = st.columns(2)
            with colA:
                st.write("**Invoice**")
                st.json(invoice_values)
            with colB:
                st.write("**Facture**")
                st.json(facture_values)

            inv1, inv2 = invoice_values.values()
            fac1, fac2 = facture_values.values()

            match_1 = inv1 and fac1 and abs(inv1 - fac1) < 1
            match_2 = inv2 and fac2 and abs(inv2 - fac2) < 1

            if match_1 and match_2:
                st.success("✅ Values match! Merged PDF ready for download.")
                merged = merge_pdfs(invoice_bytes, facture_bytes)
                st.download_button("Download Merged PDF", data=merged, file_name="merged.pdf", mime="application/pdf")
            else:
                st.error("❌ Values do NOT match!")
                if inv1 and fac1:
                    st.write(f"**{inv_kw1} ↔ {fac_kw1}:** DIFF {inv1 - fac1:+,.2f}")
                if inv2 and fac2:
                    st.write(f"**{inv_kw2} ↔ {fac_kw2}:** DIFF {inv2 - fac2:+,.2f}")

elif page == "Bulk Comparison":
    st.subheader("📦 Bulk PDF Comparison")
    st.write("Upload multiple Invoice and Facture PDFs (names must match).")

    invoices = st.file_uploader("Upload Invoice PDFs", type="pdf", accept_multiple_files=True)
    factures = st.file_uploader("Upload Facture PDFs", type="pdf", accept_multiple_files=True)

    inv_kw1 = st.text_input("Invoice Keyword 1", "Sub Total")
    inv_kw2 = st.text_input("Invoice Keyword 2", "VAT")
    fac_kw1 = st.text_input("Facture Keyword 1", "Harga Jual / Penggantian / Uang Muka / Termin")
    fac_kw2 = st.text_input("Facture Keyword 2", "Jumlah PPN (Pajak Pertambahan Nilai)")

    if st.button("Start Bulk Comparison"):
        if not invoices or not factures:
            st.warning("Upload both sets of PDFs.")
        else:
            facture_dict = {f.name: f for f in factures}
            success, failed = [], []
            zip_buf = io.BytesIO()

            with zipfile.ZipFile(zip_buf, "w") as zf:
                for inv in invoices:
                    if inv.name in facture_dict:
                        inv_bytes = inv.read()
                        fac_bytes = facture_dict[inv.name].read()
                        inv_vals, fac_vals = compare_pdf_values(inv_bytes, fac_bytes, inv_kw1, inv_kw2, fac_kw1, fac_kw2)

                        inv_match = (
                            inv_vals[inv_kw1] and fac_vals[fac_kw1] and abs(inv_vals[inv_kw1] - fac_vals[fac_kw1]) < 1 and
                            inv_vals[inv_kw2] and fac_vals[fac_kw2] and abs(inv_vals[inv_kw2] - fac_vals[fac_kw2]) < 1
                        )

                        if inv_match:
                            merged = merge_pdfs(inv_bytes, fac_bytes)
                            zf.writestr(inv.name, merged.read())
                            success.append(inv.name)
                        else:
                            failed.append(inv.name)

            zip_buf.seek(0)
            st.success(f"✅ Matched: {len(success)}, ❌ Failed: {len(failed)}")
            if success:
                st.download_button("Download Merged PDFs (ZIP)", data=zip_buf, file_name="merged_pdfs.zip", mime="application/zip")
            if failed:
                st.warning(f"Failed files: {', '.join(failed)}")

elif page == "Help":
    st.subheader("📖 Help")
    st.markdown("""
    ### How to Use FusionPDF
    - Upload **Invoice** and **Facture** PDFs.
    - Enter the keywords to search for (case-insensitive).
    - System finds numeric values near those keywords.
    - Comparison succeeds if both pairs match (within ±1 tolerance).
    - If matched, merged PDFs are available for download.
    """)

