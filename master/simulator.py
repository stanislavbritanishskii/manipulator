#!/usr/bin/env python3
"""
Camera Simulator - Improved Protocol
Simulates camera(s) sending UDP video for testing without Pi hardware
"""

import socket
import struct
import time
import argparse
import cv2
import numpy as np


# Protocol constants (must match receiver)
MAGIC = b"IM"
VERSION = 1
HEADER_FORMAT = "!2sBBIHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD_SIZE = 60000


class SimulatedCamera:
    """Simulates a camera by sending test patterns via UDP"""
    
    def __init__(self, camera_id, host, port, width=1920, height=1080, fps=30):
        self.camera_id = camera_id
        self.host = host
        self.port = port
        self.width = width
        self.height = height
        self.fps = fps
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Frame counter
        self.frame_id = 0
        
        print(f"Simulated Camera {camera_id}: {width}x{height} @ {fps}fps -> {host}:{port}")
    
    def generate_test_frame(self, frame_number):
        """Generate a test pattern frame"""
        # Create a colorful test pattern
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Background gradient
        for y in range(self.height):
            color_val = int(255 * y / self.height)
            img[y, :] = [color_val, 128, 255 - color_val]
        
        # Moving bars
        bar_pos = (frame_number * 10) % self.width
        cv2.rectangle(img, (bar_pos, 0), (bar_pos + 50, self.height), (255, 255, 255), -1)
        
        # Camera ID display
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = f"SIMULATED CAMERA {self.camera_id}"
        text_size = cv2.getTextSize(text, font, 3, 5)[0]
        text_x = (self.width - text_size[0]) // 2
        text_y = (self.height + text_size[1]) // 2
        
        # Black background for text
        cv2.rectangle(img, 
                     (text_x - 20, text_y - text_size[1] - 20),
                     (text_x + text_size[0] + 20, text_y + 20),
                     (0, 0, 0), -1)
        
        # White text
        cv2.putText(img, text, (text_x, text_y), font, 3, (255, 255, 255), 5)
        
        # Frame counter
        counter_text = f"Frame: {frame_number}"
        cv2.putText(img, counter_text, (50, 100), font, 2, (0, 255, 0), 4)
        
        # Timestamp
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(img, timestamp, (50, 200), font, 2, (0, 255, 255), 4)
        
        return img
    
    def compress_frame(self, frame):
        """Compress frame to JPEG"""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        return buffer.tobytes()
    
    def send_frame(self, jpeg_data):
        """Send a frame via UDP with chunking"""
        jpeg_size = len(jpeg_data)
        total_chunks = (jpeg_size + MAX_PAYLOAD_SIZE - 1) // MAX_PAYLOAD_SIZE
        
        for chunk_index in range(total_chunks):
            start_idx = chunk_index * MAX_PAYLOAD_SIZE
            end_idx = min(start_idx + MAX_PAYLOAD_SIZE, jpeg_size)
            payload = jpeg_data[start_idx:end_idx]
            payload_size = len(payload)
            
            # Build header
            header = struct.pack(
                HEADER_FORMAT,
                MAGIC,              # magic
                VERSION,            # version
                self.camera_id,     # camera ID
                self.frame_id,      # frame ID
                total_chunks,       # total chunks
                chunk_index,        # chunk index
                jpeg_size,          # JPEG size
                payload_size,       # payload size
                0                   # flags
            )
            
            packet = header + payload
            self.sock.sendto(packet, (self.host, self.port))
    
    def run(self):
        """Main simulation loop"""
        print(f"Starting simulated camera {self.camera_id}...")
        
        frame_interval = 1.0 / self.fps
        next_frame_time = time.time()
        
        try:
            while True:
                current_time = time.time()
                
                # Wait for next frame time
                if current_time < next_frame_time:
                    time.sleep(next_frame_time - current_time)
                    continue
                
                # Generate and send frame
                frame = self.generate_test_frame(self.frame_id)
                compressed = self.compress_frame(frame)
                self.send_frame(compressed)
                
                # Update timing
                self.frame_id = (self.frame_id + 1) % (2**32)
                next_frame_time += frame_interval
                
                # Print status
                if self.frame_id % 30 == 0:
                    print(f"Camera {self.camera_id}: Frame {self.frame_id}, Size: {len(compressed)} bytes")
                
        except KeyboardInterrupt:
            print(f"\nStopping simulated camera {self.camera_id}")
        finally:
            self.sock.close()


def main():
    parser = argparse.ArgumentParser(description='Simulate camera(s) for testing')
    parser.add_argument('--camera-id', type=int, default=0,
                       help='Camera ID to simulate (default: 0)')
    parser.add_argument('--num-cameras', type=int, default=1,
                       help='Number of cameras to simulate (default: 1)')
    parser.add_argument('--host', type=str, default='localhost',
                       help='PC IP address (default: localhost)')
    parser.add_argument('--port', type=int, default=5000,
                       help='UDP port (default: 5000)')
    parser.add_argument('--width', type=int, default=1280,
                       help='Frame width (default: 1280)')
    parser.add_argument('--height', type=int, default=720,
                       help='Frame height (default: 720)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Frames per second (default: 30)')
    
    args = parser.parse_args()
    
    if args.num_cameras > 1:
        # Simulate multiple cameras with threading
        import threading
        
        cameras = []
        threads = []
        
        for i in range(args.num_cameras):
            cam_id = args.camera_id + i
            cam = SimulatedCamera(cam_id, args.host, args.port, 
                                args.width, args.height, args.fps)
            cameras.append(cam)
            
            thread = threading.Thread(target=cam.run, daemon=True)
            threads.append(thread)
            thread.start()
        
        print(f"\nSimulating {args.num_cameras} cameras. Press Ctrl+C to stop.\n")
        
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("\nStopping all simulated cameras...")
    else:
        # Single camera
        camera = SimulatedCamera(args.camera_id, args.host, args.port,
                               args.width, args.height, args.fps)
        camera.run()


if __name__ == '__main__':
    main()
