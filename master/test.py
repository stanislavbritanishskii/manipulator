#!/usr/bin/env python3
"""
Multi-Camera Display Test
Receives and displays video streams from multiple cameras via UDP
"""

import cv2
import time
import argparse
from receiver import UDPFrameReceiver
import numpy as np


class MultiCameraDisplay:
    """Displays video feeds from multiple cameras"""
    
    def __init__(self, receiver, camera_ids=None, grid_cols=2):
        self.receiver = receiver
        self.camera_ids = camera_ids  # None means auto-detect
        self.grid_cols = grid_cols
        
        # FPS tracking
        self.fps_counters = {}
        self.last_fps_update = {}
        
    def create_grid_layout(self, frames_dict):
        """
        Create a grid layout of camera feeds
        
        Args:
            frames_dict: {camera_id: (frame_number, image, timestamp)}
        
        Returns:
            numpy array with grid layout
        """
        if not frames_dict:
            # Return a blank screen if no frames
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "Waiting for camera feeds...", (50, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return blank
        
        # Sort camera IDs for consistent layout
        sorted_ids = sorted(frames_dict.keys())
        
        # Determine grid size
        num_cameras = len(sorted_ids)
        grid_cols = min(self.grid_cols, num_cameras)
        grid_rows = (num_cameras + grid_cols - 1) // grid_cols
        
        # Get a sample frame to determine size
        sample_frame = frames_dict[sorted_ids[0]][1]
        frame_height, frame_width = sample_frame.shape[:2]
        
        # Calculate display size for each camera (resize for grid)
        display_width = 640
        display_height = int(display_width * frame_height / frame_width)
        
        # Create grid
        grid_height = display_height * grid_rows
        grid_width = display_width * grid_cols
        grid = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)
        
        # Place each camera feed in the grid
        for idx, camera_id in enumerate(sorted_ids):
            frame_number, img, timestamp = frames_dict[camera_id]
            
            # Calculate grid position
            row = idx // grid_cols
            col = idx % grid_cols
            
            # Resize frame
            resized = cv2.resize(img, (display_width, display_height))
            
            # Calculate FPS for this camera
            fps = self.calculate_fps(camera_id)
            
            # Add overlay with camera info
            overlay_text = f"Camera {camera_id} | Frame: {frame_number} | FPS: {fps:.1f}"
            cv2.putText(resized, overlay_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add timestamp
            age = time.time() - timestamp
            timestamp_text = f"Age: {age*1000:.1f}ms"
            cv2.putText(resized, timestamp_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Place in grid
            y_start = row * display_height
            y_end = y_start + display_height
            x_start = col * display_width
            x_end = x_start + display_width
            
            grid[y_start:y_end, x_start:x_end] = resized
        
        return grid
    
    def calculate_fps(self, camera_id):
        """Calculate FPS for a specific camera"""
        current_time = time.time()
        
        if camera_id not in self.fps_counters:
            self.fps_counters[camera_id] = 0
            self.last_fps_update[camera_id] = current_time
            return 0.0
        
        self.fps_counters[camera_id] += 1
        
        elapsed = current_time - self.last_fps_update[camera_id]
        if elapsed >= 1.0:  # Update FPS every second
            fps = self.fps_counters[camera_id] / elapsed
            self.fps_counters[camera_id] = 0
            self.last_fps_update[camera_id] = current_time
            return fps
        
        # Return last calculated FPS
        if elapsed > 0:
            return self.fps_counters[camera_id] / elapsed
        return 0.0
    
    def run(self):
        """Main display loop"""
        print("Starting multi-camera display...")
        print("Press 'q' or ESC to quit, 's' to show statistics")
        
        window_name = "Hand Manipulator Cameras"
        
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 1280, 720)
        except Exception as e:
            print(f"Error creating window: {e}")
            return
        
        frame_count = 0
        last_status_time = time.time()
        
        print("Display loop started. Waiting for frames...")
        
        try:
            while True:
                # Get latest frames
                if self.camera_ids:
                    # Get specific cameras
                    frames = {}
                    for cam_id in self.camera_ids:
                        frame_data = self.receiver.get_latest_frame(cam_id)
                        if frame_data:
                            frames[cam_id] = frame_data
                else:
                    # Auto-detect all cameras
                    frames = self.receiver.get_all_latest_frames()
                
                # Debug output every 2 seconds
                current_time = time.time()
                if current_time - last_status_time >= 2.0:
                    print(f"Status: {len(frames)} active camera(s), frame count: {frame_count}")
                    if len(frames) == 0:
                        print("  Waiting for camera data...")
                    last_status_time = current_time
                
                # Create grid layout
                display = self.create_grid_layout(frames)
                
                # Show the display
                try:
                    cv2.imshow(window_name, display)
                except Exception as e:
                    print(f"Error displaying frame: {e}")
                    break
                
                frame_count += 1
                
                # Handle keyboard input (CRITICAL: this must be called to update window)
                key = cv2.waitKey(30) & 0xFF
                if key == ord('q') or key == 27:  # q or ESC
                    print("Quit requested by user")
                    break
                elif key == ord('s'):
                    print("\n=== Statistics ===")
                    self.receiver.print_stats()
                
                # Check if window was closed
                try:
                    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                        print("Window was closed")
                        break
                except:
                    # Window might not exist anymore
                    break
                
        except KeyboardInterrupt:
            print("\nStopping display (Ctrl+C)...")
        except Exception as e:
            print(f"\nError in display loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("Cleaning up...")
            try:
                cv2.destroyAllWindows()
                cv2.waitKey(1)
            except:
                pass
            print("Display stopped")


def main():
    parser = argparse.ArgumentParser(description='Multi-camera UDP receiver and display')
    parser.add_argument('--port', type=int, default=5000,
                       help='UDP port to listen on (default: 5000)')
    parser.add_argument('--cameras', type=str, default=None,
                       help='Comma-separated camera IDs to display (default: auto-detect all)')
    parser.add_argument('--grid-cols', type=int, default=2,
                       help='Number of columns in grid layout (default: 2)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose debug output')
    
    args = parser.parse_args()
    
    # Parse camera IDs if specified
    camera_ids = None
    if args.cameras:
        try:
            camera_ids = [int(x.strip()) for x in args.cameras.split(',')]
            print(f"Displaying cameras: {camera_ids}")
        except ValueError:
            print("Error: Invalid camera IDs. Use comma-separated integers.")
            return
    
    # Create receiver
    print(f"Starting UDP receiver on port {args.port}...")
    receiver = UDPFrameReceiver(port=args.port)
    receiver.start()
    
    # Give receiver a moment to start
    time.sleep(0.5)
    print("Receiver started")
    
    # Create and run display
    display = MultiCameraDisplay(receiver, camera_ids=camera_ids, grid_cols=args.grid_cols)
    
    try:
        display.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    print("\nStopping receiver...")
    receiver.stop()
    
    print("\nFinal Statistics:")
    receiver.print_stats()
    
    print("\nDone!")


if __name__ == '__main__':
    main()
