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
    "Plymouth Harbor": (3, 3),  # 3 hrs before and after [cite: 1]
    "Duxbury Harbor": (1, 1),  # 1 hr before or after [cite: 1]
    "Green Harbor (Taylors)": (3, 3),  # 3 hrs before and after [cite: 1]
    "Safe Harbor (Green Harbor)": (1, 1),  # 1 hr before and after [cite: 1]
    "Ferry Street (Marshfield Yacht Club)": (3, 3),  # 3 hrs before and after [cite: 1]
    "South River Yacht Yard": (2, 2),  # 2 hrs before or after [cite: 1]
    "Roht (A to Z/ Mary's)": (1, 1),  # 1 hr before or after [cite: 1]
    "Scituate Harbor (Jericho Road)": None,  # Any tide, special rule for 5' draft [cite: 1]
    "Harbor Cohasset (Parker Ave)": (3, 3),  # 3 hrs before or after [cite: 1]
    "Hull (A St, Sunset, Steamboat)": (3, 1.5),  # 3 hrs before, 1.5 hrs after for 6'+ draft [cite: 1]
    "Hull (X Y Z St) (Goodwiny st)": (1, 1),  # 1 hr before or after [cite: 1]
    "Hingham Harbor": (3, 3),  # 3 hrs before and after [cite: 1]
    "Weymouth Harbor (Wessagusset)": (3, 3),  # 3 hrs before and after [cite: 1]
    "Sandwich Basin": None # Any tide [cite: 1]
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
    return df[df["Customer Name"].str.lower().contains(query)] # Removed extra '()'


def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
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

    if ramp == "Scituate Harbor (Jericho Road)" and boat_draft and boat_draft > 5:  # [cite: 1]
        tide_window = (3, 3)  # Special rule for Scituate with draft > 5' [cite: 1]

    if tide_window:
        #  Use only the first high tide of the day
        first_high_tide = high_tides_data[0] if high_tides_data else None
        if first_high_tide:
            ht_datetime = datetime.strptime(first_high_tide[0], "%Y-%m-%d %H:%M")
            high_tide_time = ht_datetime.strftime("%I:%M %p")
            valid_slots = generate_slots_for_high_tide(first_high_tide[0], tide_window[0], tide_window[1])
    elif ramp == "Sandwich Basin":
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3) # "Any tide" - provide middle of the day window [cite: 1]
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


def format_date(date_obj):
    return date_obj.strftime("%B %d") + ("th" if 11 <= date_obj.day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date_obj.day % 10, 'th')) + f", {date_obj.year}"


def find_three_dates(start_date: datetime, ramp: str, boat_len: int, duration: float, boat_draft: float = None, search_days_limit: int = 7):
    found = []
    current = start_date
    trucks = eligible_trucks(boat_len)
    if not trucks:
        return []

    days_searched = 0
    while len(found) < 3 and days_searched < search_days_limit:
        if is_workday(current):
            valid_slots, high_tide_time = get_valid_slots_with_tides(current, ramp, boat_draft)

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

            # Sort the 'found' list by date and then time to prioritize earlier slots
            found.sort(key=lambda x: (x["date"], x["time"]))

            # If we've found 3, we can stop searching
            if len(found) >= 3:
                break

        current += timedelta(days=1)
        days_searched += 1

    return found[:3]  # Return at most the first 3 slots (or fewer if we didn't find 3)


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
        if ramp_choice == "Scituate Harbor (Jericho Road)":
            boat_draft = st.number_input("Boat Draft (feet)", min_value=0.0, value=0.0)
        else:
            boat_draft = None
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
            duration,
            boat_draft
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
                    st.markdown(f"<span style='font-size: 0.8em;'>**Truck:** {slot['truck']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='font-size: 0.8em;'>Time: {slot['time'].strftime('%H:%M')}</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='font-size: 0.8em;'>**Ramp:** {slot['ramp']}</span>", unsafe_allow_html=True)
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
