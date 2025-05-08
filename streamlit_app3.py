# ECM Scheduler — NOAA + Ramp Buffers + Exportable Log
import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import io

RAMP_TO_STATION_ID = {
    "Sandwich": "8446493", "Plymouth": "8446493", "Cordage": "8446493",
    "Duxbury": "8446166", "Green Harbor": "8447001", "Taylor": "8447001",
    "Safe Harbor": "8447001", "Ferry Street": "8447001", "Marshfield": "8447001",
    "South River": "8447001", "Roht": "8447001", "Mary": "8447001",
    "Scituate": "8445138", "Cohasset": "8444762", "Hull": "8444762",
    "Hingham": "8444762", "Weymouth": "8444762"
}

RAMP_BUFFERS = {
    "Duxbury": (60, 60), "Green Harbor": (180, 180), "Taylor": (180, 180),
    "Safe Harbor": (60, 60), "Ferry Street": (60, 60), "Marshfield": (60, 60),
    "South River": (60, 60), "Roht": (60, 60), "Mary": (60, 60),
    "Scituate": (180, 180), "Cohasset": (180, 180), "Hull": (180, 180),
    "Hingham": (180, 180), "Weymouth": (180, 180), "Sandwich": (60, 60),
    "Plymouth": (60, 60), "Cordage": (60, 60)
}

if "TRUCKS" not in st.session_state:
    st.session_state.TRUCKS = {"S20": [], "S21": [], "S23": []}
if "ALL_JOBS" not in st.session_state:
    st.session_state.ALL_JOBS = []

DURATION = {"Powerboat": timedelta(hours=1.5), "Sailboat": timedelta(hours=3)}

def get_station_for_ramp(ramp):
    for name, sid in RAMP_TO_STATION_ID.items():
        if name.lower() in ramp.lower():
            return sid
    return "8445138"

def fetch_noaa_high_tides(station_id, date):
    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "product": "predictions", "datum": "MLLW", "station": station_id,
        "time_zone": "lst_ldt", "units": "english", "interval": "hilo",
        "format": "json", "begin_date": date.strftime("%Y%m%d"), "end_date": date.strftime("%Y%m%d")
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json().get("predictions", [])
        return [datetime.strptime(d["t"], "%Y-%m-%d %H:%M") for d in data if d["type"] == "H"]
    except:
        return []

def generate_valid_start_times(tides, ramp, date):
    buffer = RAMP_BUFFERS.get(ramp, (60, 60))
    valid_starts = []
    for tide in tides:
        start_window = tide - timedelta(minutes=buffer[0])
        end_window = tide + timedelta(minutes=buffer[1])
        t = datetime.combine(date, datetime.strptime("07:30", "%H:%M").time())
        while t < datetime.combine(date, datetime.strptime("17:00", "%H:%M").time()):
            if start_window <= t <= end_window:
                valid_starts.append(t)
            t += timedelta(minutes=15)
    return valid_starts

def find_slot(valid_starts, truck_jobs, job_length):
    for start in valid_starts:
        conflict = any(start < j[1] and start + job_length > j[0] for j in truck_jobs)
        if not conflict:
            return start
    return None

def get_daytime_high_tides(tide_times):
    return [t.strftime("%-I:%M %p") for t in tide_times if t.time() >= datetime.strptime("07:30", "%H:%M").time() and t.time() <= datetime.strptime("17:00", "%H:%M").time()]

st.set_page_config("ECM Scheduler", layout="wide")
st.title("🚛 ECM Scheduler — NOAA + Ramp Verified")

# Sidebar toggle for master CSV display
with st.sidebar:
    show_table = st.checkbox("📋 Show All Scheduled Jobs Table")

# Input form
with st.form("schedule_form"):
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("Customer Name")
        boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
        boat_length = st.number_input("Boat Length (ft)", min_value=10, max_value=100, step=1)
        service = st.selectbox("Service Type", ["Launch", "Haul"])
    with col2:
        ramp = st.selectbox("Ramp", list(RAMP_TO_STATION_ID.keys()))
        start_date = st.date_input("Requested Start Date", datetime.today())
        debug = st.checkbox("Enable Tide Debug Info")
    submitted = st.form_submit_button("Schedule This Job")

if submitted:
    job_length = DURATION[boat_type]
    station_id = get_station_for_ramp(ramp)
    assigned = False
    fallback_days = []

    for offset in range(0, 45):
        day = start_date + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        tides = fetch_noaa_high_tides(station_id, day)
        valid_slots = generate_valid_start_times(tides, ramp, day)
        for truck, jobs in st.session_state.TRUCKS.items():
            slot = find_slot(valid_slots, jobs, job_length)
            if slot:
                st.session_state.TRUCKS[truck].append((slot, slot + job_length, customer))
                st.session_state.ALL_JOBS.append({
                    "Customer": customer, "Boat Type": boat_type, "Boat Length": boat_length, "Service": service,
                    "Ramp": ramp, "Date": day.strftime("%Y-%m-%d"),
                    "Start": slot.strftime("%I:%M %p"),
                    "End": (slot + job_length).strftime("%I:%M %p"),
                    "Truck": truck
                })
                high_tide_times = get_daytime_high_tides(tides)
                tide_str = ", ".join(high_tide_times) if high_tide_times else "No daytime high tide"
                st.success(f"✅ Scheduled: {customer} on {day.strftime('%a %b %d')} at {slot.strftime('%I:%M %p')} — Truck {truck} — High Tide: {tide_str}")
                assigned = True
                break
        if assigned:
            break
        fallback_days.append(day.strftime("%a %b %d"))

    if not assigned:
        st.error("❌ No slot found in 45-day tide + buffer window")
        if debug:
            for d in fallback_days:
                st.text(f"Tried {d}")

# Optional master job table view
if show_table and st.session_state.ALL_JOBS:
    st.markdown("### 📋 Master List: All Scheduled Jobs")
    st.dataframe(pd.DataFrame(st.session_state.ALL_JOBS))
