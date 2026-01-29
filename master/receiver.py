#!/usr/bin/env python3
"""
Improved UDP JPEG Receiver
Based on better protocol design with proper headers and chunking
"""

import socket
import struct
import time
import threading
from collections import defaultdict
import numpy as np
import cv2


# Protocol constants
MAGIC = b"IM"
VERSION = 1
HEADER_FORMAT = "!2sBBIHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


class UDPJPEGReceiver:
    """
    Receives JPEG frames via UDP with chunking support
    
    Protocol:
    - Magic: 2 bytes ("IM")
    - Version: 1 byte
    - Camera ID: 1 byte
    - Frame ID: 4 bytes
    - Total chunks: 2 bytes
    - Chunk index: 2 bytes
    - JPEG size: 4 bytes
    - Payload size: 2 bytes
    - Flags: 2 bytes
    - Payload: variable
    """
    
    def __init__(self, bind_ip="0.0.0.0", bind_port=5000, 
                 rcvbuf_bytes=8*1024*1024, 
                 frame_timeout=0.5,
                 max_inflight_per_cam=10):
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.frame_timeout = frame_timeout
        self.max_inflight_per_cam = max_inflight_per_cam
        
        # Create socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf_bytes)
        self.sock.bind((self.bind_ip, self.bind_port))
        self.sock.settimeout(0.1)
        
        # Thread control
        self.running = False
        self.thread = None
        
        # Data structures
        self.lock = threading.Lock()
        
        # inflight[camera_id][frame_id] = FrameBuffer
        self.inflight = defaultdict(dict)
        
        # latest[camera_id] = (timestamp, bgr_image)
        self.latest = {}
        
        # Statistics
        self.stats = {
            'packets_received': 0,
            'packets_bad': 0,
            'frames_complete': 0,
            'frames_dropped': 0
        }
        self.last_stats_time = time.time()
        self.last_stats_print = time.time()
        
        print(f"UDP JPEG receiver listening on {bind_ip}:{bind_port}")
    
    def start(self):
        """Start the receiver thread"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()
        print("Receiver thread started")
    
    def stop(self):
        """Stop the receiver thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        try:
            self.sock.close()
        except:
            pass
        print("Receiver stopped")
    
    def get_latest_frames(self):
        """
        Get latest frame from all cameras
        
        Returns:
            dict: {camera_id: (timestamp, bgr_image)}
        """
        with self.lock:
            # Return copies to avoid threading issues
            return {
                cam_id: (t, img.copy())
                for cam_id, (t, img) in self.latest.items()
            }
    
    def get_latest_frame(self, camera_id):
        """
        Get latest frame from specific camera
        
        Returns:
            tuple: (timestamp, bgr_image) or None
        """
        with self.lock:
            if camera_id not in self.latest:
                return None
            t, img = self.latest[camera_id]
            return (t, img.copy())
    
    def _receive_loop(self):
        """Main receive loop"""
        while self.running:
            now = time.time()
            
            # Clean up old incomplete frames
            self._cleanup_timeouts(now)
            
            # Receive packet
            try:
                packet, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                self._maybe_print_stats()
                continue
            except Exception as e:
                if self.running:
                    print(f"Socket error: {e}")
                continue
            
            self.stats['packets_received'] += 1
            
            # Parse packet
            if len(packet) < HEADER_SIZE:
                self.stats['packets_bad'] += 1
                continue
            
            header = packet[:HEADER_SIZE]
            payload = packet[HEADER_SIZE:]
            
            try:
                (magic, version, camera_id, frame_id, 
                 total_chunks, chunk_index, jpeg_size, 
                 payload_size, flags) = struct.unpack(HEADER_FORMAT, header)
            except:
                self.stats['packets_bad'] += 1
                continue
            
            # Validate header
            if magic != MAGIC or version != VERSION:
                self.stats['packets_bad'] += 1
                continue
            
            if payload_size != len(payload):
                self.stats['packets_bad'] += 1
                continue
            
            if total_chunks == 0 or chunk_index >= total_chunks:
                self.stats['packets_bad'] += 1
                continue
            
            # Get or create frame buffer
            cam_frames = self.inflight[camera_id]
            
            if frame_id not in cam_frames:
                # New frame
                cam_frames[frame_id] = {
                    'chunks': [None] * total_chunks,
                    'total_chunks': total_chunks,
                    'jpeg_size': jpeg_size,
                    'received': 0,
                    'created_time': now
                }
                
                # Enforce limit on inflight frames
                self._enforce_inflight_limit(camera_id)
            
            frame_buffer = cam_frames[frame_id]
            
            # Validate consistency
            if (frame_buffer['total_chunks'] != total_chunks or 
                frame_buffer['jpeg_size'] != jpeg_size):
                # Inconsistent metadata, drop this frame
                del cam_frames[frame_id]
                self.stats['frames_dropped'] += 1
                continue
            
            # Store chunk if not already received
            if frame_buffer['chunks'][chunk_index] is None:
                frame_buffer['chunks'][chunk_index] = payload
                frame_buffer['received'] += 1
            
            # Check if frame is complete
            if frame_buffer['received'] == total_chunks:
                self._finalize_frame(camera_id, frame_id, frame_buffer)
                # Remove from inflight
                if frame_id in cam_frames:
                    del cam_frames[frame_id]
            
            self._maybe_print_stats()
    
    def _finalize_frame(self, camera_id, frame_id, frame_buffer):
        """Decode and store completed frame"""
        # Concatenate chunks
        jpeg_data = b''.join(frame_buffer['chunks'])
        
        # Trim to exact JPEG size
        if len(jpeg_data) > frame_buffer['jpeg_size']:
            jpeg_data = jpeg_data[:frame_buffer['jpeg_size']]
        
        # Decode JPEG
        try:
            arr = np.frombuffer(jpeg_data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            
            if img is not None:
                with self.lock:
                    self.latest[camera_id] = (time.time(), img)
                self.stats['frames_complete'] += 1
            else:
                self.stats['frames_dropped'] += 1
        except Exception as e:
            print(f"Error decoding frame from camera {camera_id}: {e}")
            self.stats['frames_dropped'] += 1
    
    def _cleanup_timeouts(self, now):
        """Remove old incomplete frames"""
        for camera_id in list(self.inflight.keys()):
            cam_frames = self.inflight[camera_id]
            
            for frame_id in list(cam_frames.keys()):
                frame_buffer = cam_frames[frame_id]
                age = now - frame_buffer['created_time']
                
                if age > self.frame_timeout:
                    del cam_frames[frame_id]
                    self.stats['frames_dropped'] += 1
            
            # Remove camera entry if no frames
            if not cam_frames:
                del self.inflight[camera_id]
    
    def _enforce_inflight_limit(self, camera_id):
        """Drop oldest frames if too many in flight"""
        cam_frames = self.inflight[camera_id]
        
        if len(cam_frames) <= self.max_inflight_per_cam:
            return
        
        # Sort by creation time and drop oldest
        frames_list = [
            (fid, fb) for fid, fb in cam_frames.items()
        ]
        frames_list.sort(key=lambda x: x[1]['created_time'])
        
        to_drop = len(frames_list) - self.max_inflight_per_cam
        for i in range(to_drop):
            frame_id = frames_list[i][0]
            del cam_frames[frame_id]
            self.stats['frames_dropped'] += 1
    
    def _maybe_print_stats(self):
        """Print statistics periodically"""
        now = time.time()
        
        if now - self.last_stats_print < 2.0:
            return
        
        elapsed = now - self.last_stats_time
        
        if elapsed > 0:
            pps = self.stats['packets_received'] / elapsed
            print(f"RX: {pps:.0f} pkts/s | "
                  f"Frames OK: {self.stats['frames_complete']} | "
                  f"Dropped: {self.stats['frames_dropped']} | "
                  f"Bad pkts: {self.stats['packets_bad']} | "
                  f"Active cams: {len(self.latest)}")
        
        # Reset counters
        self.stats['packets_received'] = 0
        self.stats['packets_bad'] = 0
        self.stats['frames_complete'] = 0
        self.stats['frames_dropped'] = 0
        self.last_stats_time = now
        self.last_stats_print = now
    
    def print_stats(self):
        """Print current statistics"""
        with self.lock:
            print("\n=== Statistics ===")
            print(f"Active cameras: {len(self.latest)}")
            for cam_id in sorted(self.latest.keys()):
                t, img = self.latest[cam_id]
                age = time.time() - t
                print(f"  Camera {cam_id}: {img.shape[1]}x{img.shape[0]}, age: {age*1000:.1f}ms")


def main():
    """Test the receiver"""
    import argparse
    
    parser = argparse.ArgumentParser(description='UDP JPEG Receiver Test')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--timeout', type=float, default=0.5)
    args = parser.parse_args()
    
    receiver = UDPJPEGReceiver(bind_port=args.port, frame_timeout=args.timeout)
    receiver.start()
    
    print("Displaying frames. Press 'q' or ESC to quit, 's' for stats")
    
    try:
        while True:
            frames = receiver.get_latest_frames()
            
            # Display each camera in its own window
            for camera_id, (timestamp, img) in frames.items():
                window_name = f"Camera {camera_id}"
                cv2.imshow(window_name, img)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('s'):
                receiver.print_stats()
    
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        receiver.stop()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
