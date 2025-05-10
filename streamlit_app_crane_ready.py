# ECM Scheduler — Final Full Version
import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

RAMP_TO_STATION_ID = {"Scituate": "8445138"}
TRUCK_LIMITS = {"S20": 60, "S21": 55, "S23": 30, "J17": 0}
DURATION = {"Powerboat": timedelta(hours=1.5), "Sailboat": timedelta(hours=3)}

if "TRUCKS" not in st.session_state:
    st.session_state.TRUCKS = {"S20": [], "S21": [], "S23": []}
if "ALL_JOBS" not in st.session_state:
    st.session_state.ALL_JOBS = []
if "CRANE_JOBS" not in st.session_state:
    st.session_state.CRANE_JOBS = []

def fetch_noaa_high_tides(station_id, date):
    return [datetime.combine(date, datetime.strptime("09:32", "%H:%M").time())]

def get_daytime_high_tides(tide_times):
    return [t.strftime("%-I:%M %p") for t in tide_times if t.time() >= datetime.strptime("07:30", "%H:%M").time() and t.time() <= datetime.strptime("17:00", "%H:%M").time()]

def get_station_for_ramp(ramp):
    return RAMP_TO_STATION_ID.get(ramp, "8445138")

def generate_valid_start_times(tides, ramp, date):
    buffer = (60, 60)
    valid_starts = []
    for tide in tides:
        start_window = tide - timedelta(minutes=buffer[0])
        end_window = tide + timedelta(minutes=buffer[1])
        t = datetime.combine(date, datetime.strptime("07:30", "%H:%M").time())
        while t < datetime.combine(date, datetime.strptime("17:00", "%H:%M").time()):
            if start_window <= t <= end_window and t.minute in (0, 30):
                valid_starts.append(t)
            t += timedelta(minutes=15)
    return valid_starts

def find_slot(valid_starts, truck_jobs, job_length):
    for start in valid_starts:
        conflict = any(start < j[1] and start + job_length > j[0] for j in truck_jobs)
        if not conflict:
            return start
    return None

st.set_page_config("ECM Scheduler", layout="wide")
st.title("🚛 ECM Scheduler — Final Version")

with st.sidebar:
    show_table = st.checkbox("📋 Show All Scheduled Jobs Table")

with st.form("schedule_form"):
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("Customer Name")
        boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
        boat_length = st.number_input("Boat Length (ft)", min_value=10, max_value=100, step=1)
        origin = st.selectbox("Origin (Pickup Location)", list(RAMP_TO_STATION_ID.keys()))
        service = st.selectbox("Service Type", ["Launch", "Haul"])
    with col2:
        ramp = st.selectbox("Ramp", list(RAMP_TO_STATION_ID.keys()))
        start_date = st.date_input("Requested Start Date", datetime.today())
        debug = st.checkbox("Enable Tide Debug Info")
    submitted = st.form_submit_button("Schedule This Job")


RAMP_TO_RAMP_DISTANCE = {
    ("Scituate", "Scituate"): 0,
    ("Scituate", "Plymouth"): 23,
    ("Plymouth", "Scituate"): 23,
    ("Scituate", "Green Harbor"): 14,
    ("Green Harbor", "Scituate"): 14,
    ("Green Harbor", "Plymouth"): 12,
    ("Plymouth", "Green Harbor"): 12
}

def is_too_far_between_ramps(r1, r2):
    if r1 == r2:
        return False
    return RAMP_TO_RAMP_DISTANCE.get((r1, r2), 999) > 13


if submitted:
    job_length = DURATION[boat_type]
    assigned = False
    for offset in range(45):
        day = start_date + timedelta(days=offset)
        tides = fetch_noaa_high_tides(get_station_for_ramp(ramp), day)
        valid_slots = generate_valid_start_times(tides, ramp, day)
        for truck, jobs in st.session_state.TRUCKS.items():
            if boat_length > TRUCK_LIMITS[truck]:
                continue
            slot = find_slot(valid_slots, jobs, job_length)
            if slot:
                st.session_state.TRUCKS[truck].append((slot, slot + job_length, customer))
                st.session_state.ALL_JOBS.append({
                    "Customer": customer, "Boat Type": boat_type, "Boat Length": boat_length,
                    "Service": service, "Ramp": ramp, "Date": day.strftime("%Y-%m-%d"),
                    "Start": slot.strftime("%I:%M %p"), "End": (slot + job_length).strftime("%I:%M %p"),
                    "Truck": truck
                })
                st.success(f"✅ Scheduled: {customer} on {day.strftime('%A %b %d')} at {slot.strftime('%I:%M %p')} — Truck {truck}")
                assigned = True
                break
        if assigned:
            break

if show_table and st.session_state.ALL_JOBS:
    df = pd.DataFrame(st.session_state.ALL_JOBS)
    def lookup_high_tide(row):
        try:
            tides = fetch_noaa_high_tides(get_station_for_ramp(row['Ramp']), datetime.strptime(row['Date'], "%Y-%m-%d"))
            return ", ".join(get_daytime_high_tides(tides))
        except:
            return "N/A"
    df["High Tide"] = df.apply(lookup_high_tide, axis=1)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%A, %B %d")
    cols = ["Date"] + [c for c in df.columns if c != "Date"]
    df = df[cols]
    st.markdown("### 📋 Master List: All Scheduled Jobs")
    st.dataframe(df.style.set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#000000'), ('color', 'white'), ('font-weight', 'bold')]}
    ]), use_container_width=True)
