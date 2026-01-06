#include "SerialCommunicator.hpp"
#include <string.h>

SerialCommunicator::SerialCommunicator() {
	Serial.begin(115200);
	_data_updated = false;

	memset(&data, 0, sizeof(data));

	buf = static_cast<uint8_t *>(malloc(sizeof(data)));
	if (buf != NULL) {
		memset(buf, 0, sizeof(data));
	}
}

void SerialCommunicator::read() {
	int counter = 0;
	_data_updated = false;

	while (Serial.available() > 0) {
		buf[counter] = Serial.read();
		counter++;
		counter %= sizeof(data);
		_data_updated = true;
	}

	_data_updated *= (counter == 0);

	if (_data_updated) {
		memcpy(&data, buf, sizeof(data));
	}
}

bool SerialCommunicator::data_updated() {
	return _data_updated;
}

uint8_t SerialCommunicator::getBaseRotation() {
	return data.base_rotation;
}

uint8_t SerialCommunicator::getBaseAngle() {
	return data.base_angle;
}

uint8_t SerialCommunicator::getElbowAngle() {
	return data.elbow_angle;
}

uint8_t SerialCommunicator::getWristAngle() {
	return data.wrist_angle;
}

uint8_t SerialCommunicator::getWristRotation() {
	return data.wrist_rotation;
}

uint8_t SerialCommunicator::getFinger1() {
	return data.finger1;
}

uint8_t SerialCommunicator::getFinger2() {
	return data.finger2;
}
