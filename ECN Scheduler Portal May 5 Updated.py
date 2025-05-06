
def render_calendar(scheduled_df, suggestions, start_date, ramp_name):
    time_slots = [dt.time(hour=h, minute=m) for h in range(8, 17) for m in [0, 15, 30, 45]]
    days = [start_date + dt.timedelta(days=i) for i in range(5)]

    # Use row labels as first column
    time_labels = [t.strftime("%-I:%M %p") for t in time_slots]
    grid = pd.DataFrame(index=time_labels,
                        columns=[d.strftime("%a\n%b %d") for d in days])

    for _, row in scheduled_df.iterrows():
        d = pd.to_datetime(row["Date"])
        col = d.strftime("%a\n%b %d")
        t = pd.to_datetime(str(row["Time"]))
        row_label = t.strftime("%-I:%M %p")
        if col in grid.columns and row_label in grid.index:
            grid.at[row_label, col] = f"🛥 {row['Customer']}"

    for t in suggestions:
        col = t.strftime("%a\n%b %d")
        row_label = t.strftime("%-I:%M %p")
        if col in grid.columns and row_label in grid.index:
            if pd.isna(grid.at[row_label, col]):
                grid.at[row_label, col] = "✅ AVAILABLE"

    tide_file = TIDE_FILES.get(ramp_name.strip(), TIDE_FILES["Scituate"])
    tide_df = pd.read_csv(tide_file)
    tide_df.columns = tide_df.columns.str.strip()
    tide_df["DateTime"] = pd.to_datetime(tide_df.iloc[:, 0], errors='coerce')
    tide_df = tide_df.dropna(subset=["DateTime"])
    tide_df = tide_df[tide_df["DateTime"].dt.time.between(dt.time(7, 30), dt.time(16, 0))]

    tide_by_day = {}
    for d in days:
        key = d.strftime("%a\n%b %d")
        tide_by_day[key] = tide_df[tide_df["DateTime"].dt.date == d.date()]

    # Determine time labels to highlight
    highlight_times = set()
    for d in days:
        key = d.strftime("%a\n%b %d")
        for _, tide_row in tide_by_day.get(key, pd.DataFrame()).iterrows():
            if tide_row["High/Low"] == "H":
                tide_time = tide_row["DateTime"].time()
                tide_dt = dt.datetime.combine(dt.date.today(), tide_time)
                for t in time_slots:
                    slot_dt = dt.datetime.combine(dt.date.today(), t)
                    if abs((slot_dt - tide_dt).total_seconds()) <= 450:
                        highlight_times.add(t.strftime("%-I:%M %p"))

    grid.insert(0, "Time", grid.index)  # simulate index highlighting

    def style_func(val, row_idx, col_name):
        if col_name == "Time" and row_idx in highlight_times:
            return "background-color: yellow"
        if isinstance(val, str) and "AVAILABLE" in val:
            return "background-color: lightgreen"
        elif isinstance(val, str) and "🛥" in val:
            return "color: gray"
        return ""

    styled = grid.style.apply(lambda row: [style_func(row[col], row.name, col) for col in row.index], axis=1)
    st.subheader("📊 Weekly Calendar Grid with Tide Highlights")
    st.dataframe(styled, use_container_width=True, height=800)
