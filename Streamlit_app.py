import streamlit as st
import json
import uuid
from datetime import datetime
import os

# --- Configuration (same as before) ---
CUSTOMER_DATA_FILE = 'customers.json'
JOB_DATA_FILE = 'jobs.json'
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

# --- Helper Functions for Data Handling (same as before) ---
def load_data(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data
    except (json.JSONDecodeError, IOError):
        # On Streamlit Cloud, if files are corrupted or empty in an unexpected way
        st.error(f"Error loading data from {file_path}. Starting with empty data for this section.")
        return {}

def save_data(data, file_path):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError:
        st.error(f"Error: Could not save data to {file_path}")

# --- Customer Class (mostly the same) ---
class Customer:
    def __init__(self, name, phone, email, address, boat_make, boat_model, boat_length, boat_name="", customer_id=None):
        self.customer_id = customer_id if customer_id else str(uuid.uuid4())
        self.name = name
        self.phone = phone
        self.email = email
        self.address = address
        self.boat_make = boat_make
        self.boat_model = boat_model
        self.boat_length = boat_length
        self.boat_name = boat_name

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_dict(data):
        return Customer(**data)

    # __str__ is less used in Streamlit, but can be helpful for debugging or specific displays
    def __str__(self):
        return (f"ID: {self.customer_id}\n"
                f"  Name: {self.name}\n"
                f"  Phone: {self.phone}\n"
                f"  Email: {self.email}\n"
                f"  Address: {self.address}\n"
                f"  Boat: {self.boat_length}ft {self.boat_make} {self.boat_model} (Name: {self.boat_name if self.boat_name else 'N/A'})")

# --- Job Class (mostly the same) ---
class Job:
    VALID_STATUSES = ["Scheduled", "In Progress", "Completed", "Cancelled", "Invoiced", "Paid"]

    def __init__(self, customer_id, service_type, scheduled_datetime_str, origin_location, destination_location, quoted_price, notes="", job_id=None, status="Scheduled"):
        self.job_id = job_id if job_id else str(uuid.uuid4())
        self.customer_id = customer_id
        self.service_type = service_type
        try:
            # Ensure datetime is stored consistently; parsing happens at creation
            self.scheduled_datetime = datetime.strptime(scheduled_datetime_str, DATETIME_FORMAT).strftime(DATETIME_FORMAT)
        except ValueError:
            raise ValueError(f"Invalid datetime format. Please use YYYY-MM-DD HH:MM (e.g., 2025-09-15 14:30)")
        self.origin_location = origin_location
        self.destination_location = destination_location
        self.quoted_price = float(quoted_price)
        self.status = status if status in self.VALID_STATUSES else "Scheduled"
        self.notes = notes
        self.created_at = datetime.now().strftime(DATETIME_FORMAT)
        self.updated_at = self.created_at

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_dict(data):
        return Job(**data)

    def update_status(self, new_status):
        if new_status in self.VALID_STATUSES:
            self.status = new_status
            self.updated_at = datetime.now().strftime(DATETIME_FORMAT)
            return True
        return False

# --- Business Logic (BoatHaulingManager - modified to remove input() calls) ---
class BoatHaulingManager:
    def __init__(self):
        # Load data at initialization
        self.customers_data = load_data(CUSTOMER_DATA_FILE)
        self.jobs_data = load_data(JOB_DATA_FILE)

        # Convert dicts to objects
        self.customers = {cid: Customer.from_dict(cdata) for cid, cdata in self.customers_data.items()}
        self.jobs = {jid: Job.from_dict(jdata) for jid, jdata in self.jobs_data.items()}


    def save_all(self):
        # Convert objects back to dicts for saving
        customer_dicts_to_save = {cid: c.to_dict() for cid, c in self.customers.items()}
        job_dicts_to_save = {jid: j.to_dict() for jid, j in self.jobs.items()}
        save_data(customer_dicts_to_save, CUSTOMER_DATA_FILE)
        save_data(job_dicts_to_save, JOB_DATA_FILE)
        st.sidebar.success("Data saved successfully!") # Feedback in Streamlit

    def get_customer_by_id(self, customer_id):
        return self.customers.get(customer_id)

    def get_job_by_id(self, job_id):
        return self.jobs.get(job_id)

# --- Streamlit UI Application ---
def streamlit_main():
    st.set_page_config(layout="wide", page_title="Boat Hauling Automator")
    st.title("🚤 Boat Hauling Business Automator")
    st.write("Current Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Initialize manager - this will load data from files
    # To persist manager across reruns more efficiently, use st.session_state
    if 'manager' not in st.session_state:
        st.session_state.manager = BoatHaulingManager()
    manager = st.session_state.manager


    menu_options = [
        "Home",
        "Add New Customer",
        "List/View All Customers",
        "Find Customer",
        "Add New Job",
        "List/View Jobs",
        "Update Job Status",
    ]
    menu_choice = st.sidebar.selectbox("Navigation", menu_options)

    # --- Home Page ---
    if menu_choice == "Home":
        st.header("Welcome!")
        st.write("Select an option from the sidebar to manage your boat hauling business.")
        # Display some quick stats
        st.subheader("Quick Stats")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Customers", len(manager.customers))
        col2.metric("Total Jobs", len(manager.jobs))
        scheduled_jobs = sum(1 for job in manager.jobs.values() if job.status == "Scheduled")
        col3.metric("Scheduled Jobs", scheduled_jobs)

    # --- Add New Customer ---
    elif menu_choice == "Add New Customer":
        st.header("➕ Add New Customer")
        with st.form("add_customer_form", clear_on_submit=True):
            st.subheader("Customer Details")
            name = st.text_input("Customer Name*", help="Required")
            phone = st.text_input("Phone Number*", help="Required")
            email = st.text_input("Email Address*", help="Required")
            address = st.text_area("Billing Address")

            st.subheader("Boat Details")
            boat_make = st.text_input("Boat Make*", help="Required")
            boat_model = st.text_input("Boat Model*", help="Required")
            boat_length = st.number_input("Boat Length (ft)*", min_value=1.0, value=20.0, format="%.1f", help="Required")
            boat_name = st.text_input("Boat Name (optional)")

            submitted = st.form_submit_button("Add Customer")

            if submitted:
                if not all([name, phone, email, boat_make, boat_model, boat_length > 0]):
                    st.error("Please fill in all required fields marked with *.")
                else:
                    customer = Customer(name, phone, email, address, boat_make, boat_model, boat_length, boat_name)
                    manager.customers[customer.customer_id] = customer
                    manager.save_all() # Save after adding
                    st.success(f"Customer '{name}' added successfully! ID: {customer.customer_id}")

    # --- List/View All Customers ---
    elif menu_choice == "List/View All Customers":
        st.header("👥 List of Customers")
        if not manager.customers:
            st.info("No customers found.")
        else:
            search_query = st.text_input("Search customers by name, email, or boat...", key="customer_search_list")
            
            filtered_customers = []
            if search_query:
                search_query = search_query.lower()
                for cust_id, customer in manager.customers.items():
                    if (search_query in customer.name.lower() or
                        search_query in customer.email.lower() or
                        search_query in customer.boat_make.lower() or
                        search_query in customer.boat_model.lower() or
                        search_query in customer.boat_name.lower()):
                        filtered_customers.append(customer)
            else:
                filtered_customers = list(manager.customers.values())


            if not filtered_customers:
                st.info(f"No customers found matching '{search_query}'.")
            else:
                st.write(f"Showing {len(filtered_customers)} customer(s).")
                for customer in sorted(filtered_customers, key=lambda c: c.name):
                    with st.expander(f"{customer.name} (Boat: {customer.boat_length}ft {customer.boat_make} {customer.boat_model}) - ID: ...{customer.customer_id[-6:]}"):
                        st.markdown(f"**Phone:** {customer.phone}")
                        st.markdown(f"**Email:** {customer.email}")
                        st.markdown(f"**Address:** {customer.address if customer.address else 'N/A'}")
                        st.markdown(f"**Boat Name:** {customer.boat_name if customer.boat_name else 'N/A'}")
                        st.markdown(f"**Customer ID:** `{customer.customer_id}`")

                        customer_jobs = [job for job in manager.jobs.values() if job.customer_id == customer.customer_id]
                        if customer_jobs:
                            st.write("**Associated Jobs:**")
                            for job in sorted(customer_jobs, key=lambda j: datetime.strptime(j.scheduled_datetime, DATETIME_FORMAT), reverse=True):
                                st.info(f"- {job.scheduled_datetime}: {job.service_type} ({job.status}) - Job ID: ...{job.job_id[-6:]}")
                        else:
                            st.write("No associated jobs.")

    # --- Find Customer (Simplified for Streamlit context) ---
    elif menu_choice == "Find Customer":
        st.header("🔍 Find Customer")
        search_term = st.text_input("Enter Customer Name, Phone, or Email to search:").lower()
        results = []
        if search_term: # Only search if there's a term
            for cust_id, customer in manager.customers.items():
                if (search_term in customer.name.lower() or
                    (customer.phone and search_term in customer.phone.lower()) or
                    (customer.email and search_term in customer.email.lower())):
                    results.append(customer)

        if search_term and not results:
            st.info("No customers found matching your search.")
        elif results:
            st.success(f"Found {len(results)} customer(s):")
            for customer in results:
                with st.expander(f"{customer.name} (ID: ...{customer.customer_id[-6:]})"):
                    # (Re-using display from List Customers)
                    st.markdown(f"**Phone:** {customer.phone}")
                    st.markdown(f"**Email:** {customer.email}")
                    st.markdown(f"**Address:** {customer.address if customer.address else 'N/A'}")
                    st.markdown(f"**Boat:** {customer.boat_length}ft {customer.boat_make} {customer.boat_model} (Name: {customer.boat_name if customer.boat_name else 'N/A'})")
                    st.markdown(f"**Customer ID:** `{customer.customer_id}`")


    # --- Add New Job ---
    elif menu_choice == "Add New Job":
        st.header("🗓️ Add New Job")
        if not manager.customers:
            st.warning("No customers available. Please add a customer first.")
            if st.button("Go to Add Customer Page"):
                # Hacky navigation, Streamlit is ideally single-page or uses more complex multi-page app setup
                st.info("Please select 'Add New Customer' from the sidebar.")
            return

        with st.form("add_job_form", clear_on_submit=True):
            customer_list = list(manager.customers.values())
            customer_options = {f"{c.name} ({c.boat_make} {c.boat_model}, ID: ...{c.customer_id[-6:]})": c.customer_id for c in sorted(customer_list, key=lambda c: c.name)}

            if not customer_options: # Should be caught by manager.customers check
                 st.error("Cannot add job: No customers exist.")
                 return

            selected_customer_display_name = st.selectbox("Select Customer*", list(customer_options.keys()), help="Required")
            customer_id = customer_options.get(selected_customer_display_name)

            service_type = st.text_input("Service Type*", help="e.g., Haul Out, Launch, Transport. Required")
            
            # Datetime input
            col_date, col_time = st.columns(2)
            default_date = datetime.now().date()
            default_time = datetime.now().time().replace(second=0, microsecond=0)

            scheduled_date = col_date.date_input("Scheduled Date*", default_date, help="Required")
            scheduled_time = col_time.time_input("Scheduled Time*", default_time, help="Required")
            
            origin_location = st.text_input("Origin Location*", help="e.g., Marina name, address. Required")
            destination_location = st.text_input("Destination Location (if different)")
            
            quoted_price = st.number_input("Quoted Price ($)*", min_value=0.01, value=100.0, format="%.2f", help="Required")
            notes = st.text_area("Additional Notes (optional)")
            
            job_submitted = st.form_submit_button("Add Job")

            if job_submitted:
                if not all([customer_id, service_type, scheduled_date, scheduled_time, origin_location, quoted_price > 0]):
                     st.error("Please fill in all required fields marked with *.")
                else:
                    scheduled_datetime_str = f"{scheduled_date.strftime('%Y-%m-%d')} {scheduled_time.strftime('%H:%M')}"
                    try:
                        job = Job(customer_id, service_type, scheduled_datetime_str, origin_location, destination_location, quoted_price, notes)
                        manager.jobs[job.job_id] = job
                        manager.save_all()
                        customer_name = manager.get_customer_by_id(customer_id).name if manager.get_customer_by_id(customer_id) else "Unknown"
                        st.success(f"Job for '{customer_name}' added successfully! Job ID: {job.job_id}")
                    except ValueError as e: # Catch invalid date format from Job class
                        st.error(f"Error creating job: {e}")
                    except KeyError: # Should not happen if customer_id is from selectbox
                        st.error(f"Error: Customer ID {customer_id} is invalid.")


    # --- List/View Jobs ---
    elif menu_choice == "List/View Jobs":
        st.header("📋 List of Jobs")
        if not manager.jobs:
            st.info("No jobs found.")
        else:
            status_options = ["All"] + Job.VALID_STATUSES
            filter_status = st.selectbox("Filter by status", status_options, key="job_status_filter")

            search_job_query = st.text_input("Search jobs (customer name, service, notes)...", key="job_search_list")

            jobs_to_display = []
            for job_id, job in manager.jobs.items():
                if filter_status != "All" and job.status != filter_status:
                    continue
                
                customer = manager.get_customer_by_id(job.customer_id)
                customer_name = customer.name if customer else "N/A (Customer not found)"

                display_job = True
                if search_job_query:
                    sq = search_job_query.lower()
                    if not (sq in customer_name.lower() or
                            sq in job.service_type.lower() or
                            sq in job.origin_location.lower() or
                            (job.destination_location and sq in job.destination_location.lower()) or
                            sq in job.notes.lower()):
                        display_job = False
                
                if display_job:
                    jobs_to_display.append((job, customer_name))


            if not jobs_to_display:
                st.info(f"No jobs found matching your criteria.")
            else:
                st.write(f"Showing {len(jobs_to_display)} job(s).")
                # Sort jobs by scheduled date
                jobs_to_display.sort(key=lambda item: datetime.strptime(item[0].scheduled_datetime, DATETIME_FORMAT), reverse=True)

                for job, customer_name_for_job in jobs_to_display:
                    expander_title = f"{job.scheduled_datetime} - {job.service_type} for {customer_name_for_job} - Status: {job.status} (ID: ...{job.job_id[-6:]})"
                    with st.expander(expander_title):
                        st.markdown(f"**Job ID:** `{job.job_id}`")
                        st.markdown(f"**Customer:** {customer_name_for_job} (ID: `{job.customer_id}`)")
                        st.markdown(f"**Service:** {job.service_type}")
                        st.markdown(f"**Origin:** {job.origin_location}")
                        st.markdown(f"**Destination:** {job.destination_location if job.destination_location else 'Same as Origin'}")
                        st.markdown(f"**Price:** ${job.quoted_price:.2f}")
                        st.markdown(f"**Status:** `{job.status}`")
                        st.markdown(f"**Notes:** {job.notes if job.notes else 'N/A'}")
                        st.caption(f"Created: {job.created_at} | Last Updated: {job.updated_at}")


    # --- Update Job Status ---
    elif menu_choice == "Update Job Status":
        st.header("🔄 Update Job Status")
        if not manager.jobs:
            st.info("No jobs to update.")
            return

        job_list = list(manager.jobs.values())
        job_options = {}
        for j in sorted(job_list, key=lambda job: datetime.strptime(job.scheduled_datetime, DATETIME_FORMAT), reverse=True):
            customer = manager.get_customer_by_id(j.customer_id)
            customer_name = customer.name if customer else "Unknown Cust."
            job_options[f"{j.scheduled_datetime} - {j.service_type} for {customer_name} (ID: ...{j.job_id[-6:]}) - Current: {j.status}"] = j.job_id
        
        if not job_options:
            st.info("No jobs available to select for update.")
            return

        selected_job_display_name = st.selectbox("Select Job to Update", list(job_options.keys()))

        if selected_job_display_name:
            job_id_to_update = job_options[selected_job_display_name]
            job_to_update = manager.get_job_by_id(job_id_to_update)

            if job_to_update:
                current_status_index = Job.VALID_STATUSES.index(job_to_update.status) if job_to_update.status in Job.VALID_STATUSES else 0
                new_status = st.selectbox("Select New Status", Job.VALID_STATUSES, index=current_status_index, key=f"status_update_{job_id_to_update}")

                if st.button("Confirm Status Update", key=f"btn_update_{job_id_to_update}"):
                    if job_to_update.update_status(new_status):
                        manager.save_all()
                        st.success(f"Job {job_to_update.job_id} status updated to '{new_status}'.")
                        st.experimental_rerun() # Rerun to refresh display/selectbox options
                    else:
                        # This path should ideally not be reached if VALID_STATUSES is used for selectbox
                        st.error(f"Invalid status '{new_status}'. Status not updated.")
            else:
                st.error("Selected job not found. This shouldn't happen.")
        else:
            st.info("Please select a job to update.")

    # --- Manual Save Button in Sidebar ---
    st.sidebar.markdown("---")
    if st.sidebar.button("Save All Data Manually"):
        manager.save_all() # save_all now includes its own success message

# --- Main Execution for Streamlit ---
if __name__ == "__main__":
    # Ensure data files exist or create them empty if they don't
    # This should be fine on Streamlit Cloud for initial writes.
    for data_file in [CUSTOMER_DATA_FILE, JOB_DATA_FILE]:
        if not os.path.exists(data_file):
            try:
                with open(data_file, 'w') as f:
                    json.dump({}, f) # Create an empty JSON object
            except IOError:
                # This error will be caught by load_data if it persists
                pass
    streamlit_main()