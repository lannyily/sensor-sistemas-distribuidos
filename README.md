# Sensor de Proximidade para Monitoramento Remoto

## 📖 Descrição

Este projeto é um plicativo Android que utilize o sensor de proximidade para ativar um modo de segurança. Quando o sensor detectar movimento, um sinal de alerta será enviado a um servidor Python rodando em um notebook, acionando um alarme sonoro ininterrupto. Além disso, o aplicativo capturará uma foto do intruso e enviará ao servidor, que armazenará a imagem para consulta posterior.

## ⚙️ Tecnologias Utilizadas

### Linguagens e Frameworks

- **Python** – Linguagem de programação ultilizada no servidor
- **Flutter** – Framework para desenvolvimento do aplicativo
- **Dart** – Linguagem de programação do Flutter.

### Pacotes e Bibliotecas Utilizadas

**Aplicativo:** 

- proximity_sensor: Para detectar proximidade do dispositivo.
- camera: Para acessar a câmera do dispositivo.
- path_provider: Para obter diretórios do sistema, como armazenamento temporário e permanente.
- path: Para manipular caminhos de arquivos de forma cross-platform.
- permission_handler: Para gerenciar permissões do sistema, como câmera e armazenamento.
- crypto: Para criptografia e hashing de dados (MD5, SHA-256, etc.).
- flutter/services.dart: Para comunicação com serviços nativos do sistema operacional.

**Servidor:**

- socket: Para comunicação via TCP/IP entre cliente e servidor.
- pygame: Para reprodução de áudio do alarme.
- sys e os: Para manipulação do sistema de arquivos e operações do sistema operacional.
- base64 e hashlib: Para codificação e decodificação de imagens, além de gerar hash para verificação de integridade.
- datetime: Para trabalhar com datas e timestamps.
- PyQt5 (QtCore, QtGui, QtWidgets): Para criar a interface gráfica do monitor de segurança.
- threading (Thread, Lock): Para gerenciar threads e sincronização de acesso a recursos compartilhados.
- time: Para gerenciar intervalos e tempos de espera.

### APIs e Funcionalidades

- Sockets (dart:io) – Comunicação com um servidor via TCP.
- Timers (dart:async) – Execução de tarefas periódicas.
- JSON (dart:convert) – Codificação e decodificação de dados em JSON.

## 📌 Guia de Instalação e Uso

### 1️⃣ Instalar Python 3.11.6

O Python 3.11.6 foi escolhido porque versões mais novas do Python (como 3.13) podem ter incompatibilidade com PyQt5, devido a mudanças internas na API do Python. Algumas versões mais antigas do PyQt5 podem não funcionar corretamente no Python 3.13, exigindo um downgrade para Python 3.11.6.

🔹 Baixe e instale o Python 3.11.6 em:
[Download Python 3.11.6](https://www.python.org/downloads/release/python-3116/)

### 2️⃣ Instalar as Bibliotecas

```sh
pip install -r requirements.txt
```
