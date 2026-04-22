import sys
import socket
import subprocess
import os
import time
import av
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, QThread, Signal


def get_connected_devices(adb_path):
    result = subprocess.run([adb_path, "devices"], capture_output=True, text=True)
    return [line.split("\t")[0] for line in result.stdout.splitlines() if "\tdevice" in line]


class VideoStreamThread(QThread):
    frame_ready = Signal(QImage)
    resize_requested = Signal(int, int)

    def __init__(self, adb_path, jar_path, scrcpy_path, device_id, port):
        super().__init__()
        self.adb_path = adb_path
        self.jar_path = jar_path
        self.scrcpy_path = scrcpy_path
        self.device_id = device_id
        self.port = port
        self.last_orientation = None
        self.audio_process = None

    def run(self):
        print(f"📱 Iniciando {self.device_id}")

        # 🔊 AUDIO SIN VENTANA
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.audio_process = subprocess.Popen([
                "C:\\xampp\\htdocs\\MirrorScreen\\scrcpy-win64-v3.3.4\\scrcpy.exe",
                "-s", self.device_id,
                "--no-video-playback",
                "--audio-source=output"
            ],
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # Subir server
        subprocess.run([
            self.adb_path, "-s", self.device_id,
            "push", self.jar_path, "/data/local/tmp/scrcpy-server.jar"
        ])

        subprocess.run([
            self.adb_path, "-s", self.device_id,
            "forward", "--remove-all"
        ])

        subprocess.run([
            self.adb_path, "-s", self.device_id,
            "forward", f"tcp:{self.port}", "localabstract:scrcpy"
        ], check=True)

        shell_cmd = (
            "CLASSPATH=/data/local/tmp/scrcpy-server.jar app_process / "
            "com.genymobile.scrcpy.Server 3.3.4 "
            "log_level=error video=true audio=false control=false "
            "max_size=1024 "
            "tunnel_forward=true send_device_meta=true send_frame_meta=true "
            "video_codec=h264"
        )

        subprocess.Popen([
            self.adb_path, "-s", self.device_id,
            "shell", shell_cmd
        ])

        time.sleep(3)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", self.port))

        sock.recv(64)
        sock.recv(8)

        codec = av.CodecContext.create('h264', 'r')

        fps_limit = 30
        last_time = 0

        try:
            while True:
                data = sock.recv(65536)
                if not data:
                    break

                packets = codec.parse(data)

                for packet in packets:
                    frames = codec.decode(packet)

                    for frame in frames:
                        now = time.time()
                        if now - last_time < 1 / fps_limit:
                            continue
                        last_time = now

                        
                        img = frame.to_ndarray(format='rgb24')

                        h, w, _ = img.shape

                        # 🔄 DETECTAR ROTACIÓN
                        orientation = "landscape" if w > h else "portrait"

                        if orientation != self.last_orientation:
                            self.last_orientation = orientation
                            self.resize_requested.emit(w, h)

                        qt_img = QImage(
                            img.data,
                            w,
                            h,
                            3 * w,
                            QImage.Format_RGB888
                        )

                        self.frame_ready.emit(qt_img.copy())

        except Exception as e:
            print(f"⚠️ Error {self.device_id}: {e}")

        finally:
            sock.close()

            if self.audio_process:
                self.audio_process.terminate()


class MirrorApp(QMainWindow):
    def __init__(self, title):
        super().__init__()

        self.setWindowTitle(title)
        self.resize(400, 700)
        self.setStyleSheet("background-color: black;")

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.label)

    def display_frame(self, q_img):
        pixmap = QPixmap.fromImage(q_img)

        scaled = pixmap.scaled(
            self.label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.label.setPixmap(scaled)
        
    def resize_window(self, w, h):
        screen = self.screen().availableGeometry()
        max_w = screen.width() * 0.6
        max_h = screen.height() * 0.9
        
        scale = min(max_w / w, max_h / h)
        
        new_w = int(w * scale)
        new_h = int(h * scale)
        self.resize(new_w, new_h)

    def closeEvent(self, event):
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    adb_path = os.path.normpath(os.path.join(base_dir, "..", "bin", "adb.exe"))
    jar_path = os.path.join(base_dir, "scrcpy-server.jar")
    scrcpy_path = os.path.normpath(os.path.join(base_dir, "..", "scrcpy", "scrcpy.exe"))

    devices = get_connected_devices(adb_path)

    if not devices:
        print("❌ No hay dispositivos conectados")
        sys.exit()

    windows = []
    base_port = 1234

    for i, device in enumerate(devices):
        port = base_port + i

        window = MirrorApp(f"📱 {device}")
        thread = VideoStreamThread(adb_path, jar_path, scrcpy_path, device, port)

        thread.frame_ready.connect(window.display_frame)
        thread.resize_requested.connect(window.resize_window)

        window.thread = thread
        thread.start()

        window.show()
        windows.append(window)

    sys.exit(app.exec())