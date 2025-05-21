import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time, date
import requests

# ====================================
# ------------ CONSTANTS -------------
# ====================================
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
    "Safe Harbor (Green Harbor)": "8443970",  # Assuming same NOAA ID
    "Ferry Street (Marshfield Yacht Club)": None,  # No NOAA ID provided
    "South River Yacht Yard": None,  # No NOAA ID provided
    "Roht (A to Z/ Mary's)": None,  # No NOAA ID provided
    "Scituate Harbor (Jericho Road)": None,  # No NOAA ID provided
    "Harbor Cohasset (Parker Ave)": None,  # No NOAA ID provided
    "Hull (A St, Sunset, Steamboat)": None,  # No NOAA ID provided
    "Hull (X Y Z St) (Goodwiny st)": None,  # No NOAA ID provided
    "Hingham Harbor": "8444841",
    "Weymouth Harbor (Wessagusset)": None,  # No NOAA ID provided
    "Sandwich Basin": None # No NOAA ID provided
}
RAMP_TIDE_WINDOWS = {
    "Plymouth Harbor": (3, 3),  # 3 hrs before and after
    "Duxbury Harbor": (1, 1),  # 1 hr before or after
    "Green Harbor (Taylors)": (3, 3),  # 3 hrs before and after
    "Safe Harbor (Green Harbor)": (1, 1),  # 1 hr before or after
    "Ferry Street (Marshfield Yacht Club)": (3, 3),  # 3 hrs before and after
    "South River Yacht Yard": (2, 2),  # 2 hrs before or after
    "Roht (A to Z/ Mary's)": (1, 1),  # 1 hr before or after
    "Scituate Harbor (Jericho Road)": None,  # Any tide, special rule for 5' draft
    "Harbor Cohasset (Parker Ave)": (3, 3),  # 3 hrs before or after
    "Hull (A St, Sunset, Steamboat)": (3, 1.5),  # 3 hrs before, 1.5 hrs after for 6'+ draft
    "Hull (X Y Z St) (Goodwiny st)": (1, 1),  # 1 hr before or after
    "Hingham Harbor": (3, 3),  # 3 hrs before and after
    "Weymouth Harbor (Wessagusset)": (3, 3),  # 3 hrs before and after
    "Sandwich Basin": None # Any tide
}
TRUCK_LIMITS = {"S20": 60, "S21": 50, "S23": 30, "J17": 0}
JOB_DURATION_HRS = {"Powerboat": 1.5, "Sailboat MD": 3.0, "Sailboat MT": 3.0}

if "schedule" not in st.session_state:
    st.session_state["schedule"] = []

# ====================================
# ------------ HELPERS ---------------
# ====================================
@st.cache_data
def load_customer_data():
    df = pd.read_csv(CUSTOMER_CSV)
    # Store a copy in session state to ensure persistence
    st.session_state['customers_df_loaded'] = df.copy()
    return df

def filter_customers(df, query):
    query = query.lower()
    return df[df["Customer Name"].str.lower().str.contains(query)]


def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        station_id = "8445138"  # Fallback to Scituate for any ramp without assigned NOAA ID
    params = NOAA_PARAMS_TEMPLATE | {
        "station": station_id,
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d")
    }
    try:
        resp = requests.get(NOAA_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("predictions", [])
        high_tides = [(d["t"], d["v"]) for d in data if d["type"] == "H"]
        return [(d["t"], d["type"]) for d in data], high_tides, None
    except Exception as e:
        return None, [], str(e)

    if not station_id:
        return None, [], f"No NOAA station ID mapped for {ramp}"
    params = NOAA_PARAMS_TEMPLATE | {
        "station": station_id,
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d")
    }
    try:
        resp = requests.get(NOAA_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("predictions", [])
        high_tides = [(d["t"], d["v"]) for d in data if d["type"] == "H"]
        return [(d["t"], d["type"]) for d in data], high_tides, None
    except Exception as e:
        return None, [], str(e)

def generate_slots_for_high_tide(high_tide_ts: str, before_hours: float, after_hours: float):
    ht = datetime.strptime(high_tide_ts, "%Y-%m-%d %H:%M")
    win_start = ht - timedelta(hours=before_hours)
    win_end = ht + timedelta(hours=after_hours)
    slots = []
    t = datetime.combine(ht.date(), time(8, 0))  # Start checking from 8:00 AM
    end_day = datetime.combine(ht.date(), time(14, 30)) # Check until 2:30 PM

    while t <= end_day:
        if win_start <= t <= win_end:
            slots.append(t.time())
        t += timedelta(minutes=30)
    return slots

def get_valid_slots_with_tides(date: datetime, ramp: str, boat_draft: float = None):
    preds, high_tides_data, err = get_tide_predictions(date, ramp)
    if err or not preds:
        return [], None

    valid_slots = []
    high_tide_time = None
    tide_window = RAMP_TIDE_WINDOWS.get(ramp)

    if ramp == "Scituate Harbor (Jericho Road)" and boat_draft and boat_draft > 5:  #
        tide_window = (3, 3)  # Special rule for Scituate with draft > 5'

    if tide_window:
        #  Use only the first high tide of the day
        first_high_tide = high_tides_data[0] if high_tides_data else None
        if first_high_tide:
            ht_datetime = datetime.strptime(first_high_tide[0], "%Y-%m-%d %H:%M")
            high_tide_time = ht_datetime.strftime("%I:%M %p")
            valid_slots = generate_slots_for_high_tide(first_high_tide[0], tide_window[0], tide_window[1])
    elif ramp == "Sandwich Basin":
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3) # "Any tide" - provide middle of the day window
    else:
        # If no tide window is specified, return all slots (or a reasonable default)
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3) # Default to 3 hours before/after 10:00 AM

    return sorted(set(valid_slots)), high_tide_time

def is_workday(date: datetime):
    wk = date.weekday()
    if wk == 6:
        return False
    if wk == 5:
        return date.month in (5, 9)
    return True

def get_j17_available_until(boat_type: str):
    if boat_type == "Sailboat MD":
        return timedelta(hours=1)
    elif boat_type == "Sailboat MT":
        return timedelta(hours=1.5)
    return timedelta(hours=0) # Not a sailboat, J17 not applicable

def eligible_trucks(boat_len: int, boat_type: str):
    trucks = []
    for t, lim in TRUCK_LIMITS.items():
        if boat_len <= lim:
            trucks.append(t)
    if "Sailboat" in boat_type:
        trucks.append("J17")
    return trucks

def has_truck_scheduled(truck: str, date: datetime):
    for job in st.session_state["schedule"]:
        if job["truck"] == truck and job["date"].date() == date.date(): # Ensure comparing date objects
            return True
    return False

def is_truck_free(truck: str, date: datetime, start_t: time, dur_hrs: float, customer=None, boat_type=None):
    start_dt = datetime.combine(date, start_t)
    end_dt = start_dt + timedelta(hours=dur_hrs)

    for job in st.session_state["schedule"]:
        if job["truck"] == truck and job["date"].date() == date.date():
            job_start = datetime.combine(job["date"].date(), job["time"])
            job_end = job_start + timedelta(hours=job["duration"])
            latest_start = max(start_dt, job_start)
            earliest_end = min(end_dt, job_end)
            overlap = (earliest_end - latest_start).total_seconds() > 0
            if overlap:
                return False
        elif truck == "J17" and job["date"].date() == date.date():
            job_boat_type = ""
            try:
                job_boat_type = customers_df[customers_df["Customer Name"] == job["customer"]]["Boat Type"].iloc[0]
            except (KeyError, IndexError):
                job_boat_type = "Unknown"
            j17_available_until_job = datetime.combine(job["date"].date(), job["time"]) + get_j17_available_until(job_boat_type)
            j17_available_until_new = start_dt + get_j17_available_until(boat_type)

            # Check if the new job's J17 usage overlaps with existing J17 usage
            overlap_new_starts_during_old = start_dt < j17_available_until_job and start_dt >= datetime.combine(job["date"].date(), job["time"])
            overlap_old_starts_during_new = datetime.combine(job["date"].date(), job["time"]) < j17_available_until_new and datetime.combine(job["date"].date(), job["time"]) >= start_dt
            overlap_contains_old = start_dt <= datetime.combine(job["date"].date(), job["time"]) and j17_available_until_new >= j1
