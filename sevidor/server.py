import socket
import pygame
import sys
import os
import base64
import hashlib
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QHBoxLayout, QPushButton, QFrame, QApplication
from threading import Thread, Lock
import time

pygame.mixer.init()
ALARME_SOM = "audio/alarme.mp3"  

HOST = "0.0.0.0"
PORT = 5000

FOTOS_DIR = "fotos"
if not os.path.exists(FOTOS_DIR):
    os.makedirs(FOTOS_DIR)

fotos_recebidas = []
fotos_lock = Lock()  

def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  
    
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    if hasattr(socket, 'TCP_KEEPIDLE'):
        server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)  
    if hasattr(socket, 'TCP_KEEPINTVL'):
        server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  
    if hasattr(socket, 'TCP_KEEPCNT'):
        server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3) 
        
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Servidor ouvindo em {HOST}:{PORT}")

    while True:
        try:
            conn, addr = server_socket.accept()
           
            conn.settimeout(120)  
            
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  
            
            
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, 'TCP_KEEPIDLE'):
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, 'TCP_KEEPCNT'):
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                
            print(f"Conexão recebida de {addr}")
            
            client_thread = Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
        except Exception as e:
            print(f"Erro ao aceitar conexão: {e}")
            

def add_base64_padding(base64_str):
    
    padding_needed = 4 - len(base64_str) % 4
    if padding_needed != 4:
        
        base64_str += "=" * padding_needed
    return base64_str

def handle_client(conn, addr):
    max_errors = 5
    error_count = 0
    
    try:
        receiving_photo = False
        photo_data = ""
        photo_name = f"photo_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        photo_size = 0
        photo_timestamp = ""
        photo_hash = ""
        in_data_section = False
        last_activity = time.time()
        
        print(f"Nova conexão de {addr}")
        
        while True:
            try:
                
                if time.time() - last_activity > 180:  
                    print(f"⏱️ Conexão com {addr} inativa por muito tempo. Fechando.")
                    break
                
                error_count = 0
                
                conn.settimeout(30)
                data = conn.recv(32768)  
                
                if not data:
                    print(f"Cliente {addr} desconectado - dados vazios")
                    break
                
                last_activity = time.time()
                
                try:
                    message = data.decode('utf-8', errors='replace').strip()
                    lines = message.splitlines()
                    
                    for line in lines:
                        line = line.strip()
                        
                        
                        if line == "HELLO":
                            print(f"Recebido handshake de {addr}")
                            try:
                                conn.send("HELLO_ACK\n".encode())
                                print(f"Resposta de handshake enviada para {addr}")
                            except Exception as e:
                                print(f"Erro ao enviar resposta de handshake: {e}")
                            continue
                            
                       
                        if line == "PING":
                            try:
                                conn.send("PONG\n".encode())
                                print(f"Keepalive recebido de {addr}, enviado PONG")
                            except Exception as e:
                                print(f"Erro ao enviar resposta de keepalive: {e}")
                            continue
                        
                        if in_data_section and "END_DATA" not in line:
                            
                            base64_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
                            filtered_line = ''.join(c for c in line if c in base64_chars)
                            photo_data += filtered_line
                            
                            if len(photo_data) % 10000 == 0:
                                print(f"Recebidos {len(photo_data)} caracteres base64 até agora...")
                            continue
                        
                        if line == "STORE_PHOTO":
                            receiving_photo = True
                            photo_data = ""
                            in_data_section = False
                            print(f"Iniciando recebimento de foto de {addr}")
                        
                        elif line.startswith("TIMESTAMP:"):
                            photo_timestamp = line[10:]
                            print(f"Timestamp: {photo_timestamp}")
                        
                        elif line.startswith("SIZE:"):
                            try:
                                photo_size = int(line[5:])
                                print(f"Tamanho da foto: {photo_size} bytes")
                            except ValueError:
                                print(f"Erro ao converter tamanho da foto: {line[5:]}")
                                photo_size = 0
                        
                        elif line.startswith("HASH:"):
                            photo_hash = line[5:]
                            print(f"Hash recebido: {photo_hash}")
                        
                        elif line == "BEGIN_DATA":
                            in_data_section = True
                            print("Iniciando recebimento de dados da foto")
                        
                        elif line == "END_DATA" and receiving_photo:
                            in_data_section = False
                            print(f"Dados recebidos. Tamanho: {len(photo_data)} caracteres")
                            
                            try:
                                padded_data = add_base64_padding(photo_data)
                                
                                
                                try:
                                    decoded_data = base64.b64decode(padded_data)
                                    print(f"Tamanho da imagem decodificada: {len(decoded_data)} bytes")
                                    
                                    
                                    if photo_hash:
                                        calculated_hash = hashlib.md5(decoded_data).hexdigest()
                                        if calculated_hash != photo_hash:
                                            print(f"Aviso: Hash não corresponde! Esperado: {photo_hash}, Calculado: {calculated_hash}")
                                    
                                    safe_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    if photo_timestamp:
                                        try:
                                            ts = datetime.fromisoformat(photo_timestamp)
                                            safe_timestamp = ts.strftime("%Y%m%d_%H%M%S")
                                        except:
                                            pass
                                    
                                    file_path = os.path.join(FOTOS_DIR, f"{safe_timestamp}.jpg")
                                    
                                    with open(file_path, "wb") as fh:
                                        fh.write(decoded_data)
                                    
                                    print(f"Foto salva: {file_path}")
                                    
                                    with fotos_lock:
                                        fotos_recebidas.append({
                                            'filename': os.path.basename(file_path),
                                            'timestamp': photo_timestamp or datetime.now().isoformat(),
                                            'filepath': file_path,
                                            'size': len(decoded_data)
                                        })
                                    
                                    try:
                                        conn.send(f"PHOTO_STORED:{os.path.basename(file_path)}\n".encode())
                                    except:
                                        print("Erro ao enviar confirmação")
                                    
                                except base64.binascii.Error as e:
                                    print(f"Erro ao decodificar Base64: {e}")
                                    conn.send(f"ERROR:Falha ao decodificar imagem\n".encode())
                            
                            except Exception as e:
                                print(f"Erro ao processar imagem: {e}")
                                conn.send(f"ERROR:Erro no processamento: {str(e)}\n".encode())
                            
                            receiving_photo = False
                            photo_data = ""
                            in_data_section = False
                        
                        elif line == "1":
                            print("Sensor ativado! Tocando alarme...")
                            alarm_thread = Thread(target=play_alarm)
                            alarm_thread.daemon = True
                            alarm_thread.start()
                
                except UnicodeDecodeError as e:
                    print(f"Erro ao decodificar texto: {e}")
                    
                    if in_data_section:
                        try:
                            photo_data += data.decode('ascii', errors='ignore')
                        except:
                            print("Não foi possível processar os dados binários")
            
            except socket.timeout:
                print(f"Timeout na recepção para {addr}")
                continue
            
            except ConnectionResetError:
                print(f"Conexão com {addr} foi resetada")
                break
                
            except Exception as socket_error:
                error_count += 1
                
                
                if hasattr(socket_error, 'winerror') and socket_error.winerror == 10053:
                    print(f"Conexão abortada pelo software do host com {addr}: {socket_error}")
                    break
                elif error_count >= max_errors:
                    print(f"Muitos erros consecutivos ({error_count}) com {addr}, fechando conexão: {socket_error}")
                    break
                else:
                    print(f"Erro na comunicação com {addr} (tentativa {error_count}/{max_errors}): {socket_error}")
                    time.sleep(1)
                    continue
    
    except Exception as e:
        print(f"Erro ao processar conexão de {addr}: {e}")
    
    finally:
        try:
            conn.close()
        except:
            pass
        print(f"Conexão com {addr} fechada")


def play_alarm():
    try:
        pygame.mixer.music.load(ALARME_SOM)
        pygame.mixer.music.play(-1)
        if hasattr(window, 'atualizar_status'):
            window.atualizar_status("Alarme ligado! Movimento detectado!")
    except Exception as e:
        print(f"Erro ao tocar alarme: {e}")

class AlarmeApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Monitor de Segurança")
        self.setGeometry(200, 200, 600, 400)

        self.setStyleSheet("background-color: #f8f8ff;")

        self.main_layout = QVBoxLayout()

        self.label = QLabel("Aguardando movimento...", self)
        self.label.setFont(QFont("Arial", 14, QFont.Bold))
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #333333;")
        self.main_layout.addWidget(self.label)

        self.fotos_label = QLabel("Fotos capturadas:", self)
        self.fotos_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.fotos_label.setStyleSheet("color: #333333;")
        self.main_layout.addWidget(self.fotos_label)

        self.lista_fotos = QListWidget(self)
        self.lista_fotos.setStyleSheet("background-color: #ffffff; border-radius: 8px; padding: 10px;")
        self.lista_fotos.setFont(QFont("Arial", 10))
        self.main_layout.addWidget(self.lista_fotos)

        self.botoes_layout = QHBoxLayout()

        self.desligar_alarme_btn = QPushButton("Desligar Alarme", self)
        self.desligar_alarme_btn.setFont(QFont("Arial", 12))
        self.desligar_alarme_btn.setStyleSheet("background-color: #ff4c4c; color: white; border-radius: 5px; padding: 10px;")
        self.desligar_alarme_btn.clicked.connect(self.desligar_alarme)
        self.botoes_layout.addWidget(self.desligar_alarme_btn)

        self.atualizar_lista_btn = QPushButton("Atualizar Lista", self)
        self.atualizar_lista_btn.setFont(QFont("Arial", 12))
        self.atualizar_lista_btn.setStyleSheet("background-color: #4caf50; color: white; border-radius: 5px; padding: 10px;")
        self.atualizar_lista_btn.clicked.connect(self.atualizar_lista_fotos)
        self.botoes_layout.addWidget(self.atualizar_lista_btn)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        self.main_layout.addWidget(separator)

        self.main_layout.addLayout(self.botoes_layout)

        self.setLayout(self.main_layout)

        self.timer_id = self.startTimer(5000)

    def timerEvent(self, event):
        if event.timerId() == self.timer_id:
            self.atualizar_lista_fotos()

    def atualizar_status(self, mensagem):
        self.label.setText(mensagem)

    def atualizar_lista_fotos(self):
        self.lista_fotos.clear()
        with fotos_lock:
            for foto in fotos_recebidas:
                filename = foto['filename']
                timestamp = foto['timestamp']

                try:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime("%d/%m/%Y %H:%M:%S")
                except:
                    formatted_time = timestamp

                self.lista_fotos.addItem(f"{filename} - {formatted_time}")

    def tocar_alarme(self):
        pygame.mixer.music.load(ALARME_SOM)
        pygame.mixer.music.play(-1)
        self.label.setText("Alarme ligado!")

    def desligar_alarme(self):
        pygame.mixer.music.stop()
        self.label.setText("Alarme desligado")

if __name__ == '__main__':
    if os.path.exists(FOTOS_DIR):
        for filename in os.listdir(FOTOS_DIR):
            filepath = os.path.join(FOTOS_DIR, filename)
            if os.path.isfile(filepath) and filename.endswith('.jpg'):
                stat = os.stat(filepath)
                
                timestamp = datetime.fromtimestamp(stat.st_mtime).isoformat()
                fotos_recebidas.append({
                    'filename': filename,
                    'timestamp': timestamp,
                    'filepath': filepath,
                    'size': stat.st_size
                })
        
        fotos_recebidas.sort(key=lambda x: x['timestamp'], reverse=True)
        print(f"Carregadas {len(fotos_recebidas)} fotos existentes")
    
    server_thread = Thread(target=run_server)
    server_thread.daemon = True 
    server_thread.start()

    app = QApplication(sys.argv)
    window = AlarmeApp()
    window.atualizar_lista_fotos()  
    window.show()
    sys.exit(app.exec_())
