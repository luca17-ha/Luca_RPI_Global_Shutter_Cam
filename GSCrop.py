"""
GScrop converted to python
"""
import subprocess
import os
import re


def set_camera_crop(width, height, x_offset=None, y_offset=None, media_device=None):
    """
    Set camera crop settings using media-ctl.

    Args:
        width (int): Width of the crop window (must be even)
        height (int): Height of the crop window (must be even)
        x_offset (int, optional): X offset for crop. If None, centers the crop.
        y_offset (int, optional): Y offset for crop. If None, centers the crop.
        media_device (int, optional): Media device number. If None, tries devices 0-5.

    Returns:
        bool: True if successful, False otherwise
    """
    # Validate width and height are even numbers
    if width % 2 != 0 or height % 2 != 0:
        raise ValueError("Width and height must be even numbers")

    # Detect if we're on a Raspberry Pi 5 with CM4 camera (like the script does)
    is_pi_5 = False
    device_id = "10"  # Default device ID

    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            if re.search(r"Revision.*: ...17.$", cpuinfo):
                is_pi_5 = True
                # Check for cam1 environment variable as in original script
                if os.environ.get("cam1"):
                    device_id = "11"
                else:
                    device_id = "10"
    except:
        pass

    # Calculate crop offsets if not provided (center crop)
    if x_offset is None:
        x_offset = (1440 - width) // 2
    if y_offset is None:
        y_offset = (1088 - height) // 2

    # Determine which media device to use
    if media_device is not None:
        media_devices = [media_device]
    else:
        media_devices = range(6)  # Try devices 0-5 as in the original script

    # Format the media-ctl command
    crop_fmt = f"'imx296 {device_id}-001a':0 [fmt:SBGGR10_1X10/{width}x{height} crop:({x_offset},{y_offset})/{width}x{height}]"

    # Try to set the crop on each media device until success
    for m in media_devices:
        cmd = ["media-ctl", "-d", f"/dev/media{m}", "--set-v4l2", crop_fmt]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(
                    f"Successfully set crop on /dev/media{m}: {width}x{height} at offset ({x_offset},{y_offset})"
                )
                return True
        except Exception as e:
            print(f"Error setting crop on /dev/media{m}: {e}")

    print("Failed to set crop on any media device")
    return False


def list_cameras():
    """List available cameras using libcamera-hello"""
    try:
        subprocess.run(["libcamera-hello", "--list-cameras"], check=True)
        return True
    except Exception as e:
        print(f"Error listing cameras: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Set camera crop settings")
    parser.add_argument(
        "width", type=int, help="Width of the crop window (must be even)"
    )
    parser.add_argument(
        "height", type=int, help="Height of the crop window (must be even)"
    )
    parser.add_argument(
        "--x-offset", type=int, help="X offset for crop (default: centered)"
    )
    parser.add_argument(
        "--y-offset", type=int, help="Y offset for crop (default: centered)"
    )
    parser.add_argument(
        "--media-device", type=int, help="Media device number (default: auto-detect)"
    )
    parser.add_argument(
        "--list-cameras", action="store_true", help="List available cameras"
    )

    args = parser.parse_args()

    if args.list_cameras:
        list_cameras()

    set_camera_crop(
        args.width, args.height, args.x_offset, args.y_offset, args.media_device
    )