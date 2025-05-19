# ECM Scheduler with Ramp-Specific Tide Buffers - Fully Patched and Job-Type Aware
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import requests

CUSTOMER_CSV = "customers.csv"
NOAA_API_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NOAA_PARAMS_TEMPLATE = {
    "product": "predictions",
    "datum": "MLLW",
    "units": "english",
    "time_zone": "lst_ldt",
    "format": "json",
    "interval": "hilo"
}

RAMP_TO_NOAA_ID = {
    "Plymouth Harbor": "8446493",
    "Duxbury Harbor": "8446166",
    "Green Harbor (Taylors)": "8443970",
    "Safe Harbor (Green Harbor)": "8443971",
    "Ferry Street (Marshfield Yacht Club)": "8443972",
    "South River Yacht Yard": "8443973",
    "Roht (A to Z/ Mary's)": "8443974",
    "Scituate Harbor (Jericho Road)": "8445138",
    "Cohasset Harbor (Parker Ave)": "8444762",
    "Hull (A St, Sunset, Steamboat)": "8445247",
    "Hull (X Y Z v st)": "8445248",
    "Hingham Harbor": "8444841",
    "Weymouth Harbor (Wessagusset)": "8444788",
    "Cordage Park (Ply)": "8446494",
    "Sandwich Basin": "8447180"
}

RAMP_TIDE_BUFFERS = {
    "Plymouth Harbor": {"before": 2.0, "after": 2.0},
    "Duxbury Harbor": {"before": 1.0, "after": 1.0},
    "Green Harbor (Taylors)": {"before": 3.0, "after": 3.0},
    "Safe Harbor (Green Harbor)": {"before": 2.0, "after": 2.0},
    "Ferry Street (Marshfield Yacht Club)": {"before": 2.0, "after": 2.0},
    "South River Yacht Yard": {"before": 1.5, "after": 1.5},
    "Roht (A to Z/ Mary's)": {"before": 1.0, "after": 1.0},
    "Scituate Harbor (Jericho Road)": {"before": 3.0, "after": 3.0},
    "Cohasset Harbor (Parker Ave)": {"before": 1.0, "after": 1.0},
    "Hull (A St, Sunset, Steamboat)": {"before": 2.0, "after": 2.0},
    "Hull (X Y Z v st)": {"before": 1.0, "after": 1.0},
    "Hingham Harbor": {"before": 2.0, "after": 2.0},
    "Weymouth Harbor (Wessagusset)": {"before": 2.0, "after": 2.0},
    "Cordage Park (Ply)": {"before": 1.5, "after": 1.5},
    "Sandwich Basin": {"before": 1.0, "after": 1.0}
}

TRUCK_LIMITS = {"S20": 60, "S21": 50, "S23": 30, "J17": 0}
JOB_DURATION_HRS = {"Powerboat": 1.5, "Sailboat MD": 3.0, "Sailboat MT": 3.0}

if "schedule" not in st.session_state:
    st.session_state["schedule"] = []

@st.cache_data
def load_customer_data():
    return pd.read_csv(CUSTOMER_CSV)

def filter_customers(df, query):
    return df[df["Customer Name"].str.lower().str.contains(query.lower())]

def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        return None, f"No station ID"
    params = NOAA_PARAMS_TEMPLATE | {
        "station": station_id,
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d")
    }
    try:
        resp = requests.get(NOAA_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("predictions", [])
        return [(d["t"], d["type"]) for d in data], None
    except Exception as e:
        return None, str(e)

def generate_slots_for_high_tide_with_buffer(high_tide_ts: str, ramp: str, job_duration_hrs: float):
    ht = datetime.strptime(high_tide_ts, "%Y-%m-%d %H:%M")
    buffer = RAMP_TIDE_BUFFERS.get(ramp, {"before": 3.0, "after": 3.0})
    win_start = ht - timedelta(hours=buffer["before"])
    win_end = ht + timedelta(hours=buffer["after"])
    latest_start = win_end - timedelta(hours=job_duration_hrs)
    earliest_start = win_start - timedelta(minutes=30)
    slots = []
    t = datetime.combine(ht.date(), time(8, 0))
    end_day = datetime.combine(ht.date(), time(14, 30))
    while t <= end_day:
        if earliest_start <= t <= latest_start:
            slots.append(t.time())
        t += timedelta(minutes=30)
    return slots

def get_valid_slots_with_tides(date: datetime, ramp: str, job_type: str):
    predictions, error = get_tide_predictions(date, ramp)
    if error or not predictions:
        return [], [], []
    high_tides = [t for t, kind in predictions if kind == "H"]
    valid_slots = []
    all_high_tides_data = []
    for ht in high_tides:
        try:
            slots = generate_slots_for_high_tide_with_buffer(ht, ramp, JOB_DURATION_HRS[job_type])
            if slots:
                valid_slots.append((ht, slots))
            all_high_tides_data.append({"high_tide": ht, "slots": slots})
        except:
            continue
    return valid_slots, high_tides, all_high_tides_data

def find_three_dates(start_date: datetime, ramp: str, job_type: str):
    scheduled = []
    current = start_date
    max_lookahead_days = 30
    while len(scheduled) < 3 and (current - start_date).days < max_lookahead_days:
        valid_slots, high_tide_times, _ = get_valid_slots_with_tides(current, ramp, job_type)
        for ht, slots in valid_slots:
            for slot in slots:
                dt = datetime.combine(current, slot)
                scheduled.append(dt)
                if len(scheduled) == 3:
                    return scheduled
        current += timedelta(days=1)
    return scheduled

# Simple UI for testing
st.title("ECM Scheduler Viewer")
selected_ramp = st.selectbox("Select Ramp", list(RAMP_TO_NOAA_ID.keys()))
selected_date = st.date_input("Start Search Date", datetime.now().date())
selected_job = st.selectbox("Select Job Type", list(JOB_DURATION_HRS.keys()))

if st.button("Find 3 Earliest Dates"):
    slots = find_three_dates(selected_date, selected_ramp, selected_job)
    if slots:
        st.success("Viable time slots:")
        for s in slots:
            st.write(s.strftime("%A, %B %d, %Y — %I:%M %p"))
    else:
        st.error("No viable slots found in next 30 days.")
