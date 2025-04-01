import tkinter as tk
from tkinter import ttk
import serial
import threading
import time
from datetime import datetime
import sqlite3
import re
import serial.tools.list_ports
import requests
import sys
import os 

class AttendanceSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID Attendance System")
        self.root.geometry("800x600")
        self.root.configure(bg="#f0f0f0")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.system_label = tk.Label(self.root, text="RFID Attendance System", font=('Arial', 22, 'bold'), bg="#d9eaf5", bd=2, relief="solid", anchor="w")
        self.system_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.time_label = tk.Label(self.root, font=('Arial', 20, 'bold'), bg="#d9eaf5", bd=2, relief="solid", anchor="e")
        self.time_label.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="e")
        self.update_time_label()

        self.logs_frame = tk.Frame(self.root, width=706, height=120, bg="red", bd=2, relief="solid")
        self.logs_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.style = ttk.Style()
        self.style.configure("Treeview", font=('Arial', 17), padding=(5, 5), rowheight=55)
        self.style.configure("Treeview.Heading", font=('Arial', 20, 'bold'))
        self.style.configure("Treeview.Even", background="#e8f2fe")  # Even row color
        self.style.configure("Treeview.Odd", background="#ffffff")  # Odd row color

        self.tree = ttk.Treeview(self.logs_frame, columns=("Name", "Time In", "Time Out"), show="headings", height=10, style="Treeview")
        self.tree.heading("Name", text="Name", anchor="center")
        self.tree.heading("Time In", text="Time In", anchor="center")
        self.tree.heading("Time Out", text="Time Out", anchor="center")

        self.tree.column("Name", width=250, anchor="center")
        self.tree.column("Time In", width=250, anchor="center")
        self.tree.column("Time Out", width=250, anchor="center")

        self.tree.pack(fill="both", expand=True)

        
        self.baud_rate = 9600   # ESP32's default baud rate is often 115200
        self.serial_port = self.find_serial_port()
        self.ser = None
        self.connect_serial()

        self.serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        self.serial_thread.start()
        self.update_logs()
        self.hex_pattern = re.compile(r"([0-9A-Fa-f]+)")
        self.receive_hex_pattern = re.compile(r"Received Hexcode:\s*([0-9A-Fa-f]+)", re.IGNORECASE)

        # EmailJS setup (Hardcoded, NOT recommended for production)
        self.email_service_id = "service_9zbj8qj"
        self.email_template_id = "template_dgjrz3d"
        self.email_user_id = "Dj3EBJY39okL6yTPP"
        self.reply_to_email = "brealwinkorogoki@gmail.com"  # Your reply-to email

    def get_db_path(self):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, 'attendance.db') 
        return 'attendance.db'  





    def find_serial_port(self):
        """Finds the first available serial port."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "COM" in port.device:
                print(f"Found Serial Port: {port.device}")
                return port.device
        print("No available COM port found.")
        return None
    

    def connect_serial(self):
        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            print("Serial connection established.")
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            self.ser = None

    def read_serial_data(self):
        if self.ser is None:
            return
        while True:
            try:
                if self.ser.in_waiting:
                    raw_line = self.ser.readline()
                    line = raw_line.decode("utf-8", errors='ignore').strip()
                    match = self.receive_hex_pattern.search(line)
                    if match:
                        hex_code = match.group(1)
                        print(f"Hex Code Received: {hex_code}")
                        self.process_rfid_data(hex_code)
                    else:
                        print(f"Line from ESP32: {line} (No hex code found)")

            except serial.SerialException as e:
                print(f"Serial communication error: {e}")
                self.connect_serial()
            except UnicodeDecodeError:
                print("UnicodeDecodeError occured")
            except Exception as e:
                print(f"An error occurred: {e}")
            time.sleep(0.1)

    def process_rfid_data(self, rfid_data):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_info = self.get_user_info(rfid_data)
        if user_info:
            name, email = user_info
            if self.check_time_out(name):
                self.insert_time_out(name, timestamp)
                self.update_logs()
                self.send_email(email, name, timestamp, "Time Out")
                self.ser.write(('success' + '\n').encode())
                self.Zshow_message()
            else:
                self.insert_log(name, timestamp)
                self.update_logs()
                self.send_email(email, name, timestamp, "Time In")
                self.ser.write(('success' + '\n').encode())
                self.Zshow_message()
        else:
            print("Hex code not found in the database.")
            self.ser.write(('failed' + '\n').encode())
            self.show_message()

    def show_message(self):
        popup = tk.Toplevel()
        popup.title("Notice")
        popup.geometry("200x100")
        tk.Label(popup, text="Invalid ID").pack(expand=True)
        popup.after(3000, popup.destroy)

    def Zshow_message(self):
        popup = tk.Toplevel()
        popup.title("Notice")
        popup.geometry("200x100")
        tk.Label(popup, text="Valid ID").pack(expand=True)
        popup.after(3000, popup.destroy)


    def get_user_info(self, rfid_data):
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, email FROM Users WHERE hexcode=?", (rfid_data,))
        result = cursor.fetchone()
        conn.close()
        return result

    def insert_log(self, name, timestamp):
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO logs (name, time_in) VALUES (?, ?)", (name, timestamp))
        conn.commit()
        conn.close()

    def insert_time_out(self, name, timestamp):
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE logs SET time_out = ? WHERE name = ? AND time_out IS NULL", (timestamp, name))
        conn.commit()
        conn.close()

    def update_logs(self):
        self.tree.delete(*self.tree.get_children())
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, time_in, time_out FROM logs ORDER BY time_in DESC")
        logs = cursor.fetchall()
        for i, (name, time_in, time_out) in enumerate(logs):
            time_in_formatted = self.format_time(time_in)
            time_out_formatted = self.format_time(time_out) if time_out else ""
            tag = "even" if i % 2 == 0 else "odd"  # Apply even/odd tags
            self.tree.insert("", "end", values=(name, time_in_formatted, time_out_formatted), tags=(tag,))
        conn.close()

    def update_time_label(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time_label)

    def on_close(self):
        if self.ser:
            self.ser.close()
        self.root.destroy()

    def check_time_out(self, name):
        db = self.get_db_path()
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT time_out FROM logs WHERE name = ? AND time_out IS NULL", (name,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def format_time(self, time_str):
        if not time_str:
            return ""
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y %I:%M %p")

    def send_email(self, recipient_email, name, timestamp, event_type):
        formatted_time = self.format_time(timestamp)
        message = f"Dear {name},\n\nYou have successfully {event_type} at {formatted_time}."

        payload = {
            "service_id": self.email_service_id,
            "template_id": self.email_template_id,
            "user_id": self.email_user_id,
            "template_params": {
                "to_name": name,
                "from_name": "RFID System",
                "message": message,
                "to_email": recipient_email,
                "reply_to": self.reply_to_email
            }
        }

        try:
            response = requests.post("https://api.emailjs.com/api/v1.0/email/send", json=payload)
            response.raise_for_status()
            print("Email sent successfully!")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send email: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AttendanceSystem(root)
    root.mainloop()
