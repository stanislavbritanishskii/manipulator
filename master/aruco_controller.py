from image_funcs import _rotmat_to_rpy_zyx
from receiver import UDPJPEGReceiver
from image_funcs import *
from settings_reader import load_camera_intrinsics_json, get_intrinsics_for_camera

from coordinates_transformation import ArucoGroundFrame

import cv2
import argparse
import numpy as np
from IK import Arm
from arm_settings_reader import SettingsReader
import udp_sender
import math
from math import pi


def calculate_desired_arm_position(pose: dict):
	"""
	pose is expected to contain:
		- pose["t_g_m"] : (3,) translation [x,y,z] in ground coords
		- pose["R_g_m"] : (3,3) rotation matrix (preferred)
		  OR pose["rvec_g_m"] : (3,) Rodrigues vector (fallback)

	Returns:
		Whatever self.calculate_angles(...) returns, or None if x <= 0.
	"""

	t = pose.get("t_g_m", None)
	if t is None:
		return None

	t = np.asarray(t, dtype=np.float64).reshape(3)
	x = float(t[0])
	y = float(t[1])
	z = float(t[2])

	# Function exists only for x > 0
	if x <= 0.0:
		return None

	# dist in XY plane
	dist = math.sqrt(x * x + y * y)

	# yaw from position
	yaw = math.atan2(x, y)

	# pitch/roll from marker orientation (in ground coords)
	R = pose.get("R_g_m", None)
	if R is None:
		rvec = pose.get("rvec_g_m", None)
		if rvec is None:
			return None
		R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).reshape(3, 1))

	roll, pitch, _yaw_from_R = _rotmat_to_rpy_zyx (R)

	# Use pitch + roll from marker, yaw from position
	return dist, z, -pitch, pi-yaw, -roll


def main():
	parser = argparse.ArgumentParser(description='UDP JPEG Receiver Test')
	parser.add_argument('--port', type=int, default=5000)
	parser.add_argument('--timeout', type=float, default=0.5)
	parser.add_argument('--settings', type=str, default='settings.json')
	parser.add_argument('--marker-len', type=float, default=0.094)
	parser.add_argument('--ground-id', type=int, default=0)
	parser.add_argument('--arm-settings', type=str, default="arm_settings.json")

	args = parser.parse_args()
	settings = SettingsReader(args.arm_settings)
	base_len, shoulder_len, arm_len, wrist_len = settings.get_arm_dimensions()
	arm = Arm(base_len, shoulder_len, arm_len, wrist_len)
	sender = udp_sender.UdpSender(
		settings.get_udp_ip(),
		settings.get_udp_port()
	)
	motor_offsets = settings.get_motor_offsets_list()

	intrinsics_map = load_camera_intrinsics_json(args.settings)

	receiver = UDPJPEGReceiver(bind_port=args.port, frame_timeout=args.timeout)
	receiver.start()

	ground = ArucoGroundFrame(dict_id=cv2.aruco.DICT_4X4_100)

	print("Displaying frames. Press 'q' or ESC to quit, 's' for stats, SPACE to set ground")

	try:
		while True:
			frames = receiver.get_latest_frames()

			key = cv2.waitKey(1) & 0xFF
			do_set_ground = (key == 32)

			# Display each camera in its own window
			for camera_id, (timestamp, img) in frames.items():
				K, D = get_intrinsics_for_camera(intrinsics_map, camera_id)
				if K is None or D is None:
					window_name = f"Camera {camera_id} (no intrinsics)"
					img_disp = scale_image(img, 0.5)
					cv2.imshow(window_name, img_disp)
					continue

				window_name = f"Camera {camera_id}"

				if do_set_ground:
					vis, ok = ground.set_ground(
						img,
						ground_marker_id=args.ground_id,
						K=K,
						D=D,
						marker_length=args.marker_len,
						draw=True
					)
					if ok:
						cv2.putText(vis, "GROUND SET", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2,
									cv2.LINE_AA)
					else:
						cv2.putText(vis, "GROUND NOT SET (marker not found)", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
									(0, 0, 255), 2, cv2.LINE_AA)

					cv2.imshow(window_name, vis)
				else:
					# If ground is set -> show markers in ground coordinates.
					# If ground is not set yet -> fall back to camera-coordinates drawing (your existing function).
					if ground.R_g_c is not None:
						vis, poses = ground.detect_in_ground(
							img,
							K=K,
							D=D,
							marker_length=args.marker_len,
							draw=True,
							include_ground=True
						)

						id_0_pose = poses.get(0)
						print(id_0_pose)
						if id_0_pose :
							pos = calculate_desired_arm_position(id_0_pose)


							if pos :
								print("distance = ", pos[0], "height = ", pos[1], "pitch = ", pos[2], "yaw = ", pos[3],
									  "roll = ", pos[4])

								arm.calculate_angles(*pos)
								angles = list(map(lambda x: x[0], arm.get_angles())) + [0, 0]
								angles[2] -= pi / 4
								if any(map(lambda x: x > pi / 2 or x < -pi / 2, angles[:-4])):
									angles = list(map(lambda x: x[1], arm.get_angles())) + [0, 0]
									angles[2] -= pi / 4
								if not any(map(lambda x: x > pi / 2 or x < -pi / 2, angles[:-4])):
								# Replace last two values with gripper control
								# Gripper is 0-180 degrees, but rad_to_byte expects -90 to +90 degrees
								# So we map: gripper 0-180° -> -90 to +90° -> -π/2 to +π/2 radians
									finger1_degrees = 45
									finger2_degrees = 45
									angles[-2] = finger1_degrees * pi / 180.0
									angles[-1] = finger2_degrees * pi / 180.0
									angles[1] *= 180 / 270
									print(angles)
									# Apply motor offsets to all angles
									for i in range(len(angles)):
										angles[i] += motor_offsets[i]
									sender.send(*angles)
								else:
									print("error calculating angles")


					else:
						vis, poses = aruco_detect_draw_pose_cam_coordinates(
							img,
							K,
							D,
							args.marker_len,
							dict_id=cv2.aruco.DICT_4X4_100
						)

					cv2.imshow(window_name, vis)

			if key == ord('q') or key == 27:
				break
			elif key == ord('s'):
				receiver.print_stats()

	except KeyboardInterrupt:
		print("\nStopping...")
	finally:
		receiver.stop()
		cv2.destroyAllWindows()


if __name__ == "__main__":
	main()
