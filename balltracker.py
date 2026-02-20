import time
import threading
from picamera2 import Picamera2
import cv2
import numpy as np
from GSCrop import set_camera_crop


class Balltracker:

    def __init__(self, width=400, height=400):
        
        self.width = width
        self.height = height
        self.tracking_task_period_us = 10000
        self.picam2 = None
        self.thread = None
        self.running = False
        self.mode = "color"
        self.mode_lock = threading.Lock()
        self.lock = threading.Lock()
        self.position = (0, 0, 0)



        # --- Kamera vorbereiten ---
        # Sensor auf hohen FPS-Modus croppen
        set_camera_crop(width, height)

    def start_balltracker(self, mode):

        with self.mode_lock:
            self.mode = mode

        # Kamera initialisieren
        self.picam2 = Picamera2()
        video_config = self.picam2.create_video_configuration(
            main={"size": (self.width, self.height)},
            raw=None,
            controls={
                "NoiseReductionMode": 0,  # deaktiviert Noise Reduction
                "FrameDurationLimits": (2000, 2000),  # 500 fps theoretisch
            }
        )

        self.picam2.configure(video_config)
        self.picam2.start()
        self.running = True
        self.thread = threading.Thread(
            target=self._detection_loop,
            daemon=True
        )
        self.thread.start()

        


    # --- Bildverarbeitung ---
    def _detect_ball_hough(self, frame):
        MIN_RADIUS = 20
        MAX_RADIUS = 100
        x = y = r = 0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.5, minDist=50,
                                param1=100, param2=40, minRadius=MIN_RADIUS, maxRadius=MAX_RADIUS)
        if circles is not None:
            circles = np.uint16(np.around(circles))
            c = circles[0][0]
            cv2.circle(frame, (c[0], c[1]), c[2], (0, 255, 0), 2)
            cv2.circle(frame, (c[0], c[1]), 2, (0, 0, 255), 3)
            x = c[0]
            y = c[1]
            r = c[2]
        return frame, x, y, r

    def _detect_ball_color(self, frame):
        x = y = radius = 0
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_orange = np.array([5, 150, 150])
        upper_orange = np.array([25, 255, 255])
        mask = cv2.inRange(hsv, lower_orange, upper_orange)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(largest)
            if radius > 5:
                center = (int(x), int(y))
                cv2.circle(frame, center, int(radius), (0, 255, 0), 2)
                cv2.circle(frame, center, 2, (0, 0, 255), 3)

        return frame, x, y, radius
    


    #test function to test performance without ball detection
    def _detect_ball_color_test(self, frame):
        x = y = radius = 0
        return frame, x, y, radius



    def _detection_loop(self):

        while self.running:
            # Start timer (like main_task_timer.reset() in C++)
            cycle_start_time = time.perf_counter()

            frame = self.picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            with self.mode_lock:
                current_mode = self.mode

            if current_mode == "hough":
                frame, x, y, r = self._detect_ball_hough(frame)
            elif current_mode == "color":
                frame, x, y, r = self._detect_ball_color(frame)
            else:
                raise RuntimeError("no or wrong mode selected")



            #To Do: calculation to get height / z from radius
            z = round(r,0) #change as soon as height is defined
            x = round(x,0)
            y = round(y,0)



            # Thread-sicher speichern
            with self.lock:
                self.position = (x, y, z)

            tracking_task_elapsed_time_us = (time.perf_counter() - cycle_start_time) * 1_000_000.0
            remaining_us = self.tracking_task_period_us - tracking_task_elapsed_time_us

            if remaining_us < 0:
                print("Warning: Main task took longer than main_task_period_ms")
            else:
                time.sleep(remaining_us / 1_000_000.0)


    def get_position(self):
        with self.lock:
            return self.position

    def stop(self):
        self.running = False
        self.thread.join()    