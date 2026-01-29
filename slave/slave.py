#!/usr/bin/env python3
"""
Improved Camera Sender for Raspberry Pi
Uses proper protocol with headers for reliable transmission
"""

import socket
import struct
import time
import argparse
import cv2
from picamera2 import Picamera2


# Protocol constants (must match receiver)
MAGIC = b"IM"
VERSION = 1
HEADER_FORMAT = "!2sBBIHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD_SIZE = 60000  # Leave room for headers in 65507 UDP max


class ImprovedCameraSender:
    """Sends camera frames via UDP with chunking"""
    
    def __init__(self, camera_id, host, port, 
                 width=1920, height=1080, fps=30, quality=95):
        self.camera_id = camera_id
        self.host = host
        self.port = port
        self.width = width
        self.height = height
        self.fps = fps
        self.quality = quality
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Frame counter
        self.frame_id = 0
        
        # Statistics
        self.frames_sent = 0
        self.bytes_sent = 0
        self.start_time = time.time()
        self.last_stats_time = time.time()
        
        # Initialize camera
        self.setup_camera()
        
        print(f"Camera {camera_id} initialized: {width}x{height} @ {fps}fps")
        print(f"Streaming to {host}:{port}")
    
    def setup_camera(self):
        """Configure camera for video streaming"""
        self.camera = Picamera2()
        
        config = self.camera.create_video_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"},
            controls={"FrameRate": self.fps}
        )
        self.camera.configure(config)
        
        print(f"Camera configured successfully")
    
    def compress_frame(self, frame):
        """Compress frame to JPEG"""
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
        success, buffer = cv2.imencode('.jpg', frame, encode_params)
        
        if not success:
            return None
        
        return buffer.tobytes()
    
    def send_frame(self, jpeg_data):
        """
        Send a frame via UDP with chunking if necessary
        
        Returns:
            Number of chunks sent
        """
        jpeg_size = len(jpeg_data)
        
        # Calculate number of chunks needed
        total_chunks = (jpeg_size + MAX_PAYLOAD_SIZE - 1) // MAX_PAYLOAD_SIZE
        
        # Send each chunk
        for chunk_index in range(total_chunks):
            start_idx = chunk_index * MAX_PAYLOAD_SIZE
            end_idx = min(start_idx + MAX_PAYLOAD_SIZE, jpeg_size)
            payload = jpeg_data[start_idx:end_idx]
            payload_size = len(payload)
            
            # Build header
            header = struct.pack(
                HEADER_FORMAT,
                MAGIC,              # 2 bytes: magic
                VERSION,            # 1 byte: version
                self.camera_id,     # 1 byte: camera ID
                self.frame_id,      # 4 bytes: frame ID
                total_chunks,       # 2 bytes: total chunks
                chunk_index,        # 2 bytes: chunk index
                jpeg_size,          # 4 bytes: total JPEG size
                payload_size,       # 2 bytes: this payload size
                0                   # 2 bytes: flags (reserved)
            )
            
            # Send packet
            packet = header + payload
            self.sock.sendto(packet, (self.host, self.port))
            self.bytes_sent += len(packet)
        
        return total_chunks
    
    def print_stats(self):
        """Print transmission statistics"""
        now = time.time()
        elapsed = now - self.last_stats_time
        
        if elapsed >= 2.0:
            total_elapsed = now - self.start_time
            avg_fps = self.frames_sent / total_elapsed if total_elapsed > 0 else 0
            
            mbps = (self.bytes_sent * 8 / elapsed) / (1024 * 1024)
            
            print(f"Camera {self.camera_id}: "
                  f"{self.frames_sent} frames | "
                  f"FPS: {avg_fps:.1f} | "
                  f"Bandwidth: {mbps:.2f} Mbps")
            
            self.bytes_sent = 0
            self.last_stats_time = now
    
    def run(self):
        """Main capture and send loop"""
        print(f"Starting camera {self.camera_id}...")
        self.camera.start()
        
        frame_interval = 1.0 / self.fps
        next_frame_time = time.time()
        
        try:
            while True:
                current_time = time.time()
                
                # Wait for next frame time (frame rate limiting)
                if current_time < next_frame_time:
                    time.sleep(next_frame_time - current_time)
                    continue
                
                # Capture frame
                frame = self.camera.capture_array()
                
                # Compress to JPEG
                jpeg_data = self.compress_frame(frame)
                
                if jpeg_data is None:
                    print(f"Warning: Failed to compress frame {self.frame_id}")
                    continue
                
                # Send via UDP
                chunks_sent = self.send_frame(jpeg_data)
                
                # Update counters
                self.frames_sent += 1
                self.frame_id = (self.frame_id + 1) % (2**32)
                
                # Update timing for next frame
                next_frame_time += frame_interval
                
                # Prevent drift - if we're falling behind, reset
                if next_frame_time < current_time - frame_interval:
                    next_frame_time = current_time + frame_interval
                
                # Print stats
                self.print_stats()
                
        except KeyboardInterrupt:
            print(f"\nStopping camera {self.camera_id}...")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.camera.stop()
            self.sock.close()
            print(f"Camera {self.camera_id} stopped")


def main():
    parser = argparse.ArgumentParser(description='Improved Camera Sender for Pi')
    parser.add_argument('--camera-id', type=int, required=True,
                       help='Unique camera ID (0-255)')
    parser.add_argument('--host', type=str, required=True,
                       help='PC IP address')
    parser.add_argument('--port', type=int, default=5000,
                       help='UDP port (default: 5000)')
    parser.add_argument('--width', type=int, default=1920,
                       help='Frame width (default: 1920)')
    parser.add_argument('--height', type=int, default=1080,
                       help='Frame height (default: 1080)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Frames per second (default: 30)')
    parser.add_argument('--quality', type=int, default=95,
                       help='JPEG quality 1-100 (default: 95)')
    
    args = parser.parse_args()
    
    # Validate
    if args.camera_id < 0 or args.camera_id > 255:
        print("Error: camera-id must be 0-255")
        return
    
    if args.quality < 1 or args.quality > 100:
        print("Error: quality must be 1-100")
        return
    
    # Create and run sender
    sender = ImprovedCameraSender(
        camera_id=args.camera_id,
        host=args.host,
        port=args.port,
        width=args.width,
        height=args.height,
        fps=args.fps,
        quality=args.quality
    )
    
    sender.run()


if __name__ == '__main__':
    main()
