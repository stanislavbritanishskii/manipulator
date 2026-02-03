import cv2
import numpy as np

class CameraCalibratorChessboard:
	def __init__(
		self,
		board_size,				# (cols, rows) inner corners, e.g. (9, 6)
		square_size,			# meters (or any unit)
		use_sb=True,			# try findChessboardCornersSB first
		min_frames=5			# start calibrating after this many successful detections
	):
		self.board_size = (int(board_size[0]), int(board_size[1]))
		self.square_size = float(square_size)
		self.use_sb = bool(use_sb)
		self.min_frames = int(min_frames)

		# Collected calibration data
		self.objpoints = []		# list of (N,3)
		self.imgpoints = []		# list of (N,1,2)
		self.image_size = None	# (w,h)

		# Current estimate
		self.K = None
		self.D = None
		self.rvecs = None
		self.tvecs = None
		self.rms = None
		self.num_used = 0

		# Precompute object points for this board
		self._objp = self._make_object_points(self.board_size, self.square_size)

		# Corner refinement criteria
		self._subpix_criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)

	def _make_object_points(self, board_size, square_size):
		cols, rows = board_size
		objp = np.zeros((rows * cols, 3), dtype=np.float32)
		# grid: x grows along columns, y grows along rows
		objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
		objp *= float(square_size)
		return objp

	def _to_gray(self, img):
		if img is None:
			return None
		if img.ndim == 2:
			return img
		return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

	def _detect_corners(self, gray):
		cols, rows = self.board_size
		pattern_size = (cols, rows)

		# Try the more robust SB detector first (OpenCV >= 4.x usually)
		if self.use_sb and hasattr(cv2, "findChessboardCornersSB"):
			# SB returns corners as (N,1,2) float32 when found
			ok, corners = cv2.findChessboardCornersSB(gray, pattern_size, flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
			if ok:
				return True, corners

		# Classic detector
		flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
		ok, corners = cv2.findChessboardCorners(gray, pattern_size, flags)
		if not ok:
			return False, None

		# Refine corners to sub-pixel (classic path)
		# window size 11x11 is a common default
		corners = cv2.cornerSubPix(
			gray,
			corners,
			(11, 11),
			(-1, -1),
			self._subpix_criteria
		)
		return True, corners

	def _maybe_init_intrinsics(self):
		# Optional: provide a reasonable initial guess
		if self.K is None and self.image_size is not None:
			w, h = self.image_size
			f = 0.8 * max(w, h)
			self.K = np.array([
				[f, 0.0, w * 0.5],
				[0.0, f, h * 0.5],
				[0.0, 0.0, 1.0]
			], dtype=np.float64)

	def add_frame(self, image):
		"""
		Add a new frame. If chessboard found, store points and (re)calibrate.

		Returns a dict every call:
		{
			"found": bool,
			"used_frames": int,
			"rms": float or None,
			"K": (3,3) float64 or None,
			"D": (1,N) float64 or None,
			"corners": (N,1,2) float32/64 or None
		}
		"""
		gray = self._to_gray(image)
		if gray is None:
			return {"found": False, "used_frames": self.num_used, "rms": self.rms, "K": self.K, "D": self.D, "corners": None}

		h, w = gray.shape[:2]
		if self.image_size is None:
			self.image_size = (w, h)
		else:
			if self.image_size != (w, h):
				# Mixing sizes breaks calibration; enforce consistency
				raise ValueError(f"Image size changed from {self.image_size} to {(w, h)}; keep all frames same size.")

		found, corners = self._detect_corners(gray)
		if not found:
			return {"found": False, "used_frames": self.num_used, "rms": self.rms, "K": self.K, "D": self.D, "corners": None}

		# Store data
		self.objpoints.append(self._objp.copy())
		self.imgpoints.append(np.asarray(corners, dtype=np.float32))
		self.num_used = len(self.objpoints)

		# Only calibrate after enough frames
		if self.num_used < self.min_frames:
			return {"found": True, "used_frames": self.num_used, "rms": self.rms, "K": self.K, "D": self.D, "corners": corners}

		self._maybe_init_intrinsics()

		# Calibrate (re-run every time with all collected frames)
		# Keep it simple + robust:
		# - Start with zero distortion, estimate everything.
		# - You can add flags later if you want to constrain model.
		K0 = None if self.K is None else self.K.copy()
		D0 = None if self.D is None else self.D.copy()

		flags = 0
		# If we have an initial K, tell OpenCV to use it as initial guess
		if K0 is not None:
			flags |= cv2.CALIB_USE_INTRINSIC_GUESS

		if D0 is None:
			D0 = np.zeros((1, 5), dtype=np.float64)

		rms, K, D, rvecs, tvecs = cv2.calibrateCamera(
			self.objpoints,
			self.imgpoints,
			self.image_size,
			K0,
			D0,
			flags=flags
		)

		self.rms = float(rms)
		self.K = np.asarray(K, dtype=np.float64)
		self.D = np.asarray(D, dtype=np.float64).reshape(1, -1)
		self.rvecs = rvecs
		self.tvecs = tvecs

		return {"found": True, "used_frames": self.num_used, "rms": self.rms, "K": self.K, "D": self.D, "corners": corners}

	def get_intrinsics(self):
		"""
		Return current (K, D, rms, used_frames).
		K or D may be None if not calibrated yet.
		"""
		return self.K, self.D, self.rms, self.num_used

	def draw_last_detection(self, image, corners, found=True):
		"""
		Convenience helper: returns a copy with drawn chessboard corners.
		"""
		out = image.copy()
		if found and corners is not None:
			cv2.drawChessboardCorners(out, self.board_size, corners, True)
		return out


if __name__ == "__main__":
	import argparse
	from receiver import UDPJPEGReceiver
	from image_funcs import scale_image

	parser = argparse.ArgumentParser(description='UDP JPEG Receiver Test')
	parser.add_argument('--port', type=int, default=5000)
	parser.add_argument('--timeout', type=float, default=0.5)
	args = parser.parse_args()

	receiver = UDPJPEGReceiver(bind_port=args.port, frame_timeout=args.timeout)
	receiver.start()
	calibrator = CameraCalibratorChessboard((5, 6), 0.124)
	try:
		while True:
			frames = receiver.get_latest_frames()
			for camera_id, (timestamp, img) in frames.items():
				window_name = f"Camera {camera_id}"

				res = calibrator.add_frame(img)
				if res["found"]:
					vis = calibrator.draw_last_detection(img, res["corners"], True)
					print("frames:", res["used_frames"], "rms:", res["rms"])
					if res["K"] is not None:
						print("K:\n", res["K"])
						print("D:\n", res["D"])
				else:
					vis = calibrator.draw_last_detection(img, res["corners"], True)
					print("no board")
				img = scale_image(vis, 0.5)
				cv2.imshow(window_name, img)
			cv2.waitKey(1)
			# key = cv2.waitKey(1) & 0xFF
			# if key == ord('q') or key == 27:
			# 	break
			# elif key == ord('s'):
			# 	receiver.print_stats()

	except KeyboardInterrupt:
		print("\nStopping...")
	finally:
		receiver.stop()
		cv2.destroyAllWindows()

