import time
import threading
from flask import Flask, Response, request
from picamera2 import Picamera2
import cv2
import numpy as np
from GSCrop import set_camera_crop

app = Flask(__name__)
picam2 = Picamera2()

# --- Kamera vorbereiten ---
# schneller FPS-Modus
CROP_WIDTH_FAST = 400
CROP_HEIGHT_FAST = 400
# Sensor auf langsamen FPS-Modus croppen
CROP_WIDTH_SLOW = 800
CROP_HEIGHT_SLOW = 800
# Calculate crop offsets if not provided (center crop)
x_offset_initial = (1440 - CROP_WIDTH_SLOW) // 2
y_offset_initial = (1088 - CROP_HEIGHT_SLOW) // 2
set_camera_crop(CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW, x_offset_initial, y_offset_initial)

# Kamera initialisieren
video_config = picam2.create_video_configuration(
    main={"size": (CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW)},
    raw=None,
    controls={
        "NoiseReductionMode": 0,  # deaktiviert Noise Reduction
        "FrameDurationLimits": (2000, 2000),  # 500 fps theoretisch
    }
)
picam2.configure(video_config)

picam2.start()

# Globale Variablen
fps = 0.0
MIN_RADIUS = 20
MAX_RADIUS = 100
fps_lock = threading.Lock()
mode_lock = threading.Lock()
mode = "hough"

# --- Bildverarbeitung ---
def detect_ball_hough(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.5, minDist=50,
                               param1=100, param2=30, minRadius=MIN_RADIUS, maxRadius=MAX_RADIUS)
    if circles is not None:
        circles = np.uint16(np.around(circles))
        # c = Tupel mit x, y, R
        c = circles[0][0]
        cv2.circle(frame, (c[0], c[1]), c[2], (0, 255, 0), 2)
        cv2.circle(frame, (c[0], c[1]), 2, (0, 0, 255), 3)
        return frame, True, (c[0], c[1], c[2])
    else:
        return frame, False, (None, None, None)

def detect_ball_color(frame):
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
            return frame, True, (int(x), int(y), int(radius))

    return frame, False, (None, None, None)


def draw_reference_circles(frame):
    h, w = frame.shape[:2]
    center = (w // 2, h // 2)
    cv2.circle(frame, center, MIN_RADIUS, (255, 0, 0), 1)
    cv2.circle(frame, center, MAX_RADIUS, (255, 0, 0), 1)
    return frame

# --- Streaming Funktion ---
def gen_frames():
    global fps, mode, x_offset_initial, y_offset_initial
    frame_counter = 0
    previous_mode = mode
    no_ball_counter = 0
    MAX_NO_BALL_FRAMES = 20

    crop_active = False  # Ob aktuell der Crop-Modus läuft
    # Sensorgröße (angepasst auf IMX296)
    sensor_width = 800
    sensor_height = 800
    start_time = time.time()


    while True:
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        with mode_lock:
            current_mode = mode
        
        if previous_mode != current_mode:
            print("restarting picam")
            # Crop deaktivieren, wieder ganzes Bild zeigen
            crop_active = False
            no_ball_counter = 0
            set_camera_crop(CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW)
            picam2.stop()
            video_config = picam2.create_video_configuration(
                main={"size": (CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW)},
                raw=None,
                controls={
                    "NoiseReductionMode": 0,
                    "FrameDurationLimits": (2000, 2000),
                }
            )
            picam2.configure(video_config)
            picam2.start()

            sensor_width = 800
            sensor_height = 800
            x_offset_initial = (1440 - CROP_WIDTH_SLOW) // 2
            y_offset_initial = (1088 - CROP_HEIGHT_SLOW) // 2
            previous_mode = current_mode
            print("picam restarted")

        if current_mode == "hough":
            frame = draw_reference_circles(frame)
            frame, found, dimensions = detect_ball_hough(frame)
        elif current_mode == "color":
            frame, found, dimensions = detect_ball_color(frame)

        #print(f"Ball bei ({dimensions[0]}, {dimensions[1]})")

          

        """
        if found & found_old == False:
            picam2.stop()
            set_camera_crop(CROP_WIDTH_FAST, CROP_HEIGHT_FAST, int(dimensions[0] + CROP_WIDTH_FAST / 2), int(dimensions[1] + CROP_HEIGHT_FAST))
            video_config = picam2.create_video_configuration(
                main={"size": (CROP_WIDTH_FAST, CROP_HEIGHT_FAST)},
                raw=None,
                controls={
                    "NoiseReductionMode": 0,  # deaktiviert Noise Reduction
                    "FrameDurationLimits": (2000, 2000),  # 500 fps theoretisch
                }
            )
            picam2.configure(video_config)
            picam2.start()

        if not found & found_old == True:
            picam2.stop()
            set_camera_crop(CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW)
            video_config = picam2.create_video_configuration(
                main={"size": (CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW)},
                raw=None,
                controls={
                    "NoiseReductionMode": 0,  # deaktiviert Noise Reduction
                    "FrameDurationLimits": (2000, 2000),  # 500 fps theoretisch
                }
            )
            picam2.configure(video_config)
            picam2.start()

        found_old = found
        """


        
        # Im Frame-Loop oder wo du den Crop setzt:
        if found and dimensions[0] is not None and dimensions[1] is not None:
            no_ball_counter = 0  # Reset Counter, da Ball gefunden
            if not crop_active or True:
                crop_active = True

                # Ball-Zentrum aus dimensions (zuvor erfasst)
                ball_x = dimensions[0]
                ball_y = dimensions[1]

                # --- Flip durchführen ---
                # 180° Rotation ≡ Horizontal + Vertikal Flip
                ball_x = sensor_width - ball_x
                ball_y = sensor_height - ball_y

                # Offset berechnen, sodass der Ball in der Mitte des Crops liegt
                x_offset = int(ball_x - CROP_WIDTH_FAST / 2) + x_offset_initial
                y_offset = int(ball_y - CROP_HEIGHT_FAST / 2) +y_offset_initial

                # Werte vom aktuellen offset in zwischenvariable / Initialwert speichern
                x_offset_initial = x_offset
                y_offset_initial = y_offset

                # Offset begrenzen, damit wir nicht außerhalb des Sensors croppen
                x_offset = max(0, min(x_offset, 1440 - CROP_WIDTH_FAST))
                y_offset = max(0, min(y_offset, 1088 - CROP_HEIGHT_FAST))

                # Debug-Ausgabe
                print(f"Ball bei ({dimensions[0]}, {dimensions[1]}), gecropt bei ({x_offset}, {y_offset})")


                # Crop setzen
                set_camera_crop(CROP_WIDTH_FAST, CROP_HEIGHT_FAST, x_offset, y_offset)

                
                picam2.stop()
                video_config = picam2.create_video_configuration(
                    main={"size": (CROP_WIDTH_FAST, CROP_HEIGHT_FAST)},
                    raw=None,
                    controls={
                        "NoiseReductionMode": 0,
                        "FrameDurationLimits": (2000, 2000),
                    }
                )
                picam2.configure(video_config)
                picam2.start()

                sensor_width = 400
                sensor_height = 400

        else:
            no_ball_counter += 1
            if no_ball_counter >= MAX_NO_BALL_FRAMES and crop_active:
                # Crop deaktivieren, wieder ganzes Bild zeigen
                crop_active = False
                no_ball_counter = 0
                set_camera_crop(CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW)
                picam2.stop()
                video_config = picam2.create_video_configuration(
                    main={"size": (CROP_WIDTH_SLOW, CROP_HEIGHT_SLOW)},
                    raw=None,
                    controls={
                        "NoiseReductionMode": 0,
                        "FrameDurationLimits": (2000, 2000),
                    }
                )
                picam2.configure(video_config)
                picam2.start()

                sensor_width = 800
                sensor_height = 800
                x_offset_initial = (1440 - CROP_WIDTH_SLOW) // 2
                y_offset_initial = (1088 - CROP_HEIGHT_SLOW) // 2

                


        """
        set_camera_crop(600, 600,
                        0,
                        0)
        picam2.stop()

        video_config = picam2.create_video_configuration(
            main={"size": (600, 600)},
            raw=None,
            controls={
                "NoiseReductionMode": 0,  # deaktiviert Noise Reduction
                "FrameDurationLimits": (2000, 2000),  # 500 fps theoretisch
            }
        )
        picam2.configure(video_config)
        picam2.start()
        """

        # FPS berechnen
        frame_counter += 1
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            with fps_lock:
                fps = frame_counter / elapsed
            frame_counter = 0
            start_time = time.time()

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# --- Flask-Routen ---
@app.route('/video_feed')
def video_feed():
    global mode
    requested_mode = request.args.get('mode', 'hough')
    with mode_lock:
        mode = requested_mode
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/fps')
def get_fps():
    with fps_lock:
        current_fps = fps
    return f"{current_fps:.2f}"

@app.route('/')
def index():
    return '''
    <html>
        <head>
            <title>Live Stream mit Tracking</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    margin: 0;
                    padding: 0;
                    background-color: #f5f5f5;
                }

                h1 {
                    margin-top: 20px;
                }

                .controls {
                    margin: 20px 0;
                }

                button {
                    font-size: 1em;
                    padding: 10px 20px;
                    margin: 0 10px;
                    cursor: pointer;
                }

                button.active {
                    background-color: #4CAF50;
                    color: white;
                }

                #video {
                    transform: scale(2);
                    transform-origin: top center;
                    display: block;
                    margin: 20px auto;
                    max-width: 100%;
                }

                #fps {
                    font-size: 1.2em;
                    font-weight: bold;
                    color: black;
                    background-color: rgba(255, 255, 255, 0.8);
                    display: inline-block;
                    padding: 6px 12px;
                    margin-top: 20px;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h1>Live Stream mit Ping-Pong Ball-Tracking</h1>
            <div class="controls">
                <button id="btn-hough" class="active" onclick="changeMode('hough')">Hough Circles</button>
                <button id="btn-color" onclick="changeMode('color')">Farbtracking Orange</button>
            </div>
            <div id="fps">FPS: Berechnung...</div>
            <img id="video" src="/video_feed?mode=hough" />
            

            <script>
                function fetchFPS() {
                    fetch('/fps?t=' + Date.now())
                        .then(response => response.text())
                        .then(data => {
                            document.getElementById('fps').innerText = 'FPS: ' + data;
                        })
                        .catch(console.error);
                }

                setInterval(fetchFPS, 1000);
                fetchFPS();

                function changeMode(mode) {
                    document.getElementById('video').src = '/video_feed?mode=' + mode + '&t=' + Date.now();
                    document.getElementById('btn-hough').classList.toggle('active', mode === 'hough');
                    document.getElementById('btn-color').classList.toggle('active', mode === 'color');
                }
            </script>
        </body>
    </html>
    '''


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
