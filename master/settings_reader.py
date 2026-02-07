import json
import numpy as np


def _to_int_if_possible(x):
	try:
		return int(x)
	except Exception:
		return None


def _as_np_mat3(K_list, cam_id):
	K = np.array(K_list, dtype=np.float64)
	if K.shape != (3, 3):
		raise ValueError(f"camera {cam_id}: K must be 3x3, got shape {K.shape}")
	return K


def _as_np_dist(D_list, cam_id):
	D = np.array(D_list, dtype=np.float64)
	if D.ndim == 1:
		D = D.reshape(1, -1)
	if D.ndim != 2 or D.shape[0] != 1:
		raise ValueError(f"camera {cam_id}: D must be (1,N) or (N,), got shape {D.shape}")
	return D


def load_camera_intrinsics_json(path):
	"""
	Loads a JSON file:
	{
		"0": {"K": [[...],[...],[...]], "D": [[...]]},
		"1": {"K": [[...],[...],[...]], "D": [[...]]}
	}

	Returns:
		intrinsics: dict[int, tuple[np.ndarray, np.ndarray]]  # cam_id -> (K(3x3), D(1xN))
	"""
	with open(path, "r", encoding="utf-8") as f:
		data = json.load(f)

	if not isinstance(data, dict):
		raise ValueError("Top-level JSON must be an object/map of camera_id -> {K,D}")

	out = {}

	for key, entry in data.items():
		cam_id = _to_int_if_possible(key)
		if cam_id is None:
			raise ValueError(f"camera id key '{key}' is not an int or int-like string")

		if not isinstance(entry, dict):
			raise ValueError(f"camera {cam_id}: value must be an object with keys 'K' and 'D'")

		if "K" not in entry or "D" not in entry:
			raise ValueError(f"camera {cam_id}: missing 'K' or 'D'")

		K = _as_np_mat3(entry["K"], cam_id)
		D = _as_np_dist(entry["D"], cam_id)

		out[cam_id] = (K, D)

	return out


def get_intrinsics_for_camera(intrinsics_map, camera_id):
	"""
	camera_id can be int or string; returns (K,D) or (None,None) if not found.
	"""
	cam_int = None
	if isinstance(camera_id, int):
		cam_int = camera_id
	else:
		cam_int = _to_int_if_possible(camera_id)

	if cam_int is None:
		return (None, None)

	if cam_int in intrinsics_map:
		return intrinsics_map[cam_int]

	return (None, None)
