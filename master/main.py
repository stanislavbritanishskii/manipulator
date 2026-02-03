from receiver import UDPJPEGReceiver
from image_funcs import *
import cv2
import argparse

parser = argparse.ArgumentParser(description='UDP JPEG Receiver Test')
parser.add_argument('--port', type=int, default=5000)
parser.add_argument('--timeout', type=float, default=0.5)
args = parser.parse_args()

receiver = UDPJPEGReceiver(bind_port=args.port, frame_timeout=args.timeout)
receiver.start()

print("Displaying frames. Press 'q' or ESC to quit, 's' for stats")

K = np.array( [[1.46157610e+03, 0.00000000e+00, 1.04636446e+03],
 [0.00000000e+00, 1.45636911e+03, 5.20527437e+02],
 [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]
, dtype=np.float64)

D = np.array([[-0.09053617,  0.07942517, -0.00160313,  0.00079444, -0.03308155]], dtype=np.float64)  # or your real distortion coeffs
marker_len_m = 0.094
try:
	while True:
		frames = receiver.get_latest_frames()

		# Display each camera in its own window
		for camera_id, (timestamp, img) in frames.items():
			window_name = f"Camera {camera_id}"
			img, params = aruco_detect_draw_pose(img, K, D, marker_len_m, dict_id=cv2.aruco.DICT_4X4_100)
			img = scale_image(img, 0.5)
			cv2.imshow(window_name, img)

		key = cv2.waitKey(1) & 0xFF
		if key == ord('q') or key == 27:
			break
		elif key == ord('s'):
			receiver.print_stats()

except KeyboardInterrupt:
	print("\nStopping...")
finally:
	receiver.stop()
	cv2.destroyAllWindows()
