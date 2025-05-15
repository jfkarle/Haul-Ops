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

# try:
#     from streamlit_calendar import calendar
# except Exception as e:
#     st.error(f"Calendar import failed: {e}")


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


def get_valid_slots(date: datetime, ramp: str):
    preds, err = get_tide_predictions(date, ramp)
    if err or not preds:
        return []
    high_tides = [t for t, typ in preds if typ == "H"]
    slots = []
    for ht in high_tides:
        slots.extend(generate_slots_for_high_tide(ht))
    return sorted(set(slots))


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
            slots = get_valid_slots(current, ramp)
            for slot in slots:
                for truck in trucks:
                    if is_truck_free(truck, current, slot, duration):
                        found.append({
                            "date": current.date(),
                            "time": slot,
                            "ramp": ramp,
                            "truck": truck
                        })
                        if len(found) >= 3:
                            return found
                        break  # Move to the next slot
                if len(found) >= 3:
                    return found
                current += timedelta(days=1)
    return found


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
        boat_type = st.selectbox("Boat Type", list(JOB_DURATION_HRS.keys()))
        boat_length = st.number_input("Boat Length (feet)", min_value=0, max_value=100, value=20)
        ramp_choice = st.selectbox("Launch Ramp", list(RAMP_TO_NOAA_ID.keys()))
        earliest_date = st.date_input("Earliest Date", datetime.now().date())

        if st.button("Find Available Dates"):
            if selected_customer:
                duration = JOB_DURATION_HRS.get(boat_type, 1.0)
                available_slots = find_three_dates(
                    datetime(earliest_date.year, earliest_date.month, earliest_date.day),
                    ramp_choice,
                    boat_length,
                    duration
                )
                if available_slots:
                    st.subheader("Available Slots")
                    for slot in available_slots:
                        st.write(
                            f"- Date: {slot['date'].strftime('%Y-%m-%d')}, "
                            f"Time: {slot['time'].strftime('%H:%M')}, "
                            f"Ramp: {slot['ramp']}, "
                            f"Truck: {slot['truck']}"
                        )
                        schedule_key = f"schedule_{slot['date']}_{slot['time']}_{slot['truck']}"

                        def schedule_job():  # Define a function to schedule the job
                            new_schedule_item = {
                                "truck": slot["truck"],
                                "date": datetime.combine(slot["date"], slot["time"]),
                                "time": slot["time"],
                                "duration": duration,
                                "customer": selected_customer
                            }
                            st.session_state["schedule"].append(new_schedule_item)
                            st.success(f"Scheduled {selected_customer} with {slot['truck']} on {slot['date'].strftime('%Y-%m-%d')} at {slot['time'].strftime('%H:%M')}.")
                            st.rerun()  # Force rerun to update schedule display

                        if st.button(f"Schedule on {slot['date'].strftime('%Y-%m-%d')} at {slot['time'].strftime('%H:%M')}", key=schedule_key, on_click=schedule_job):  # Use on_click
                            pass # Nothing needed here, the function handles the logic
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

# st.subheader("Calendar View")
# events = []
# for item in st.session_state["schedule"]:
#     events.append({
#         'title': f"{item['customer']} ({item['truck']})",
#         'start': datetime.combine(item['date'].date(), item['time']).isoformat(),
#         'end': (datetime.combine(item['date'].date(), item['time']) + timedelta(hours=item['duration'])).isoformat(),
#     })
# if "calendar" in locals():
#     calendar(events=events)
