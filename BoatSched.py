import datetime as dt
import streamlit as st

# Initialize or retrieve schedule data structures
if 'truck_bookings' not in st.session_state:
    st.session_state['truck_bookings'] = {20: [], 21: [], 23: []}
if 'crane_schedule' not in st.session_state:
    st.session_state['crane_schedule'] = []

st.title("ECM Boat Hauling Scheduler")

# Input fields for scheduling a new delivery
boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
truck    = st.selectbox("Select Truck", [20, 21, 23])
boat_name = st.text_input("Boat Name/ID")
date      = st.date_input("Date", value=dt.date.today())
start_time = st.time_input("Start Time", value=dt.time(8, 0))

# Attempt to schedule when user clicks the button
if st.button("Schedule Delivery"):
    start_dt = dt.datetime.combine(date, start_time)
    # Determine job duration based on boat type
    duration = dt.timedelta(hours=1, minutes=30) if boat_type == "Powerboat" else dt.timedelta(hours=3)
    end_dt   = start_dt + duration

    conflict = False
    # Conflict check for the selected truck
    if st.session_state['truck_bookings'][truck]:
        last_end = st.session_state['truck_bookings'][truck][-1]['end']
        # Enforce sequential scheduling with no overlaps or gaps
        if start_dt != last_end:
            conflict = True
            if start_dt < last_end:
                st.error(f"Conflict: Truck {truck} is busy until {last_end.strftime('%Y-%m-%d %H:%M')}.")
            else:
                st.error(f"Conflict: Truck {truck}'s last job ended at {last_end.strftime('%Y-%m-%d %H:%M')}. "
                         f"The next job must start immediately after the previous one ends.")
    # Conflict check for crane (Truck 17) if a sailboat delivery
    if boat_type == "Sailboat":
        if st.session_state['crane_schedule']:
            crane_last_end = st.session_state['crane_schedule'][-1]['end']
            # Crane must also follow sequential scheduling with no gap or overlap
            if start_dt != crane_last_end:
                conflict = True
                if start_dt < crane_last_end:
                    st.error(f"Conflict: Crane (Truck 17) is busy until {crane_last_end.strftime('%Y-%m-%d %H:%M')}.")
                else:
                    st.error(f"Conflict: Crane (Truck 17)'s last job ended at {crane_last_end.strftime('%Y-%m-%d %H:%M')}. "
                             f"The next job must start immediately after the previous one ends.")

    # If no conflicts, add the new booking to the schedule
    if not conflict:
        # Update the selected truck's schedule
        st.session_state['truck_bookings'][truck].append({
            'boat': boat_name or 'N/A',
            'type': boat_type,
            'start': start_dt,
            'end': end_dt
        })
        # If a sailboat, also update the crane's schedule
        if boat_type == "Sailboat":
            st.session_state['crane_schedule'].append({
                'boat': boat_name or 'N/A',
                'truck': truck,
                'start': start_dt,
                'end': end_dt
            })
        st.success(f"Scheduled: {boat_name or 'Unnamed boat'} on Truck {truck} from "
                   f"{start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}.")

# Display the schedule log
st.subheader("Schedule Log")
if any(st.session_state['truck_bookings'][t] for t in [20, 21, 23]):
    # Compile all jobs into one list for display
    all_jobs = []
    for t in [20, 21, 23]:
        for job in st.session_state['truck_bookings'][t]:
            all_jobs.append({
                'Truck': t,
                'Boat' : job['boat'],
                'Type' : job['type'],
                'Start': job['start'],
                'End'  : job['end']
            })
    # Sort the log by start time (and by truck ID for ties)
    all_jobs.sort(key=lambda x: (x['Start'], x['Truck']))
    # Format datetime objects for display
    for job in all_jobs:
        job['Start'] = job['Start'].strftime('%Y-%m-%d %H:%M')
        job['End']   = job['End'].strftime('%Y-%m-%d %H:%M')
    # Show the schedule log as a table
    import pandas as pd
    df = pd.DataFrame(all_jobs, columns=['Truck', 'Boat', 'Type', 'Start', 'End'])
    st.table(df)
else:
    st.write("No deliveries scheduled yet.")
