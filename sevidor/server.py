import socket
import pygame
import sys
import os
import json
import base64
import hashlib
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QListWidget, QHBoxLayout
from threading import Thread, Lock
import time

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
    # Aumentar o buffer do socket
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB
    # Adiciona keepalive no nível do socket
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    # Configurações adicionais de keepalive (sistema-dependente)
    if hasattr(socket, 'TCP_KEEPIDLE'):
        server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)  # Reduz para 30s
    if hasattr(socket, 'TCP_KEEPINTVL'):
        server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Reduz para 10s
    if hasattr(socket, 'TCP_KEEPCNT'):
        server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)  # Reduz para 3 tentativas
        
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Servidor ouvindo em {HOST}:{PORT}")

    while True:
        try:
            conn, addr = server_socket.accept()
            # Configurar timeout para evitar bloqueio indefinido
            conn.settimeout(120)  # 120 segundos de timeout (aumentado)
            
            # Aumentar buffer de recepção da conexão específica
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB
            
            # Aplicar as mesmas configurações de keepalive para esta conexão
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, 'TCP_KEEPIDLE'):
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, 'TCP_KEEPCNT'):
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                
            print(f"Conexão recebida de {addr}")
            
            # Inicia uma thread para lidar com essa conexão
            client_thread = Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
        except Exception as e:
            print(f"Erro ao aceitar conexão: {e}")
            # Continua o loop para aceitar novas conexões

def add_base64_padding(base64_str):
    # Calcular o número de caracteres que faltam para ser múltiplo de 4
    padding_needed = 4 - len(base64_str) % 4
    if padding_needed != 4:
        # Adiciona o padding "=" necessário
        base64_str += "=" * padding_needed
    return base64_str

def handle_client(conn, addr):
    """Gerencia a conexão com um cliente"""
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
        
        print(f"🟢 Nova conexão de {addr}")
        # Envia uma mensagem de boas-vindas para garantir que a conexão esteja aberta
        try:
            conn.send("WELCOME\n".encode())
            print(f"✅ Mensagem de boas-vindas enviada para {addr}")
        except Exception as e:
            print(f"⚠️ Não foi possível enviar mensagem de boas-vindas para {addr}: {e}")
        
        while True:
            try:
                # Verifica se a conexão está inativa por muito tempo
                if time.time() - last_activity > 180:  # 3 minutos
                    print(f"⏱️ Conexão com {addr} inativa por muito tempo. Fechando.")
                    break
                
                # Reset de contagem de erros ao conseguir receber dados com sucesso
                error_count = 0
                
                # Configura um timeout menor para a recepção
                conn.settimeout(30)
                data = conn.recv(32768)  # Buffer maior: 32KB
                
                if not data:
                    print(f"Cliente {addr} desconectado - dados vazios")
                    break
                
                # Atualiza o timestamp da última atividade
                last_activity = time.time()
                
                try:
                    message = data.decode('utf-8', errors='replace').strip()
                    lines = message.splitlines()
                    print(f"📨 Recebidos {len(lines)} comando(s) de {addr}")
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Processar mensagens de handshake
                        if line == "HELLO":
                            print(f"👋 Recebido handshake de {addr}")
                            try:
                                conn.send("HELLO_ACK\n".encode())
                                print(f"✅ Resposta de handshake enviada para {addr}")
                            except Exception as e:
                                print(f"⚠️ Erro ao enviar resposta de handshake: {e}")
                            continue
                            
                        # Adicionando suporte a PING/PONG para keepalive
                        if line == "PING":
                            try:
                                conn.send("PONG\n".encode())
                                print(f"💓 Keepalive recebido de {addr}, enviado PONG")
                            except Exception as e:
                                print(f"⚠️ Erro ao enviar resposta de keepalive: {e}")
                            continue
                        
                        # Se estamos no modo de recepção de dados da foto
                        if in_data_section and "END_DATA" not in line:
                            # Filtra caracteres não-base64
                            base64_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
                            filtered_line = ''.join(c for c in line if c in base64_chars)
                            photo_data += filtered_line
                            
                            # Logamos apenas periodicamente para não sobrecarregar o console
                            if len(photo_data) % 10000 == 0:
                                print(f"📥 Recebidos {len(photo_data)} caracteres base64 até agora...")
                            continue
                        
                        # Processamento de comandos
                        if line == "STORE_PHOTO":
                            receiving_photo = True
                            photo_data = ""
                            in_data_section = False
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
                            photo_hash = line[5:]
                            print(f"🔍 Hash recebido: {photo_hash}")
                        
                        elif line == "BEGIN_DATA":
                            in_data_section = True
                            print("🔍 Iniciando recebimento de dados da foto")
                        
                        elif line == "END_DATA" and receiving_photo:
                            in_data_section = False
                            print(f"🔍 Dados recebidos. Tamanho: {len(photo_data)} caracteres")
                            
                            try:
                                # Adicionar padding se necessário
                                padded_data = add_base64_padding(photo_data)
                                
                                # Decodificar o Base64
                                try:
                                    decoded_data = base64.b64decode(padded_data)
                                    print(f"📏 Tamanho da imagem decodificada: {len(decoded_data)} bytes")
                                    
                                    # Verificar hash
                                    if photo_hash:
                                        calculated_hash = hashlib.md5(decoded_data).hexdigest()
                                        if calculated_hash != photo_hash:
                                            print(f"⚠️ Aviso: Hash não corresponde! Esperado: {photo_hash}, Calculado: {calculated_hash}")
                                    
                                    # Criar nome de arquivo seguro
                                    safe_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    if photo_timestamp:
                                        try:
                                            ts = datetime.fromisoformat(photo_timestamp)
                                            safe_timestamp = ts.strftime("%Y%m%d_%H%M%S")
                                        except:
                                            # Usar o timestamp atual se não conseguir converter
                                            pass
                                    
                                    file_path = os.path.join(FOTOS_DIR, f"{safe_timestamp}.jpg")
                                    
                                    # Salvar a imagem
                                    with open(file_path, "wb") as fh:
                                        fh.write(decoded_data)
                                    
                                    print(f"✅ Foto salva: {file_path}")
                                    
                                    # Adicionar à lista de fotos
                                    with fotos_lock:
                                        fotos_recebidas.append({
                                            'filename': os.path.basename(file_path),
                                            'timestamp': photo_timestamp or datetime.now().isoformat(),
                                            'filepath': file_path,
                                            'size': len(decoded_data)
                                        })
                                    
                                    # Enviar confirmação
                                    try:
                                        conn.send(f"PHOTO_STORED:{os.path.basename(file_path)}\n".encode())
                                    except:
                                        print("❌ Erro ao enviar confirmação")
                                    
                                except base64.binascii.Error as e:
                                    print(f"❌ Erro ao decodificar Base64: {e}")
                                    conn.send(f"ERROR:Falha ao decodificar imagem\n".encode())
                            
                            except Exception as e:
                                print(f"❌ Erro ao processar imagem: {e}")
                                conn.send(f"ERROR:Erro no processamento: {str(e)}\n".encode())
                            
                            # Reiniciar variáveis
                            receiving_photo = False
                            photo_data = ""
                            in_data_section = False
                        
                        elif line == "1":
                            print("Sensor ativado! Tocando alarme...")
                            alarm_thread = Thread(target=play_alarm)
                            alarm_thread.daemon = True
                            alarm_thread.start()
                        
                        elif line == "GET_STORED_PHOTOS_LIST":
                            try:
                                send_photos_list(conn)
                            except Exception as e:
                                print(f"❌ Erro ao enviar lista de fotos: {e}")
                
                except UnicodeDecodeError as e:
                    print(f"⚠️ Erro ao decodificar texto: {e}")
                    # Se estamos no modo de recebimento de dados, trate como dados binários
                    if in_data_section:
                        try:
                            # Tente converter para string assumindo que são dados Base64
                            photo_data += data.decode('ascii', errors='ignore')
                        except:
                            print("❌ Não foi possível processar os dados binários")
            
            except socket.timeout:
                print(f"⏱️ Timeout na recepção para {addr}")
                # Não encerra a conexão, apenas continua o loop
                continue
            
            except ConnectionResetError:
                print(f"🔴 Conexão com {addr} foi resetada")
                break
                
            except Exception as socket_error:
                # Incrementa o contador de erros
                error_count += 1
                
                # No Windows, o erro 10053 é "Software caused connection abort"
                if hasattr(socket_error, 'winerror') and socket_error.winerror == 10053:
                    print(f"🔴 Conexão abortada pelo software do host com {addr}: {socket_error}")
                    break
                elif error_count >= max_errors:
                    print(f"🔴 Muitos erros consecutivos ({error_count}) com {addr}, fechando conexão: {socket_error}")
                    break
                else:
                    print(f"⚠️ Erro na comunicação com {addr} (tentativa {error_count}/{max_errors}): {socket_error}")
                    # Pausa um pouco antes de tentar novamente
                    time.sleep(1)
                    continue
    
    except Exception as e:
        print(f"❌ Erro ao processar conexão de {addr}: {e}")
    
    finally:
        try:
            conn.close()
        except:
            pass
        print(f"🔴 Conexão com {addr} fechada")

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
