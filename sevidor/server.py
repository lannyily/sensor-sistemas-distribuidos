import socket
import pygame
import sys
import os
import json
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QListWidget, QHBoxLayout
from threading import Thread, Lock
import hashlib
import base64

pygame.mixer.init()
ALARME_SOM = "audio/alarme.mp3"  

HOST = "0.0.0.0"
PORT = 5000

# Diretório para armazenar as fotos
FOTOS_DIR = "fotos"
if not os.path.exists(FOTOS_DIR):
    os.makedirs(FOTOS_DIR)

# Lista para armazenar informações sobre fotos recebidas
fotos_recebidas = []
fotos_lock = Lock()  # Para acesso thread-safe à lista de fotos


def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Servidor ouvindo em {HOST}:{PORT}")

    while True:
        conn, addr = server_socket.accept()
        print(f"Conexão recebida de {addr}")
        
        # Inicia uma thread para lidar com essa conexão
        client_thread = Thread(target=handle_client, args=(conn, addr))
        client_thread.daemon = True
        client_thread.start()

def save_photo(image_data, photo_name, photo_timestamp):
    try:
        print("entrou no salvamento")
        
        # Substitui os dois pontos por um caractere válido (por exemplo, "-")
        safe_timestamp = photo_timestamp.replace(":", "-")
        
        # Caminho completo para salvar o arquivo
        file_path = os.path.join(os.getcwd(), "fotos", f"{safe_timestamp}_{photo_name}")
        
        # Verifique o tamanho dos dados antes de salvar
        print(f"🔍 Tamanho da imagem recebida: {len(image_data)} bytes")
        
        with open(file_path, "wb") as file:
            file.write(image_data)
        
        print(f"✅ Foto salva: {file_path}")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar foto em {file_path}: {e}")
        return False

def add_base64_padding(base64_str):
    # Calcular o número de caracteres que faltam para ser múltiplo de 4
    padding_needed = 4 - len(base64_str) % 4
    if padding_needed != 4:
        # Adiciona o padding "=" necessário
        base64_str += "=" * padding_needed
    return base64_str


def handle_client(conn, addr):
    try:
        receiving_photo = False
        photo_data = ""
        photo_name = ""
        photo_size = 0
        photo_timestamp = ""
        
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    print(f"Cliente {addr} desconectado - dados vazios")
                    break

                message = data.decode().strip()
                lines = message.splitlines()
                
                for line in lines:
                    if line == "STORE_PHOTO":
                        receiving_photo = True
                        photo_data = ""
                        print(f"📷 Iniciando recebimento de foto de {addr}")
                    
                    elif line.startswith("TIMESTAMP:"):
                        photo_timestamp = line[10:]
                        print(f"📅 Timestamp: {photo_timestamp}")
                    
                    elif line.startswith("SIZE:"):
                        try:
                            photo_size = int(line[5:])
                            print(f"📏 Tamanho da foto: {photo_size} bytes")
                        except ValueError:
                            print(f"❌ Erro ao converter tamanho da foto: {line[5:]}")
                            photo_size = 0
                    
                    elif line.startswith("HASH:"):
                        print(f"🔍 Hash recebido: {line[5:]}")
                    
                    elif line.strip() == "BEGIN_DATA":
                        receiving_photo = True
                        print(f"🔍 Iniciando recebimento de foto: {receiving_photo}")
                    
                    elif "END_DATA" in line.strip() and receiving_photo:
                        print(f"🔍 Linha antes do 'END_DATA' comparando: '{line.strip()}'")
                        try:
                            
                            data_correta = add_base64_padding(photo_data)

                            # Decodificar o Base64
                            decoded_data = base64.b64decode(data_correta)
                            print(f"📏 Tamanho da imagem decodificada: {len(decoded_data)} bytes")
                            
                            # Verificar se o tamanho dos dados recebidos corresponde ao tamanho esperado
                            if len(decoded_data) != photo_size:
                                print(f"❌ Tamanho da imagem não corresponde ao esperado! Esperado: {photo_size} bytes, Recebido: {len(decoded_data)} bytes")
                                return False
                            
                            # Salvar a imagem em um arquivo
                            # Usar um nome de arquivo seguro para o Windows
                            safe_timestamp = photo_timestamp.replace(":", "-")
                            file_path = os.path.join(os.getcwd(), "fotos", f"{safe_timestamp}_photo.png")

                            with open(file_path, "wb") as fh:
                                fh.write(decoded_data)
                            
                            print(f"✅ Foto salva: {file_path}")

                            # Se a foto foi salva corretamente, enviar resposta para o cliente
                            conn.send(f"PHOTO_STORED:{file_path}\n".encode())
                        except Exception as e:
                            print(f"❌ Erro ao decodificar imagem Base64: {e}")
                            return False

                    elif receiving_photo:
                        # Acumula os dados da imagem
                        photo_data += line.strip()

            except socket.timeout:
                continue
            except ConnectionResetError:
                print(f"🔴 Conexão com {addr} foi resetada")
                break
    
    except Exception as e:
        print(f"❌ Erro ao processar conexão de {addr}: {e}")
    
    finally:
        try:
            conn.close()
        except:
            pass
        print(f"🔴 Conexão com {addr} fechada")







def play_alarm():
    """Toca o alarme quando o sensor for ativado"""
    try:
        pygame.mixer.music.load(ALARME_SOM)
        pygame.mixer.music.play(-1)
        # Notifica a interface para atualizar o status
        if hasattr(window, 'atualizar_status'):
            window.atualizar_status("Alarme ligado! Movimento detectado!")
    except Exception as e:
        print(f"Erro ao tocar alarme: {e}")

class AlarmeApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Monitor de Segurança")
        self.setGeometry(200, 200, 600, 400)

        # Layout principal
        self.main_layout = QVBoxLayout()
        
        # Status
        self.label = QLabel("Aguardando movimento...", self)
        self.main_layout.addWidget(self.label)
        
        # Lista de fotos
        self.fotos_label = QLabel("Fotos capturadas:", self)
        self.main_layout.addWidget(self.fotos_label)
        
        self.lista_fotos = QListWidget(self)
        self.main_layout.addWidget(self.lista_fotos)
        
        # Botões
        self.botoes_layout = QHBoxLayout()
        
        self.desligar_alarme_btn = QPushButton("Desligar Alarme", self)
        self.desligar_alarme_btn.clicked.connect(self.desligar_alarme)
        self.botoes_layout.addWidget(self.desligar_alarme_btn)
        
        self.atualizar_lista_btn = QPushButton("Atualizar Lista", self)
        self.atualizar_lista_btn.clicked.connect(self.atualizar_lista_fotos)
        self.botoes_layout.addWidget(self.atualizar_lista_btn)
        
        self.main_layout.addLayout(self.botoes_layout)
        
        self.setLayout(self.main_layout)
        
        # Timer para atualizar a lista de fotos
        self.timer_id = self.startTimer(5000)  # Atualiza a cada 5 segundos
    
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
                # Formata a timestamp para exibição
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
    # Carrega fotos existentes ao iniciar
    if os.path.exists(FOTOS_DIR):
        for filename in os.listdir(FOTOS_DIR):
            filepath = os.path.join(FOTOS_DIR, filename)
            if os.path.isfile(filepath) and filename.endswith('.jpg'):
                stat = os.stat(filepath)
                # Usa a data de modificação do arquivo como timestamp
                timestamp = datetime.fromtimestamp(stat.st_mtime).isoformat()
                fotos_recebidas.append({
                    'filename': filename,
                    'timestamp': timestamp,
                    'filepath': filepath,
                    'size': stat.st_size
                })
        # Ordena por timestamp (mais recente primeiro)
        fotos_recebidas.sort(key=lambda x: x['timestamp'], reverse=True)
        print(f"Carregadas {len(fotos_recebidas)} fotos existentes")
    
    server_thread = Thread(target=run_server)
    server_thread.daemon = True 
    server_thread.start()

    app = QApplication(sys.argv)
    window = AlarmeApp()
    window.atualizar_lista_fotos()  # Carrega a lista inicial
    window.show()
    sys.exit(app.exec_())
