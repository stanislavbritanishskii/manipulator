from receiver import UDPJPEGReceiver
from image_funcs import *
from settings_reader import load_camera_intrinsics_json, get_intrinsics_for_camera

from coordinates_transformation import ArucoGroundFrame

import cv2
import argparse
import numpy as np


def main():
	parser = argparse.ArgumentParser(description='UDP JPEG Receiver Test')
	parser.add_argument('--port', type=int, default=5000)
	parser.add_argument('--timeout', type=float, default=0.5)
	parser.add_argument('--settings', type=str, default='settings.json')
	parser.add_argument('--marker-len', type=float, default=0.094)
	parser.add_argument('--ground-id', type=int, default=0)
	args = parser.parse_args()

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
						cv2.putText(vis, "GROUND SET", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
					else:
						cv2.putText(vis, "GROUND NOT SET (marker not found)", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

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
