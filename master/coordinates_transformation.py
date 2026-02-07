import numpy as np
import cv2


def _as_K(K):
	Km = np.asarray(K, dtype=np.float64)
	if Km.shape != (3, 3):
		raise ValueError("K must be (3,3)")
	return Km


def _as_D(D):
	if D is None:
		return None
	Dv = np.asarray(D, dtype=np.float64)
	if Dv.ndim == 1:
		return Dv.reshape(1, -1)
	if Dv.ndim == 2:
		if Dv.shape[0] == 1:
			return Dv
		if Dv.shape[1] == 1:
			return Dv.reshape(1, -1)
		return Dv.reshape(1, -1)
	raise ValueError("D must be None, 1D, or 2D")


def _make_marker_objp(marker_length):
	L = float(marker_length)
	if L <= 0.0:
		raise ValueError("marker_length must be > 0")
	half = 0.5 * L
	# ArUco order: top-left, top-right, bottom-right, bottom-left
	return np.array([
		[-half,  half, 0.0],
		[ half,  half, 0.0],
		[ half, -half, 0.0],
		[-half, -half, 0.0],
	], dtype=np.float64)


def _invert_T(R_c_a, t_c_a):
	# Given X_c = R_c_a * X_a + t_c_a
	# Return transform a<-c: X_a = R_a_c * X_c + t_a_c
	R_a_c = R_c_a.T
	t_a_c = -R_a_c @ t_c_a
	return R_a_c, t_a_c


def _compose_T(R_b_a, t_b_a, R_c_b, t_c_b):
	# X_b = R_b_a X_a + t_b_a
	# X_c = R_c_b X_b + t_c_b
	# => X_c = (R_c_b R_b_a) X_a + (R_c_b t_b_a + t_c_b)
	R_c_a = R_c_b @ R_b_a
	t_c_a = R_c_b @ t_b_a + t_c_b
	return R_c_a, t_c_a


class ArucoGroundFrame:
	"""
	Stores a "ground" frame defined by a chosen marker (its center = 0,0,0 and axes = marker axes).
	Then returns other marker poses relative to that ground.

	Conventions:
	- solvePnP gives marker pose in camera coordinates: X_cam = R_cam_marker * X_marker + t_cam_marker
	- Ground is the chosen marker frame at the time of set_ground().
	- Output poses are marker poses in ground coordinates: X_ground = R_ground_marker * X_marker + t_ground_marker
	"""

	def __init__(self, dict_id=cv2.aruco.DICT_4X4_100, use_ippe=True):
		if not hasattr(cv2, "aruco"):
			raise RuntimeError("cv2.aruco missing (install opencv-contrib-python)")

		self.dict_id = dict_id
		self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
		self.params = cv2.aruco.DetectorParameters()

		if hasattr(cv2.aruco, "ArucoDetector"):
			self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.params)
		else:
			self.detector = None

		self.use_ippe = bool(use_ippe)

		# Ground state (saved after set_ground)
		self.ground_id = None
		self.R_c_g = None	# (3,3) camera <- ground
		self.t_c_g = None	# (3,)  camera <- ground
		self.R_g_c = None	# (3,3) ground <- camera
		self.t_g_c = None	# (3,)  ground <- camera

	def _detect(self, image_bgr):
		gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

		if self.detector is not None:
			corners, ids, _rej = self.detector.detectMarkers(gray)
		else:
			corners, ids, _rej = cv2.aruco.detectMarkers(gray, self.aruco_dict, parameters=self.params)

		if ids is None or len(ids) == 0:
			return [], None

		ids = ids.reshape(-1).astype(np.int32)
		return corners, ids

	def _estimate_pose_one(self, corners_i, K, D, objp, pnp_flag):
		imgp = np.asarray(corners_i, dtype=np.float64).reshape(4, 2)

		ok, rvec, tvec = cv2.solvePnP(
			objp,
			imgp,
			K,
			D,
			flags=pnp_flag
		)
		if not ok:
			return None

		rvec = np.asarray(rvec, dtype=np.float64).reshape(3)
		tvec = np.asarray(tvec, dtype=np.float64).reshape(3)
		R, _ = cv2.Rodrigues(rvec.reshape(3, 1))
		return R, tvec, rvec, imgp

	def set_ground(self, image_bgr, ground_marker_id, K, D, marker_length, draw=True):
		"""
		Use only the marker with id=ground_marker_id to set the ground frame.

		Returns:
			(out_image, ok_bool)

		After success, ground is stored and used by detect_in_ground().
		"""
		out = image_bgr.copy()

		Km = _as_K(K)
		Dv = _as_D(D)
		objp = _make_marker_objp(marker_length)

		if self.use_ippe and hasattr(cv2, "SOLVEPNP_IPPE_SQUARE"):
			pnp_flag = cv2.SOLVEPNP_IPPE_SQUARE
		else:
			pnp_flag = cv2.SOLVEPNP_ITERATIVE

		corners, ids = self._detect(out)
		if ids is None:
			return out, False

		if draw:
			cv2.aruco.drawDetectedMarkers(out, corners, ids.reshape(-1, 1))

		target_id = int(ground_marker_id)
		idx = -1
		for i in range(len(ids)):
			if int(ids[i]) == target_id:
				idx = i
				break
		if idx < 0:
			return out, False

		est = self._estimate_pose_one(corners[idx], Km, Dv, objp, pnp_flag)
		if est is None:
			return out, False

		R_c_g, t_c_g, rvec, _imgp = est

		# Save ground transform
		self.ground_id = target_id
		self.R_c_g = R_c_g
		self.t_c_g = t_c_g
		self.R_g_c, self.t_g_c = _invert_T(R_c_g, t_c_g)

		if draw and hasattr(cv2, "drawFrameAxes"):
			cv2.drawFrameAxes(out, Km, Dv, rvec.reshape(3, 1), t_c_g.reshape(3, 1), float(marker_length) * 0.5)

		return out, True

	def detect_in_ground(self, image_bgr, K, D, marker_length, draw=True, include_ground=False):
		"""
		Detect markers and return their poses relative to the saved ground.

		Returns:
			(out_image, poses)

		poses is list of dicts:
		{
			"id": int,
			"t_g_m": np.ndarray (3,)	# marker center in ground coords
			"R_g_m": np.ndarray (3,3)	# rotation ground<-marker
			"rvec_g_m": np.ndarray (3,)	# Rodrigues for R_g_m
			"distance_g": float			# norm(t_g_m)
		}
		"""
		if self.R_g_c is None or self.t_g_c is None:
			raise RuntimeError("Ground is not set. Call set_ground() successfully first.")

		out = image_bgr.copy()

		Km = _as_K(K)
		Dv = _as_D(D)
		objp = _make_marker_objp(marker_length)

		if self.use_ippe and hasattr(cv2, "SOLVEPNP_IPPE_SQUARE"):
			pnp_flag = cv2.SOLVEPNP_IPPE_SQUARE
		else:
			pnp_flag = cv2.SOLVEPNP_ITERATIVE

		corners, ids = self._detect(out)
		if ids is None:
			return out, {}

		if draw:
			cv2.aruco.drawDetectedMarkers(out, corners, ids.reshape(-1, 1))

		poses = {}

		for i in range(len(ids)):
			m_id = int(ids[i])

			if (not include_ground) and (self.ground_id is not None) and (m_id == int(self.ground_id)):
				continue

			est = self._estimate_pose_one(corners[i], Km, Dv, objp, pnp_flag)
			if est is None:
				continue

			R_c_m, t_c_m, rvec_c_m, imgp = est

			# Relative transform: ground <- marker
			# T_g_m = T_g_c * T_c_m
			R_g_m = self.R_g_c @ R_c_m
			t_g_m = self.R_g_c @ (t_c_m - self.t_c_g)

			rvec_g_m, _ = cv2.Rodrigues(R_g_m)

			if draw and hasattr(cv2, "drawFrameAxes"):
				# Draw in camera image using original camera-frame pose (more stable for overlay)
				cv2.drawFrameAxes(out, Km, Dv, rvec_c_m.reshape(3, 1), t_c_m.reshape(3, 1), float(marker_length) * 0.5)

			center = np.mean(imgp, axis=0)
			x = int(center[0] + 10)
			y = int(center[1])
			if draw:
				cv2.putText(out, f"id:{m_id}", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
				cv2.putText(out, f"g:[{t_g_m[0]:.3f},{t_g_m[1]:.3f},{t_g_m[2]:.3f}]", (x, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

			poses[m_id] = {
				"id": m_id,
				"t_g_m": t_g_m,
				"R_g_m": R_g_m,
				"rvec_g_m": np.asarray(rvec_g_m, dtype=np.float64).reshape(3),
				"distance_g": float(np.linalg.norm(t_g_m))
			}
			# poses.append({
			# 	"id": m_id,
			# 	"t_g_m": t_g_m,
			# 	"R_g_m": R_g_m,
			# 	"rvec_g_m": np.asarray(rvec_g_m, dtype=np.float64).reshape(3),
			# 	"distance_g": float(np.linalg.norm(t_g_m))
			# })

		return out, poses
