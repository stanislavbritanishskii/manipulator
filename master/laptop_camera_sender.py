#!/usr/bin/env python3
"""
Laptop Camera Sender
Sends webcam video via UDP using OpenCV (for standard webcams)
"""

import socket
import struct
import time
import argparse
import cv2


# Protocol constants (must match receiver)
MAGIC = b"IM"
VERSION = 1
HEADER_FORMAT = "!2sBBIHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD_SIZE = 60000  # Leave room for headers in 65507 UDP max


class LaptopCameraSender:
    """Sends laptop/webcam frames via UDP with chunking"""
    
    def __init__(self, camera_id, host, port, 
                 device_index=0,
                 width=1920, height=1080, fps=30, quality=95):
        self.camera_id = camera_id
        self.host = host
        self.port = port
        self.device_index = device_index
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
        self.cap = None
        self.setup_camera()
        
        print(f"Laptop camera {camera_id} initialized: {width}x{height} @ {fps}fps")
        print(f"Streaming to {host}:{port}")
    
    def setup_camera(self):
        """Open and configure webcam"""
        print(f"Opening camera device {self.device_index}...")
        
        # Try to open camera
        self.cap = cv2.VideoCapture(self.device_index)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera device {self.device_index}")
        
        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Read actual properties (camera might not support requested values)
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        
        print(f"Camera opened successfully")
        print(f"  Requested: {self.width}x{self.height} @ {self.fps}fps")
        print(f"  Actual: {actual_width}x{actual_height} @ {actual_fps}fps")
        
        # Update to actual values
        self.width = actual_width
        self.height = actual_height
        if actual_fps > 0:
            self.fps = actual_fps
    
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
    
    def run(self, show_preview=False):
        """Main capture and send loop"""
        print(f"Starting laptop camera {self.camera_id}...")
        if show_preview:
            print("Showing preview window (press 'q' to quit)")
        else:
            print("Running headless (press Ctrl+C to quit)")
        
        frame_interval = 1.0 / self.fps
        next_frame_time = time.time()
        
        try:
            while True:
                current_time = time.time()
                
                # Read frame from camera
                ret, frame = self.cap.read()
                
                if not ret:
                    print("Warning: Failed to capture frame")
                    time.sleep(0.1)
                    continue
                
                # Show preview if requested
                if show_preview:
                    cv2.imshow(f'Camera {self.camera_id} Preview', frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        print("Quit requested from preview window")
                        break
                
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
                
                # Frame rate limiting
                next_frame_time += frame_interval
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                elif sleep_time < -frame_interval:
                    # We're falling behind, reset timing
                    next_frame_time = time.time() + frame_interval
                
                # Print stats
                self.print_stats()
                
        except KeyboardInterrupt:
            print(f"\nStopping camera {self.camera_id}...")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.cap is not None:
                self.cap.release()
            if show_preview:
                cv2.destroyAllWindows()
            self.sock.close()
            print(f"Camera {self.camera_id} stopped")


def list_cameras():
    """List available camera devices"""
    print("Scanning for cameras...")
    available = []
    
    for i in range(10):  # Check first 10 device indices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            available.append((i, width, height))
            cap.release()
    
    if not available:
        print("No cameras found!")
    else:
        print(f"Found {len(available)} camera(s):")
        for idx, w, h in available:
            print(f"  Device {idx}: {w}x{h}")
    
    return available


def main():
    parser = argparse.ArgumentParser(description='Laptop Camera Sender')
    parser.add_argument('--camera-id', type=int, required=True,
                       help='Unique camera ID for this stream (0-255)')
    parser.add_argument('--host', type=str, required=True,
                       help='PC IP address to send to')
    parser.add_argument('--port', type=int, default=5000,
                       help='UDP port (default: 5000)')
    parser.add_argument('--device', type=int, default=0,
                       help='Camera device index (default: 0, use --list to see available)')
    parser.add_argument('--width', type=int, default=1280,
                       help='Frame width (default: 1280)')
    parser.add_argument('--height', type=int, default=720,
                       help='Frame height (default: 720)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Frames per second (default: 30)')
    parser.add_argument('--quality', type=int, default=95,
                       help='JPEG quality 1-100 (default: 95)')
    parser.add_argument('--preview', action='store_true',
                       help='Show preview window of camera feed')
    parser.add_argument('--list', action='store_true',
                       help='List available cameras and exit')
    
    args = parser.parse_args()
    
    # List cameras if requested
    if args.list:
        list_cameras()
        return
    
    # Validate
    if args.camera_id < 0 or args.camera_id > 255:
        print("Error: camera-id must be 0-255")
        return
    
    if args.quality < 1 or args.quality > 100:
        print("Error: quality must be 1-100")
        return
    
    # Create and run sender
    try:
        sender = LaptopCameraSender(
            camera_id=args.camera_id,
            host=args.host,
            port=args.port,
            device_index=args.device,
            width=args.width,
            height=args.height,
            fps=args.fps,
            quality=args.quality
        )
        
        sender.run(show_preview=args.preview)
        
    except RuntimeError as e:
        print(f"\nError: {e}")
        print("\nTry:")
        print("  1. Run with --list to see available cameras")
        print("  2. Try different --device values (0, 1, 2, etc.)")
        print("  3. Check camera permissions")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
