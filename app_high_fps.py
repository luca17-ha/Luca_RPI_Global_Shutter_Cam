import time
import threading
from flask import Flask, Response
from picamera2 import Picamera2
import cv2
from GSCrop import set_camera_crop

# ---------- Kamera-Cropping festlegen ----------
CROP_WIDTH = 400
CROP_HEIGHT = 400
set_camera_crop(CROP_WIDTH, CROP_HEIGHT)

# ---------- Flask App vorbereiten ----------
app = Flask(__name__)
picam2 = Picamera2()

# Kamera konfigurieren (keine Rohdaten, nur das verarbeitete Bild vom ISP)
video_config = picam2.create_video_configuration(
    main={"size": (CROP_WIDTH, CROP_HEIGHT)},
    raw=None,
    controls={
        "NoiseReductionMode": 0,  # deaktiviert Noise Reduction
        "FrameDurationLimits": (2000, 2000),  # 500 fps theoretisch
    }
)
picam2.configure(video_config)

# Kamera starten
picam2.start()

# ---------- FPS-Zählung ----------
fps = 0.0
fps_lock = threading.Lock()

def gen_frames():
    global fps
    frame_counter = 0
    start_time = time.time()
    while True:
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)  # ISP liefert RGBA

        # FPS berechnen
        frame_counter += 1
        elapsed_time = time.time() - start_time
        if elapsed_time >= 1.0:
            with fps_lock:
                fps = frame_counter / elapsed_time
            frame_counter = 0
            start_time = time.time()

        # MJPEG-Stream generieren
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
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
            <title>Live Stream</title>
            <style>
                body { font-family: Arial, sans-serif; }
                #fps { font-size: 1.2em; color: black; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h1>Live Stream</h1>
            <img src="/video_feed" width="1000">
            <div id="fps">FPS: Calculating...</div>
            <script>
                function fetchFPS() {
                    fetch('/fps')
                        .then(response => response.text())
                        .then(data => {
                            document.getElementById('fps').innerText = 'FPS: ' + data;
                        })
                        .catch(error => console.error('Error fetching FPS:', error));
                }
                setInterval(fetchFPS, 1000);
                fetchFPS();
            </script>
        </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
