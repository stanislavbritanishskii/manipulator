import numpy as np
import cv2


def aruco_detect_draw_pose(image_bgr, K, D, marker_length, dict_id=cv2.aruco.DICT_4X4_100):
	out = image_bgr.copy()

	if not hasattr(cv2, "aruco"):
		raise RuntimeError("cv2.aruco missing (install opencv-contrib-python)")

	K = np.asarray(K, dtype=np.float64)
	if K.shape != (3, 3):
		raise ValueError("K must be (3,3)")

	if D is None:
		Dv = None
	else:
		Dv = np.asarray(D, dtype=np.float64)
		if Dv.ndim == 1:
			Dv = Dv.reshape(-1, 1)
		elif Dv.ndim == 2:
			# accept (1,N) or (N,1) or (N,N?) -> force column vector
			if Dv.shape[0] == 1:
				Dv = Dv.reshape(-1, 1)
			elif Dv.shape[1] == 1:
				pass
			else:
				Dv = Dv.reshape(-1, 1)
		else:
			raise ValueError("D must be None, 1D, or 2D")

	if marker_length is None or float(marker_length) <= 0.0:
		raise ValueError("marker_length must be > 0")

	gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)

	aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
	params = cv2.aruco.DetectorParameters()

	# Works on newer OpenCV; if missing, fallback to old API
	if hasattr(cv2.aruco, "ArucoDetector"):
		detector = cv2.aruco.ArucoDetector(aruco_dict, params)
		corners, ids, _rej = detector.detectMarkers(gray)
	else:
		corners, ids, _rej = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)

	if ids is None or len(ids) == 0:
		return out, []

	ids = ids.reshape(-1).astype(np.int32)

	# Draw contours
	cv2.aruco.drawDetectedMarkers(out, corners, ids.reshape(-1, 1))

	# 3D object points of marker corners in marker frame (Z=0 plane)
	# Corner order from ArUco: top-left, top-right, bottom-right, bottom-left
	L = float(marker_length)
	half = 0.5 * L
	objp = np.array([
		[-half,  half, 0.0],
		[ half,  half, 0.0],
		[ half, -half, 0.0],
		[-half, -half, 0.0],
	], dtype=np.float64)

	# Prefer IPPE for planar square markers if available
	if hasattr(cv2, "SOLVEPNP_IPPE_SQUARE"):
		pnp_flag = cv2.SOLVEPNP_IPPE_SQUARE
	else:
		pnp_flag = cv2.SOLVEPNP_ITERATIVE

	data = []
	for i in range(len(ids)):
		m_id = int(ids[i])

		imgp = np.asarray(corners[i], dtype=np.float64).reshape(4, 2)

		ok, rvec, tvec = cv2.solvePnP(
			objp,
			imgp,
			K,
			Dv,
			flags=pnp_flag
		)
		if not ok:
			continue

		rvec = np.asarray(rvec, dtype=np.float64).reshape(3)
		tvec = np.asarray(tvec, dtype=np.float64).reshape(3)

		dist = float(np.linalg.norm(tvec))

		# Orientation (stable + short): marker normal tilt vs camera optical axis
		R, _ = cv2.Rodrigues(rvec.reshape(3, 1))
		normal_cam = R[:, 2]
		nn = float(np.linalg.norm(normal_cam) + 1e-12)
		cosang = float(np.clip(normal_cam[2] / nn, -1.0, 1.0))
		tilt_deg = float(np.degrees(np.arccos(cosang)))

		# Text position near marker center
		center = np.mean(imgp, axis=0)
		x = int(center[0] + 10)
		y = int(center[1])

		cv2.putText(
			out,
			f"id:{m_id} d:{dist:.3f} tilt:{tilt_deg:.1f}",
			(x, y),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.5,
			(0, 255, 0),
			1,
			cv2.LINE_AA
		)

		# Draw axes (requires calib3d; usually present)
		if hasattr(cv2, "drawFrameAxes"):
			cv2.drawFrameAxes(out, K, Dv, rvec.reshape(3, 1), tvec.reshape(3, 1), L * 0.5)

		data.append({
			"id": m_id,
			"corners": imgp,
			"rvec": rvec,
			"tvec": tvec,
			"distance": dist,
			"tilt_deg": tilt_deg
		})

	return out, data


def scale_image(img, scale_x, scale_y=None, interpolation=None):
	if scale_y is None:
		scale_y = scale_x

	if interpolation is None:
		# good defaults
		if scale_x > 1.0 or scale_y > 1.0:
			interpolation = cv2.INTER_LINEAR
		else:
			interpolation = cv2.INTER_AREA

	return cv2.resize(img, None, fx=float(scale_x), fy=float(scale_y), interpolation=interpolation)
