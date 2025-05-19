import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
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
    "Green Harbor": "8443970",
    "Scituate Harbor": "8445138",
    "Cohasset Harbor": "8444762",
    "Hingham Harbor": "8444841",
    "Hull (A St)": "8445247",
    "Weymouth Harbor": "8444788"
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
    return pd.read_csv(CUSTOMER_CSV)


def filter_customers(df, query):
    query = query.lower()
    return df[df["Customer Name"].str.lower().str.contains(query)]


def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        return None, None, f"No NOAA station ID mapped for {ramp}"
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
        return None, None, str(e)


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
    preds, high_tides_data, err = get_tide_predictions(date, ramp)
    if err or not preds:
        return [], None
    high_tide_times = []
    if high_tides_data:
        # Only take the first high tide of the day
        first_high_tide = high_tides_data[0]
        ht_datetime = datetime.strptime(first_high_tide[0], "%Y-%m-%d %H:%M")
        high_tide_times.append(ht_datetime.strftime("%I:%M %p"))
        slots = generate_slots_for_high_tide(first_high_tide[0])
        return sorted(set(slots)), high_tide_times[0] if high_tide_times else None
    return [], None


def is_workday(date: datetime):
    wk = date.weekday()
    if wk == 6:
        return False
    if wk == 5:
        return date.month in (5, 9)
    return True


def eligible_trucks(boat_len: int):
    return [t for t, lim in TRUCK_LIMITS.items() if (lim == 0 or boat_len <= lim) and t != "J17"]


def has_truck_scheduled(truck: str, date: datetime):
    for job in st.session_state["schedule"]:
        if job["truck"] == truck and job["date"].date() == date.date():
            return True
    return False


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
            valid_slots, high_tide_time = get_valid_slots_with_tides(current, ramp)
            for truck in trucks:
                first_job_today = not has_truck_scheduled(truck, current)
                relevant_slots_for_truck = []
                if first_job_today:
                    for slot in valid_slots:
                        if slot.hour == 8 and slot.minute == 0:
                            relevant_slots_for_truck.append(slot)
                            break
                else:
                    relevant_slots_for_truck = valid_slots
                for slot in relevant_slots_for_truck:
                    if is_truck_free(truck, current, slot, duration):
                        found.append({
                            "date": current.date(),
                            "time": slot,
                            "ramp": ramp,
                            "truck": truck,
                            "high_tide": high_tide_time
                        })
                        if len(found) >= 3:
                            return found
            if len(found) >= 3:
                return found
        current += timedelta(days=1)
    return found


def format_date(date_obj):
    return date_obj.strftime("%B %d") + ("th" if 11 <= date_obj.day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date_obj.day % 10, 'th')) + f", {date_obj.year}"


# ====================================
# ------------- UI -------------------
# ====================================
st.title("Boat Ramp Scheduling")

customers_df = load_customer_data()

# --- Sidebar for Input ---
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
        find_slots_button = st.button("Find Available Dates")

# --- Main Page for Results ---
st.header("Available Slots")
if 'find_slots_button' in locals() and find_slots_button:
    if selected_customer:
        duration = JOB_DURATION_HRS.get(boat_type, 1.0)
        available_slots = find_three_dates(
            datetime(earliest_date.year, earliest_date.month, earliest_date.day),
            ramp_choice,
            boat_length,
            duration
        )

        if available_slots:
            # Display the first high tide prominently once
            first_high_tide = available_slots[0].get('high_tide') if available_slots else None
            if first_high_tide:
                st.subheader(f"High Tide: {first_high_tide}")

            cols = st.columns(len(available_slots))
            for i, slot in enumerate(available_slots):
                with cols[i]:
                    formatted_date = format_date(slot['date'])
                    st.info(f"Date: {formatted_date}")
                    st.markdown(f"<span style='font-size: 0.8em;'>Time: {slot['time'].strftime('%H:%M')}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Ramp:** {slot['ramp']}")
                    st.markdown(f"**Truck:** {slot['truck']}")
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

                    st.button(f"Schedule on {slot['time'].strftime('%H:%M')}", key=schedule_key, on_click=schedule_job)
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
