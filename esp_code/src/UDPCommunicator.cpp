// UdpCommunicator.cpp
#include "UDPCommunicator.hpp"

UdpCommunicator::UdpCommunicator(const char *ssid,
								const char *password,
								uint16_t local_port,
								uint32_t wifi_timeout_ms) {
	_ssid = ssid;
	_password = password;
	_local_port = local_port;
	_wifi_timeout_ms = wifi_timeout_ms;

	_data_updated = false;
	_udp_started = false;

	memset(&data, 0, sizeof(data));
	memset(buf, 0, sizeof(buf));
}

bool UdpCommunicator::begin() {
	bool ok = connect_wifi_();
	start_udp_();
	return ok;
}

bool UdpCommunicator::connect_wifi_() {
	if (_ssid == NULL || _password == NULL) {
		return false;
	}

	WiFi.mode(WIFI_STA);
	WiFi.setSleep(false); // reduce latency for control links
	WiFi.begin(_ssid, _password);

	uint32_t t0 = millis();
	while (WiFi.status() != WL_CONNECTED) {
		if ((millis() - t0) >= _wifi_timeout_ms) {
			return false;
		}
		delay(50);
	}
	return true;
}

void UdpCommunicator::start_udp_() {
	if (_udp_started) {
		return;
	}
	udp.begin(_local_port);
	_udp_started = true;
}

void UdpCommunicator::read() {
	_data_updated = false;

	if (!_udp_started) {
		return;
	}

	int packetSize = udp.parsePacket();
	if (packetSize <= 0) {
		_data_updated = false;
		return;
	}

	// Require exact struct size for safety/determinism
	if (packetSize != (int) sizeof(CommunicationData_t)) {
		// Drain packet
		while (udp.available() > 0) {
			(void) udp.read();
		}
		return;
	}

	int n = udp.read(buf, sizeof(buf));
	if (n != (int) sizeof(CommunicationData_t)) {
		return;
	}

	memcpy(&data, buf, sizeof(data));
	_data_updated = true;
}

bool UdpCommunicator::data_updated() {
	return _data_updated;
}

uint8_t UdpCommunicator::getBaseRotation() {
	return data.base_rotation;
}

uint8_t UdpCommunicator::getBaseAngle() {
	return data.base_angle;
}

uint8_t UdpCommunicator::getElbowAngle() {
	return data.elbow_angle;
}

uint8_t UdpCommunicator::getWristAngle() {
	return data.wrist_angle;
}

uint8_t UdpCommunicator::getWristRotation() {
	return data.wrist_rotation;
}

uint8_t UdpCommunicator::getGrabberAngle() {
	return data.grabber_angle;
}

bool UdpCommunicator::wifi_connected() {
	return (WiFi.status() == WL_CONNECTED);
}

IPAddress UdpCommunicator::local_ip() {
	return WiFi.localIP();
}

uint16_t UdpCommunicator::local_port() {
	return _local_port;
}
