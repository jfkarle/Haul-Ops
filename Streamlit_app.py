import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time, date
import requests
from fpdf import FPDF  # Make sure FPDF is imported
import os  # Make sure os is imported

st.set_page_config(
    page_title="Boat Ramp Scheduling",
    layout="wide"
)

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
    "Sandwich Basin": None  # Any tide
}
RAMP_TIDE_WINDOWS = {
    "Plymouth Harbor": (3, 3),  # 3 hrs before and after
    "Duxbury Harbor": (1, 1),  # 1 hr before or after
    "Green Harbor (Taylors)": (3, 3),  # 3 hrs before and after
    "Safe Harbor (Green Harbor)": (1, 1),  # 1 hr before and after
    "Ferry Street (Marshfield Yacht Club)": (3, 3),  # 3 hrs before and after
    "South River Yacht Yard": (2, 2),  # 2 hrs before or after
    "Roht (A to Z/ Mary's)": (1, 1),  # 1 hr before or after
    "Scituate Harbor (Jericho Road)": None,  # Any tide, special rule for 5' draft
    "Harbor Cohasset (Parker Ave)": (3, 3),  # 3 hrs before and after
    "Hull (A St, Sunset, Steamboat)": (3, 1.5),  # 3 hrs before, 1.5 hrs after for 6'+ draft
    "Hull (X Y Z St) (Goodwiny st)": (1, 1),  # 1 hr before or after
    "Hingham Harbor": (3, 3),  # 3 hrs before and after
    "Weymouth Harbor (Wessagusset)": (3, 3),  # 3 hrs before and after
    "Sandwich Basin": None  # Any tide
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
    try:
        df = pd.read_csv(CUSTOMER_CSV)
        st.session_state['customers_df_loaded'] = df.copy()
        return df
    except FileNotFoundError:
        st.error(f"Error: Could not find file '{CUSTOMER_CSV}'. Please ensure it is in the correct location.")
        return pd.DataFrame()
    except pd.errors.EmptyDataError:
        st.error(f"Error: File '{CUSTOMER_CSV}' is empty.")
        return pd.DataFrame()
    except pd.errors.ParserError as e:
        st.error(f"Error parsing file '{CUSTOMER_CSV}': {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An unexpected error occurred while loading data: {e}")
        return pd.DataFrame()

def filter_customers(df, query):
    query = query.lower()
    return df[df["Customer Name"].str.lower().str.contains(query)]

def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        return [], [], f"No NOAA station ID mapped for {ramp}"

    params = NOAA_PARAMS_TEMPLATE | {
        "station": station_id,
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d")
    }
    try:
        resp = requests.get(NOAA_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("predictions", [])
        all_tides = [(d["t"], d["type"]) for d in data]
        high_tides = [(d["t"], d["v"]) for d in data if d["type"] == "H"]
        return all_tides, high_tides, None
    except Exception as e:
        return [], [], str(e)

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

    if ramp == "Scituate Harbor (Jericho Road)" and boat_draft and boat_draft > 5:
        tide_window = (3, 3)  # Special rule for Scituate with draft > 5'

    if tide_window:
        # Use only the first high tide of the day
        first_high_tide = high_tides_data[0] if high_tides_data else None
        if first_high_tide:
            ht_datetime = datetime.strptime(first_high_tide[0], "%Y-%m-%d %H:%M")
            high_tide_time = ht_datetime.strftime("%I:%M %p")
            valid_slots = generate_slots_for_high_tide(first_high_tide[0], tide_window[0], tide_window[1])
    elif ramp == "Sandwich Basin":
        # "Any tide" - provide middle of the day window centered at 10:00 AM
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3)
    else:
        # If no tide window is specified, return all slots (or a reasonable default)
        # Default to 3 hours before/after 10:00 AM if no specific rule
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3)

    return sorted(set(valid_slots)), high_tide_time

def is_workday(date: datetime):
    wk = date.weekday()
    if wk == 6: # Sunday
        return False
    if wk == 5: # Saturday
        return date.month in (5, 9) # May and September
    return True # Weekdays

def eligible_trucks(boat_len: int, boat_type: str):
    if "Sailboat" in boat_type:
        return [t for t, lim in TRUCK_LIMITS.items() if boat_len <= lim]
    return [t for t, lim in TRUCK_LIMITS.items() if boat_len <= lim and t != "J17"]

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
        if customer and job["customer"] == customer and job["date"].date() == date.date() and \
           start_dt < datetime.combine(job["date"].date(), job["time"]) + timedelta(hours=job["duration"]) and \
           end_dt > datetime.combine(job["date"].date(), job["time"]):
            return False
    return True

def format_date_display(date_obj):
    """Formats a date object to 'Month Day, Year' (e.g., July 5, 2025)."""
    if isinstance(date_obj, datetime):
        return date_obj.strftime("%B %d, %Y")
    elif isinstance(date_obj, date):
        return date_obj.strftime("%B %d, %Y")
    return str(date_obj)

def find_three_dates(start_date: datetime, ramp: str, boat_len: int, boat_type_arg: str, duration: float, boat_draft: float = None, search_days_limit: int = 7):
    found = []

    trucks = eligible_trucks(boat_len, boat_type_arg)
    if not trucks:
        return []

    j17_duration = 0
    if "Sailboat MD" in boat_type_arg:
        j17_duration = 1.0
    elif "Sailboat MT" in boat_type_arg:
        j17_duration = 1.5

    # New Logic: Prioritize dates with existing J17 schedule at the ramp
    j17_scheduled_dates_at_ramp = set()
    for job in st.session_state["schedule"]:
        if job["truck"] == "J17" and job["ramp"] == ramp:
            j17_scheduled_dates_at_ramp.add(job["date"])

    prioritized_dates = []
    other_dates_to_check = []

    # Check dates around the requested earliest_date_input (7 days before/after)
    # The actual date in current_date for the `find_three_dates` function comes from `earliest_date_input` in the UI.
    # So, the search window should be relative to `start_date`.
    for i in range(-7, 8): # 7 days before to 7 days after
        check_date = start_date + timedelta(days=i)
        if is_workday(check_date):
            if check_date.date() in j17_scheduled_dates_at_ramp:
                # Add to prioritized dates, ensuring uniqueness and order
                if check_date not in prioritized_dates:
                    prioritized_dates.append(check_date)
            else:
                if check_date not in other_dates_to_check: # Avoid duplicates if already in prioritized
                    other_dates_to_check.append(check_date)

    # Sort prioritized dates to check them in chronological order
    prioritized_dates.sort()

    # Combine prioritized dates with other dates, ensuring we don't exceed search_days_limit
    # and removing duplicates that might have been added to prioritized_dates.
    full_date_search_order = prioritized_dates + [d for d in other_dates_to_check if d not in prioritized_dates]

    days_searched = 0
    for current_date in full_date_search_order:
        if len(found) >= 3 or days_searched >= search_days_limit:
            break # Stop if we found enough slots or exceeded search limit

        if is_workday(current_date):
            valid_slots, high_tide_time = get_valid_slots_with_tides(current_date, ramp, boat_draft)
            if valid_slots:
                for truck in trucks:
                    for slot in valid_slots:
                        # Check if both hauling truck and (if needed) J17 are free
                        hauling_free = is_truck_free(truck, current_date, slot, duration)
                        j17_free = True
                        if j17_duration > 0:
                            j17_free = is_truck_free("J17", current_date, slot, j17_duration)
                        if hauling_free and j17_free:
                            # Store hauling truck job
                            found.append({
                                "date": current_date.date(),
                                "time": slot,
                                "ramp": ramp,
                                "truck": truck,
                                "high_tide": high_tide_time,
                                "boat_type": boat_type_arg,
                                "j17_required": j17_duration > 0,
                                "j17_duration": j17_duration
                            })
                            break # Found a slot for this truck on this day, move to next date/truck
                    if len(found) >= 3:
                        break
        days_searched += 1 # Increment days searched for each distinct date checked

    return found[:3] # Return up to 3 found slots


def generate_daily_schedule_pdf_bold_end_line_streamlit(date_obj, jobs, customers_df):
    pdf = FPDF(orientation='P', unit='pt', format='Letter')

    # Margins (3/4 inch = 54 pt)
    margin_left = 54
    margin_top = 54
    margin_right = 54
    margin_bottom = 54

    pdf.set_left_margin(margin_left)
    pdf.set_top_margin(margin_top)
    pdf.set_right_margin(margin_right)
    # Set auto_page_break to False as the entire day must fit on one page
    pdf.set_auto_page_break(auto=False)

    pdf.add_page() # Only one page needed for the whole day

    page_width = pdf.w
    page_height = pdf.h

    # Calculate column widths to fit content width
    total_original_width = 60 + (4 * 100) # 460
    available_content_width = page_width - (margin_left + margin_right) # 612 - 108 = 504
