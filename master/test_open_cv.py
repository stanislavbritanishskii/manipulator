#!/usr/bin/env python3
"""
Minimal Display Test
Tests if OpenCV window works properly on your system
"""

import cv2
import numpy as np
import time

def test_opencv_window():
    """Test basic OpenCV window functionality"""
    
    print("Testing OpenCV window...")
    print("This will display a simple animation for 5 seconds")
    print("Press 'q' to quit early, or wait for auto-close")
    print()
    
    window_name = "OpenCV Test"
    
    try:
        # Create window
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 640, 480)
        print("✓ Window created")
        
        # Test animation
        start_time = time.time()
        frame_count = 0
        
        while True:
            # Create test image
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Moving circle
            elapsed = time.time() - start_time
            x = int((np.sin(elapsed * 2) * 0.4 + 0.5) * 640)
            y = int((np.cos(elapsed * 2) * 0.4 + 0.5) * 480)
            
            cv2.circle(img, (x, y), 50, (0, 255, 0), -1)
            
            # Text
            cv2.putText(img, f"Frame: {frame_count}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(img, f"Time: {elapsed:.1f}s", (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(img, "Press 'q' to quit", (10, 110),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # Display
            cv2.imshow(window_name, img)
            
            # Wait and check for key
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q') or key == 27:
                print("\n✓ User quit - window is responsive!")
                break
            
            # Auto-quit after 5 seconds
            if elapsed > 5.0:
                print("\n✓ Test complete - window works!")
                break
            
            # Check if window still exists
            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    print("\n✓ Window close detected!")
                    break
            except:
                print("\n⚠ Window disappeared unexpectedly")
                break
            
            frame_count += 1
        
        print(f"Displayed {frame_count} frames")
        print()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            cv2.destroyAllWindows()
            cv2.waitKey(1)
        except:
            pass
    
    return True

if __name__ == '__main__':
    print("="*60)
    print("OpenCV Window Test")
    print("="*60)
    print()
    
    success = test_opencv_window()
    
    print()
    if success:
        print("✓ OpenCV is working correctly on your system!")
        print("  You can now test the camera display.")
    else:
        print("✗ OpenCV window test failed!")
        print("  Check your OpenCV installation:")
        print("    pip install --upgrade opencv-python")
    
    print()
