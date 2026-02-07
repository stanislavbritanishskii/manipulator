#!/usr/bin/env python3
import json
import os


class SettingsReader:
	def __init__(self, settings_file="settings.json"):
		"""Load settings from JSON file"""
		if not os.path.exists(settings_file):
			raise FileNotFoundError(f"Settings file '{settings_file}' not found")

		with open(settings_file, 'r') as f:
			self.settings = json.load(f)

	# Arm dimensions getters
	def get_base_len(self):
		return self.settings["arm_dimensions"]["base_len"]

	def get_shoulder_len(self):
		return self.settings["arm_dimensions"]["shoulder_len"]

	def get_arm_len(self):
		return self.settings["arm_dimensions"]["arm_len"]

	def get_wrist_len(self):
		return self.settings["arm_dimensions"]["wrist_len"]

	def get_arm_dimensions(self):
		"""Returns all arm dimensions as a tuple (base, shoulder, arm, wrist)"""
		d = self.settings["arm_dimensions"]
		return (d["base_len"], d["shoulder_len"], d["arm_len"], d["wrist_len"])

	# Motor offsets getters
	def get_motor_offset(self, motor_name):
		"""Get offset for a specific motor"""
		return self.settings["motor_offsets"].get(motor_name, 0)

	def get_all_motor_offsets(self):
		"""Returns all motor offsets as a dict"""
		return self.settings["motor_offsets"].copy()

	def get_motor_offsets_list(self):
		"""Returns motor offsets as a list in order:
		[base_rotation, base_angle, elbow, wrist_angle, wrist_rotation, finger1, finger2]"""
		offsets = self.settings["motor_offsets"]
		return [
			offsets["base_rotation"],
			offsets["base_angle"],
			offsets["elbow"],
			offsets["wrist_angle"],
			offsets["wrist_rotation"],
			offsets["finger1"],
			offsets["finger2"]
		]

	# Default position getters
	def get_default_dist(self):
		return self.settings["default_position"]["dist"]

	def get_default_z(self):
		return self.settings["default_position"]["z"]

	def get_default_pitch(self):
		return self.settings["default_position"]["pitch"]

	def get_default_yaw(self):
		return self.settings["default_position"]["yaw"]

	def get_default_roll(self):
		return self.settings["default_position"]["roll"]

	def get_default_gripper(self):
		return self.settings["default_position"]["gripper"]

	def get_default_position(self):
		"""Returns all default position values as a dict"""
		return self.settings["default_position"].copy()

	# Network settings getters
	def get_udp_ip(self):
		return self.settings["network"]["udp_ip"]

	def get_udp_port(self):
		return self.settings["network"]["udp_port"]

	def get_websocket_port(self):
		return self.settings["network"]["websocket_port"]

	def get_http_port(self):
		return self.settings["network"]["http_port"]

	def get_network_settings(self):
		"""Returns all network settings as a dict"""
		return self.settings["network"].copy()

	# Control limits getters
	def get_dist_limits(self):
		return (self.settings["control_limits"]["dist_min"],
				self.settings["control_limits"]["dist_max"])

	def get_z_limits(self):
		return (self.settings["control_limits"]["z_min"],
				self.settings["control_limits"]["z_max"])

	def get_pitch_limits(self):
		return (self.settings["control_limits"]["pitch_min"],
				self.settings["control_limits"]["pitch_max"])

	def get_yaw_limits(self):
		return (self.settings["control_limits"]["yaw_min"],
				self.settings["control_limits"]["yaw_max"])

	def get_roll_limits(self):
		return (self.settings["control_limits"]["roll_min"],
				self.settings["control_limits"]["roll_max"])

	def get_gripper_limits(self):
		return (self.settings["control_limits"]["gripper_min"],
				self.settings["control_limits"]["gripper_max"])

	def get_all_control_limits(self):
		"""Returns all control limits as a dict"""
		return self.settings["control_limits"].copy()

	# Control sensitivity getters
	def get_dist_sensitivity(self):
		return self.settings["control_sensitivity"]["dist"]

	def get_yaw_sensitivity(self):
		return self.settings["control_sensitivity"]["yaw"]

	def get_z_sensitivity(self):
		return self.settings["control_sensitivity"]["z"]

	def get_pitch_sensitivity(self):
		return self.settings["control_sensitivity"]["pitch"]

	def get_roll_sensitivity(self):
		return self.settings["control_sensitivity"]["roll"]

	def get_gripper_sensitivity(self):
		return self.settings["control_sensitivity"]["gripper"]

	def get_all_sensitivities(self):
		"""Returns all sensitivities as a dict"""
		return self.settings["control_sensitivity"].copy()

	# Gripper settings getters
	def get_finger_offset(self):
		return self.settings["gripper"]["finger_offset"]

	# Utility method to get raw settings
	def get_raw_settings(self):
		"""Returns the entire settings dict"""
		return self.settings.copy()


# Example usage
if __name__ == "__main__":
	try:
		settings = SettingsReader()
		print("Arm dimensions:", settings.get_arm_dimensions())
		print("UDP address:", settings.get_udp_ip(), ":", settings.get_udp_port())
		print("Default position:", settings.get_default_position())
		print("Finger offset:", settings.get_finger_offset())
		print("Motor offsets:", settings.get_motor_offsets_list())
	except FileNotFoundError as e:
		print(f"Error: {e}")