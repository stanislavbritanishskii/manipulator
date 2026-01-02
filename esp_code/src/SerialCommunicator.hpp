#ifndef SERIALCOMMUNICATOR_HPP
#define SERIALCOMMUNICATOR_HPP
#include <Arduino.h>


typedef struct CommunicationData {
	uint8_t base_rotation;
	uint8_t base_angle;
	uint8_t elbow_angle;
	uint8_t wrist_angle;
	uint8_t wrist_rotation;
	uint8_t grabber_angle;
} CommunicationData_t;

class SerialCommunicator {
public:
	SerialCommunicator();

	void read();

	bool data_updated();

	uint8_t getBaseRotation();

	uint8_t getBaseAngle();

	uint8_t getElbowAngle();

	uint8_t getWristAngle();

	uint8_t getWristRotation();

	uint8_t getGrabberAngle();

private:
	CommunicationData_t data;
	bool _data_updated;
	uint8_t *buf;
};


#endif
