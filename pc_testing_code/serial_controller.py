#!/usr/bin/env python3
import sys
import time
import tkinter as tk

try:
	import serial
except ImportError:
	print("Missing dependency: pyserial\nInstall: pip install pyserial", file=sys.stderr)
	sys.exit(1)

FIELDS = [
	("base_rotation", 0),
	("base_angle", 0),
	("elbow_angle", 0),
	("wrist_angle", 0),
	("wrist_rotation", 0),
	("grabber_angle", 0),
]

class SerialSliderUI:
	def __init__(self, port, baud=115200):
		self.ser = serial.Serial(port=port, baudrate=baud, timeout=0)
		time.sleep(0.2)

		self.root = tk.Tk()
		self.root.title("ESP32 Arm Control (6x uint8)")

		self.values = [tk.IntVar(value=init) for (_, init) in FIELDS]
		self.scales = []

		self._send_scheduled = False

		for i, (name, _) in enumerate(FIELDS):
			row = tk.Frame(self.root)
			row.pack(fill="x", padx=10, pady=6)

			lbl = tk.Label(row, text=name, width=16, anchor="w")
			lbl.pack(side="left")

			scale = tk.Scale(
				row,
				from_=0,
				to=180,
				orient="horizontal",
				length=420,
				variable=self.values[i],
				command=self._on_slider_change,
				showvalue=True,
				resolution=1
			)
			scale.pack(side="left", fill="x", expand=True)
			self.scales.append(scale)

		btnrow = tk.Frame(self.root)
		btnrow.pack(fill="x", padx=10, pady=10)

		send_btn = tk.Button(btnrow, text="Send now", command=self.send_packet)
		send_btn.pack(side="left")

		quit_btn = tk.Button(btnrow, text="Quit", command=self.close)
		quit_btn.pack(side="right")

		# Send initial packet once UI is up
		self.root.after(50, self.send_packet)

	def _on_slider_change(self, _unused=None):
		# Tkinter calls this a lot while dragging; coalesce to one send per UI tick.
		if not self._send_scheduled:
			self._send_scheduled = True
			self.root.after(10, self._send_debounced)

	def _send_debounced(self):
		self._send_scheduled = False
		self.send_packet()

	def get_packet_bytes(self):
		out = bytearray(6)
		for i in range(6):
			v = int(self.values[i].get())
			if v < 0:
				v = 0
			if v > 180:
				v = 180
			out[i] = v & 0xFF
		return bytes(out)

	def send_packet(self):
		try:
			packet = self.get_packet_bytes()
			self.ser.write(packet)
			self.ser.flush()
		except Exception as e:
			print("Serial write failed:", e, file=sys.stderr)

	def run(self):
		self.root.protocol("WM_DELETE_WINDOW", self.close)
		self.root.mainloop()

	def close(self):
		try:
			if self.ser is not None and self.ser.is_open:
				self.ser.close()
		except Exception:
			pass
		self.root.destroy()

def main():
	if len(sys.argv) < 2:
		print("Usage: python3 sliders.py <serial_port> [baud]\n"
			  "Example Linux: python3 sliders.py /dev/ttyUSB0\n"
			  "Example macOS: python3 sliders.py /dev/tty.usbserial-XXXX\n"
			  "Example Win:   python3 sliders.py COM5", file=sys.stderr)
		sys.exit(2)

	port = sys.argv[1]
	baud = 115200
	if len(sys.argv) >= 3:
		baud = int(sys.argv[2])

	app = SerialSliderUI(port, baud)
	app.run()

if __name__ == "__main__":
	main()

