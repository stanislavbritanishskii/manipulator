#!/usr/bin/env python3
import socket
import math


def clamp(x, lo, hi):
	if x < lo:
		return lo
	if x > hi:
		return hi
	return x


def rad_to_byte(rad):
	# inverse of your byte_to_rad():
	# 0 rad -> 90
	# -pi/2 -> 0
	# +pi/2 -> 180
	r = float(rad)
	r = clamp(r, -math.pi / 2.0, math.pi / 2.0)
	deg = r * (180.0 / math.pi)           # [-90..+90]
	v = int(round(deg + 90.0))            # [0..180]
	return clamp(v, 0, 180)


class UdpSender:
	def __init__(self, ip, port):
		self.ip = str(ip)
		self.port = int(port)
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.addr = (self.ip, self.port)

	def close(self):
		if self.sock is not None:
			try:
				self.sock.close()
			except Exception:
				pass
			self.sock = None

	def send(self,
			base_rotation,
			shoulder_angle,
			elbow_angle,
			wrist_angle,
			wrist_rotation,
			finger1,
			finger2):
		# All inputs expected in radians, each clamped to [-pi/2, +pi/2]
		payload = bytes([
			rad_to_byte(base_rotation),
			rad_to_byte(shoulder_angle),
			rad_to_byte(elbow_angle),
			rad_to_byte(wrist_angle),
			rad_to_byte(wrist_rotation),
			rad_to_byte(finger1),
			rad_to_byte(finger2),
		])
		return self.sock.sendto(payload, self.addr)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc, tb):
		self.close()


# Example usage:
# if __name__ == "__main__":
# 	s = UdpSender("127.0.0.1", 5005)
# 	s.send(0.0, 0.0, 0.0, 0.0, 0.0, 0.2, -0.2)
# 	s.close()
