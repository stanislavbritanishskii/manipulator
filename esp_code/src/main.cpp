#include <ESP32Servo.h>
#include "SerialCommunicator.hpp"
#include "UDPCommunicator.hpp"
#include "local_secrets.hpp"

static const uint16_t LISTEN_PORT = 5005;


static const int servoPin = 13;
static const int servoPin2 = 16;
static const int servoPin3 = 17;
static const int servoPin4 = 18;
static const int servoPin5 = 19;
static const int servoPin6 = 21;


Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;
Servo servo5;
Servo servo6;
SerialCommunicator SC;
UdpCommunicator comm(WIFI_SSID, WIFI_PASS, LISTEN_PORT);

void setup() {

	Serial.begin(115200);
	Serial.println("starting");
	servo1.attach(servoPin);
	servo2.attach(servoPin2);
	servo3.attach(servoPin3);
	servo4.attach(servoPin4);
	servo5.attach(servoPin5);
	servo6.attach(servoPin6);

	Serial.println("attached servos, waiting for wifi");
	bool wifi_ok = comm.begin();
	Serial.print("WiFi: ");
	Serial.println(wifi_ok ? "connected" : "NOT connected");
	Serial.print("IP: ");
	Serial.println(comm.local_ip());
	Serial.print("UDP port: ");
	Serial.println(comm.local_port());
}

void loop() {
	SC.read();
	if (SC.data_updated()) {
		servo1.write(SC.getBaseRotation());
		servo2.write(SC.getBaseAngle());
		servo3.write(SC.getElbowAngle());
		servo4.write(SC.getWristAngle());
		servo5.write(SC.getWristRotation());
		servo6.write(SC.getGrabberAngle());
	}
	comm.read();
	if (comm.data_updated()) {
		servo1.write(comm.getBaseRotation());
		servo2.write(comm.getBaseAngle());
		servo3.write(comm.getElbowAngle());
		servo4.write(comm.getWristAngle());
		servo5.write(comm.getWristRotation());
		servo6.write(comm.getGrabberAngle());

	}
	delay(20);
}
