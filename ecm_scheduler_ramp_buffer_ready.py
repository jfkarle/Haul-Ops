
# ECM Scheduler with Ramp-Specific Tide Buffers - Fully Patched
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

st.title("🚤 ECM Scheduler: Ramp Tide Buffer Viewer")

# UI: Customer search and ramp/date selection
with st.sidebar:
    selected_ramp = st.selectbox("Select Ramp", list(RAMP_TO_NOAA_ID.keys()))
    selected_date = st.date_input("Select Date", datetime.now().date())
    selected_job_type = st.selectbox("Job Type", list(JOB_DURATION_HRS.keys()))
    if st.button("Find Time Slots"):
        st.session_state["run_query"] = True

if st.session_state.get("run_query"):
    st.subheader(f"Tide Slots for {selected_ramp} on {selected_date.strftime('%B %d, %Y')}")

    predictions, error = get_tide_predictions(selected_date, selected_ramp)
    if error:
        st.error(f"Tide fetch error: {error}")
    elif not predictions:
        st.warning("No tide predictions available for this date.")
    else:
        high_tides = [t for t, kind in predictions if kind == "H"]
        if not high_tides:
            st.info("No high tides found.")
        else:
            for ht in high_tides:
                slots = generate_slots_for_high_tide_with_buffer(ht, selected_ramp, JOB_DURATION_HRS[selected_job_type])
                if slots:
                    st.markdown(f"**High Tide: {ht}**")
                    st.markdown(f"Viable start slots:")
                    st.write([t.strftime('%I:%M %p') for t in slots])
                else:
                    st.markdown(f"**High Tide: {ht}** — No viable slots based on buffer/job type.")
    st.session_state["run_query"] = False

