import math
from math import pi, cos, sin, acos, atan2, sqrt


class Point:
	def __init__(self, x, y, z):
		self.x = x
		self.y = y
		self.z = z

	def __str__(self):
		return f"{self.x};{self.y};{self.z}"

	def __add__(self, other):
		if type(other) == Point:
			return Point(self.x + other.x, self.y + other.y, self.z + other.z)
		else:
			return Point(self.x + other[0], self.y + other[1], self.z + other[2])

	def __sub__(self, other):
		if type(other) == Point:
			return Point(self.x - other.x, self.y - other.y, self.z - other.z)
		else:
			return Point(self.x - other[0], self.y - other[1], self.z - other[2])

	def __mul__(self, other):
		return Point(self.x * other, self.y * other, self.z * other)

	def norm(self):
		return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)


class Range:
	def __init__(self, start, end):
		self.start = start
		self.end = end

	def __contains__(self, value):
		return self.start <= value <= self.end


def to_degrees(val):
	return val * 180 / math.pi

def _normalize_yaw_dist(yaw, dist):
	# enforce yaw in [0..pi] by wrapping and inverting dist each time we cross a boundary
	while yaw < 0.0:
		yaw += math.pi
		dist = -dist
	while yaw > math.pi:
		yaw -= math.pi
		dist = -dist
	return yaw, dist

class Arm:
	def __init__(self, base_len, shoulder_len, arm_len, wrist_len):
		# lengths are in centimeter
		self.base_len = base_len
		self.shoulder_len = shoulder_len
		self.arm_len = arm_len
		self.wrist_len = wrist_len

		self.base_rotation_range = Range(-pi / 2, pi / 2)
		self.base_angle_range = Range(-pi / 2, pi / 2)
		self.elbow_range = Range(-pi / 2, pi / 2)
		self.wrist_angle_range = Range(-pi / 2, pi / 2)
		self.wrist_rotation_range = Range(-pi / 2, pi / 2)

		self.base_rotation = 0
		self.base_angle = 0
		self.elbow = 0
		self.wrist_angle = 0
		self.wrist_rotation = 0

	def calculate_angles(self, dist, z, pitch, yaw, roll):
		# pitch - nose up or tail up. positive pitches upward, (+Z), θ=0 is horizontal
		#
		# yaw - nose moves from side to side. ψ=0 points along +X, ψ=+90° points along +Y
		#
		# roll - a circular(clockwise or anticlockwise) movement of the body as it moves forward
		yaw, dist = _normalize_yaw_dist(yaw, dist)
		x = cos(yaw) * dist
		y = sin(yaw) * dist
		end_point = Point(x, y, z)
		print(end_point)
		# self.wrist_angle = pitch
		self.wrist_rotation = [roll, roll]
		self.base_rotation = [yaw-pi/2, yaw-pi/2]

		arm_squared = self.arm_len * self.arm_len
		shoulder_squared = self.shoulder_len * self.shoulder_len

		# top end of wrist calculation
		dx = -cos(pitch) * cos(yaw)
		dy = -cos(pitch) * sin(yaw)
		dz = -sin(pitch)
		top_wrist = (end_point) + [dx * self.wrist_len, dy * self.wrist_len, dz * self.wrist_len]
		point = top_wrist - Point(0, 0, self.base_len)
		dist = point.norm()
		min_dist = math.sqrt(
			shoulder_squared + arm_squared - 2.0 * self.shoulder_len * self.arm_len * cos(pi/4)
		)
		print("top wrist before norm ", top_wrist)

		if dist > self.arm_len + self.shoulder_len:
			point *= (self.arm_len + self.shoulder_len) / dist
			top_wrist = point + Point(0,0,self.base_len)

		if dist < min_dist:
			point *= min_dist / dist
			top_wrist = point + Point(0,0,self.base_len)



		print("top wrist ", top_wrist)
		# top_wrist = end_point

		# shoulder angle calculation
		shoulder_point = Point(0, 0, self.base_len)
		arm_squared = self.arm_len * self.arm_len
		shoulder_squared = self.shoulder_len * self.shoulder_len

		third = (top_wrist - shoulder_point).norm()  # - distance between shoulder joint and wrist joint
		third_squared = third * third

		shoulder_wrist_diff = top_wrist - shoulder_point

		swd = shoulder_wrist_diff  # for short

		shoulder_wrist_pitch = atan2(swd.z, sqrt(swd.x ** 2 + swd.y ** 2))
		print("shoulder wrist pitch", shoulder_wrist_pitch)

		shoulder_arm_triangle_angle_cos = (shoulder_squared + third_squared - arm_squared) / (
				2 * self.shoulder_len * third)

		if shoulder_arm_triangle_angle_cos > 1:
			shoulder_arm_triangle_angle_cos = 1
		if shoulder_arm_triangle_angle_cos < -1:
			shoulder_arm_triangle_angle_cos = -1
		shoulder_arm_triangle_angle = acos(shoulder_arm_triangle_angle_cos)

		print("shoulder_arm_triangle_angle ", shoulder_arm_triangle_angle)
		#
		# shoulder_angle = shoulder_wrist_pitch - shoulder_arm_triangle_angle - pi / 2
		shoulder_angles = [-(shoulder_wrist_pitch + shoulder_arm_triangle_angle - pi/2),
						   pi/2 - shoulder_wrist_pitch + shoulder_arm_triangle_angle]
		elbow_angles = []
		wrist_angles = []
		# elbow angle with law of cosine
		elbow_cos = (shoulder_squared + arm_squared - third_squared) / (2 * self.shoulder_len * self.arm_len)
		if elbow_cos > 1:
			elbow_cos = 1
		if elbow_cos < -1:
			elbow_cos = -1
		elbow_angle = acos(elbow_cos)
		for i in range(len(shoulder_angles)):

		# elbow angle adjustment
			real_shoulder_pitch = pi / 2 - shoulder_angles[i]
			print("shoulder pitch ", real_shoulder_pitch)

			dx = cos(real_shoulder_pitch) * cos(yaw)
			dy = cos(real_shoulder_pitch) * sin(yaw)
			dz = sin(real_shoulder_pitch)
			elbow_point = shoulder_point + [dx * self.shoulder_len, dy * self.shoulder_len, dz * self.shoulder_len]
			print("elbow_point", elbow_point)
			elbow_to_wrist = top_wrist - elbow_point
			print("distnace from elbow joint to wrist top", elbow_to_wrist.norm())
			if (elbow_to_wrist.norm() > self.arm_len + 0.1 or elbow_to_wrist.norm() < self.arm_len - 0.1):
				# print("reversing shoulder angle")
				shoulder_angles[i] *= -1
				real_shoulder_pitch = pi / 2 - shoulder_angles[i]
				# print("shoulder pitch ", real_shoulder_pitch)

				dx = cos(real_shoulder_pitch) * cos(yaw)
				dy = cos(real_shoulder_pitch) * sin(yaw)
				dz = sin(real_shoulder_pitch)
				elbow_point = shoulder_point + [dx * self.shoulder_len, dy * self.shoulder_len, dz * self.shoulder_len]
				print("elbow_point", elbow_point)
				elbow_to_wrist = elbow_point - top_wrist
				print("distnace from elbow joint to wrist top", elbow_to_wrist.norm())
			etw = elbow_to_wrist # for short

			# if shoulder_wrist_pitch < real_shoulder_pitch:
			# 	elbow_angles.append(pi - elbow_angle)
			# else:
			# 	elbow_angles.append(-pi + elbow_angle)

			elbow_angles.append(-pi + elbow_angle)
			elbow_pitch = pi / 2 - shoulder_angles[i] - elbow_angles[i]
			dx = cos(elbow_pitch) * cos(yaw)
			dy = cos(elbow_pitch) * sin(yaw)
			dz = sin(elbow_pitch)
			calculated_top_wrist = elbow_point + [dx * self.arm_len, dy * self.arm_len, dz * self.arm_len]
			if (calculated_top_wrist - top_wrist).norm() > 0.1:
				elbow_angles[i] *= -1
				elbow_pitch = pi / 2 - shoulder_angles[i] - elbow_angles[i]

			print("elbow pitch", elbow_pitch)
			print((calculated_top_wrist - top_wrist).norm())

			wrist_angles.append(-pitch + elbow_pitch)



		self.base_angle = shoulder_angles
		self.elbow = elbow_angles
		self.wrist_angle = wrist_angles

	def get_angles(self):
		return self.base_rotation, self.base_angle, self.elbow, self.wrist_angle, self.wrist_rotation


if __name__ == "__main__":
	import udp_sender
	import sys
	import time

	args = sys.argv
	if len(args) < 6:
		args = (-10, 30, pi, pi / 2, 0)
	else:
		args = list(map(float, args[1:]))

	arm = Arm(10, 30, 20, 8)
	sender = udp_sender.UdpSender("127.0.0.1", 5005)
	arm.calculate_angles(*args)
	angles = list(map(lambda x: x[0], arm.get_angles())) + [0, 00]
	angles[2] -= pi/4
	if any(map (lambda x: x > pi/2 or x < -pi/2,angles)):
		angles = list(map(lambda x: x[1], arm.get_angles())) + [0, 00]
		angles[2]-= pi/4

	sender.send(*angles)
	# sender.send(0,-0,0,0,0,0,0)
	print(angles)
	exit()
