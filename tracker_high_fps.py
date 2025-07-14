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
# Sensor auf hohen FPS-Modus croppen
CROP_WIDTH = 400
CROP_HEIGHT = 400
set_camera_crop(CROP_WIDTH, CROP_HEIGHT)

# Kamera initialisieren
video_config = picam2.create_video_configuration(
    main={"size": (CROP_WIDTH, CROP_HEIGHT)},
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
                               param1=100, param2=40, minRadius=MIN_RADIUS, maxRadius=MAX_RADIUS)
    if circles is not None:
        circles = np.uint16(np.around(circles))
        c = circles[0][0]
        cv2.circle(frame, (c[0], c[1]), c[2], (0, 255, 0), 2)
        cv2.circle(frame, (c[0], c[1]), 2, (0, 0, 255), 3)
    return frame

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

    return frame

def draw_reference_circles(frame):
    h, w = frame.shape[:2]
    center = (w // 2, h // 2)
    cv2.circle(frame, center, MIN_RADIUS, (255, 0, 0), 1)
    cv2.circle(frame, center, MAX_RADIUS, (255, 0, 0), 1)
    return frame

# --- Streaming Funktion ---
def gen_frames():
    global fps, mode
    frame_counter = 0
    start_time = time.time()

    while True:
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        with mode_lock:
            current_mode = mode

        if current_mode == "hough":
            frame = draw_reference_circles(frame)
            frame = detect_ball_hough(frame)
        elif current_mode == "color":
            frame = detect_ball_color(frame)

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
                    margin-top: 2px;
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
