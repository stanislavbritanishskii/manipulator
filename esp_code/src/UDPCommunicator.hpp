#ifndef UDPCOMMUNICATOR_HPP
#define UDPCOMMUNICATOR_HPP

#include <Arduino.h>
#include "SerialCommunicator.hpp"
#include <WiFi.h>
#include <WiFiUdp.h>
#include <string.h>

class UdpCommunicator {
public:
	UdpCommunicator(const char *ssid,
					const char *password,
					uint16_t local_port,
					uint32_t wifi_timeout_ms = 15000);

	bool begin();
	void read();
	bool data_updated();

	uint8_t getBaseRotation();
	uint8_t getBaseAngle();
	uint8_t getElbowAngle();
	uint8_t getWristAngle();
	uint8_t getWristRotation();
	uint8_t getFinger1();
	uint8_t getFinger2();

	bool wifi_connected();
	IPAddress local_ip();
	uint16_t local_port();

private:
	bool connect_wifi_();
	void start_udp_();

private:
	CommunicationData_t data;
	bool _data_updated;

	uint8_t buf[sizeof(CommunicationData_t)];

	const char *_ssid;
	const char *_password;
	uint16_t _local_port;
	uint32_t _wifi_timeout_ms;

	WiFiUDP udp;
	bool _udp_started;
};

#endif
