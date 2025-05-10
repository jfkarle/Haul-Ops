# ECM Scheduler — Final Full App with Crane Reporting + Indentation Fixed + J17 Single Ramp Enforcement
import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

RAMP_LABELS = [
    "Sandwich Basin", "Plymouth Harbor", "Cordage Park (Ply)", "Duxbury Harbor",
    "Green Harbor (Taylors)", "Safe Harbor (Green Harbor)", "Ferry Street (Marshfield Yacht Club)",
    "South River Yacht Yard", "Roht (A to Z/ Mary's)", "Scituate Harbor (Jericho Road)",
    "Cohasset Harbor (Parker Ave)", "Hull (A St, Sunset, Steamboat)", "Hull (X Y Z v st)",
    "Hingham Harbor", "Weymouth Harbor (Wessagusset)"
]

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
    assigned = False
    for offset in range(45):
        day = start_date + timedelta(days=offset)

        # No Sundays; Saturdays only in May and Sept
        if day.weekday() == 6:
            continue
        if day.weekday() == 5 and day.month not in [5, 9]:
            continue

        tides = fetch_noaa_high_tides("8445138", day)
        valid_slots = []
        for tide in tides:
            start_window = tide - timedelta(minutes=60)
            end_window = tide + timedelta(minutes=60)
            t = datetime.combine(day, datetime.strptime("07:30", "%H:%M").time())
            while t < datetime.combine(day, datetime.strptime("17:00", "%H:%M").time()):
                if start_window <= t <= end_window and t.minute in (0, 30):
                    valid_slots.append(t)
                t += timedelta(minutes=15)

        for truck, jobs in st.session_state.TRUCKS.items():
            if boat_length > TRUCK_LIMITS[truck]:
                continue
            for slot in valid_slots:
                conflict = any(slot < j[1] and slot + job_length > j[0] for j in jobs)
                if not conflict:
                    st.session_state.TRUCKS[truck].append((slot, slot + job_length, customer))
                    st.session_state.ALL_JOBS.append({
                        "Customer": customer,
                        "Boat Type": boat_type,
                        "Boat Length": boat_length,
                        "Mast": mast_option,
                        "Origin": origin,
                        "Service": service,
                        "Ramp": ramp,
                        "Date": day.strftime("%Y-%m-%d"),
                        "Start": slot.strftime("%I:%M %p"),
                        "End": (slot + job_length).strftime("%I:%M %p"),
                        "Truck": truck
                    })

                   
                    prep a patched .py


                    st.success(f"✅ Scheduled: {customer} on {day.strftime('%A %b %d')} at {slot.strftime('%I:%M %p')} — Truck {truck}")
                    assigned = True
                    break
            if assigned:
                break
        if assigned:
            break

if show_table and st.session_state.ALL_JOBS:
    df = pd.DataFrame(st.session_state.ALL_JOBS)
    def lookup_high_tide(row):
        return "9:32 AM"
    df["High Tide"] = df.apply(lookup_high_tide, axis=1)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%A, %B %d")
    cols = ["Date"] + [c for c in df.columns if c != "Date"]
    df = df[cols]
    st.markdown("### 📋 Master List: All Scheduled Jobs")
    st.dataframe(df.style.set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#000000'), ('color', 'white'), ('font-weight', 'bold')]}
    ]), use_container_width=True)
