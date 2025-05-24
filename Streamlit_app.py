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

# ====================================
# ------------ CONSTANTS -------------
# ====================================
CUSTOMER_CSV = "customer_with_coords.csv"
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
    "Sandwich Basin": None # Any tide
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

def is_truck_free(truck: str, date: datetime, start_t: time, dur_hrs: float):
    start_dt = datetime.combine(date, start_t)
    end_dt = start_dt + timedelta(hours=dur_hrs)
    for job in st.session_state["schedule"]:
        if job["truck"] != truck:
            continue
        if job["date"].date() != date.date(): # Compare date parts
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
    scale_factor = available_content_width / total_original_width

    column_widths = [
        60 * scale_factor, # Time column
        100 * scale_factor, # S20
        100 * scale_factor, # S21
        100 * scale_factor, # S23
        100 * scale_factor  # Crane J17
    ]
    
    start_hour = 8
    end_hour = 19
    num_rows = (end_hour - start_hour) * 4 # 44 rows (15-min intervals)

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
                _, high_tides_data, _ = get_tide_predictions(current_date_obj, first_job_ramp)
                if high_tides_data:
                    ht_datetime = datetime.strptime(high_tides_data[0][0], "%Y-%m-%d %H:%M")
                    high_tide_display = f"High Tide: {ht_datetime.strftime('%I:%M %p')}"

        if high_tide_display:
            current_pdf.set_font("Helvetica", size=9)
            text_width = current_pdf.get_string_width(high_tide_display)
            current_pdf.text(page_width - margin_right - text_width, margin_top - 15, high_tide_display)

        # Table Headers
        current_pdf.set_fill_color(220, 220, 220)
        current_pdf.set_font("Helvetica", size=11, style="B")
        current_x = margin_left
        header_y_pos = margin_top 

        for i, h in enumerate(headers):
            x = current_x
            current_pdf.rect(x, header_y_pos, column_widths[i], row_height, 'FD')
            current_pdf.text(x + 4, header_y_pos + row_height / 2 + current_pdf.font_size / 2 - 2, h)
            current_x += column_widths[i]
        
        # Set Y position for content to start below headers
        current_pdf.set_y(header_y_pos + row_height)
        current_pdf.set_font("Helvetica", size=11) # Reset font for content

    draw_page_header(pdf, date_obj, jobs)

    # Collect all tides for the given date and relevant ramps
    unique_ramps = list(set(job['ramp'] for job in jobs if 'ramp' in job))
    all_tides_for_day = []
    for ramp in unique_ramps:
        preds, _, err = get_tide_predictions(date_obj, ramp)
        if not err:
            all_tides_for_day.extend(preds)

    tide_marks = {"H": [], "L": []}
    for t_str, t_type in all_tides_for_day:
        try:
            dt_obj = datetime.strptime(t_str, "%Y-%m-%d %H:%M")
            total_minutes = dt_obj.hour * 60 + dt_obj.minute
            rounded_minutes = round(total_minutes / 15) * 15
            rounded_hour = rounded_minutes // 60
            rounded_minute = rounded_minutes % 60
            rounded_t = time(rounded_hour % 24, rounded_minute)
            if t_type == "H":
                tide_marks["H"].append(rounded_t)
            elif t_type == "L":
                tide_marks["L"].append(rounded_t)
        except Exception as e:
            pass

    rows = []
    for hour in range(start_hour, end_hour):
        for minute in [0, 15, 30, 45]:
            t = time(hour, minute)
            rows.append(t)

    # Prepare content for each display cell (customer, boat, ramp)
    # Key: (time_obj, truck_name) -> { "text": "...", "font_size": int, "font_style": str }
    display_content_map = {} 

    for job in jobs:
        job_start_t = job["time"]
        job_start_dt = datetime.combine(date_obj, job_start_t)
        job_truck = job["truck"]

        # 1. Customer Name (at job start time)
        display_content_map[(job_start_t, job_truck)] = {
            "text": job["customer"],
            "font_size": 9, "font_style": "B"
        }

        # 2. Boat Details (15 mins after job start)
        boat_details_t = (job_start_dt + timedelta(minutes=15)).time()
        customer_row_data = customers_df[customers_df["Customer Name"] == job["customer"]].iloc[0]
        boat_type = customer_row_data["Boat Type"]
        boat_length = customer_row_data["Boat Length"]
        boat_details_text = f"{boat_length}' {boat_type}"
        display_content_map[(boat_details_t, job_truck)] = {
            "text": boat_details_text,
            "font_size": 8, "font_style": ""
        }

        # 3. Ramp (30 mins after job start)
        ramp_t = (job_start_dt + timedelta(minutes=30)).time()
        ramp_text = job.get("ramp", "Unknown")
        display_content_map[(ramp_t, job_truck)] = {
            "text": ramp_text,
            "font_size": 8, "font_style": ""
        }
    
    # Function to convert time object to its corresponding row index
    def time_to_idx(t_obj):
        return (t_obj.hour - start_hour) * 4 + t_obj.minute // 15

    # Main loop to draw the grid and content
    for idx, t in enumerate(rows): # Iterate through each 15-minute time slot
        y_row_start = margin_top + row_height * (idx + 1) # Y position for this row, +1 for header
        
        # Draw time/tide labels in the first column
        x_first_col = margin_left
        
        display_label = t.strftime("%-I:%M") if t.minute else t.strftime("%-I:00")
        label_style = "Helvetica"
        label_size = 11
        label_color = (0, 0, 0)

        if t in tide_marks["H"]:
            display_label = "HIGH TIDE"
            label_style = "Helvetica"
            label_size = 10
            label_color = (0, 100, 0)
        elif t in tide_marks["L"]:
            display_label = "LOW TIDE"
            label_style = "Helvetica"
            label_size = 10
            label_color = (200, 0, 0)
        elif t.minute != 0:
            label_color = (150, 150, 150)

        pdf.set_font(label_style, size=label_size)
        pdf.set_text_color(*label_color)
        # Position text to be vertically centered in its row
        pdf.text(x_first_col + 4, y_row_start + row_height / 2 + pdf.font_size / 2 - 2, display_label)
        pdf.set_text_color(0, 0, 0) # Reset color

        # Draw grid cells for this row
        current_x_grid = margin_left
        truck_col_map = {"S20": 1, "S21": 2, "S23": 3, "J17": 4} 
        for col_idx in range(len(column_widths)):
            x_col = current_x_grid
            pdf.rect(x_col, y_row_start, column_widths[col_idx], row_height)
            
            # Draw content if it exists for this cell (skip first column for time labels)
            if col_idx > 0: 
                truck_name = list(truck_col_map.keys())[col_idx - 1] 
                content_data = display_content_map.get((t, truck_name))
                if content_data:
                    pdf.set_font("Helvetica", size=content_data["font_size"], style=content_data["font_style"])
                    # Center text vertically in the row
                    pdf.text(x_col + 4, y_row_start + row_height / 2 + pdf.font_size / 2 - 2, content_data["text"])
                    pdf.set_font("Helvetica", size=11) # Reset font

            current_x_grid += column_widths[col_idx]
        
    # After drawing all cells, draw the vertical lines for job durations
    truck_col_map = {"S20": 1, "S21": 2, "S23": 3, "J17": 4} 
    for job in jobs:
        job_start_t = job["time"]
        job_truck = job["truck"]
        job_start_dt = datetime.combine(date_obj, job_start_t)
        job_end_dt = job_start_dt + timedelta(hours=job["duration"])

        # Calculate the Y coordinate for the start of the line (bottom of the Ramp cell)
        # Ramp text is at job_start_t + 30 mins. Line starts *below* this cell.
        ramp_slot_time = (job_start_dt + timedelta(minutes=30)).time()
        start_line_row_idx = time_to_idx(ramp_slot_time) # Get index of the ramp cell
        y_line_start = margin_top + row_height * (start_line_row_idx + 1 + 1) # +1 for header, +1 for bottom of ramp cell

        # Calculate the Y coordinate for the end of the line (bottom of the last job cell)
        # The line terminates at the bottom of the last *occupied* 15-min slot
        end_job_row_idx = time_to_idx((job_end_dt - timedelta(seconds=1)).time())
        y_line_end = margin_top + row_height * (end_job_row_idx + 1 + 1) # +1 for header, +1 for bottom of row

        col_idx = truck_col_map.get(job_truck)
        if col_idx is None: continue
        
        x_center_line = margin_left + sum(column_widths[:col_idx]) + column_widths[col_idx] / 2
        
        # Draw the vertical line
        pdf.line(x_center_line, y_line_start, x_center_line, y_line_end)

        # Draw the horizontal end cap
        cap_length = 20 # length of the horizontal cap line
        pdf.line(x_center_line - cap_length/2, y_line_end, x_center_line + cap_length/2, y_line_end)


    # Add copyright text at the bottom of the page
    pdf.set_y(page_height - margin_bottom + 10) # Position from bottom margin, 10pt up
    pdf.set_font("Helvetica", size=8)
    copyright_text = "© Copyright ECM, Inc 2025"
    text_width = pdf.get_string_width(copyright_text)
    x_center = (page_width - text_width) / 2
    pdf.text(x_center, pdf.get_y(), copyright_text)

    filename = f"schedule_{date_obj.strftime('%Y-%m-%d')}.pdf"
    pdf.output(filename)
    return filename if os.path.exists(filename) else None


# ====================================
# ------------- UI -------------------
# ====================================
st.title("Boat Ramp Scheduling")

# High Tide display for the first available slot
if "available_slots" in st.session_state and st.session_state["available_slots"]:
    first_slot = st.session_state["available_slots"][0]
    if first_slot.get("high_tide"):
        tide_time = first_slot["high_tide"]
        slot_date = first_slot["date"]
        st.markdown(f"**High Tide on {format_date_display(slot_date)}: {tide_time}**")

if 'customers_df_loaded' not in st.session_state:
    customers_df = load_customer_data()
else:
    customers_df = st.session_state['customers_df_loaded']

# --- Sidebar for Input ---
with st.sidebar:
    st.header("New Job")
    customer_query = st.text_input("Find Customer:", "")
    filtered_customers = filter_customers(customers_df, customer_query)

    selected_customer = None
    if not filtered_customers.empty:
        selected_customer = st.selectbox("Select Customer", filtered_customers["Customer Name"])
    else:
        st.info("No matching customers found.")

    if selected_customer:
        customer_row = customers_df[customers_df["Customer Name"] == selected_customer].iloc[0]
        boat_type = customer_row["Boat Type"]
        boat_length = customer_row["Boat Length"]
        st.write(f"Selected Boat Type: **{boat_type}**")
        st.write(f"Selected Boat Length: **{boat_length} feet**")
        ramp_choice = st.selectbox("Launch Ramp", list(RAMP_TO_NOAA_ID.keys()))
        boat_draft = 0.0 # Default to 0
        if ramp_choice == "Scituate Harbor (Jericho Road)":
            boat_draft = st.number_input("Boat Draft (feet)", min_value=0.0, value=0.0)
        
        earliest_date_input = st.date_input("Earliest Date", datetime.now().date())
        earliest_datetime = datetime.combine(earliest_date_input, datetime.min.time())
        
        duration = JOB_DURATION_HRS.get(boat_type, 1.5) # Default to 1.5 hrs if not found

        if st.button("Find Available Slots"):
            st.session_state["available_slots"] = find_three_dates(
                earliest_datetime,
                ramp_choice,
                boat_length,
                boat_type, 
                duration,
                boat_draft
            )
    else:
        st.warning("Please select a customer first.")


# Available Slots section (main column)
current_available_slots = st.session_state.get('available_slots')

if current_available_slots:
    st.subheader("Available Slots")
    cols = st.columns(len(current_available_slots))
    for i, slot in enumerate(current_available_slots):
        with cols[i]:
            day_name = slot['date'].strftime("%A")  # e.g., Monday
            formatted_date_display = format_date_display(slot['date'])
            st.markdown(f"**{day_name}**")
            st.info(f"Date: {formatted_date_display}")
            st.markdown(f"**Time:** {slot['time'].strftime('%I:%M %p')}")
            st.markdown(f"**Ramp:** {slot['ramp']}")
            st.markdown(f"**Truck:** {slot['truck']}")
            schedule_key = f"schedule_{formatted_date_display}_{slot['time'].strftime('%H%M')}_{slot['truck']}" # Ensure key is unique

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
                            'customer': current_customer,
                            'ramp': current_slot.get("ramp", "") # Add the ramp information here!
                        }
                        st.session_state['schedule'].append(crane_job)
                    st.success(
                        f"Scheduled {current_customer} with Truck {current_slot['truck']}"
                        f"{' and Crane (J17) for ' + str(current_slot['j17_duration']) + ' hrs' if current_slot.get('j17_required') else ''} "
                        f"on {current_formatted_date} at {current_slot['time'].strftime('%I:%M %p')}."
                    )
                return schedule_job_callback

            st.button(
                f"Schedule on {slot['time'].strftime('%H:%M')}",
                key=schedule_key,
                on_click=create_schedule_callback(slot, duration, selected_customer, formatted_date_display)
            )
    st.markdown("---")
else:
    st.info("No suitable slots found for the selected criteria.")


st.header("Current Schedule")
if st.session_state["schedule"]:
    # Create a DataFrame for display, formatting the date here
    display_schedule_list = []
    seen = set()

    for job in st.session_state["schedule"]:
        key = (job["customer"], job["date"], job["time"])
        # Only process hauling truck jobs for display; J17 is implicitly handled by 'Crane' column
        if job["truck"] == "J17" and key in seen: # Ensure we don't double count if J17 is added separately
            continue
        if job["truck"] != "J17": # Process hauling truck and mark as seen
            seen.add(key)
        
        try:
            customer_row = customers_df[customers_df["Customer Name"] == job["customer"]].iloc[0]
            boat_type = customer_row["Boat Type"]
            boat_name = customer_row.get("Boat Name", "Unknown") # Use .get with default
        except (KeyError, IndexError):
            boat_type = "Unknown"
            boat_name = "Unknown"

        # Check if a J17 job exists for this customer at this date/time
        has_j17 = any(
            j["truck"] == "J17" and
            j["customer"] == job["customer"] and
            j["date"] == job["date"] and
            j["time"] == job["time"]
            for j in st.session_state["schedule"]
        )

        # Only add the main hauling job to the display list if it's not J17,
        # or if it's a J17 job that hasn't been "seen" (meaning it's the primary/only entry for that time)
        # This prevents duplicate rows if both hauling and J17 are listed separately
        if job["truck"] != "J17": # We only want one row per customer/date/time, associated with the main truck
            display_schedule_list.append({
                "Customer": job["customer"],
                "Boat Name": boat_name,
                "Boat Type": boat_type,
                "Date": format_date_display(job["date"]),
                "Ramp": job.get("ramp", "Unknown"),
                "Time": job["time"].strftime('%H:%M'),
                "Truck": job["truck"],
                "Truck Duration": f"{int(job['duration'])}:{int((job['duration'] % 1) * 60):02d}",
                "Crane": "Yes" if has_j17 else "No",
                "High Tide": job.get("high_tide", "")
            })

    schedule_df_display = pd.DataFrame(display_schedule_list)
    

    def highlight_crane(val):
        if val == "Yes":
            return "background-color: #ffcccc; font-weight: bold"
        return ""

    # Ensure all columns exist before selecting
    columns_to_display = [
        "Customer", "Boat Name", "Boat Type", "Date", "Ramp", "Time",
        "Truck", "Truck Duration", "Crane", "High Tide"
    ]
    # Filter to only columns that are actually in the DataFrame
    display_df = schedule_df_display[[col for col in columns_to_display if col in schedule_df_display.columns]]


    styled_df = display_df.style \
        .applymap(highlight_crane, subset=["Crane"]) \
        .set_table_styles([
            {"selector": "thead th", "props": [("font-weight", "bold"), ("background-color", "#f0f0f0"), ("border", "2px solid black")]},
            {"selector": "td", "props": [("border", "2px solid black")]}
        ])

    st.dataframe(styled_df, use_container_width=True)
else:
    st.info("The schedule is currently empty.")


# ========== Daily PDF Export UI ==========
st.header("📄 Daily Schedule PDF")

selected_date_for_pdf = st.date_input("Select Date for Daily PDF Export", datetime.now().date())

if st.button("Generate PDF"):
    # Filter jobs for the selected date
    filtered_jobs_for_pdf = [
        job for job in st.session_state["schedule"] 
        if job["date"].date() == selected_date_for_pdf
    ]

    if filtered_jobs_for_pdf:
        # Pass customers_df to the PDF function
        pdf_path = generate_daily_schedule_pdf_bold_end_line_streamlit(
            datetime.combine(selected_date_for_pdf, datetime.min.time()), 
            filtered_jobs_for_pdf,
            customers_df # Pass the customers_df here
        )
        if pdf_path:
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, file_name=f"Truck_Schedule_{selected_date_for_pdf}.pdf")
        else:
            st.error("PDF generation failed.")
    else:
        st.warning("No scheduled jobs found for the selected date to generate PDF.")

