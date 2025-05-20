if available_slots:
    first_high_tide = available_slots[0].get('high_tide') if available_slots else None
    if first_high_tide:
        st.markdown(
            f"<h4 style='margin-bottom: 10px;'>High Tide on {format_date_mmddyy(available_slots[0]['date'])}: {first_high_tide}</h4>",
            unsafe_allow_html=True
        )

    # Inject custom styles
    st.markdown("""
        <style>
            h1 {
                font-size: 2rem !important;  /* Reduce main title */
            }
            h2 {
                font-size: 1.5rem !important;  /* Reduce Available Slots title */
            }
            .custom-time {
                font-size: 0.8em !important;
            }
            .schedule-button button {
                border: 2px solid #333;
                font-weight: 600;
                padding: 0.5em 1em;
                border-radius: 5px;
                margin-top: 5px;
            }
        </style>
    """, unsafe_allow_html=True)

    cols = st.columns(len(available_slots))
    for i, slot in enumerate(available_slots):
        with cols[i]:
            formatted_date_display = format_date_mmddyy(slot['date'])
            st.info(f"Date: {formatted_date_display}")
            st.markdown(f"<div class='custom-time'>**Time:** {slot['time'].strftime('%H:%M')}</div>", unsafe_allow_html=True)
            st.markdown(f"**Ramp:** {slot['ramp']}")
            st.markdown(f"**Truck:** {slot['truck']}")
            schedule_key = f"schedule_{formatted_date_display}_{slot['time'].strftime('%H%M')}_{slot['truck']}"

            def create_schedule_callback(current_slot, current_duration, current_customer, current_formatted_date):
                def schedule_job_callback():
                    new_schedule_item = {
                        "truck": current_slot["truck"],
                        "date": datetime.combine(current_slot["date"], current_slot["time"]),
                        "time": current_slot["time"],
                        "duration": current_duration,
                        "customer": current_customer
                    }
                    st.session_state["schedule"].append(new_schedule_item)
                    st.success(f"Scheduled {current_customer} with {current_slot['truck']} on {current_formatted_date} at {current_slot['time'].strftime('%H:%M')}.")
                return schedule_job_callback

            with st.container():
                st.markdown('<div class="schedule-button">', unsafe_allow_html=True)
                st.button(
                    f"Schedule on {slot['time'].strftime('%H:%M')}",
                    key=schedule_key,
                    on_click=create_schedule_callback(slot, duration, selected_customer, formatted_date_display)
                )
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")
