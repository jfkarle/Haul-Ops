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
    df = pd.read_csv(CUSTOMER_CSV)
    # Store a copy in session state to ensure persistence
    st.session_state['customers_df_loaded'] = df.copy()
    return df


def filter_customers(df, query):
    query = query.lower()
    return df[df["Customer Name"].str.lower().str.contains(query)]


def format_time(time_str: str) -> str:
    """Formats a time string in HH:MM format to HH:MM AM/PM."""
    time_obj = datetime.strptime(time_str, "%H:%M")
    return time_obj.strftime("%I:%M %p")


def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp) or "8445138"  # Scituate fallback

    params = NOAA_PARAMS_TEMPLATE | {
        "station": station_id,
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d"),
        "product": "predictions",
        "interval": "hilo"
    }
    try:
        resp = requests.get(NOAA_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("predictions", [])
        filtered_tides = []
        for item in data:
            try:
                tide_time_dt = datetime.strptime(item["t"], "%Y-%m-%d %H:%M")
                if time(5, 0) <= tide_time_dt.time() <= time(19, 0):
                    filtered_tides.append({"time": item['t'], "type": item['type']})
            except ValueError as e:
                print(f"Error parsing time '{item['t']}': {e}")
        return filtered_tides, None
    except Exception as e:
        return [], str(e)


def get_valid_slots_with_tides(date: datetime, ramp: str, boat_draft: float = None):
    tide_data, err = get_tide_predictions(date, ramp)
    if err:
        return [], None

    valid_slots = []
    high_tide_time = None
    tide_window = RAMP_TIDE_WINDOWS.get(ramp)

    if ramp == "Scituate Harbor (Jericho Road)" and boat_draft and boat_draft > 5:
        tide_window = (3, 3)  # Special rule for Scituate with draft > 5'

    if tide_window:
        # Use only the first high tide of the day
        first_high_tide_item = next((item for item in tide_data if item["type"] == 'H'), None)
        if first_high_tide_item:
            try:
                ht_datetime = datetime.strptime(first_high_tide_item["time"], "%Y-%m-%d %H:%M")  # Parse original string
                high_tide_time = ht_datetime.strftime("%I:%M %p")
                valid_slots = generate_slots_for_high_tide(first_high_tide_item["time"], tide_window[0], tide_window[1])
            except ValueError as e:
                print(f"Error parsing high tide time '{first_high_tide_item['time']}': {e}")
    elif ramp == "Sandwich Basin":
        # "Any tide" - provide middle of the day window centered at 10:00 AM
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3)
    else:
        # If no tide window is specified, return all slots (or a reasonable default)
        # Default to 3 hours before/after 10:00 AM if no specific rule
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3)

    return sorted(set(valid_slots)), high_tide_time


def generate_slots_for_high_tide(high_tide_ts: str, before_hours: float, after_hours: float):
    ht = datetime.strptime(high_tide_ts, "%Y-%m-%d %H:%M")
    win_start = ht - timedelta(hours=before_hours)
    win_end = ht + timedelta(hours=after_hours)
    slots = []
    t = datetime.combine(ht.date(), time(8, 0))  # Start checking from 8:00 AM
    end_day = datetime.combine(ht.date(), time(14, 30))  # Check until 2:30 PM

    while t <= end_day:
        if win_start <= t <= win_end:
            slots.append(t.time())
        t += timedelta(minutes=30)
    return slots


def format_time(time_str: str) -> str:
    """Formats a time string in HH:MM format to HH:MM AM/PM."""
    time_obj = datetime.strptime(time_str, "%H:%M")
    return time_obj.strftime("%I:%M %p")


def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        return [], f"No NOAA station ID mapped for {ramp}"

    params = NOAA_PARAMS_TEMPLATE | {
        "station": station_id,
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d"),
        "product": "predictions",
        "interval": "hilo"
    }
    try:
        resp = requests.get(NOAA_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("predictions", [])
        filtered_tides = []
        for item in data:
            try:
                tide_time_dt = datetime.strptime(item["t"], "%Y-%m-%d %H:%M")
                if time(5, 0) <= tide_time_dt.time() <= time(19, 0):
                    filtered_tides.append({"time": item['t'], "type": item['type']})  # Store data as dictionary
            except ValueError as e:
                print(f"Error parsing time '{item['t']}': {e}")  # Log the error
        return filtered_tides, None
    except Exception as e:
        return [], str(e)


def is_workday(date: datetime):
    wk = date.weekday()
    if wk == 6:  # Sunday
        return False
    if wk == 5:  # Saturday
        return date.month in (5, 9)  # May and September
    return True  # Weekdays


def eligible_trucks(boat_len: int, boat_type: str):
    if "Sailboat" in boat_type:
        return [t for t, lim in TRUCK_LIMITS.items() if boat_len <= lim]
    return [t for t, lim in TRUCK_LIMITS.items() if boat_len <= lim and t != "J17"]


def has_truck_scheduled(truck: str, date: datetime):
    for job in st.session_state["schedule"]:
        if job["truck"] == truck and job["date"].date() == date.date():  # Ensure comparing date objects
            return True
    return False


def is_truck_free(truck: str, date: datetime, start_t: time, dur_hrs: float):
    start_dt = datetime.combine(date, start_t)
    end_dt = start_dt + timedelta(hours=dur_hrs)
    for job in st.session_state["schedule"]:
        if job["truck"] != truck:
            continue
        if job["date"].date() != date.date():  # Compare date parts
            continue
        job_start = datetime.combine(job["date"].date(), job["time"])
        job_end = job_start + timedelta(hours=job["duration"])
        latest_start = max(start_dt, job_start)
        earliest_end = min(end_dt, job_end)
        overlap = (earliest_end - latest_start).total_seconds() > 0
        if overlap:
            return False
    return True


def format_date_display(date_obj):
    """Formats a date object to 'Month Day, Year' (e.g., July 5, 2025)."""
    if isinstance(date_obj, datetime):
        return date_obj.strftime("%B %d, %Y")
    elif isinstance(date_obj, date):
        return date_obj.strftime("%B %d, %Y")
    return str(date_obj)


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

    pdf.add_page()  # Only one page needed for the whole day

    page_width = pdf.w
    page_height = pdf.h

    # Calculate column widths to fit content width
    total_original_width = 60 + (4 * 100)  # 460
    available_content_width = page_width - (margin_left + margin_right)  # 612 - 108 = 504
    scale_factor = available_content_width / total_original_width

    column_widths = [
        60 * scale_factor,  # Time column
        100 * scale_factor,  # S20
        100 * scale_factor,  # S21
        100 * scale_factor,  # S23
        100 * scale_factor  # Crane J17
    ]

    start_hour = 8
    end_hour = 19
    num_rows = (end_hour - start_hour) * 4  # 44 rows (15-min intervals)

    # Calculate exact row_height to fit all rows on one page
    # `row_height = (usable_vertical_space) / (num_rows + 1)` where `+1` is for the header row
    usable_vertical_space = page_height - margin_top - margin_bottom
    row_height = usable_vertical_space / (num_rows + 1)

    headers = ["", "S20", "S21", "S23", "Crane J17"]

    # Function to draw header content (date, high tide, table headers)
    def draw_page_header(current_pdf, current_date_obj, current_jobs):
        # Top-left date heading
        current_pdf.set_font("Helvetica", size=14, style='B')
        current_pdf.text(margin_left, margin_top - 15, current_date_obj.strftime("%A, %B %d, %Y"))

        # High Tide in upper right corner (using the first job's ramp for simplicity)
        high_tide_display = ""
        if current_jobs:
            first_job_ramp = current_jobs[0].get("ramp")
            if first_job_ramp:
                tide_result = get_tide_predictions(current_date_obj, first_job_ramp)
                if len(tide_result) == 2:
                    tide_predictions, _ = tide_result
                    if tide_predictions:
                        # Find the first high tide
                        first_high_tide = next(
                            (item for item in tide_predictions if item['type'] == 'H'), None)
                        if first_high_tide:
                            try:
                                ht_datetime = datetime.strptime(
                                    first_high_tide['time'], "%Y-%m-%d %H:%M")
                                high_tide_display = f"High Tide: {ht_datetime.strftime('%I:%M %p')}"
                            except (ValueError, TypeError) as e:
                                print(f"Error processing tide
