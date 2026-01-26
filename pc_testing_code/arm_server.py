import asyncio
import websockets
import json
from math import pi
import sys
import os
from aiohttp import web

# Import your existing modules
from IK import Arm
import udp_sender
from settings_reader import SettingsReader


class ArmController:
	def __init__(self, settings):
		"""Initialize arm controller with settings"""
		self.settings = settings

		# Initialize arm with dimensions from settings
		base_len, shoulder_len, arm_len, wrist_len = settings.get_arm_dimensions()
		self.arm = Arm(base_len, shoulder_len, arm_len, wrist_len)

		# Initialize UDP sender with settings
		self.sender = udp_sender.UdpSender(
			settings.get_udp_ip(),
			settings.get_udp_port()
		)

		# Load motor offsets
		self.motor_offsets = settings.get_motor_offsets_list()

		# Current state values from default position
		self.dist = settings.get_default_dist()
		self.z = settings.get_default_z()
		self.pitch = settings.get_default_pitch()
		self.yaw = settings.get_default_yaw()
		self.roll = settings.get_default_roll()
		self.gripper = settings.get_default_gripper()

		# Load control sensitivities
		sensitivities = settings.get_all_sensitivities()
		self.dist_sensitivity = sensitivities["dist"]
		self.yaw_sensitivity = sensitivities["yaw"]
		self.z_sensitivity = sensitivities["z"]
		self.pitch_sensitivity = sensitivities["pitch"]
		self.roll_sensitivity = sensitivities["roll"]
		self.gripper_sensitivity = sensitivities["gripper"]

		# Load control limits
		self.dist_limits = settings.get_dist_limits()
		self.z_limits = settings.get_z_limits()
		self.pitch_limits = settings.get_pitch_limits()
		self.yaw_limits = settings.get_yaw_limits()
		self.roll_limits = settings.get_roll_limits()
		self.gripper_limits = settings.get_gripper_limits()

		# Load finger offset
		self.finger_offset = settings.get_finger_offset()

	def update_from_joysticks(self, joy_left, joy_slider, joy_right, gripper_slider):
		"""
		Update arm state from joystick inputs
		joy_left: {x, y} - controls yaw (x) and dist (y)
		joy_slider: {y} - controls height (z)
		joy_right: {x, y} - controls roll (x) and pitch (y)
		gripper_slider: {x} - controls gripper (last two parameters)
		"""
		# Left joystick: yaw (x) and distance (y)
		self.dist += -joy_left['y'] * self.dist_sensitivity
		self.dist = max(self.dist_limits[0], min(self.dist_limits[1], self.dist))

		# Yaw control with wrapping
		self.yaw -= joy_left['x'] * self.yaw_sensitivity

		# Handle yaw wrapping and distance inversion
		if self.yaw > pi:
			self.yaw = pi
			# self.yaw = self.yaw - pi
			# self.dist = -self.dist
		elif self.yaw < 0:
			self.yaw = 0
			# self.yaw = self.yaw + pi
			# self.dist = -self.dist

		# Ensure distance is positive after inversion
		if self.dist < 0:
			self.dist = abs(self.dist)

		# Slider: height (z)
		self.z += -joy_slider['y'] * self.z_sensitivity
		self.z = max(self.z_limits[0], min(self.z_limits[1], self.z))

		# Right joystick: pitch (y) and roll (x)
		self.pitch += -joy_right['y'] * self.pitch_sensitivity
		self.pitch = max(self.pitch_limits[0], min(self.pitch_limits[1], self.pitch))

		self.roll += joy_right['x'] * self.roll_sensitivity
		self.roll = max(self.roll_limits[0], min(self.roll_limits[1], self.roll))

		# Gripper slider: controls gripper angle
		self.gripper += gripper_slider['x'] * self.gripper_sensitivity
		self.gripper = max(self.gripper_limits[0], min(self.gripper_limits[1], self.gripper))

	def send_to_arm(self):
		"""Calculate angles and send to arm"""
		try:
			self.arm.calculate_angles(self.dist, self.z, self.pitch, self.yaw, self.roll)
			angles = list(map(lambda x: x[0], self.arm.get_angles())) + [0, 0]

			# Check if angles are valid, otherwise use alternative solution
			# limits_bottom = [-pi/2, -pi/2, -pi / 4, -pi / 2]
			# limits_top = [pi/2, pi/2, 3 * pi/4, pi/2]
			# limits_bottom = [-pi / 2, -pi / 2, -3 * pi / 4, -pi / 2]
			# limits_top = [pi / 2, pi / 2,  pi / 4, pi / 2]
			# if any(map(lambda x: angles[x] > limits_top[x] or angles[x] < limits_bottom[x], range(4))):
			angles[2] -= pi / 4

			if any(map(lambda x: x > pi / 2 or x < -pi / 2, angles[:-4])):
				angles = list(map(lambda x: x[1], self.arm.get_angles())) + [0, 0]
				angles[2] -= pi/4

			# if not any(map(lambda x: angles[x] > limits_top[x] or angles[x] < limits_bottom[x], range(4))):
			if not any(map(lambda x: x > pi / 2 or x < -pi / 2, angles[:-4])):

				# Replace last two values with gripper control
				# Gripper is 0-180 degrees, but rad_to_byte expects -90 to +90 degrees
				# So we map: gripper 0-180° -> -90 to +90° -> -π/2 to +π/2 radians
				finger1_degrees = self.gripper - 90.0
				finger2_degrees = (180.0 - self.gripper + self.finger_offset) - 90.0

				angles[-2] = finger1_degrees * pi / 180.0
				angles[-1] = finger2_degrees * pi / 180.0
				print(angles)
				# Apply motor offsets to all angles
				for i in range(len(angles)):
					angles[i] += self.motor_offsets[i]

				self.sender.send(*angles)
			else:
				print("all angles are bad")
				print(angles)
			return angles
		except Exception as e:
			print(f"Error calculating/sending angles: {e}")
			return None

	def get_state(self):
		"""Return current state for debugging"""
		return {
			'dist': self.dist,
			'z': self.z,
			'pitch': self.pitch,
			'yaw': self.yaw,
			'roll': self.roll,
			'gripper': self.gripper
		}


async def handle_websocket(websocket, controller):
	"""Handle WebSocket connection from client"""
	print("Client connected")
	try:
		async for message in websocket:
			data = json.loads(message)

			# Update controller with joystick data
			controller.update_from_joysticks(
				data.get('joy1', {'x': 0, 'y': 0}),
				data.get('slider', {'y': 0}),
				data.get('joy2', {'x': 0, 'y': 0}),
				data.get('gripperSlider', {'x': 0})
			)

			# Send updated angles to arm
			angles = controller.send_to_arm()

			# Send state back to client for display
			state = controller.get_state()
			if angles:
				state['angles'] = angles
			await websocket.send(json.dumps(state))

	except websockets.exceptions.ConnectionClosed:
		print("Client disconnected")
	except Exception as e:
		print(f"Error: {e}")


async def http_handler(request):
	"""Serve the HTML file"""
	html_path = os.path.join(os.path.dirname(__file__), 'arm_control.html')
	if os.path.exists(html_path):
		with open(html_path, 'r') as f:
			return web.Response(text=f.read(), content_type='text/html')
	else:
		return web.Response(text='arm_control.html not found', status=404)


async def main():
	# Get settings file path from command line argument
	if len(sys.argv) < 2:
		print("Usage: python3 arm_server.py <settings_file>")
		print("Example: python3 arm_server.py settings.json")
		sys.exit(1)

	settings_file = sys.argv[1]

	# Load settings
	try:
		settings = SettingsReader(settings_file)
		print(f"Loaded settings from: {settings_file}")
	except FileNotFoundError as e:
		print(f"Error: {e}")
		print(f"Please ensure '{settings_file}' exists")
		sys.exit(1)
	except json.JSONDecodeError as e:
		print(f"Error parsing JSON in '{settings_file}': {e}")
		sys.exit(1)

	controller = ArmController(settings)

	# Start WebSocket server
	ws_server = await websockets.serve(
		lambda ws: handle_websocket(ws, controller),
		"0.0.0.0",
		settings.get_websocket_port()
	)

	# Start HTTP server
	app = web.Application()
	app.router.add_get('/', http_handler)
	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, '0.0.0.0', settings.get_http_port())
	await site.start()

	print("=" * 50)
	print("Server started successfully!")
	print("=" * 50)
	print(f"WebSocket server: ws://localhost:{settings.get_websocket_port()}")
	print(f"HTTP server: http://localhost:{settings.get_http_port()}")
	print(f"UDP target: {settings.get_udp_ip()}:{settings.get_udp_port()}")
	print("")
	print(f"Open http://localhost:{settings.get_http_port()} in your browser")
	print("=" * 50)

	await asyncio.Future()  # Run forever


if __name__ == "__main__":
	asyncio.run(main())