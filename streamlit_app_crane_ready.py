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
            self.cell(200, 10, txt=f"Customer: {job['Customer']}", ln=True)
            self.cell(200, 10, txt=f"Boat Type: {job['Boat Type']} ({job['Boat Length']} ft, {job['Mast']})", ln=True)
            self.cell(200, 10, txt=f"Service: {job['Service']}", ln=True)
            self.cell(200, 10, txt=f"Origin: {job['Origin']}", ln=True)
            self.cell(200, 10, txt=f"Ramp: {job['Ramp']}", ln=True)
            self.cell(200, 10, txt=f"Date: {job['Date']}  Time: {job['Start']}–{job['End']}", ln=True)
            self.cell(200, 10, txt=f"Truck: {job['Truck']}", ln=True)
            self.cell(200, 10, txt=f"High Tide: {job['High Tide']}", ln=True)
            self.ln(5)
            self.set_font("Arial", style="B", size=12)
            self.cell(200, 10, txt="Scheduling Reasoning:", ln=True)
            self.set_font("Arial", size=11)
            for line in explanation.strip().split("\n"):
                self.multi_cell(0, 8, line)
    st.session_state.PDF_REPORT = PDFReport()

# --- NOAA Tide Fetching Function ---
def fetch_noaa_high_tides(station_id: str, date: datetime.date):
    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "product": "predictions",
        "datum": "MLLW",
        "station": station_id,
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d")
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        highs = [
            datetime.strptime(p["t"], "%Y-%m-%d %H:%M")
            for p in data.get("predictions", [])
            if p["type"] == "H"
            and datetime.strptime(p["t"], "%Y-%m-%d %H:%M").time() >= datetime.strptime("07:30", "%H:%M").time()
            and datetime.strptime(p["t"], "%Y-%m-%d %H:%M").time() <= datetime.strptime("17:00", "%H:%M").time()
        ]
        return highs
    except Exception as e:
        st.error(f"🌊 NOAA tide fetch failed: {e}")
        return []

# --- Streamlit UI ---
st.set_page_config("ECM Scheduler", layout="wide")
st.title("🚛 ECM Scheduler — Final Version")

with st.sidebar:
    show_table = st.checkbox("📋 Show All Scheduled Jobs Table")
    if st.session_state.ALL_JOBS:
        buffer = io.BytesIO()
        st.session_state.PDF_REPORT.output(buffer)
        st.download_button(
            label="📅 Download PDF Report",
            data=buffer.getvalue(),
            file_name="ecm_schedule_report.pdf",
            mime="application/pdf"
        )

# --- Show Scheduled Jobs Table ---
if show_table:
    st.subheader("🧾 All Scheduled Jobs")
    if st.session_state.ALL_JOBS:
        df = pd.DataFrame(st.session_state.ALL_JOBS)
        st.dataframe(df)

    st.subheader("🛠️ J17 Crane Jobs")
    if st.session_state.CRANE_JOBS:
        crane_df = pd.DataFrame(st.session_state.CRANE_JOBS, columns=["Start", "End", "Customer", "Ramp"])
        st.dataframe(crane_df)
if show_table and st.session_state.ALL_JOBS:
    st.subheader("🧾 All Scheduled Jobs")
    df = pd.DataFrame(st.session_state.ALL_JOBS)
    st.dataframe(df)

# --- Scheduler Form ---
with st.form("schedule_form"):
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("Customer Name")
        boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
        boat_length = st.number_input("Boat Length (ft)", min_value=10, max_value=100, step=1)
        service = st.selectbox("Service Type", ["Launch", "Haul", "Land-Land"])
        origin = st.text_input("Origin (Pickup Address)", placeholder="e.g. 100 Prospect Street, Marshfield, MA")
        mast_option = st.selectbox("Sailboat Mast Handling", ["None", "Mast On Deck", "Mast Transport"])
    with col2:
        ramp = st.selectbox("Ramp", RAMP_LABELS)
        start_date = st.date_input("Requested Start Date", datetime.today())
        debug = st.checkbox("Enable Tide Debug Info")
    submitted = st.form_submit_button("Schedule This Job")

if submitted:
    job_length = DURATION[boat_type]
    station_id = RAMP_TO_NOAA.get(ramp, "8445138")
    tide_times = fetch_noaa_high_tides(station_id, start_date)

    explanation = ""
    for tide in tide_times:
        start = tide - timedelta(minutes=45)
        end = start + job_length

        truck = "J17" if boat_type == "Sailboat" else "S20"
        job_record = {
            "Customer": customer,
            "Boat Type": boat_type,
            "Boat Length": boat_length,
            "Mast": mast_option,
            "Service": service,
            "Origin": origin,
            "Ramp": ramp,
            "Date": start.strftime("%B %d, %Y"),
            "Start": start.strftime("%I:%M %p"),
            "End": end.strftime("%I:%M %p"),
            "Truck": truck,
            "High Tide": tide.strftime("%I:%M %p")
        }

        st.session_state.ALL_JOBS.append(job_record)
        if truck == "J17":
            st.session_state.CRANE_JOBS.append((start, end, customer, ramp))

        explanation += f"- Truck {truck} assigned for {boat_type}\n"
        explanation += f"- Job scheduled {job_length.total_seconds() / 60:.0f} minutes before high tide ({tide.strftime('%I:%M %p')})\n"

        st.success(f"✅ Scheduled: {customer} on {start.strftime('%A %b %d')} at {start.strftime('%I:%M %p')} — Truck {truck}")
        st.markdown("**Why this slot was chosen:**
```" + explanation + "
```")
        st.session_state.PDF_REPORT.add_job_page(job_record, explanation)
        break
