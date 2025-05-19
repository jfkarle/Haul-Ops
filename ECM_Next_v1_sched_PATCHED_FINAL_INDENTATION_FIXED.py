import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import requests

# ... (Constants and helper functions from your code)

def get_valid_slots_with_tides(date: datetime, ramp: str):
    preds, err = get_tide_predictions(date, ramp)
    if err or not preds:
        return [], []

    st.write("First few 'preds':", preds[:5])  # Enhanced debug: Show up to 5 elements

    high_tides_data = []
    for i, p in enumerate(preds):
        st.write(f"Processing preds[{i}]: {p}, Type: {type(p)}")  # Detailed debug

        try:
            if isinstance(p, dict):
                if 't' in p and 'type' in p and p.get('type') == 'H':
                    high_tides_data.append((datetime.strptime(p['t'], "%Y-%m-%d %H:%M"), p['type']))
                else:
                    st.warning(f"Unexpected dict format in preds[{i}]: {p}")
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                if p[1] == 'H':
                    high_tides_data.append((datetime.strptime(p[0], "%Y-%m-%d %H:%M"), p[1]))
                else:
                    st.warning(f"Unexpected tuple/list format in preds[{i}]: {p}")
            else:
                st.error(f"Unexpected data type in preds[{i}]: {p}, Type: {type(p)}")
        except (ValueError, KeyError) as e:
            st.error(f"Error processing preds[{i}]: {p}, Error: {e}")

    slots = []
    high_tide_times = []
    for ht_datetime, _ in high_tides_data:
        high_tide_times.append(ht_datetime.strftime("%I:%M %p"))
        slots.extend(generate_slots_for_high_tide(ht_datetime.strftime("%Y-%m-%d %H:%M")))

    return sorted(set(slots)), high_tide_times

# ... (Rest of your code)


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
                            "high_tides": relevant_high_tides  # Store relevant high tides
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

def load_customer_data():
    # Replace this with your actual implementation of load_customer_data
    # For example, if it's in a CSV:
    try:
        return pd.read_csv(CUSTOMER_CSV)
    except FileNotFoundError:
        st.error(f"Error: Customer data file '{CUSTOMER_CSV}' not found.")
        return pd.DataFrame()  # Return an empty DataFrame to avoid errors later
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
    schedule_df["Date"] = schedule_df["date"].dt.date
    schedule_df["Time"] = schedule_df["time"].astype(str)
    st.dataframe(schedule_df[["customer", "Date", "Time", "truck", "duration"]])
else:
    st.info("The schedule is currently empty.")

if 'ramp_choice' in st.session_state:
    st.session_state['last_ramp_choice'] = st.session_state['ramp_choice']
elif list(RAMP_TO_NOAA_ID.keys()):
    st.session_state['last_ramp_choice'] = list(RAMP_TO_NOAA_ID.keys())[0]
