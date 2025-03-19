import socket
import pygame
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
from threading import Thread

pygame.mixer.init()
ALARME_SOM = "audio/alarme.mp3"  

HOST = "0.0.0.0"
PORT = 5000

def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Servidor ouvindo em {HOST}:{PORT}")

    while True:
        conn, addr = server_socket.accept()
        print(f"Conexão recebida de {addr}")

        while True:
            data = conn.recv(1024)
            if not data:
                break

            valor_sensor = data.decode().strip()
            print(f"Dado recebido: {valor_sensor}")

            if valor_sensor == "1":
                print("Sensor ativado! Tocando alarme...")
                pygame.mixer.music.load(ALARME_SOM)
                pygame.mixer.music.play(-1)  

        conn.close()

class AlarmeApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Controle de Alarme")
        self.setGeometry(200, 200, 300, 200)

        self.layout = QVBoxLayout()

        self.label = QLabel("Alarme desligado", self)
        self.layout.addWidget(self.label)

        self.desligar_alarme_btn = QPushButton("Desligar Alarme", self)
        self.desligar_alarme_btn.clicked.connect(self.desligar_alarme)
        self.layout.addWidget(self.desligar_alarme_btn)

        self.setLayout(self.layout)

    def tocar_alarme(self):
        pygame.mixer.music.load(ALARME_SOM)
        pygame.mixer.music.play(-1) 
        self.label.setText("Alarme ligado!")

    def desligar_alarme(self):
        pygame.mixer.music.stop()
        self.label.setText("Alarme desligado")

if __name__ == '__main__':
    server_thread = Thread(target=run_server)
    server_thread.daemon = True 
    server_thread.start()

    app = QApplication(sys.argv)
    window = AlarmeApp()
    window.show()
    sys.exit(app.exec_())
