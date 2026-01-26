#!/usr/bin/env python3
import asyncio
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# You already have these:
# - Arm class (put it in arm.py, or adjust import)
# - udp_sender.py with UdpSender(host, port) and send(*angles)
from IK import Arm
import udp_sender

try:
	import websockets
except ImportError:
	websockets = None


INDEX_HTML = r"""<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
	<title>Arm Web Control</title>
	<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
	<style>
		body {
			margin: 0;
			background: #000;
			overflow: hidden;
			font-family: sans-serif;
			color: #fff;
		}

		.panel {
			position: absolute;
			top: 0;
			left: 0;
			width: 100vw;
			height: 100vh;
			user-select: none;
			touch-action: none;
		}

		.joystick-container {
			position: absolute;
			width: 180px;
			height: 180px;
			background: rgba(255, 255, 255, 0.08);
			border: 2px solid rgba(255, 255, 255, 0.2);
			border-radius: 50%;
			touch-action: none;
		}

		.joystick-thumb {
			position: absolute;
			width: 60px;
			height: 60px;
			background: rgba(255, 255, 255, 0.45);
			border-radius: 50%;
			top: 50%;
			left: 50%;
			transform: translate(-50%, -50%);
		}

		#joy_left {
			left: 7%;
			bottom: 10%;
		}

		#joy_right {
			right: 7%;
			bottom: 10%;
		}

		#slider {
			position: absolute;
			left: 50%;
			top: 12%;
			transform: translateX(-50%);
			width: 70px;
			height: 70vh;
			background: rgba(255, 255, 255, 0.08);
			border: 2px solid rgba(255, 255, 255, 0.2);
			border-radius: 18px;
			touch-action: none;
		}

		#slider_thumb {
			position: absolute;
			left: 50%;
			top: 50%;
			transform: translate(-50%, -50%);
			width: 64px;
			height: 64px;
			border-radius: 16px;
			background: rgba(255, 255, 255, 0.45);
		}

		#debug {
			position: absolute;
			left: 12px;
			top: 12px;
			padding: 10px 12px;
			background: rgba(0,0,0,0.55);
			border: 1px solid rgba(255,255,255,0.15);
			border-radius: 10px;
			font-size: 14px;
			line-height: 1.3em;
			white-space: pre;
		}
	</style>
</head>
<body>
	<div class="panel">
		<div id="debug">connecting...</div>

		<div id="joy_left" class="joystick-container">
			<div class="joystick-thumb"></div>
		</div>

		<div id="slider">
			<div id="slider_thumb"></div>
		</div>

		<div id="joy_right" class="joystick-container">
			<div class="joystick-thumb"></div>
		</div>
	</div>

<script>
(function() {
	// document.documentElement.requestFullscreen().catch(()=>{});

	const ws = new WebSocket("ws://" + location.hostname + ":8765");

	function clamp(v, a, b) {
		return Math.max(a, Math.min(b, v));
	}

	function setupJoystick(id) {
		const container = document.getElementById(id);
		const thumb = container.querySelector(".joystick-thumb");
		let active = false;
		let pos = {x: 0, y: 0};

		function getOffset(e) {
			const rect = container.getBoundingClientRect();
			const cx = rect.left + rect.width * 0.5;
			const cy = rect.top + rect.height * 0.5;

			let px = 0;
			let py = 0;
			if (e.touches && e.touches.length) {
				px = e.touches[0].clientX;
				py = e.touches[0].clientY;
			} else {
				px = e.clientX;
				py = e.clientY;
			}

			const dx = (px - cx) / (rect.width * 0.5);
			const dy = (py - cy) / (rect.height * 0.5);
			return {x: clamp(dx, -1, 1), y: clamp(dy, -1, 1)};
		}

		function moveThumb(p) {
			thumb.style.left = (50 + p.x * 35) + "%";
			thumb.style.top = (50 + p.y * 35) + "%";
		}

		function reset() {
			pos = {x: 0, y: 0};
			moveThumb(pos);
		}

		function update(e) {
			if (!active) return;
			e.preventDefault();
			pos = getOffset(e);
			moveThumb(pos);
		}

		container.addEventListener("mousedown", (e) => { active = true; update(e); });
		container.addEventListener("touchstart", (e) => { active = true; update(e); }, {passive: false});

		window.addEventListener("mouseup", () => { active = false; reset(); });
		window.addEventListener("touchend", () => { active = false; reset(); });

		window.addEventListener("mousemove", update);
		window.addEventListener("touchmove", update, {passive: false});

		return function() { return pos; };
	}

	function setupSlider(id, thumb_id) {
		const container = document.getElementById(id);
		const thumb = document.getElementById(thumb_id);
		let active = false;

		// slider value in [-1..1], -1 = top, +1 = bottom
		let value = 0;

		function getValue(e) {
			const rect = container.getBoundingClientRect();
			let py = 0;
			if (e.touches && e.touches.length) py = e.touches[0].clientY;
			else py = e.clientY;

			const t = (py - rect.top) / rect.height; // 0..1
			const v = (t * 2.0) - 1.0; // -1..1
			return clamp(v, -1, 1);
		}

		function moveThumb(v) {
			// map [-1..1] to [10%..90%]
			const p = 50 + v * 40;
			thumb.style.top = p + "%";
		}

		function reset() {
			value = 0;
			moveThumb(value);
		}

		function update(e) {
			if (!active) return;
			e.preventDefault();
			value = getValue(e);
			moveThumb(value);
		}

		container.addEventListener("mousedown", (e) => { active = true; update(e); });
		container.addEventListener("touchstart", (e) => { active = true; update(e); }, {passive: false});
		window.addEventListener("mouseup", () => { active = false; reset(); });
		window.addEventListener("touchend", () => { active = false; reset(); });
		window.addEventListener("mousemove", update);
		window.addEventListener("touchmove", update, {passive: false});

		return function() { return value; };
	}

	const joyLeft = setupJoystick("joy_left");
	const joyRight = setupJoystick("joy_right");
	const slider = setupSlider("slider", "slider_thumb");

	// keyboard fallback:
	// - left joystick: WASD
	// - right joystick: arrows
	// - slider: R (up), F (down)
	let kLeft = {x: 0, y: 0};
	let kRight = {x: 0, y: 0};
	let kSlide = 0;

	document.addEventListener("keydown", (e) => {
		switch (e.key) {
			case "w": case "W": kLeft.y = -1; break;
			case "s": case "S": kLeft.y =  1; break;
			case "a": case "A": kLeft.x = -1; break;
			case "d": case "D": kLeft.x =  1; break;

			case "ArrowUp": kRight.y = -1; break;
			case "ArrowDown": kRight.y =  1; break;
			case "ArrowLeft": kRight.x = -1; break;
			case "ArrowRight": kRight.x =  1; break;

			case "r": case "R": kSlide = -1; break;
			case "f": case "F": kSlide =  1; break;
		}
	});

	document.addEventListener("keyup", (e) => {
		switch (e.key) {
			case "w": case "W": case "s": case "S": kLeft.y = 0; break;
			case "a": case "A": case "d": case "D": kLeft.x = 0; break;

			case "ArrowUp": case "ArrowDown": kRight.y = 0; break;
			case "ArrowLeft": case "ArrowRight": kRight.x = 0; break;

			case "r": case "R": case "f": case "F": kSlide = 0; break;
		}
	});

	const dbg = document.getElementById("debug");

	ws.onmessage = (ev) => {
		// server may send debug state
		try {
			const obj = JSON.parse(ev.data);
			if (obj && obj.state_text) dbg.textContent = obj.state_text;
		} catch (e) {}
	};

	ws.onopen = () => { dbg.textContent = "connected"; };
	ws.onclose = () => { dbg.textContent = "ws closed"; };

	setInterval(() => {
		const l = (kLeft.x || kLeft.y) ? kLeft : joyLeft();
		const r = (kRight.x || kRight.y) ? kRight : joyRight();
		const s = (kSlide !== 0) ? kSlide : slider();

		const data = {
			left: {x: l.x, y: l.y},
			right: {x: r.x, y: r.y},
			slider: s
		};

		if (ws.readyState === WebSocket.OPEN) {
			ws.send(JSON.stringify(data));
		}
	}, 33);
})();
</script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
	def do_GET(self):
		if self.path == "/" or self.path == "/index.html":
			body = INDEX_HTML.encode("utf-8")
			self.send_response(200)
			self.send_header("Content-Type", "text/html; charset=utf-8")
			self.send_header("Content-Length", str(len(body)))
			self.end_headers()
			self.wfile.write(body)
			return

		self.send_response(404)
		self.send_header("Content-Type", "text/plain; charset=utf-8")
		self.end_headers()
		self.wfile.write(b"404\n")

	def log_message(self, fmt, *args):
		# keep stdout clean
		return


def _start_http(host, port):
	server = ThreadingHTTPServer((host, port), _Handler)
	server.serve_forever()


def _clamp(v, lo, hi):
	if v < lo:
		return lo
	if v > hi:
		return hi
	return v


def _pick_angles(arm):
	# Same idea as your current script: prefer solution 0; if any joint out of [-pi/2, pi/2], use solution 1.
	base_rotation, base_angle, elbow, wrist_angle, wrist_rotation = arm.get_angles()

	a0 = [
		base_rotation[0],
		base_angle[0],
		elbow[0],
		wrist_angle[0],
		wrist_rotation[0],
		0.0,
		0.0,
	]
	limit = math.pi / 2.0
	ok0 = True
	for v in a0:
		if v > limit or v < -limit:
			ok0 = False
			break
	if ok0:
		return a0

	a1 = [
		base_rotation[1],
		base_angle[1],
		elbow[1],
		wrist_angle[1],
		wrist_rotation[1],
		0.0,
		0.0,
	]
	return a1


async def main():
	if websockets is None:
		raise SystemExit("python module 'websockets' not found. Install: pip3 install websockets")

	# === CONFIG ===
	http_host = "0.0.0.0"
	http_port = 8000
	ws_host = "0.0.0.0"
	ws_port = 8765

	udp_host = "127.0.0.1"
	udp_port = 5005

	# Arm geometry
	arm = Arm(base_len=10, shoulder_len=30, arm_len=20, wrist_len=8)
	sender = udp_sender.UdpSender(udp_host, udp_port)

	# State (stored + updated by small increments)
	state = {
		"dist": 20.0,
		"yaw": math.pi / 2.0,
		"z": 20.0,
		"pitch": 0.0,
		"roll": 0.0,
	}

	# Per-tick step sizes (at full joystick deflection)
	steps = {
		"dist": 0.6,					# cm per tick
		"yaw": 0.04,					# rad per tick
		"z": 0.6,						# cm per tick
		"pitch": 0.03,					# rad per tick
		"roll": 0.04,					# rad per tick
	}

	# Limits
	lims = {
		"dist": (-60.0, 60.0),
		"z": (-10.0, 70.0),
		"pitch": (-math.pi, math.pi),
		"roll": (-math.pi, math.pi),
	}

	# Latest inputs from UI
	inputs = {
		"left": {"x": 0.0, "y": 0.0},
		"right": {"x": 0.0, "y": 0.0},
		"slider": 0.0,
	}

	clients = set()
	clients_lock = asyncio.Lock()

	def apply_wrap_yaw():
		# keep yaw in [0..pi], flipping dist when crossing boundary
		if state["yaw"] < 0.0:
			state["yaw"] += math.pi
			state["dist"] *= -1.0
		elif state["yaw"] > math.pi:
			state["yaw"] -= math.pi
			state["dist"] *= -1.0

	def tick_update():
		# left joystick: dist + yaw
		# - y up => increase dist (invert sign because screen y is down-positive)
		# - x right => increase yaw
		lx = float(inputs["left"]["x"])
		ly = float(inputs["left"]["y"])

		state["dist"] += (-ly) * steps["dist"]
		state["yaw"] += (lx) * steps["yaw"]
		apply_wrap_yaw()

		# slider: height z (value -1 top, +1 bottom)
		sv = float(inputs["slider"])
		state["z"] += (-sv) * steps["z"]

		# right joystick: pitch + roll
		# - y up => increase pitch (nose up)
		# - x right => increase roll
		rx = float(inputs["right"]["x"])
		ry = float(inputs["right"]["y"])
		state["pitch"] += (-ry) * steps["pitch"]
		state["roll"] += (rx) * steps["roll"]

		# clamp
		state["dist"] = _clamp(state["dist"], lims["dist"][0], lims["dist"][1])
		state["z"] = _clamp(state["z"], lims["z"][0], lims["z"][1])
		state["pitch"] = _clamp(state["pitch"], lims["pitch"][0], lims["pitch"][1])
		state["roll"] = _clamp(state["roll"], lims["roll"][0], lims["roll"][1])

	async def ws_handler(websocket):
		async with clients_lock:
			clients.add(websocket)
		try:
			async for msg in websocket:
				try:
					obj = json.loads(msg)
					if "left" in obj and "x" in obj["left"] and "y" in obj["left"]:
						inputs["left"]["x"] = float(obj["left"]["x"])
						inputs["left"]["y"] = float(obj["left"]["y"])
					if "right" in obj and "x" in obj["right"] and "y" in obj["right"]:
						inputs["right"]["x"] = float(obj["right"]["x"])
						inputs["right"]["y"] = float(obj["right"]["y"])
					if "slider" in obj:
						inputs["slider"] = float(obj["slider"])
				except Exception:
					# ignore malformed messages
					pass
		finally:
			async with clients_lock:
				if websocket in clients:
					clients.remove(websocket)

	async def broadcast_debug(text):
		payload = json.dumps({"state_text": text})
		async with clients_lock:
			ws_list = list(clients)
		if not ws_list:
			return
		for ws in ws_list:
			try:
				await ws.send(payload)
			except Exception:
				pass

	# HTTP server in background thread
	t = threading.Thread(target=_start_http, args=(http_host, http_port), daemon=True)
	t.start()

	# WebSocket server + control loop
	async with websockets.serve(ws_handler, ws_host, ws_port):
		last_debug = 0.0
		while True:
			t0 = time.time()

			# update state from inputs
			tick_update()

			# run IK + send
			try:
				arm.calculate_angles(state["dist"], state["z"], state["pitch"], state["yaw"], state["roll"])
				angles = _pick_angles(arm)
				sender.send(*angles)
			except Exception:
				# keep running even if IK fails for a moment
				pass

			# debug back to UI ~10 Hz
			now = time.time()
			if now - last_debug > 0.10:
				last_debug = now
				txt = (
					"dist:  %.2f\n"
					"yaw:   %.2f deg\n"
					"z:     %.2f\n"
					"pitch: %.2f deg\n"
					"roll:  %.2f deg\n"
					"\n"
					"left:  x=%.2f y=%.2f\n"
					"right: x=%.2f y=%.2f\n"
					"slide: %.2f\n"
				) % (
					state["dist"],
					state["yaw"] * 180.0 / math.pi,
					state["z"],
					state["pitch"] * 180.0 / math.pi,
					state["roll"] * 180.0 / math.pi,
					inputs["left"]["x"], inputs["left"]["y"],
					inputs["right"]["x"], inputs["right"]["y"],
					inputs["slider"],
				)
				await broadcast_debug(txt)

			# ~30 Hz pacing
			dt = time.time() - t0
			sleep_s = (1.0 / 30.0) - dt
			if sleep_s < 0.0:
				sleep_s = 0.0
			await asyncio.sleep(sleep_s)


if __name__ == "__main__":
	asyncio.run(main())
