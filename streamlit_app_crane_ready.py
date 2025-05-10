import streamlit as st
from fpdf import FPDF
import io

# --- Unicode-safe PDF class using DejaVuSans ---
class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        self.set_font("DejaVu", size=12)

    def add_job_page(self, job, explanation):
        self.add_page()
        self.set_font("DejaVu", size=12)
        self.cell(200, 10, txt=f"Customer: {job['Customer']}", ln=True)
        self.cell(200, 10, txt=f"Boat Type: {job['Boat Type']} ({job['Boat Length']} ft, {job['Mast']})", ln=True)
        self.cell(200, 10, txt=f"Service: {job['Service']}", ln=True)
        self.cell(200, 10, txt=f"Origin: {job['Origin']}", ln=True)
        self.cell(200, 10, txt=f"Ramp: {job['Ramp']}", ln=True)
        self.cell(200, 10, txt=f"Date: {job['Date']}  Time: {job['Start']}–{job['End']}", ln=True)
        self.cell(200, 10, txt=f"Truck: {job['Truck']}", ln=True)
        self.cell(200, 10, txt=f"High Tide: {job['High Tide']}", ln=True)
        self.ln(5)
        self.set_font("DejaVu", style="B", size=12)
        self.cell(200, 10, txt="Scheduling Reasoning:", ln=True)
        self.set_font("DejaVu", size=11)
        for line in explanation.strip().split("\n"):
            self.multi_cell(0, 8, line)

# --- Session Setup + Sidebar ---
if "ALL_JOBS" not in st.session_state:
    st.session_state.ALL_JOBS = []
if "PDF_REPORT" not in st.session_state:
    st.session_state.PDF_REPORT = PDFReport()

with st.sidebar:
    st.write("Download PDF once jobs are added:")
    if st.session_state.ALL_JOBS:
        buffer = io.BytesIO()
        st.session_state.PDF_REPORT.output(buffer)
        st.download_button(
            label="📄 Download PDF Report",
            data=buffer.getvalue(),
            file_name="ecm_schedule_report.pdf",
            mime="application/pdf"
        )

# --- Demo Job Entry ---
st.title("ECM Scheduler — PDF Unicode Test")
if st.button("Add Test Job"):
    job = {
        "Customer": "Björk Guðmundsdóttir",
        "Boat Type": "Sailboat",
        "Boat Length": 38,
        "Mast": "Mast On Deck",
        "Service": "Launch",
        "Origin": "101 Reykjavík Harbor",
        "Ramp": "Scituate Harbor (Jericho Road)",
        "Date": "May 15, 2025",
        "Start": "09:30 AM",
        "End": "12:30 PM",
        "Truck": "J17",
        "High Tide": "10:15 AM"
    }
    explanation = "- Unicode test: handled successfully.\n- Truck assigned based on mast type.\n- Scheduled around valid tide window."
    st.session_state.ALL_JOBS.append(job)
    st.session_state.PDF_REPORT.add_job_page(job, explanation)
    st.success("✅ Unicode-safe job added.")