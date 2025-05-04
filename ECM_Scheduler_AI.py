import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
from dateutil import parser
import re

# --- Setup ---
SCHEDULE_FILE = "scheduled_jobs.csv"

# --- Initialize Schedule File ---
if SCHEDULE_FILE not in st.session_state:
    try:
        scheduled_jobs = pd.read_csv(SCHEDULE_FILE)
    except FileNotFoundError:
        scheduled_jobs = pd.DataFrame(columns=["Customer", "Service", "Date"])
        scheduled_jobs.to_csv(SCHEDULE_FILE, index=False)
    st.session_state[SCHEDULE_FILE] = scheduled_jobs

# --- Smarter Offline Parser ---
def parse_customer_prompt(prompt):
    st.warning("⚠️ AI offline — using rule-based parser.")

    # Extract name using capitalization and common patterns
    name_match = re.search(r"(?:this is|i am|i’m|my name is) ([A-Z][a-z]+ [A-Z][a-z]+)", prompt, re.IGNORECASE)
    name = name_match.group(1) if name_match else "Unknown"

    # Extract service type
    if "launch" in prompt.lower():
        service = "Launch"
    elif "haul" in prompt.lower():
        service = "Haul"
    elif "land-land" in prompt.lower():
        service = "Land-Land"
    else:
        service = "Unknown"

    # Extract date reference
    date_match = re.search(r"(?:week of|on|around|for) ([A-Za-z]+ \d{1,2})", prompt, re.IGNORECASE)
    if date_match:
        try:
            parsed_date = parser.parse(date_match.group(1))
        except:
            parsed_date = datetime.date.today() + datetime.timedelta(days=7)
    else:
        parsed_date = datetime.date.today() + datetime.timedelta(days=7)

    return f"Name: {name}\nService: {service}\nDate: {parsed_date.strftime('%B %d, %Y')}"


def get_next_available_dates(service, earliest_date, taken_dates):
    results = []
    dt = earliest_date

    while len(results) < 3:
        weekday = dt.weekday()
        is_may_or_sept = dt.month in [5, 9]
        is_weekday = weekday < 5
        is_saturday_ok = is_may_or_sept and weekday == 5

        if (is_weekday or is_saturday_ok) and dt not in taken_dates:
            results.append(dt)
        dt += datetime.timedelta(days=1)

    return results


def plot_calendar(available_dates, taken_dates):
    start_date = min(available_dates + taken_dates)
    end_date = max(available_dates + taken_dates) + datetime.timedelta(days=7)
    date_range = pd.date_range(start=start_date, end=end_date)

    colors = []
    for d in date_range:
        if d in available_dates:
            colors.append("green")
        elif d in taken_dates:
            colors.append("gray")
        else:
            colors.append("white")

    fig = go.Figure(data=[
        go.Bar(
            x=date_range,
            y=[1]*len(date_range),
            marker_color=colors,
            hovertext=[d.strftime("%B %d, %Y") for d in date_range],
        )
    ])
    fig.update_layout(
        title="Schedule Overview",
        xaxis_title="Date",
        yaxis=dict(showticklabels=False),
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig)


# --- Streamlit App ---
st.title("⚓ ECM Boat Transport Scheduler")

user_input = st.text_area("Enter your scheduling request:")

if st.button("Check Availability") and user_input:
    st.markdown("---")

    parsed = parse_customer_prompt(user_input)
    st.markdown("### 🧾 Parsed Request")
    st.code(parsed)

    try:
        lines = parsed.strip().split("\n")
        name = [l for l in lines if "name" in l.lower()][0].split(":")[-1].strip()
        service = [l for l in lines if "service" in l.lower()][0].split(":")[-1].strip()
        date_str = [l for l in lines if "date" in l.lower()][0].split(":")[-1].strip()
        earliest_date = parser.parse(date_str).date()
    except Exception as e:
        st.error(f"Could not interpret the parsed output. Error: {e}")
        st.stop()

    taken_dates = pd.to_datetime(st.session_state[SCHEDULE_FILE]["Date"]).dt.date.tolist()
    available_dates = get_next_available_dates(service, earliest_date, taken_dates)

    # Store the first scheduled date
    new_row = pd.DataFrame({
        "Customer": [name],
        "Service": [service],
        "Date": [available_dates[0]]
    })
    st.session_state[SCHEDULE_FILE] = pd.concat([st.session_state[SCHEDULE_FILE], new_row], ignore_index=True)
    st.session_state[SCHEDULE_FILE].to_csv(SCHEDULE_FILE, index=False)

    st.markdown("### ✅ Earliest Available Dates")
    for d in available_dates:
        st.write(f"- {d.strftime('%A, %B %d, %Y')}")

    st.markdown("### 📅 Schedule Calendar")
    plot_calendar(available_dates, taken_dates)
