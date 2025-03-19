import socket
import pygame
import sys
import os
import json
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QListWidget, QHBoxLayout
from threading import Thread, Lock

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

def handle_client(conn, addr):
    try:
        receiving_photo = False
        photo_data = bytearray()
        photo_name = ""
        photo_size = 0
        photo_timestamp = ""
        
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    print(f"Cliente {addr} desconectado - dados vazios")
                    break

                # Se não estiver recebendo foto, processa como comando de texto
                if not receiving_photo:
                    try:
                        message = data.decode().strip()
                        lines = message.split('\n')
                        
                        for line in lines:
                            if line == "STORE_PHOTO":
                                receiving_photo = True
                                photo_data = bytearray()
                                print(f"Iniciando recebimento de foto de {addr}")
                            
                            elif line.startswith("FILENAME:"):
                                photo_name = line[9:]
                                print(f"Nome da foto: {photo_name}")
                            
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
                            
                            elif line == "BEGIN_DATA":
                                # O próximo recv conterá os dados da imagem
                                print("Iniciando transferência de dados")
                            
                            elif line == "END_DATA" and photo_data:
                                # Terminou de receber os dados da imagem
                                if photo_name and len(photo_data) > 0:
                                    print(f"💾 Recebidos {len(photo_data)} bytes de dados de imagem para {photo_name}")
                                    
                                    # Limpa os cabeçalhos que possam ter sido misturados com os dados da imagem
                                    # Tenta encontrar JPEG/PNG header
                                    jpeg_marker = bytes([0xFF, 0xD8])  # JPEG header
                                    png_marker = bytes([0x89, 0x50, 0x4E, 0x47])  # PNG header
                                    
                                    start_pos = 0
                                    if jpeg_marker in photo_data[:100]:
                                        start_pos = photo_data.find(jpeg_marker)
                                        print(f"Encontrado marcador JPEG na posição {start_pos}")
                                    elif png_marker in photo_data[:100]:
                                        start_pos = photo_data.find(png_marker)
                                        print(f"Encontrado marcador PNG na posição {start_pos}")
                                    
                                    # Extrai apenas a parte válida da imagem
                                    valid_photo_data = photo_data[start_pos:]
                                    print(f"Usando {len(valid_photo_data)} bytes válidos da imagem")
                                    
                                    # Salva a imagem
                                    if save_photo(valid_photo_data, photo_name, photo_timestamp):
                                        try:
                                            # Envia confirmação de armazenamento
                                            conn.send(f"PHOTO_STORED:{photo_name}\n".encode())
                                            print(f"Foto {photo_name} recebida e armazenada com sucesso!")
                                        except Exception as e:
                                            print(f"Erro ao enviar confirmação: {e}")
                                    else:
                                        print(f"Falha ao salvar foto {photo_name}")
                                else:
                                    print(f"Dados de foto inválidos: nome={photo_name}, tamanho={len(photo_data)}")
                                
                                receiving_photo = False
                                photo_data = bytearray()
                            
                            elif line == "1":
                                print("Sensor ativado! Tocando alarme...")
                                # Executar em uma thread separada para não bloquear
                                alarm_thread = Thread(target=play_alarm)
                                alarm_thread.daemon = True
                                alarm_thread.start()
                            
                            elif line == "GET_STORED_PHOTOS_LIST":
                                # Envia a lista de fotos armazenadas
                                try:
                                    send_photos_list(conn)
                                except Exception as e:
                                    print(f"Erro ao enviar lista de fotos: {e}")
                            
                            elif receiving_photo and line:
                                # Pode ser parte do dado binário
                                photo_data.extend(line.encode())
                    except UnicodeDecodeError:
                        # Se não conseguir decodificar como texto, provavelmente são dados binários
                        if receiving_photo:
                            photo_data.extend(data)
                            print(f"Adicionados {len(data)} bytes aos dados da foto")
                
                # Se estiver no modo de recepção de foto, adiciona os dados ao buffer
                else:
                    photo_data.extend(data)
                    print(f"Adicionados {len(data)} bytes aos dados da foto (modo recepção)")
                    
                    # Verifica se os dados contêm a marcação END_DATA
                    end_marker = b"END_DATA\n"
                    if end_marker in photo_data:
                        # Encontrar a posição do marcador
                        end_pos = photo_data.find(end_marker)
                        
                        # Salva a parte antes do END_DATA
                        image_data = photo_data[:end_pos]
                        
                        if photo_name and len(image_data) > 0:
                            save_photo(image_data, photo_name, photo_timestamp)
                            
                            try:
                                # Envia confirmação de armazenamento
                                conn.send(f"PHOTO_STORED:{photo_name}\n".encode())
                                print(f"Foto {photo_name} recebida e armazenada com sucesso!")
                            except Exception as e:
                                print(f"Erro ao enviar confirmação: {e}")
                        else:
                            print(f"Dados de foto inválidos: nome={photo_name}, tamanho={len(image_data)}")
                        
                        # Processa o restante da mensagem normalmente
                        remaining = photo_data[end_pos + len(end_marker):]
                        receiving_photo = False
                        
                        # Se houver dados remanescentes, processa-os
                        if remaining:
                            print(f"Processando {len(remaining)} bytes remanescentes")
                            photo_data = remaining
                        else:
                            photo_data = bytearray()
            except socket.timeout:
                continue
            except ConnectionResetError:
                print(f"Conexão com {addr} foi resetada")
                break
    
    except Exception as e:
        print(f"Erro ao processar conexão de {addr}: {e}")
    
    finally:
        try:
            conn.close()
        except:
            pass
        print(f"Conexão com {addr} fechada")

def save_photo(data, filename, timestamp):
    """Salva a foto recebida no sistema de arquivos"""
    if not data or len(data) == 0:
        print(f"❌ ERRO: Dados vazios para foto {filename}, impossível salvar")
        return False
    
    if not filename:
        print("❌ ERRO: Nome de arquivo vazio")
        return False
    
    print(f"💾 Tentando salvar foto: {filename} com {len(data)} bytes")
    
    # Garante que o diretório existe
    if not os.path.exists(FOTOS_DIR):
        print(f"Criando diretório {FOTOS_DIR}")
        os.makedirs(FOTOS_DIR)
    
    filepath = os.path.join(FOTOS_DIR, filename)
    
    try:
        with open(filepath, 'wb') as f:
            f.write(data)
        
        # Verifica se o arquivo foi realmente criado
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"✅ Foto salva com sucesso: {filepath} ({file_size} bytes)")
            
            # Adiciona à lista de fotos recebidas
            with fotos_lock:
                # Verifica se a foto já está na lista
                if not any(foto['filename'] == filename for foto in fotos_recebidas):
                    fotos_recebidas.append({
                        'filename': filename,
                        'timestamp': timestamp or datetime.now().isoformat(),
                        'filepath': filepath,
                        'size': len(data)
                    })
                    # Ordena por timestamp (mais recente primeiro)
                    fotos_recebidas.sort(key=lambda x: x['timestamp'], reverse=True)
                    print(f"ℹ️ Foto {filename} adicionada à lista (total: {len(fotos_recebidas)})")
                else:
                    print(f"ℹ️ Foto {filename} já está na lista")
            
            return True
        else:
            print(f"❌ ERRO: Falha ao verificar arquivo após gravação: {filepath}")
            return False
            
    except Exception as e:
        print(f"❌ ERRO ao salvar arquivo {filepath}: {e}")
        return False

def send_photos_list(conn):
    """Envia a lista de fotos armazenadas para o cliente"""
    with fotos_lock:
        # Cria uma cópia da lista para enviar (sem o filepath completo por segurança)
        photos_to_send = []
        for foto in fotos_recebidas:
            photos_to_send.append({
                'filename': foto['filename'],
                'timestamp': foto['timestamp'],
                'size': foto.get('size', 0)
            })
    
    # Converte para JSON e envia
    photos_json = json.dumps(photos_to_send)
    response = f"STORED_PHOTOS_LIST:{photos_json}\n"
    conn.send(response.encode())
    print(f"Lista de {len(photos_to_send)} fotos enviada para o cliente")

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
