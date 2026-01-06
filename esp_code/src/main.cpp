#include <ESP32Servo.h>
#include "SerialCommunicator.hpp"
#include "UDPCommunicator.hpp"
#include "local_secrets.hpp"

static const uint16_t LISTEN_PORT = 5005;

static const int servoPin = 13;
static const int servoPin2 = 22;
static const int servoPin3 = 23;
static const int servoPin4 = 18;
static const int servoPin5 = 19;
static const int servoPin_gripper1 = 21;
static const int servoPin_gripper2 = 22;

Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;
Servo servo5;
Servo servo_gripper1;
Servo servo_gripper2;

SerialCommunicator SC;
UdpCommunicator comm(WIFI_SSID, WIFI_PASS, LISTEN_PORT);

void setup() {
	Serial.begin(115200);

	servo1.attach(servoPin);
	servo2.attach(servoPin2);
	servo3.attach(servoPin3);
	servo4.attach(servoPin4);
	servo5.attach(servoPin5);
	servo_gripper1.attach(servoPin_gripper1);
	servo_gripper2.attach(servoPin_gripper2);

	bool wifi_ok = comm.begin();
	Serial.println(wifi_ok ? "WiFi connected" : "WiFi NOT connected");
}

void loop() {
	SC.read();
	if (SC.data_updated()) {
		servo1.write(SC.getBaseRotation());
		servo2.write(SC.getBaseAngle());
		servo3.write(SC.getElbowAngle());
		servo4.write(SC.getWristAngle());
		servo5.write(SC.getWristRotation());
		servo_gripper1.write(SC.getFinger1());
		servo_gripper2.write(SC.getFinger2());
	}

	comm.read();
	if (comm.data_updated()) {
		servo1.write(comm.getBaseRotation());
		servo2.write(comm.getBaseAngle());
		servo3.write(comm.getElbowAngle());
		servo4.write(comm.getWristAngle());
		servo5.write(comm.getWristRotation());
		servo_gripper1.write(comm.getFinger1());
		servo_gripper2.write(comm.getFinger2());
	}

	delay(20);
}
