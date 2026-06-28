import streamlit as st
import pandas as pd
import json
from database import SessionLocal, Paper
from ingestion import process_uploaded_pdf
from fpdf import FPDF

# --- HELPER FUNCTIONS ---
def generate_pdf(doc_title, doc_summary, ai_results):
    """Generates a PDF byte string from the extracted text."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title Section
    pdf.set_font("Arial", 'B', 16)
    pdf.multi_cell(0, 10, f"Literature Review: {doc_title}")
    
    # Description/Summary Section
    pdf.set_font("Arial", 'I', 12)
    pdf.multi_cell(0, 10, f"Context: {doc_summary}")
    pdf.ln(5)
    
    # AI Extraction Results
    pdf.set_font("Arial", '', 12)
    clean_text = str(ai_results).encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, clean_text)
    
    return pdf.output(dest="S").encode("latin-1")

# --- PAGE CONFIG ---
st.set_page_config(layout="wide")
st.title("📚 Academic Literature Review Repository")

# --- DATABASE CONNECTION ---
@st.cache_resource
def get_db_session():
    return SessionLocal()

db = get_db_session()

# --- DATA LOADING ---
def load_data_from_db():
    papers = db.query(Paper).all()
    if not papers:
        return pd.DataFrame(columns=[
            "id", "Title", "Authors", "Year", "Domain", 
            "Sample", "Technique", "Findings", "Variables", 
            "Limitations", "File"
        ])
    
    data = []
    for p in papers:
        data.append({
            "id": p.id,
            "Title": p.title,
            "Authors": p.authors,
            "Year": p.year,
            "Domain": p.domain,
            "Sample": p.sample_size,
            "Technique": p.technique,
            "Findings": p.findings,
            "Variables": p.variables,
            "Limitations": p.limitations,
            "File": p.file_reference
        })
    return pd.DataFrame(data)

df = load_data_from_db()

# --- UPLOAD SIDEBAR ---
st.sidebar.header("📤 Upload New Research")
uploaded_file = st.sidebar.file_uploader("Upload a PDF article", type=["pdf"])

if uploaded_file is not None:
    if st.sidebar.button("Process Document"):
        with st.spinner("Extracting methodology and variables..."):
            success, message = process_uploaded_pdf(uploaded_file)
            if success:
                st.sidebar.success(message)
                st.rerun()
            else:
                st.sidebar.error(message)

# --- GOOGLE FORM FEEDBACK ---
st.sidebar.markdown("---")
st.sidebar.subheader("📝 Help Us Improve")
st.sidebar.write("If you found this tool useful, please share your experience!")
# Replace the link below when your form is ready
st.sidebar.link_button("Submit Feedback", "https://docs.google.com/forms/your-link-here")


# --- GLOBAL FILTERS SIDEBAR ---
st.sidebar.header("🔍 Global Filters")
if df is not None and not df.empty:
    search_query = st.sidebar.text_input("Search keywords or frameworks:")
    domain_filter = st.sidebar.multiselect("Filter by Domain:", options=df["Domain"].unique(), default=df["Domain"].unique())

    filtered_df = df[df["Domain"].isin(domain_filter)]
    if search_query:
        filtered_df = filtered_df[
            filtered_df["Title"].str.contains(search_query, case=False, na=False) | 
            filtered_df["Findings"].str.contains(search_query, case=False, na=False)
        ]
else:
    st.sidebar.info("Database is empty. Upload papers to activate filters.")
    filtered_df = pd.DataFrame()

# --- MAIN LAYOUT ---
col_table, col_details = st.columns([2, 3])

with col_table:
    st.subheader("Repository Directory")
    if not filtered_df.empty:
        selected_row_idx = st.selectbox("Select an article to deep dive:", options=filtered_df.index, format_func=lambda x: filtered_df.loc[x, "Title"])
        st.dataframe(filtered_df[["Title", "Authors", "Year", "Domain"]], width='stretch')
    else:
        st.info("No articles found in the database.")

with col_details:
    st.subheader("📑 Review Insights Panel")
    if not filtered_df.empty and selected_row_idx in filtered_df.index:
        article = filtered_df.loc[selected_row_idx]
        
        st.markdown(f"### {article['Title']}")
        st.caption(f"**Authors:** {article['Authors']} | **Year:** {article['Year']}")
        st.markdown("---")
        
        st.markdown("#### 🔬 Data & Methodology")
        st.write(f"**Sample:** {article['Sample']}")
        st.write(f"**Approach:** {article['Technique']}")
        
        st.markdown("#### 💡 Core Findings")
        findings_list = str(article["Findings"]).split(" | ")
        for finding in findings_list:
            if finding.strip():
                st.markdown(f"- {finding.strip()}")
                
        if "Variables" in article and pd.notna(article["Variables"]):
            st.markdown("#### 📊 Core Variables")
            try:
                vars_dict = json.loads(article["Variables"])
                if vars_dict.get("independent"):
                    st.write("**Independent:**", ", ".join(vars_dict["independent"]))
                if vars_dict.get("dependent"):
                    st.write("**Dependent:**", ", ".join(vars_dict["dependent"]))
                if vars_dict.get("control_or_other"):
                    st.write("**Control/Other:**", ", ".join(vars_dict["control_or_other"]))
            except json.JSONDecodeError:
                st.write(article["Variables"])
        
        st.markdown("#### ⚠️ Methodological Limitations")
        try:
            limits_dict = json.loads(article["Limitations"])
            for key, val in limits_dict.items():
                if val and str(val).strip(): 
                    clean_key = key.replace('_', ' ').title()
                    st.markdown(f"**{clean_key}:** {val}")
        except json.JSONDecodeError:
            st.warning(article["Limitations"])

        st.markdown("---")
        
        # --- PDF GENERATION & SHARING ---
        st.subheader("📤 Export & Share")
        
        # Compiles the database row into a clean text block for the PDF
        compiled_insights = f"Methodology: {article['Technique']}\n\nFindings: {article['Findings']}\n\nLimitations: {article['Limitations']}"
        doc_summary = f"Authors: {article['Authors']} ({article['Year']})"
        
        # Generate the PDF in the background
        pdf_bytes = generate_pdf(article['Title'], doc_summary, compiled_insights)
        
        # Display the Download Button
        st.download_button(
            label="📄 Download Insight as PDF",
            data=pdf_bytes,
            file_name=f"extraction_{article['Year']}.pdf",
            mime="application/pdf"
        )
        
        # Display the Copy block
        combined_output = f"DOCUMENT: {article['Title']}\nCONTEXT: {doc_summary}\n---\nEXTRACTION RESULTS:\n{compiled_insights}"
        st.code(combined_output, language="markdown") 

        st.markdown("---")
        st.markdown("#### ✍️ Custom Synthesis Notes")
        st.text_area("Log observations:", key=f"notes_{article['id']}")
    else:
        st.info("Select an article from the list to populate structural insights.")