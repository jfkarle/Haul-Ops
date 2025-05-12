
import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
from fpdf import FPDF
import io

# --- Constants ---
RAMP_LABELS = [
    "Sandwich Basin", "Plymouth Harbor", "Cordage Park (Ply)", "Duxbury Harbor",
    "Green Harbor (Taylors)", "Safe Harbor (Green Harbor)", "Ferry Street (Marshfield Yacht Club)",
    "South River Yacht Yard", "Roht (A to Z/ Mary's)", "Scituate Harbor (Jericho Road)",
    "Cohasset Harbor (Parker Ave)", "Hull (A St, Sunset, Steamboat)", "Hull (X Y Z v st)",
    "Hingham Harbor", "Weymouth Harbor (Wessagusset)"
]

TRUCK_LIMITS = {"S20": 60, "S21": 55, "S23": 30, "J17": 0}
DURATION = {"Powerboat": timedelta(hours=1.5), "Sailboat": timedelta(hours=3)}

RAMP_TO_NOAA = {
    "Duxbury Harbor": "8446166",
    "Scituate Harbor (Jericho Road)": "8445138",
    "Plymouth Harbor": "8446493",
    "Cohasset Harbor (Parker Ave)": "8444762",
    "Weymouth Harbor (Wessagusset)": "8444788",
    "Green Harbor (Taylors)": "8446493"
}

ECM_ADDRESS = "43 Mattakeeset Street, Pembroke, MA"

# --- Session State Initialization ---
if "TRUCKS" not in st.session_state:
    st.session_state.TRUCKS = {"S20": [], "S21": [], "S23": []}
if "ALL_JOBS" not in st.session_state:
    st.session_state.ALL_JOBS = []
if "CRANE_JOBS" not in st.session_state:
    st.session_state.CRANE_JOBS = []
if "PDF_REPORT" not in st.session_state:
    class PDFReport(FPDF):
        def __init__(self):
            super().__init__()
            self.set_auto_page_break(auto=True, margin=15)

        def add_job_page(self, job, explanation):
            self.add_page()
            self.set_font("Arial", size=12)
            self.cell(200, 10, txt=f"Customer: {job['Customer']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Boat Type: {job['Boat Type']} ({job['Boat Length']} ft, {job['Mast']})".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Service: {job['Service']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Origin: {job['Origin']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Ramp: {job['Ramp']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Date: {job['Date']}  Time: {job['Start']}–{job['End']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Truck: {job['Truck']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"High Tide: {job['High Tide']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.ln(5)
            self.set_font("Arial", style="B", size=12)
            self.cell(200, 10, txt="Scheduling Reasoning:", ln=True)
            self.set_font("Arial", size=11)
            for line in explanation.strip().split("\n"):
                safe_line = line.encode("latin-1", "replace").decode("latin-1")
                self.multi_cell(0, 8, safe_line)
    st.session_state.PDF_REPORT = PDFReport()
