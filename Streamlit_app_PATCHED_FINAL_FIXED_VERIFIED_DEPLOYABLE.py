import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time, date
import requests
from fpdf import FPDF # Make sure FPDF is imported
import os # Make sure os is imported

st.set_page_config(
    page_title="Boat Ramp Scheduling",
    layout="wide"
)

st.title("Is it working?")  # Add this line at the very top


# ====================================
# ------------ CONSTANTS -------------
# ====================================
CUSTOMER_CSV = "customers_with_coords.csv"
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
    "Plymouth Harbor": (3, 3),  # 3 hrs before and after
    "Duxbury Harbor": (1, 1),  # 1 hr before or after
    "Green Harbor (Taylors)": (3, 3),  # 3 hrs before and after
    "Safe Harbor (Green Harbor)": (1, 1),  # 1 hr before or after
    "Ferry Street (Marshfield Yacht Club)": (3, 3),  # 3 hrs before and after
    "South River Yacht Yard": (2, 2),  # 2 hrs before or after
    "Roht (A to Z/ Mary's)": (1, 1),  # 1 hr before or after
    "Scituate Harbor (Jericho Road)": None,  # Any tide, special rule for 5' draft
    "Harbor Cohasset (Parker Ave)": (3, 3),  # 3 hrs before or after
    "Hull (A St, Sunset, Steamboat)": (3, 1.5),  # 3 hrs before, 1.5 hrs after for 6'+ draft
    "Hull (X Y Z St) (Goodwiny st)": (1, 1),  # 1 hr before or after
    "Hingham Harbor": (3, 3),  # 3 hrs before and after
    "Weymouth Harbor (Wessagusset)": (3, 3),  # 3 hrs before and after
    "Sandwich Basin": None # Any tide
}
TRUCK_LIMITS = {"S20": 60, "S21": 50, "S23": 30, "J17": 0}
JOB_DURATION_HRS = {"Powerboat": 1.5, "Sailboat MD": 3.0, "Sailboat MT": 3.0}
RAMPS = list(RAMP_TO_NOAA_ID.keys())

if "schedule" not in st.session_state:
    st.session_state["schedule"] = []
if "suggested_slots" not in st.session_state:
    st.session_state["suggested_slots"] = []
if "slot_index" not in st.session_state:
    st.session_state["slot_index"] = 0

File "/mount/src/haul-ops/Streamlit_app_PATCHED_FINAL_FIXED_VERIFIED_DEPLOYABLE.py", line 94
       if 'customers_df_loaded' not in st.session_state:
                                                        ^
IndentationError: unindent does not match any outer indentation level
def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        station_id = "8445138"  # Fallback to Scituate
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
    t = datetime.combine(ht.date(), time(8, 0))
    end_day = datetime.combine(ht.date(), time(14, 30))

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
        tide_window = (3, 3)

    if tide_window:
        first_high_tide = high_tides_data[0] if high_tides_data else None
        if first_high_tide:
            ht_datetime = datetime.strptime(first_high_tide[0], "%Y-%m-%d %H:%M")
            high_tide_time = ht_datetime.strftime("%I:%M %p")
            valid_slots = generate_slots_for_high_tide(first_high_tide[0], tide_window[0], tide_window[1])
    elif ramp == "Sandwich Basin":
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3)
    else:
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3)

    return sorted(set(valid_slots)), high_tide_time

def is_workday(date: datetime):
    wk = date.weekday()
    if wk == 6:
        return False
    if wk == 5:
        return date.month in (5, 9)
    return True

def get_j17_available_until(boat_type: str):
    if boat_type == "Sailboat MD":
        return timedelta(hours=1)
    elif boat_type == "Sailboat MT":
        return timedelta(hours=1.5)
    return timedelta(hours=0)

def eligible_trucks(boat_len: int, boat_type: str):
    trucks = []
    for t, lim in TRUCK_LIMITS.items():
        if boat_len <= lim:
            trucks.append(t)
    if "Sailboat" in boat_type:
        trucks.append("J17")
    return trucks

def has_truck_scheduled(truck: str, date: datetime):
    for job in st.session_state["schedule"]:
        if job["truck"] == truck and job["date"].date() == date.date():
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
        elif truck == "J17" and job["date"].date() == date.date():
            job_boat_type = ""
            try:
                job_boat_type = customers_df[customers_df["Customer Name"] == job["customer"]]["Boat Type"].iloc[0]
            except (KeyError, IndexError):
                job_boat_type = "Unknown"
            j17_available_until_job = datetime.combine(job["date"].date(), job["time"]) + get_j17_available_until(job_boat_type)
            j17_available_until_new = start_dt + get_j17_available_until(boat_type)

            overlap_new_starts_during_old = start_dt < j17_available_until_job and start_dt >= datetime.combine(job["date"].date(), job["time"])
            overlap_old_starts_during_new = datetime.combine(job["date"].date(), job["time"]) < j17_available_until_new and datetime.combine(job["date"].date(), job["time"]) >= start_dt
            overlap_contains_old = start_dt <= datetime.combine(job["date"].date(), job["time"]) and j17_available_until_new >= j17_available_until_job
            overlap_contained_by_old = start_dt >= datetime.combine(job["date"].date(), job["time"]) and j17_available_until_new <= j17_available_until_job

            if overlap_new_starts_during_old or overlap_old_starts_during_new or overlap_contains_old or overlap_contained_by_old:
                return False
    return True

def format_date_display(date_obj):
    if isinstance(date_obj, datetime):
        return date_obj.strftime("%B %d, %Y")
    elif isinstance(date_obj, date):
        return date_obj.strftime("%B %d, %Y")
    return str(date_obj)

def find_three_dates(start_date: datetime, ramp: str, boat_len: int, boat_type_arg: str, duration: float, boat_draft: float = None, search_days_limit: int = 14): # Increased search limit
    found = []
    current_date = start_date
    trucks = eligible_trucks(boat_len, boat_type_arg)
    if not trucks:
        return []

    days_searched = 0
    while len(found) < 10 and days_searched < search_days_limit: # Increased number of slots found initially
        if is_workday(current_date):
            valid_slots, high_tide_time = get_valid_slots_with_tides(current_date, ramp, boat_draft)
            if valid_slots:
                for truck in trucks:
                    for slot in sorted(valid_slots):
                        if is_truck_free(truck, current_date, slot, duration, boat_type=boat_type_arg):
                            found.append({
                                "date": current_date.date(),
                                "time": slot,
                                "ramp": ramp,
                                "truck": truck,
                                "high_tide": high_tide_time
                            })
        current_date += timedelta(days=1)
        days_searched += 1

    return sorted(found, key=lambda x: (x['date'], x['time']))

def add_job_to_schedule(job):
    st.session_state["schedule"].append(job)
    st.rerun()

def remove_job_from_schedule(job_to_remove):
    st.session_state["schedule"] = [job for job in st.session_state["schedule"] if job != job_to_remove]
    st.rerun()

def generate_daily_schedule_pdf_bold_end_line_streamlit(selected_date, jobs, customers_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Truck Schedule for {selected_date.strftime('%B %d, %Y')}", ln=1, align="C", bold=True)
    pdf.ln(5)

    if not jobs:
        pdf.cell(200, 10, txt="No jobs scheduled for this date.", ln=1, align="C")
        pdf_filename = f"Truck_Schedule_{selected_date.strftime('%Y-%m-%d')}.pdf"
        pdf.output(pdf_filename, "F")
        return pdf_filename

    for job in jobs:
        job_time_str = job["time"].strftime("%I:%M %p")
        customer_name = job.get("customer", "N/A")
        ramp = job["ramp"]
        truck = job["truck"]
        high_tide = job.get("high_tide", "N/A")

        customer_info = customers_df[customers_df["Customer Name"] == customer_name].iloc[0] if customer_name != "N/A" and not customers_df.empty else None
        boat_type = customer_info["Boat Type"] if customer_info is not None else "N/A"

        line = f"Time: {job_time_str}, Customer: {customer_name}, Boat: {boat_type}, Ramp: {ramp}, Truck: {truck}, High Tide: {high_tide}"
        pdf.cell(0, 10, txt=line, ln=1)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', size=12) # Bold font for the end line
    pdf.cell(0, 10, txt="--- End of Schedule ---", ln=1, align="C")

    pdf_filename = f"Truck_Schedule_{selected_date.strftime('%Y-%m-%d')}.pdf"
    pdf.output(pdf_filename, "F")
    return pdf_filename

# ====================================
#
