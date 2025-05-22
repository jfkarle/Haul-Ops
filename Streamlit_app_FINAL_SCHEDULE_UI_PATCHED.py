
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import requests
from fpdf import FPDF
import io

# ---------------------- CONSTANTS ----------------------
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
    "Safe Harbor (Green Harbor)": "8443970",
    "Ferry Street (Marshfield Yacht Club)": "8443970",
    "Cohasset Harbor (Parker Ave)": "8444762",
    "Weymouth Harbor (Wessagusset)": "8444788",
    "Scituate Harbor (Jericho Road)": "8445138",
    "Fallback": "8445138"  # Scituate as universal fallback
}

RAMP_TIDE_BUFFERS = {
    "Duxbury Harbor": 1,
    "Green Harbor (Taylors)": 3,
    "Safe Harbor (Green Harbor)": 3,
    "Ferry Street (Marshfield Yacht Club)": 3,
    "Plymouth Harbor": 2,
    "Cohasset Harbor (Parker Ave)": 3,
    "Weymouth Harbor (Wessagusset)": 3,
    "Scituate Harbor (Jericho Road)": 3
}

TRUCKS = ["S20", "S21", "S23", "J17"]

# ---------------------- STATE INIT ----------------------
if "schedule" not in st.session_state:
    st.session_state["schedule"] = []

# ---------------------- FUNCTIONS ----------------------
def fetch_high_tides(ramp, target_date):
    station = RAMP_TO_NOAA_ID.get(ramp, RAMP_TO_NOAA_ID["Fallback"])
    params = NOAA_PARAMS_TEMPLATE.copy()
    params["begin_date"] = target_date.strftime("%Y%m%d")
    params["end_date"] = target_date.strftime("%Y%m%d")
    params["station"] = station
    try:
        resp = requests.get(NOAA_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        tide_data = resp.json().get("predictions", [])
        highs = [datetime.strptime(t["t"], "%Y-%m-%d %H:%M") for t in tide_data if t["type"] == "H"]
        return highs
    except Exception as e:
        return []

def is_within_tide_buffer(tide, proposed_start, duration, ramp):
    buffer = timedelta(hours=RAMP_TIDE_BUFFERS.get(ramp, 3))
    tide_start = tide - buffer
    tide_end = tide + buffer
    return tide_start <= proposed_start and (proposed_start + duration) <= tide_end

def find_three_valid_slots(date, ramp, duration):
    highs = fetch_high_tides(ramp, date)
    valid_slots = []
    earliest = datetime.combine(date, time(8, 0))
    latest = datetime.combine(date, time(14, 30)) - duration
    while earliest <= latest:
        for tide in highs:
            if is_within_tide_buffer(tide, earliest, duration, ramp):
                valid_slots.append(earliest.time())
                break
        if len(valid_slots) == 3:
            break
        earliest += timedelta(minutes=15)
    return valid_slots, highs

def format_date_display(dt):
    return dt.strftime("%B %d, %Y")

# ---------------------- UI ----------------------
st.title("📅 ECM Boat Scheduling Tool")

st.sidebar.header("Enter Job Info")
customer = st.sidebar.text_input("Customer Name")
job_type = st.sidebar.selectbox("Job Type", ["Launch", "Haul", "Land-Land"])
boat_type = st.sidebar.selectbox("Boat Type", ["Powerboat", "Sailboat"])
ramp = st.sidebar.selectbox("Destination Ramp", list(RAMP_TO_NOAA_ID.keys()))
target_date = st.sidebar.date_input("Preferred Date", datetime.now().date())

if boat_type == "Powerboat":
    duration = timedelta(minutes=90)
else:
    duration = timedelta(hours=3)

if st.sidebar.button("Find Available Dates"):
    slots, tides = find_three_valid_slots(target_date, ramp, duration)
    if not slots:
        st.warning("No valid time slots found for selected day.")
    else:
        st.write(f"### 🕒 High Tides on {target_date.strftime('%B %d, %Y')}")
        for t in tides:
            st.write(f"- {t.strftime('%I:%M %p')}")
        st.write("### ✅ Available Time Slots")
        for idx, s in enumerate(slots):
            st.write(f"{idx+1}. {s.strftime('%I:%M %p')}")

        selected_slot = st.selectbox("Select Time Slot to Schedule", slots)
        truck = st.selectbox("Assign Truck", TRUCKS)
        if st.button("Schedule This Job"):
            st.session_state.schedule.append({
                "customer": customer,
                "job_type": job_type,
                "boat_type": boat_type,
                "ramp": ramp,
                "date": target_date,
                "time": selected_slot,
                "truck": truck
            })
            st.success(f"✅ Scheduled {customer} on {format_date_display(target_date)} at {selected_slot.strftime('%I:%M %p')} with truck {truck}")

if st.sidebar.button("Show Scheduled Jobs"):
    if st.session_state.schedule:
        df = pd.DataFrame(st.session_state.schedule)
        df["Date"] = df["date"].apply(format_date_display)
        df["Time"] = df["time"].apply(lambda t: t.strftime("%I:%M %p"))
        st.dataframe(df)
    else:
        st.info("No jobs scheduled yet.")
