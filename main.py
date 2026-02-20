from balltracker import Balltracker
import time
import board
import neopixel



"""
#LED Ring
"""
NUM_PIXELS = 24
pixels = neopixel.NeoPixel(board.D18, NUM_PIXELS, brightness=0.0, auto_write=True)
pixels.fill((255, 255, 255))


"""
#Balltracker
"""

# Create an instance
tracker = Balltracker(width=640, height=640)

# Start detection in a thread
tracker.start_balltracker(mode="color")


# Get the ball position
while True:
    pos = tracker.get_position()  # (x, y, z)
    print(pos)
    time.sleep(0.05)  # every 50 ms