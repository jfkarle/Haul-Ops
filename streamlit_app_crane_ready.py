for truck, jobs in st.session_state.TRUCKS.items():
            if boat_length > TRUCK_LIMITS[truck]:
                continue
            for slot in valid_slots:
                conflict = any(slot < j[1] and slot + job_length > j[0] for j in jobs)
                if not conflict:
                    # Assign truck job
                    st.session_state.TRUCKS[truck].append((slot, slot + job_length, customer))
                    st.session_state.ALL_JOBS.append({
                        "Customer": customer,
                        "Boat Type": boat_type,
                        "Boat Length": boat_length,
                        "Mast": mast_option,
                        "Origin": origin,
                        "Service": service,
                        "Ramp": ramp,
                        "Date": day.strftime("%Y-%m-%d"),
                        "Start": slot.strftime("%I:%M %p"),
                        "End": (slot + job_length).strftime("%I:%M %p"),
                        "Truck": truck
                    })

                    # Enforce J17 single-ramp rule and assign crane if needed
                    if mast_option in ["Mast On Deck", "Mast Transport"]:
                        j17_conflict = any(
                            j[0].date() == day.date() and j[3] != ramp
                            for j in st.session_state.CRANE_JOBS
                        )
                        if j17_conflict:
                            continue
                        st.session_state.ALL_JOBS.append({
                            "Customer": customer,
                            "Boat Type": "",
                            "Boat Length": "",
                            "Mast": mast_option,
                            "Origin": origin,
                            "Service": "Crane Assist",
                            "Ramp": ramp,
                            "Date": day.strftime("%Y-%m-%d"),
                            "Start": slot.strftime("%I:%M %p"),
                            "End": (slot + job_length).strftime("%I:%M %p"),
                            "Truck": "J17"
                        })
                        st.session_state.CRANE_JOBS.append((slot, slot + job_length, customer, ramp))

                    st.success(f"✅ Scheduled: {customer} on {day.strftime('%A %b %d')} at {slot.strftime('%I:%M %p')} — Truck {truck}")
                    assigned = True
                    break
            if assigned:
                break
