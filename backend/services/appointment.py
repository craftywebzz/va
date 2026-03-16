from datetime import datetime, timedelta
import uuid

class AppointmentService:
    def __init__(self):
        # In-memory storage for demonstration (can be swapped for DB)
        self.appointments = []
        self.doctors = [
            {"id": "d1", "name": "Dr. Sharma", "specialty": "General Physician"},
            {"id": "d2", "name": "Dr. Priya", "specialty": "Pediatrician"},
            {"id": "d3", "name": "Dr. Karthik", "specialty": "Cardiologist"}
        ]
        self.working_hours = (9, 17) # 9 AM to 5 PM

    def get_available_slots(self, doctor_id, date_str):
        # Generate 30-min slots
        slots = []
        start_time = datetime.strptime(f"{date_str} {self.working_hours[0]}:00", "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(f"{date_str} {self.working_hours[1]}:00", "%Y-%m-%d %H:%M")
        
        current = start_time
        while current < end_time:
            slot_str = current.strftime("%H:%M")
            # Check if occupied
            is_occupied = any(
                a for a in self.appointments 
                if a["doctor_id"] == doctor_id and a["date"] == date_str and a["time"] == slot_str
            )
            if not is_occupied:
                slots.append(slot_str)
            current += timedelta(minutes=30)
            
        return slots

    def list_doctors(self):
        """
        Return the list of doctors. Useful for disambiguation flows.
        """
        return self.doctors

    def book_appointment(self, patient_id, doctor_id, date_str, time_str, mode="in_person"):
        # Validation
        appointment_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if appointment_time < datetime.now():
            return {"success": False, "message": "Cannot book in the past."}
            
        # Check conflict
        conflict = any(
            a for a in self.appointments 
            if a["doctor_id"] == doctor_id and a["date"] == date_str and a["time"] == time_str
        )
        if conflict:
            return {"success": False, "message": "Slot already booked."}
            
        appointment = {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "date": date_str,
            "time": time_str,
            "mode": mode,
            "status": "confirmed"
        }
        self.appointments.append(appointment)
        return {"success": True, "appointment": appointment}

    def find_patient_appointments(self, patient_id):
        """
        Return all future appointments for a given patient.
        """
        now = datetime.now()
        upcoming = []
        for a in self.appointments:
            start = datetime.strptime(f"{a['date']} {a['time']}", "%Y-%m-%d %H:%M")
            if a["patient_id"] == patient_id and start >= now and a["status"] == "confirmed":
                upcoming.append(a)
        return upcoming

    def reschedule_appointment(self, appointment_id, new_date_str, new_time_str):
        """
        Reschedule an existing appointment, enforcing the same conflict rules.
        """
        # Locate appointment
        target = None
        for a in self.appointments:
            if a["id"] == appointment_id:
                target = a
                break
        if not target:
            return {"success": False, "message": "Appointment not found."}

        new_time = datetime.strptime(f"{new_date_str} {new_time_str}", "%Y-%m-%d %H:%M")
        if new_time < datetime.now():
            return {"success": False, "message": "Cannot reschedule to the past."}

        # Check conflict for same doctor/new slot
        conflict = any(
            a for a in self.appointments
            if a["doctor_id"] == target["doctor_id"]
            and a["date"] == new_date_str
            and a["time"] == new_time_str
            and a["id"] != appointment_id
            and a["status"] == "confirmed"
        )
        if conflict:
            return {"success": False, "message": "Requested slot is already booked."}

        # Update appointment
        target["date"] = new_date_str
        target["time"] = new_time_str
        return {"success": True, "appointment": target}

    def cancel_appointment(self, appointment_id):
        for i, a in enumerate(self.appointments):
            if a["id"] == appointment_id:
                self.appointments.pop(i)
                return {"success": True}
        return {"success": False, "message": "Appointment not found."}
