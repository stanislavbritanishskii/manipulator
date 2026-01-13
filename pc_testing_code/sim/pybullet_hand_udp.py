#!/usr/bin/env python3
import os
import sys
import math
import time
import socket
import argparse

import pybullet as p
import pybullet_data


def clamp(x, lo, hi):
	if x < lo:
		return lo
	if x > hi:
		return hi
	return x


def byte_to_rad(v_u8):
	# 0..180 maps to -90..+90 degrees
	v = clamp(int(v_u8), 0, 180)
	deg = float(v - 90)
	return deg * (math.pi / 180.0)


def setup_udp(bind_ip, bind_port):
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	sock.bind((bind_ip, bind_port))
	sock.setblocking(False)
	return sock


def main():
	parser = argparse.ArgumentParser(description="PyBullet UDP hand/arm controller (7x uint8, 0..180).")
	parser.add_argument("--urdf", default="hand_arm.urdf", help="Path to URDF file.")
	parser.add_argument("--bind-ip", default="0.0.0.0", help="UDP bind IP.")
	parser.add_argument("--port", type=int, default=5005, help="UDP bind port.")
	parser.add_argument("--hz", type=float, default=240.0, help="Simulation step rate.")
	parser.add_argument("--gui", action="store_true", help="Use GUI (default).")
	parser.add_argument("--direct", action="store_true", help="Use DIRECT (no GUI).")
	args = parser.parse_args()

	if args.direct:
		cid = p.connect(p.DIRECT)
	else:
		cid = p.connect(p.GUI)

	if cid < 0:
		print("PyBullet connect failed", file=sys.stderr)
		return 1

	p.resetSimulation()
	p.setAdditionalSearchPath(pybullet_data.getDataPath())
	p.setGravity(0, 0, -9.81)
	p.setTimeStep(1.0 / max(1.0, args.hz))

	p.loadURDF("plane.urdf")

	urdf_path = os.path.abspath(args.urdf)
	robot_id = p.loadURDF(urdf_path, basePosition=[0, 0, 0], baseOrientation=[0, 0, 0, 1], useFixedBase=True)
    # --- spawn a 5cm cube next to the hand ---
	half = 0.025  # 5cm cube => half extents 2.5cm

	col_id = p.createCollisionShape(p.GEOM_BOX, halfExtents=[half, half, half])
	vis_id = p.createVisualShape(p.GEOM_BOX, halfExtents=[half, half, half])

# approximate position: near the palm (x forward), slightly to the side (y), above ground (z)
	cube_pos = [0.35, 0.10, 0.05]

	cube_orn = p.getQuaternionFromEuler([0.0, 0.0, 0.0])

	cube_id = p.createMultiBody(
	baseMass=0.2,
	baseCollisionShapeIndex=col_id,
	baseVisualShapeIndex=vis_id,
	basePosition=cube_pos,
	baseOrientation=cube_orn)

# friction so it doesn't slide forever
	p.changeDynamics(cube_id, -1, lateralFriction=1.0, rollingFriction=0.001, spinningFriction=0.001)

	# Joint order expected by your sender:
	# [base_rotation, shoulder_angle, elbow_angle, wrist_angle, wrist_rotation, finger1, finger2]
# --- friction tuning (cube + finger links) ---

# Cube friction
	p.changeDynamics(
	cube_id,
	-1,
	lateralFriction=2.0,
	spinningFriction=0.02,
	rollingFriction=0.01,
	restitution=0.0
	)

# Finger friction (robot links)
	finger_joint_names = ["finger1", "finger2"]

	name_to_joint_index = {}
	num_joints = p.getNumJoints(robot_id)
	for ji in range(num_joints):
		info = p.getJointInfo(robot_id, ji)
		jname = info[1].decode("utf-8")
		name_to_joint_index[jname] = ji

	for fname in finger_joint_names:
		link_index = name_to_joint_index[fname]  # in PyBullet jointIndex == child link index
		p.changeDynamics(
		robot_id,
		link_index,
		lateralFriction=2.5,
		spinningFriction=0.03,
		rollingFriction=0.01,
		restitution=0.0
		)

	expected_joint_names = [
		"base_rotation",
		"shoulder_angle",
		"elbow_angle",
		"wrist_angle",
		"wrist_rotation",
		"finger1",
		"finger2",
	]

	name_to_index = {}
	num_joints = p.getNumJoints(robot_id)
	for ji in range(num_joints):
		info = p.getJointInfo(robot_id, ji)
		jname = info[1].decode("utf-8")
		name_to_index[jname] = ji

	joint_indices = []
	for n in expected_joint_names:
		if n not in name_to_index:
			print("Missing joint in URDF:", n, file=sys.stderr)
			return 2
		joint_indices.append(name_to_index[n])

	# Reset joints to "middle" = 90deg -> 0 rad
	for ji in joint_indices:
		p.resetJointState(robot_id, ji, targetValue=0.0)
		p.setJointMotorControl2(
			robot_id,
			ji,
			p.POSITION_CONTROL,
			targetPosition=0.0,
			force=50.0
		)

	sock = setup_udp(args.bind_ip, args.port)

	last_packet = None
	targets = [0.0] * 7

	hz = max(1.0, float(args.hz))
	dt = 1.0 / hz
	next_t = time.time()

	while True:
		# Receive latest packet (non-blocking); keep only the newest in the queue
		while True:
			try:
				data, _addr = sock.recvfrom(64)
			except BlockingIOError:
				break
			except Exception as e:
				print("UDP recv error:", e, file=sys.stderr)
				break

			if data is None:
				break
			if len(data) >= 7:
				last_packet = data[:7]

		if last_packet is not None:
			for i in range(7):
				targets[i] = clamp(byte_to_rad(last_packet[i]), -math.pi / 2.0, math.pi / 2.0)

		# Apply motor targets
		for i, ji in enumerate(joint_indices):
			p.setJointMotorControl2(
				robot_id,
				ji,
				p.POSITION_CONTROL,
				targetPosition=targets[i],
				force=50.0,
				positionGain=0.15,
				velocityGain=1.0
			)

		p.stepSimulation()

		# pacing
		now = time.time()
		if now < next_t:
			time.sleep(next_t - now)
		next_t += dt

	return 0


if __name__ == "__main__":
	sys.exit(main())
