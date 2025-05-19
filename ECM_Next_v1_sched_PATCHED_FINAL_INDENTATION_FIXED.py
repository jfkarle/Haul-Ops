import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import requests
import json  # Ensure json is imported if you don't have it already

# ====================================
# ------------ CONSTANTS -------------\
# ====================================\
CUSTOMER_CSV = "customers.csv"  # path or raw-GitHub URL
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
    "Green Harbor": "8443970",
    "Scituate Harbor": "8445138",
    "Cohasset Harbor": "8444762",
    "Hingham Harbor": "8444841",
    "Hull (A St)": "8445247",
    "Weymouth Harbor": "8444788"
}

TRUCK_LIMITS = {"S20": 60, "S21": 50, "S23": 30, "J17": 0}
JOB_DURATION_HRS = {"Powerboat": 1.5, "Sailboat MD": 3.0, "Sailboat MT": 3.0}

# Persistent schedule held in session (one-page memory...)
if "schedule" not in st.session_state:
    st.session_state["schedule"] = []

# ====================================
# ------------ HELPERS ---------------
# ====================================
@st.cache_data
def load_customer_data():
    return pd.read_csv(CUSTOMER_CSV)

def filter_customers(df, query):
    query = query.lower()
    return df[df["Customer Name"].str.lower().str.contains(query)]

def get_tide_predictions(date: datetime, station_id: str):
    params = NOAA_PARAMS_TEMPLATE.copy()
    params["station"] = station_id
    params["begin_date"] = date.strftime("%Y%m%d")
    params["end_date"] = date.strftime("%Y%m%d")
    response = requests.get(NOAA_API_URL, params=params)
    if response.status_code == 200:
        try:
            data = response.json()
            st.write("Raw NOAA API Response:", data)  # Add this line for debugging
            if "predictions" in data:
                return data["predictions"], None
            else:
                return [], "No predictions found in NOAA API response"
        except json.JSONDecodeError:
            return [], "Error decoding JSON from NOAA API"
    else:
        return [], f"Error from NOAA API: {response.status_code}"

def generate_slots_for_high_tide(high_tide_time_str: str):
    high_tide_time = datetime.strptime(high_tide_time_str, "%Y-%m-%d %H:%M")
    slot_start = high_tide_time - timedelta(hours=2)
    slots = []
    for i in range(5):  # 4-hour window
        slots.append(slot_start.time())
        slot_start += timedelta(hours=1)
    return slots

def find_next_workday(start_date: datetime):
    next_day = start_date + timedelta(days=1)
    while not is_workday(next_day):
        next_day += timedelta(days=1)
    return next_day

def find_previous_workday(start_date: datetime):
    prev_day = start_date - timedelta(days=1)
    while not is_workday(prev_day):
        prev_day -= timedelta(days=1)
    return prev_day

def is_workday(date: datetime):
    wk = date.weekday()
    if wk == 6:
        return False  # Sunday
    if wk == 5:  # Saturday
        return date.month in (5, 9)
    return True

def eligible_trucks(boat_len: int):
    return [t for t, lim in TRUCK_LIMITS.items() if (lim == 0 or boat_len <= lim) and t != "J17"]

def is_truck_free(truck: str, date: datetime, start_t: time, dur_hrs: float):
    start_dt = datetime.combine(date, start_t)
    end_dt = start_dt + timedelta(hours=dur_hrs)
    for job in st.session_state["schedule"]:
        if job["truck"] != truck:
            continue
        if job["date"].date() != date.date():
            continue
        job_start = datetime.combine(job["date"], job["time"])
        job_end = job_start + timedelta(hours=job["duration"])
        latest_start = max(start_dt, job_start)
        earliest_end = min(end_dt, job_end)
        overlap = (earliest_end - latest_start).total_seconds() > 0
        if overlap:
            return False
    return True

def find_three_dates(start_date: datetime, ramp: str, boat_len: int, duration: float):
    found = []
    current = start_date
    trucks = eligible_trucks(boat_len)
    if not trucks:
        return []

    while len(found) < 3:
        if is_workday(current):
            valid_slots, high_tide_times, all_high_tides_data = get_valid_slots_with_tides(current, ramp)
            relevant_high_tides = [ht.strftime("%I:%M %p") for ht, _ in all_high_tides_data if 6 <= ht.hour < 18]
            for slot_index, slot in enumerate(valid_slots):
                for truck in trucks:
                    if is_truck_free(truck, current, slot, duration):
                        found.append({
                            "date": current.date(),
                            "time": slot,
                            "ramp": ramp,
                            "truck": truck,
                            "high_tides": relevant_high_tides  # Store relevant high tides
                        })
                        if len(found) >= 3:
                            return found
                    break  # Move to the next slot
                if len(found) >= 3:
                    return found
            current += timedelta(days=1)
    return found

def format_date_display(date_obj):
    return date_obj.strftime("%b %d, %Y")

def format_date_schedule(date_obj):
    return date_obj.strftime("%Y-%m-%d")

# ====================================
# ------------- UI -------------------
# ====================================
st.title("Boat Ramp Scheduling")

customers_df = load_customer_data()

with st.sidebar:
    st.header("New Job")
    customer_query = st.text_input("Find Customer:", "")
    filtered_customers = filter_customers(customers_df, customer_query)
    if not filtered_customers.empty:
        selected_customer = st.selectbox("Select Customer", filtered_customers["Customer Name"])
    else:
        selected_customer = None
        st.info("No matching customers found.")

    if selected_customer:
        customer_row = customers_df[customers_df["Customer Name"] == selected_customer].iloc[0]
        boat_type = customer_row["Boat Type"]
        boat_length = customer_row["Boat Length"]
        st.write(f"Selected Boat Type: **{boat_type}**")
        st.write(f"Selected Boat Length: **{boat_length} feet**")
        ramp_choice = st.selectbox("Launch Ramp", list(RAMP_TO_NOAA_ID.keys()))
        earliest_date = st.date_input("Earliest Date", datetime.now().date())

        if st.button("Find Available Dates"):
            if selected_customer:
                duration = JOB_DURATION_HRS.get(boat_type, 1.0)
                start_search_date = datetime(earliest_date.year, earliest_date.month, earliest_date.day)
                available_slots = find_three_dates(
                    start_search_date,
                    ramp_choice,
                    boat_length,
                    duration
                )
                if available_slots:
                    st.subheader("Available Slots")
                    for slot in available_slots:
                        formatted_date = format_date_display(slot['date'])
                        st.write(f"**Date:** {formatted_date}")
                        st.write(f"**Time:** {slot['time'].strftime('%H:%M')}")
                        if slot['high_tides']:
                            high_tides_str = ", ".join(slot['high_tides'])
                            st.write(f"**High Tides (6AM-6PM approx.):** {high_tides_str}")
                        else:
                            st.write("**High Tides (6AM-6PM approx.):** N/A")
                        st.write(f"**Ramp:** {slot['ramp']}, **Truck:** {slot['truck']}")
                        schedule_key = f"schedule_{slot['date']}_{slot['time']}_{slot['truck']}"

                        def schedule_job():
                            new_schedule_item = {
                                "truck": slot["truck"],
                                "date": datetime.combine(slot["date"], slot["time"]),
                                "time": slot["time"],
                                "duration": duration,
                                "customer": selected_customer
                            }
                            st.session_state["schedule"].append(new_schedule_item)
                            st.success(f"Scheduled {selected_customer} with {slot['truck']} on {formatted_date} at {slot['time'].strftime('%H:%M')}.")

                        if st.button(f"Schedule on {slot['time'].strftime('%H:%M')}", key=schedule_key, on_click=schedule_job):
                            pass
                        st.markdown("---")
                else:
                    st.info("No suitable slots found for the selected criteria.")
            else:
                st.warning("Please select a customer first.")

st.header("Current Schedule")
if st.session_state["schedule"]:
    schedule_df = pd.DataFrame(st.session_state["schedule"])
    schedule_df["Date"] = schedule_df["date"].dt.date
    schedule_df["Time"] = schedule_df["time"].astype(str)
    st.dataframe(schedule_df[["customer", "Date", "Time", "truck", "duration"]])
else:
    st.info("The schedule is currently empty.")

if 'ramp_choice' in st.session_state:
    st.session_state['last_ramp_choice'] = st.session_state['ramp_choice']
elif list(RAMP_TO_NOAA_ID.keys()):
    st.session_state['last_ramp_choice'] = list(RAMP_TO_NOAA_ID.keys())[0]


def get_valid_slots_with_tides(date: datetime, ramp: str):
    preds, err = get_tide_predictions(date, ramp)
    if err or not preds:
        return [], []

    st.write("First few 'preds':", preds[:5])  # Enhanced debug: Show up to 5 elements

    high_tides_data = []
    for i, p in enumerate(preds):
        st.write(f"Processing preds[{i}]: {p}, Type: {type(p)}, Value: {p}")  # Detailed debug

        try:
            if isinstance(p, dict):
                # Handle dictionary case
                if 't' in p and 'type' in p and p.get('type') == 'H':
                    high_tides_data.append((datetime.strptime(p['t'], "%Y-%m-%d %H:%M"), p['type']))
                else:
                    st.warning(f"Unexpected dict format in preds[{i}]: {p}")
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                # Handle tuple/list case
                if p[1] == 'H':
                    high_tides_data.append((datetime.strptime(p[0], "%Y-%m-%d %H:%M"), p[1]))
                else:
                    st.warning(f"Unexpected tuple/list format in preds[{i}]: {p}")
            else:
                st.error(f"Unexpected data type in preds[{i}]: {p}, Type: {type(p)}")
        except (ValueError, KeyError, IndexError) as e:
            st.error(f"Error processing preds[{i}]: {p}, Error: {e}")

    slots = []
    high_tide_times = []
    for ht_datetime, _ in high_tides_data:
        high_tide_times.append(ht_datetime.strftime("%I:%M %p"))
        slots.extend(generate_slots_for_high_tide(ht_datetime.strftime("%Y-%m-%d %H:%M")))

    return sorted(set(slots)), high_tide_times
