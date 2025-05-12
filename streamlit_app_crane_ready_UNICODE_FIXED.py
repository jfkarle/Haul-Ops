import streamlit as st

        def add_job_page(self, job, explanation):
            self.add_page()
            self.set_font("Arial", size=12)
            self.cell(200, 10, txt=f"Customer: {job['Customer']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Boat Type: {job['Boat Type']} ({job['Boat Length']} ft, {job['Mast']})".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Service: {job['Service']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Origin: {job['Origin']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Ramp: {job['Ramp']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Date: {job['Date']}  Time: {job['Start']}–{job['End']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"Truck: {job['Truck']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.cell(200, 10, txt=f"High Tide: {job['High Tide']}".encode("latin-1", "replace").decode("latin-1"), ln=True)
            self.ln(5)
            self.set_font("Arial", style="B", size=12)
            self.cell(200, 10, txt="Scheduling Reasoning:", ln=True)
            self.set_font("Arial", size=11)
            for line in explanation.strip().split("\n"):
                safe_line = line.encode("latin-1", "replace").decode("latin-1")
                self.multi_cell(0, 8, safe_line)

st.write('Bootloader')
