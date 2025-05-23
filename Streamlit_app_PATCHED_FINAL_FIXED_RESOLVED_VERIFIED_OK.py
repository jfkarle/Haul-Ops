import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time, date
import requests

st.set_page_config(
    page_title="Boat Ramp Scheduling",
    layout="wide"
)
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
    "Sandwich Basin": None # No NOAA ID provided
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
    "Harbor Cohasset (Parker Ave)": (3, 3),  # 3 hrs before or after
    "Hull (A St, Sunset, Steamboat)": (3, 1.5),  # 3 hrs before, 1.5 hrs after for 6'+ draft
    "Hull (X Y Z St) (Goodwiny st)": (1, 1),  # 1 hr before or after
    "Hingham Harbor": (3, 3),  # 3 hrs before and after
    "Weymouth Harbor (Wessagusset)": (3, 3),  # 3 hrs before and after
    "Sandwich Basin": None # Any tide
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


def get_tide_predictions(date: datetime, ramp: str):
    station_id = RAMP_TO_NOAA_ID.get(ramp)
    if not station_id:
        station_id = "8445138"  # Fallback to Scituate for any ramp without assigned NOAA ID
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

    if ramp == "Scituate Harbor (Jericho Road)" and boat_draft and boat_draft > 5:  #
        tide_window = (3, 3)  # Special rule for Scituate with draft > 5'

    if tide_window:
        #  Use only the first high tide of the day
        first_high_tide = high_tides_data[0] if high_tides_data else None
        if first_high_tide:
            ht_datetime = datetime.strptime(first_high_tide[0], "%Y-%m-%d %H:%M")
            high_tide_time = ht_datetime.strftime("%I:%M %p")
            valid_slots = generate_slots_for_high_tide(first_high_tide[0], tide_window[0], tide_window[1])
    elif ramp == "Sandwich Basin":
        valid_slots = generate_slots_for_high_tide(datetime.combine(date, time(10, 0)).strftime("%Y-%m-%d %H:%M"), 3, 3) # "Any tide" - provide middle of the day window
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

def eligible_trucks(boat_len: int, boat_type: str):
    if "Sailboat" in boat_type:
        return [t for t, lim in TRUCK_LIMITS.items() if boat_len <= lim]
    return [t for t, lim in TRUCK_LIMITS.items() if boat_len <= lim and t != "J17"]

def has_truck_scheduled(truck: str, date: datetime):
    for job in st.session_state["schedule"]:
        if job["truck"] == truck and job["date"].date() == date.date(): # Ensure comparing date objects
            return True
    return False

def is_truck_free(truck: str, date: datetime, start_t: time, dur_hrs: float):
    start_dt = datetime.combine(date, start_t) # date is already a datetime object here
    end_dt = start_dt + timedelta(hours=dur_hrs)
    for job in st.session_state["schedule"]:
        if job["truck"] != truck:
            continue
        # job["date"] is a datetime object from scheduling
        if job["date"].date() != date.date(): # Compare date parts
            continue
        job_start = datetime.combine(job["date"].date(), job["time"]) # Use job["date"].date()
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

def find_three_dates(start_date: datetime, ramp: str, boat_len: int, boat_type_arg: str, duration: float, boat_draft: float = None, search_days_limit: int = 7):
    found = []
    current_date = start_date
    trucks = eligible_trucks(boat_len, boat_type_arg)
    if not trucks:
        return []

    j17_duration = 0
    if "Sailboat MD" in boat_type_arg:
        j17_duration = 1.0
    elif "Sailboat MT" in boat_type_arg:
        j17_duration = 1.5

    days_searched = 0
    while len(found) < 3 and days_searched < search_days_limit:
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
                            break
                    if len(found) >= 3:
                        break
        current_date += timedelta(days=1)
        days_searched += 1

    return found[:3]


from fpdf import FPDF
import os

def generate_daily_schedule_pdf_bold_end_line_streamlit(date_obj, jobs):
    pdf = FPDF(orientation='P', unit='pt', format='Letter')
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)
    # Top-left date heading
    pdf.set_font("Helvetica", size=14, style='B')
    margin_left = 40
    margin_top = 40
    pdf.text(margin_left, margin_top - 15, date_obj.strftime("%A, %B %d, %Y"))
    pdf.set_font("Helvetica", size=11)

    # Fonts and colors
    pdf.set_font("Helvetica", size=11)
    pdf.set_text_color(0)

    # Margins and layout constants
    margin_left = 40
    margin_top = 40
    pdf.set_font("Helvetica", size=14, style="B")
    margin_left = 40
    margin_top = 40
    pdf.text(margin_left, margin_top - 15, date_obj.strftime("%A, %B %d, %Y"))
    pdf.set_font("Helvetica", size=11)
    page_width = 612
    column_widths = [60, 100, 100, 100, 100]
    row_height = 18

    headers = ["", "S20", "S21", "S23", "Crane J17"]
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Helvetica", size=11, style="B")
    for i, h in enumerate(headers):
        x = margin_left + sum(column_widths[:i])
        pdf.rect(x, margin_top, column_widths[i], row_height, 'FD')
        pdf.text(x + 4, margin_top + 13, h)
    pdf.set_font("Helvetica", size=11)

    start_hour = 8
    end_hour = 19
    
    # Gather high/low tide times (rounded to nearest 30min)
    tide_marks = {"H": [], "L": []}
    for job in jobs:
        if job.get("high_tide"):
            try:
                ht = datetime.strptime(job["high_tide"], "%I:%M %p").time()
                rounded_ht = time(ht.hour, 30 if ht.minute >= 15 else 0)
                tide_marks["H"].append(rounded_ht)
            except:
                pass
        if job.get("low_tide"):
            try:
                lt = datetime.strptime(job["low_tide"], "%I:%M %p").time()
                rounded_lt = time(lt.hour, 30 if lt.minute >= 15 else 0)
                tide_marks["L"].append(rounded_lt)
            except:
                pass


    rows = []
    for hour in range(start_hour, end_hour):
        for quarter in [0, 15, 30, 45]:
            t = time(hour, quarter)
            label = t.strftime("%-I:%M") if quarter else t.strftime("%-I:00")
            rows.append((t, label))

    for idx, (t, label) in enumerate(rows):
        y = margin_top + row_height * (idx + 1)
        x = margin_left
        if t.minute == 0:
            pdf.set_font("Helvetica", size=11, style="B")
            pdf.text(x + 4, y + 13, label)
            pdf.set_font("Helvetica", size=11)
        elif t.minute in [15, 30, 45]:
            pdf.set_text_color(150)
            pdf.text(x + 4, y + 13, label)
            pdf.set_text_color(0)
        for col in range(5):
            x_col = margin_left + sum(column_widths[:col])
            pdf.rect(x_col, y, column_widths[col], row_height)

    for job in jobs:
        truck_col_map = {"S20": 1, "S21": 2, "S23": 3, "J17": 4}
        col = truck_col_map.get(job["truck"], None)
        if col is None:
            continue
        job_start = job["time"]
        duration = timedelta(hours=job["duration"])
        job_end = (datetime.combine(datetime.today(), job_start) + duration).time()
        def time_to_index(t): return (t.hour - start_hour) * 4 + t.minute // 15
        start_idx = time_to_index(job_start)
        end_idx = time_to_index(job_end)
        for i in range(start_idx, end_idx):
            y = margin_top + row_height * (i + 1)
            x = margin_left + sum(column_widths[:col])
            if i == start_idx:
                pdf.set_font("Helvetica", size=11, style="B")
                pdf.text(x + 4, y + 13, job["customer"])
                pdf.set_font("Helvetica", size=11)
            elif i == end_idx - 1:
                pdf.line(x + 4, y + 14, x + column_widths[col] - 4, y + 14)
            else:
                pdf.text(x + column_widths[col] / 2 - 2, y + 13, "|")

    filename = f"schedule_{date_obj.strftime('%Y-%m-%d')}.pdf"
    pdf.output(filename)
    return filename if os.path.exists(filename) else None



# ====================================
# ------------- UI -------------------
# ====================================
st.title("Boat Ramp Scheduling")

# Clean: Ensure nothing outputs accidental None
# If you want to display tide info or status later, gate it properly like this:
if "available_slots" in st.session_state and st.session_state["available_slots"]:
    first_slot = st.session_state["available_slots"][0]
    if first_slot.get("high_tide"):
        tide_time = first_slot["high_tide"]
        slot_date = first_slot["date"].strftime("%A, %B %d, %Y")
        st.markdown(f"**High Tide on {slot_date}: {tide_time}**")


if 'customers_df_loaded' not in st.session_state:
    customers_df = load_customer_data()
else:
    customers_df = st.session_state['customers_df_loaded']

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
    earliest_date_input = st.date_input("Earliest Date", datetime.now().date())

    if "available_slots" in st.session_state and st.session_state["available_slots"]:
        slot = st.session_state["available_slots"][0]
        ht = slot.get("high_tide")
        if ht:
            st.markdown(f"**High Tide on {format_date_display(slot['date'])}: {ht}**")


# --- Main Page for Results ---
# st.header("Available Slots")
if 'find_slots_button' in locals() and find_slots_button:
    if selected_customer:
        duration = JOB_DURATION_HRS.get(boat_type, 1.0)
        # Convert earliest_date_input (date) to datetime for find_three_dates
        earliest_datetime = datetime.combine(earliest_date_input, datetime.min.time())

        st.session_state['available_slots'] = find_three_dates(
        current_available_slots = st.session_state.get('available_slots')
            earliest_datetime,
            ramp_choice,
            boat_length,
            boat_type,  # Pass the boat_type variable here
            duration,
            boat_draft

        # Streamlit_app_FINAL_HIGHTIDE_J17_PATCHED_FIXED.py
        boat_draft
        # boat_type also needs to be passed here, see point 3 below
    

    # The result is in st.session_state['available_slots'].
    # Use a local variable to hold the slots for this block for clarity.
    current_available_slots = st.session_state.get('available_slots') 

    if current_available_slots:
        # The variable 'first_high_tide' previously defined here (line 290) was not used
        # in this block. High tide for the first slot is shown in the sidebar.
        # You can remove that line if it's not used elsewhere.

        cols = st.columns(len(current_available_slots))
        if current_available_slots:
            cols = st.columns(len(current_available_slots))
            for i, slot in enumerate(current_available_slots):
            # ...
                with cols[i]:
                    # slot['date'] is a date object here
                    ### formatted_date_display = format_date_display(slot['date'])
                    ### st.info(f"Date: {formatted_date_display}")
                    day_name = slot['date'].strftime("%A")  # e.g., Monday
                    formatted_date_display = format_date_display(slot['date'])
                    st.markdown(f"**{day_name}**")
                    st.info(f"Date: {formatted_date_display}")
                    st.markdown(f"**Time:** {slot['time'].strftime('%I:%M %p')}")
                    st.markdown(f"**Ramp:** {slot['ramp']}")
                    st.markdown(f"**Truck:** {slot['truck']}")
                    schedule_key = f"schedule_{format_date_display(slot['date'])}_{slot['time'].strftime('%H%M')}_{slot['truck']}" # Ensure key is unique

                    def create_schedule_callback(current_slot, current_duration, current_customer, current_formatted_date):
                        def schedule_job_callback():
                            # Schedule hauling truck job
                            hauling_job = {
                                'truck': current_slot['truck'],
                                'date': datetime.combine(current_slot['date'], current_slot['time']),
                                'time': current_slot['time'],
                                'duration': current_duration,
                                'customer': current_customer,
                                'high_tide': current_slot.get("high_tide", ""),
                                'ramp': current_slot.get("ramp", "")
                            }
                            st.session_state['schedule'].append(hauling_job)
                            # Schedule crane truck J17 if required
                            if current_slot.get('j17_required'):
                                crane_job = {
                                    'truck': 'J17',
                                    'date': datetime.combine(current_slot['date'], current_slot['time']),
                                    'time': current_slot['time'],
                                    'duration': current_slot['j17_duration'],
                                    'customer': current_customer
                                }
                                st.session_state['schedule'].append(crane_job)
                            st.success(
                                f"Scheduled {current_customer} with Truck {current_slot['truck']}"
                                f"{' and Crane (J17) for ' + str(current_slot['j17_duration']) + ' hrs' if current_slot.get('j17_required') else ''} "
                                f"on {current_formatted_date} at {current_slot['time'].strftime('%I:%M %p')}."
                        return schedule_job_callback


            st.button(
                f"Schedule on {slot['time'].strftime('%H:%M')}",
                key=schedule_key,
                on_click=create_schedule_callback(slot, duration, selected_customer, formatted_date_display)
            )
                st.markdown("---")
        else:
            st.info("No suitable slots found for the selected criteria.")
            st.info("No suitable slots found for the selected criteria.")
else:
        st.warning("Please select a customer first.")

st.header("Current Schedule")
if st.session_state["schedule"]:
    # Create a DataFrame for display, formatting the date here
    display_schedule_list = []
    seen = set()

    for job in st.session_state["schedule"]:
        key = (job["customer"], job["date"], job["time"])
        if job["truck"] == "J17" or key in seen:
            continue

        seen.add(key)

        try:
            customer_row = customers_df[customers_df["Customer Name"] == job["customer"]].iloc[0]
            boat_type = customer_row["Boat Type"]
            boat_name = customer_row.get("Boat Name", "Unknown")
        except (KeyError, IndexError):
            boat_type = "Unknown"
            boat_name = "Unknown"

        has_j17 = any(
            j["truck"] == "J17" and
            j["customer"] == job["customer"] and
            j["date"] == job["date"] and
            j["time"] == job["time"]
            for j in st.session_state["schedule"]

        display_schedule_list.append({
            "Customer": job["customer"],
            "Boat Name": boat_name,
            "Boat Type": boat_type,
            "Date": format_date_display(job["date"]),
            "Ramp": job.get("ramp", "Unknown"),
            "Time": job["time"].strftime('%H:%M'),
            "Truck": job["truck"],
            "Truck Duration": f"{int(job['duration'])}:{int((job['duration'] % 1) * 60):02d}",
            "J17": "Yes" if has_j17 else "No",
            "Duration": f"{int(job['duration'])}:{int((job['duration'] % 1) * 60):02d}",
            "High Tide": job.get("high_tide", "")
        })

    schedule_df_display = pd.DataFrame(display_schedule_list)
    schedule_df_display.rename(columns={"J17": "Crane"}, inplace=True)

    def highlight_crane(val):
        if val == "Yes":
            return "background-color: #ffcccc; font-weight: bold"
        return ""

    display_df = schedule_df_display[[
        "Customer", "Boat Type", "Date", "Ramp", "Time",
        "Truck", "Truck Duration", "Crane", "Duration", "High Tide"
    ]]

    styled_df = display_df.style \
        .applymap(highlight_crane, subset=["Crane"]) \
        .set_table_styles([
            {"selector": "thead th", "props": [("font-weight", "bold"), ("background-color", "#f0f0f0"), ("border", "2px solid black")]},
            {"selector": "td", "props": [("border", "2px solid black")]}
        ])

    st.dataframe(styled_df, use_container_width=True)

# ========== Daily PDF Export UI ==========
from datetime import datetime

                st.markdown("---")
st.header("📄 Daily Schedule PDF")

selected_date = st.date_input("Select Date for Daily PDF")

            st.button(
                f"Schedule on {slot['time'].strftime('%H:%M')}",
                key=schedule_key,
                on_click=create_schedule_callback(slot, duration, selected_customer, formatted_date_display)
            )
        if filtered_jobs:
            pdf_path = generate_daily_schedule_pdf_bold_end_line_streamlit(
                datetime.combine(selected_date, datetime.min.time()), filtered_jobs
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f, file_name=f"Truck_Schedule_{selected_date}.pdf")
            else:
                st.error("PDF generation failed.")
else:
            st.warning("No scheduled jobs found for the selected date.")
else:
        st.warning("No scheduled jobs found.")
        else:
            st.info("No suitable slots found for the selected criteria.")
    st.info("The schedule is currently empty.")

