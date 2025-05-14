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
    win_start, win_end = ht-timedelta(hours=3), ht+timedelta(hours=3)
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
        # Overlap check
        job_start = datetime.combine(job["date"], job["time"])
        job_end = job_start + timedelta(hours=job["duration"])
        latest_start = max(start_dt, job_start)
        earliest_end = min(end_dt, job_end)
        overlap = (earliest_end-latest_start).total_seconds() > 0
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

    while len(found) < 3 and (current-start_date).days < 60:  # 2-month search window
        if not is_workday(current):
            current += timedelta(days=1)
            continue
        slots = get_valid_slots(current, ramp)
        if not slots:
            current += timedelta(days=1)
            continue
        for slot in slots:
            for truck in trucks:
                if is_truck_free(truck, current, slot, duration):
                    found.append({"date": current, "time": slot, "truck": truck})
                    break
            if len(found) >= 3:
                break
        current += timedelta(days=1)
    return found

# ====================================
# -------- STREAMLIT  UI  ------------
# ====================================
st.title("ECM Boat Hauling Scheduler")

cust_query = st.text_input("Search by Last Name (partial accepted):")
customer_df = load_customer_data()
match_df = filter_customers(customer_df, cust_query) if cust_query else pd.DataFrame()
sel_customer = None
if not match_df.empty:
    match_df = match_df.reset_index(drop=True)
    selected_idx = st.radio("Select a customer", match_df.index,
                            format_func=lambda i: f"{match_df.loc[i, 'Customer Name']} — "
                                                   f"{match_df.loc[i, 'Boat Type']}, "
                                                   f"{match_df.loc[i, 'Length']} ft @ "
                                                   f"{match_df.loc[i, 'Ramp']}")
    sel_customer = match_df.loc[selected_idx]

job_type = st.selectbox("Job Type", ["Launch", "Haul", "Transport"])
req_date = st.date_input("Preferred Date", min_value=datetime.today())

if st.button("FIND DATES") and sel_customer is not None:
    ramp = sel_customer["Ramp"]
    boat_len = sel_customer["Length"]
    duration = JOB_DURATION_HRS[sel_customer["Boat Type"]]
    proposals = find_three_dates(req_date, ramp, boat_len, duration)
    st.session_state["proposals"] = proposals
    st.session_state["customer_selection"] = sel_customer

if "proposals" in st.session_state and st.session_state["proposals"]:
    proposals = st.session_state["proposals"]
    sel_customer = st.session_state["customer_selection"]
    st.success("Select from the earliest viable dates:")
    options = {f"{p['date'].strftime('%b %d')} at {p['time'].strftime('%I:%M %p')} (Truck {p['truck']})": i for i, p in enumerate(proposals)}
    choice = st.radio("Proposals", list(options.keys()), key="proposal_choice")
    chosen_idx = options[choice]
    chosen = proposals[chosen_idx]

    if st.button("BOOK THIS JOB"):
        st.session_state["schedule"].append({
            "customer": sel_customer["Customer Name"],
            "truck": chosen["truck"],
            "date": chosen["date"],
            "time": chosen["time"],
            "duration": JOB_DURATION_HRS[sel_customer["Boat Type"]]
        })
                d = chosen["date"].strftime("%B %d, %Y")
        t = chosen["time"].strftime("%I:%M %p")
        truck = chosen["truck"]
        st.success(f"Booked for {d} at {t} on Truck {truck}")} at {chosen['time'].strftime('%I:%M %p')} on Truck {chosen['truck']}")

# Button to view full schedule
with st.sidebar:
    if st.button("Show Scheduled Jobs Table"):
        sched_df = pd.DataFrame(st.session_state["schedule"])
        if sched_df.empty:
            st.sidebar.info("No jobs scheduled yet.")
        else:
            sched_df = sched_df.sort_values(by=["date", "time"])  # order
            st.sidebar.dataframe(sched_df)
