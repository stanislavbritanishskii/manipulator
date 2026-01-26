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
	# 90 -> 0 rad (neutral)
	# 0 -> -90 deg = -π/2
	# 180 -> +90 deg = +π/2
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

	# --- spawn a 5cm cube ---
	half = 0.025

	col_id = p.createCollisionShape(p.GEOM_BOX, halfExtents=[half, half, half])
	vis_id = p.createVisualShape(p.GEOM_BOX, halfExtents=[half, half, half])

	cube_pos = [0.0, 0.10, 0.60]
	cube_orn = p.getQuaternionFromEuler([0.0, 0.0, 0.0])

	cube_id = p.createMultiBody(
		baseMass=0.2,
		baseCollisionShapeIndex=col_id,
		baseVisualShapeIndex=vis_id,
		basePosition=cube_pos,
		baseOrientation=cube_orn)

	p.changeDynamics(
		cube_id,
		-1,
		lateralFriction=20.0,
		spinningFriction=0.02,
		rollingFriction=0.01,
		restitution=0.0
	)

	# Finger friction
	finger_joint_names = ["finger1", "finger2"]

	name_to_joint_index = {}
	num_joints = p.getNumJoints(robot_id)
	for ji in range(num_joints):
		info = p.getJointInfo(robot_id, ji)
		jname = info[1].decode("utf-8")
		name_to_joint_index[jname] = ji

	for fname in finger_joint_names:
		link_index = name_to_joint_index[fname]
		p.changeDynamics(
			robot_id,
			link_index,
			lateralFriction=20.5,
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

	# --- finger1 link index (same integer as its joint index in PyBullet) ---
	finger1_link_index = name_to_index["finger1"]

	# Reset to neutral
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

	# --- debug text handle (GUI) ---
	debug_text_id = -1
	print("\033[0;0H", end="")
	while True:
		# Receive latest packet
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
				if i == 2:
					targets[i] += math.pi/4

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

		# --- show finger1 "tip" coordinate (actually link COM/center) ---
		# This will work in GUI; in DIRECT it is harmless (no visible output).
		# before the while True loop

		# inside the loop
		try:
			ls = p.getLinkState(robot_id, finger1_link_index, computeForwardKinematics=True)
			pos = ls[0]
			txt = "x={:.2f} y={:.2f} z={:.2f}".format(pos[0], pos[1], pos[2])

			if debug_text_id >= 0:
				p.removeUserDebugItem(debug_text_id)
				debug_text_id = -1

			# draw at a fixed world position (so it's not next to the finger)
			print(txt, end="\r")
			# debug_text_id = p.addUserDebugText(
			# 	txt,
			# 	[pos[0], pos[1], pos[2]],  # pick any stable spot you like
			# 	textColorRGB=[0.0, 0.0, 0.0],
			# 	textSize=1.2,
			# 	lifeTime=0.0
			# )
		except Exception:
			pass

		# pacing
		now = time.time()
		if now < next_t:
			time.sleep(next_t - now)
		next_t += dt

	return 0


if __name__ == "__main__":
	sys.exit(main())
