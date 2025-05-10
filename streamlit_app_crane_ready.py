# ECM Scheduler — Full App Version with All Logic Embedded
import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import io

RAMP_TO_STATION_ID = {
    "Sandwich": "8446493", "Plymouth": "8446493", "Cordage": "8446493",
    "Duxbury": "8446166", "Green Harbor": "8446009", "Taylor": "8446009",
    "Safe Harbor": "8446009", "Ferry Street": "8446009", "Marshfield": "8446009",
    "South River": "8446009", "Roht": "8446009", "Mary": "8446009",
    "Scituate": "8445138", "Cohasset": "8444762", "Hull": "8444762",
    "Hingham": "8444762", "Weymouth": "8444762"
}

RAMP_DISTANCE_FROM_PEMBROKE = {
    "Plymouth": 15, "Cordage": 14, "Duxbury": 12, "Green Harbor": 10, "Taylor": 10,
    "Safe Harbor": 10, "Ferry Street": 11, "Marshfield": 11, "South River": 12,
    "Roht": 11, "Mary": 11, "Scituate": 19, "Cohasset": 22, "Hull": 25,
    "Hingham": 23, "Weymouth": 24, "Sandwich": 35
}

RAMP_TO_RAMP_DISTANCE = {
    ("Scituate", "Cohasset"): 9, ("Scituate", "Plymouth"): 23,
    ("Green Harbor", "Duxbury"): 9, ("Marshfield", "Hull"): 18,
    ("Hull", "Weymouth"): 10, ("Scituate", "Green Harbor"): 14
}

TRUCK_LIMITS = {
    "S20": 60, "S21": 55, "S23": 30, "J17": 0
}

if "TRUCKS" not in st.session_state:
    st.session_state.TRUCKS = {"S20": [], "S21": [], "S23": []}
if "ALL_JOBS" not in st.session_state:
    st.session_state.ALL_JOBS = []
if "CRANE_JOBS" not in st.session_state:
    st.session_state.CRANE_JOBS = []

def get_station_for_ramp(ramp):
    for name, sid in RAMP_TO_STATION_ID.items():
        if name.lower() in ramp.lower():
            return sid
    return "8445138"

def is_busy_season(date):
    return date.month in [4, 5, 6, 9, 10]

def is_too_far_from_home(ramp, date):
    return is_busy_season(date) and RAMP_DISTANCE_FROM_PEMBROKE.get(ramp, 999) > 20

def is_too_far_between_ramps(r1, r2):
    if r1 == r2:
        return False
    return RAMP_TO_RAMP_DISTANCE.get((r1, r2), RAMP_TO_RAMP_DISTANCE.get((r2, r1), 999)) > 10

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

# Existing code continues below...

if show_table and st.session_state.ALL_JOBS:
    df = pd.DataFrame(st.session_state.ALL_JOBS)

    # Add high tide column
    def lookup_high_tide(row):
        try:
            tide_times = fetch_noaa_high_tides(get_station_for_ramp(row['Ramp']), datetime.strptime(row['Date'], "%Y-%m-%d"))
            return ", ".join(get_daytime_high_tides(tide_times))
        except:
            return "N/A"

    df['High Tide'] = df.apply(lookup_high_tide, axis=1)

    # Reformat and move Date column to front
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime("%A, %B %d")
    cols = ['Date'] + [c for c in df.columns if c != 'Date']
    df = df[cols]

    # Render styled table
    st.markdown("### 📋 Master List: All Scheduled Jobs")
    st.dataframe(df.style.set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#000000'), ('color', 'white'), ('font-weight', 'bold')]}
    ]), use_container_width=True)
