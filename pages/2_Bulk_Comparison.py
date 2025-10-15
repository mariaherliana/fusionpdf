# pages/2_Bulk_Comparison.py
# FusionPDF — Bulk Comparison (Natural Mocha Theme)

import streamlit as st
import tempfile
import os
import zipfile
import pandas as pd
from utils.fusion_core import compare_pdf_values, merge_pdfs_bytes

# -------------------------
# UI Setup
# -------------------------
st.set_page_config(page_title="FusionPDF — Bulk Comparison", layout="wide")

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
.success {
  background-color: var(--accent-sage);
  color: var(--coffee);
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 600;
}
.warning {
  background-color: var(--accent-rose);
  color: var(--coffee);
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 600;
}
</style>
"""
st.markdown(MOCHA_CSS, unsafe_allow_html=True)

# -------------------------
# Sidebar for keywords
# -------------------------
with st.sidebar:
    st.markdown("<div class='app-card'><div class='section-title'>Keywords</div>", unsafe_allow_html=True)
    invoice_k1 = st.text_input('Invoice keyword 1', value='Sub Total')
    invoice_k2 = st.text_input('Invoice keyword 2', value='VAT')
    facture_k1 = st.text_input('Facture keyword 1', value='Harga Jual / Penggantian / Uang Muka / Termin')
    facture_k2 = st.text_input('Facture keyword 2', value='Jumlah PPN (Pajak Pertambahan Nilai)')
    st.markdown("<hr>", unsafe_allow_html=True)
    force_merge = st.checkbox('Force merge even if values don’t match', value=False)
    st.markdown("<div class='small-muted'>Used to extract and compare numeric values for all uploaded pairs.</div></div>", unsafe_allow_html=True)

# -------------------------
# Layout
# -------------------------
st.markdown("<div class='app-card'><div class='section-title'>Bulk Comparison</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    invoices = st.file_uploader("Upload Invoices (multiple PDFs)", type=['pdf'], accept_multiple_files=True)
with col2:
    factures = st.file_uploader("Upload Factures (multiple PDFs)", type=['pdf'], accept_multiple_files=True)

keywords = {
    'invoice_k1': invoice_k1,
    'invoice_k2': invoice_k2,
    'facture_k1': facture_k1,
    'facture_k2': facture_k2,
}

# -------------------------
# Helper: Save to temp
# -------------------------
def save_uploaded_to_temp(uploaded_files):
    temp_dir = tempfile.mkdtemp()
    paths = []
    for file in uploaded_files:
        temp_path = os.path.join(temp_dir, file.name)
        with open(temp_path, "wb") as f:
            f.write(file.getbuffer())
        paths.append(temp_path)
    return paths

# -------------------------
# Bulk comparison logic
# -------------------------
if st.button("Run Bulk Comparison", use_container_width=True):
    if not invoices or not factures:
        st.error("Please upload both invoices and factures.")
    else:
        inv_paths = save_uploaded_to_temp(invoices)
        fac_paths = save_uploaded_to_temp(factures)

        # Match files by basename
        invoice_map = {os.path.splitext(os.path.basename(p))[0]: p for p in inv_paths}
        facture_map = {os.path.splitext(os.path.basename(p))[0]: p for p in fac_paths}

        matched_names = set(invoice_map.keys()) & set(facture_map.keys())

        if not matched_names:
            st.warning("No matching filenames found between invoices and factures.")
        else:
            results = []
            merged_dir = tempfile.mkdtemp()

            for name in matched_names:
                inv = invoice_map[name]
                fac = facture_map[name]
                cmp = compare_pdf_values(inv, fac, keywords)
                can_merge = cmp["match"] or force_merge
                merge_status = "Merged ✅" if can_merge else "Skipped ⚠️"

                if can_merge:
                    merged_bytes = merge_pdfs_bytes(inv, fac)
                    merged_path = os.path.join(merged_dir, f"{name}_merged.pdf")
                    with open(merged_path, "wb") as f:
                        f.write(merged_bytes)

                results.append({
                    "File": name,
                    "Invoice Value 1": cmp["invoice_value1"],
                    "Invoice Value 2": cmp["invoice_value2"],
                    "Facture Value 1": cmp["facture_value1"],
                    "Facture Value 2": cmp["facture_value2"],
                    "Match": "✅" if cmp["match"] else "❌",
                    "Merged": merge_status,
                })

            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

            # --- Downloads ---
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download Summary CSV", csv_bytes, "comparison_summary.csv", "text/csv")

            # Zip all merged
            zip_path = os.path.join(tempfile.gettempdir(), "merged_results.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                for f in os.listdir(merged_dir):
                    zf.write(os.path.join(merged_dir, f), arcname=f)
            with open(zip_path, "rb") as z:
                st.download_button("Download All Merged PDFs (ZIP)", z.read(), "merged_results.zip", "application/zip")

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<div class='small-muted' style='margin-top:12px;'>FusionPDF — Bulk Comparison. Files paired by name and compared automatically.</div>", unsafe_allow_html=True)
