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
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import requests

# ====================================
# ------------ CONSTANTS -------------
# ====================================
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

# Persistent schedule held in session (one-page memory)
if "schedule" not in st.session_state:
    st.session_state["schedule"] = []  # list of dicts {truck,date,time,duration,customer}


# ====================================
# ------------ HELPERS ---------------
# ====================================
@st.cache_data
def load_customer_data():
    return pd.read_csv(CUSTOMER_CSV)


def filter_customers(df, query):
    query = query.lower()
    return df[df["Customer Name"].str.lower().str.contains(query)]


def get_tide_predictions(date: datetime, ramp: str):
    """Return list of tuples (timestamp-str, type 'H'/'L') or error."""
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        return None, f"No NOAA station ID mapped for {ramp}"

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


def generate_slots_for_high_tide(high_tide_ts: str):
    ht = datetime.strptime(high_tide_ts, "%Y-%m-%d %H:%M")
    win_start, win_end = ht - timedelta(hours=3), ht + timedelta(hours=3)
    slots = []
    t = datetime.combine(ht.date(), time(8, 0))
    end_day = datetime.combine(ht.date(), time(14, 30))
    while t <= end_day:
        if win_start <= t <= win_end:
            slots.append(t.time())
        t += timedelta(minutes=30)
    return slots


def get_valid_slots_with_tides(date: datetime, ramp: str):
    preds, err = get_tide_predictions(date, ramp)
    if err or not preds:
        return [], []
    high_tides_data = [(datetime.strptime(p['t'], "%Y-%m-%d %H:%M"), p['type']) for p in preds if p['type'] == 'H']
    slots = []
    high_tide_times = []
    for ht_datetime, _ in high_tides_data:
        high_tide_times.append(ht_datetime.strftime("%I:%M %p"))
        ht_ts = ht_datetime.strftime("%Y-%m-%d %H:%M")
        slots.extend(generate_slots_for_high_tide(ht_ts))
    return sorted(set(slots)), high_tide_times, high_tides_data


def is_workday(date: datetime):
    wk = date.weekday()
    if wk == 6:
        return False  # Sunday
    if wk == 5:  # Saturday
        return date.month in (5, 9)
    return True


def eligible_trucks(boat_len: int):
    return [t for t, lim in TRUCK_LIMITS.items() if (lim == 0 or boat_len <= lim) and t != "J17"]


# Very simple conflict check (same truck, same date, overlapping) -------------
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


# Main search for three dates -----------------------------------------------
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
                            "high_tides": relevant_high_tides # Store relevant high tides
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
    schedule_df["Date"] = schedule_df["date"].dt.date.apply(format_date_display)
    schedule_df["Time"] = schedule_df["time"].astype(str)
    schedule_df["High Tide"] = schedule_df["date"].apply(lambda d: get_tide_predictions(d, st.session_state.get('last_ramp_choice', list(RAMP_TO_NOAA_ID.keys())[0]))[0])\
        .apply(lambda preds: ", ".join([datetime.strptime(p['t'], "%Y-%m-%d %H:%M").strftime("%I:%M %p") for p in preds if p['type'] == 'H' and 6 <= datetime.strptime(p['t'], "%Y-%m-%d %H:%M").hour < 18]) if preds else "N/A")

    st.dataframe(schedule_df[["customer", "Date", "Time", "truck", "duration", "High Tide"]])
else:
    st.info("The schedule is currently empty.")

if 'ramp_choice' in st.session_state:
    st.session_state['last_ramp_choice'] = st.session_state['ramp_choice']
elif list(RAMP_TO_NOAA_ID.keys()):
    st.session_state['last_ramp_choice'] = list(RAMP_TO_NOAA_ID.keys())[0]
