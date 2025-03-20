import 'dart:io';
import 'package:flutter/material.dart';
import 'package:proximity_sensor/proximity_sensor.dart';
import 'package:camera/camera.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as path;
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:convert';
import 'dart:async';
import 'package:crypto/crypto.dart' as crypto;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  runApp(MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  _MyAppState createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  String _status = "Longe";
  bool _isSensorActive = false;
  Socket? _socket;
  CameraController? _cameraController;
  bool _isCameraInitialized = false;
  String? _lastPhotoPath;
  bool _hasPermissions = false;
  bool _isRequestingPermission = false;
  // Lista para armazenar as informações das fotos salvas no servidor
  List<Map<String, dynamic>> _storedPhotos = [];
  // Status da última transmissão
  String? _lastTransmissionStatus;

  @override
  void initState() {
    super.initState();
    _connectToServer();
    _requestPermissions();

    Future.delayed(Duration(seconds: 2), () {
      _requestStoredPhotosList();
    });


    Timer.periodic(Duration(seconds: 30), (timer) {
      if (_socket == null) {
        print("Tentando reconectar ao servidor...");
        _connectToServer().then((connected) {
          if (connected) {

            _requestStoredPhotosList();
          }
        });
      } else {

        _sendKeepAlive();
      }
    });

    Timer.periodic(Duration(seconds: 10), (timer) {
      if (_socket != null) {
        try {
          _socket!.add(utf8.encode("PING\n"));
          print("Enviado keep-alive periódico");
        } catch (e) {
          print("Erro no keep-alive periódico: $e");
          _socket = null;

        }
      }
    });
  }

  Future<void> _requestPermissions() async {

    if (_isRequestingPermission) return;

    setState(() {
      _isRequestingPermission = true;
    });

    try {
      final cameraStatus = await Permission.camera.status;

      if (cameraStatus.isGranted) {
        setState(() {
          _hasPermissions = true;
        });
        await _initializeCamera();
        return;
      }

      final cameraPermission = await Permission.camera.request();

      final permissionGranted = cameraPermission.isGranted;

      print("Status permissão câmera: $cameraPermission");
      print("Permissão concedida: $permissionGranted");

      setState(() {
        _hasPermissions = permissionGranted;
      });

      if (_hasPermissions) {
        await _initializeCamera();
      } else {

        print('Permissão da câmera negada. Verifique as configurações do aplicativo.');
      }
    } catch (e) {
      print('Erro ao solicitar permissões: $e');
    } finally {
      setState(() {
        _isRequestingPermission = false;
      });
    }
  }

  Future<void> _initializeCamera() async {
    if (!_hasPermissions) return;

    final cameras = await availableCameras();
    if (cameras.isEmpty) return;


    final frontCamera = cameras.firstWhere(
      (camera) => camera.lensDirection == CameraLensDirection.front,
      orElse: () => cameras.first,
    );

    _cameraController = CameraController(
      frontCamera,
      ResolutionPreset.medium,
      enableAudio: false,

      imageFormatGroup: ImageFormatGroup.jpeg,
    );

    try {
      await _cameraController!.initialize();
      setState(() {
        _isCameraInitialized = true;
      });
      print('Câmera inicializada com sucesso!');
    } catch (e) {
      print('Erro ao inicializar a câmera: $e');
    }
  }

  Future<void> _takePicture() async {
    if (!_isCameraInitialized || !_hasPermissions) {
      print('Câmera não inicializada ou sem permissões!');
      return;
    }

    try {

      final image = await _cameraController!.takePicture();


      final directory = await getApplicationDocumentsDirectory();
      final fileName = '${DateTime.now().millisecondsSinceEpoch}.jpg';
      final savedPath = path.join(directory.path, fileName);

      await image.saveTo(savedPath);
      setState(() {
        _lastPhotoPath = savedPath;
      });

      print('Foto capturada discretamente e salva em: $savedPath');


      await _sendPhotoToServer(savedPath, fileName);
    } catch (e) {
      print('Erro ao tirar foto: $e');
    }
  }

  Future<void> _testarEnvioFoto() async {
    if (!_isCameraInitialized || !_hasPermissions) {
      print('Câmera não inicializada ou sem permissões!');
      return;
    }

    try {
      setState(() {
        _lastTransmissionStatus = "Capturando foto para teste...";
      });

      final image = await _cameraController!.takePicture();

      final directory = await getApplicationDocumentsDirectory();
      final fileName = 'teste_${DateTime.now().millisecondsSinceEpoch}.jpg';
      final savedPath = path.join(directory.path, fileName);
      
      await image.saveTo(savedPath);
      setState(() {
        _lastPhotoPath = savedPath;
        _lastTransmissionStatus = "Foto de teste capturada, enviando...";
      });
      
      print('Foto de teste capturada e salva em: $savedPath');
      

      bool success = false;
      for (int i = 0; i < 3; i++) {
        try {
          success = await _enviarFotoComTentativas(savedPath, fileName);
          if (success) break;
          await Future.delayed(Duration(seconds: 2));
        } catch (e) {
          print('Erro na tentativa ${i+1}: $e');
          if (i == 2) {
            setState(() {
              _lastTransmissionStatus = "Falha ao enviar foto após 3 tentativas";
            });
          }
        }
      }
    } catch (e) {
      print('Erro ao tirar foto de teste: $e');
      setState(() {
        _lastTransmissionStatus = "Erro ao capturar foto de teste: $e";
      });
    }
  }


  Future<bool> _enviarFotoComTentativas(String filePath, String fileName) async {
    if (_socket == null) {
      bool connected = await _connectToServer();
      if (!connected) {
        print('Não foi possível conectar ao servidor');
        return false;
      }
    }
    
    setState(() {
      _lastTransmissionStatus = "Preparando envio de foto...";
    });
    
    try {

      File imageFile = File(filePath);
      if (!await imageFile.exists()) {
        print('Arquivo não encontrado: $filePath');
        return false;
      }
      
      List<int> imageBytes = await imageFile.readAsBytes();
      if (imageBytes.isEmpty) {
        print('Arquivo vazio');
        return false;
      }

      String base64Image = base64Encode(imageBytes);
      

      String md5Hash = crypto.md5.convert(imageBytes).toString();
      print('Hash MD5: $md5Hash');
      

      String timestamp = DateTime.now().toIso8601String();

      setState(() {
        _lastTransmissionStatus = "Enviando metadados...";
      });
      

      if (!await _sendSafeCommand("STORE_PHOTO")) return false;
      await Future.delayed(Duration(milliseconds: 50));
      
      if (!await _sendSafeCommand("TIMESTAMP:$timestamp")) return false;
      await Future.delayed(Duration(milliseconds: 50));
      
      if (!await _sendSafeCommand("SIZE:${imageBytes.length}")) return false;
      await Future.delayed(Duration(milliseconds: 50));
      
      if (!await _sendSafeCommand("HASH:$md5Hash")) return false;
      await Future.delayed(Duration(milliseconds: 50));
      
      if (!await _sendSafeCommand("BEGIN_DATA")) return false;
      await Future.delayed(Duration(milliseconds: 300));
      

      int blockSize = 512;
      int totalBlocos = (base64Image.length / blockSize).ceil();
      int blocoAtual = 0;
      
      for (int i = 0; i < base64Image.length; i += blockSize) {
        blocoAtual++;
        setState(() {
          _lastTransmissionStatus = "Enviando dados: ${(blocoAtual * 100 / totalBlocos).toStringAsFixed(1)}%";
        });
        
        int end = (i + blockSize > base64Image.length) ? base64Image.length : i + blockSize;
        String chunk = base64Image.substring(i, end);
        
        try {

          _socket!.add(utf8.encode(chunk));
          await _socket!.flush();

          await Future.delayed(Duration(milliseconds: 50));
        } catch (e) {
          print('Erro ao enviar bloco $blocoAtual: $e');
          return false;
        }

        if (blocoAtual % 20 == 0) {
          await Future.delayed(Duration(milliseconds: 300));
        }
      }

      await Future.delayed(Duration(milliseconds: 500));
      if (!await _sendSafeCommand("\nEND_DATA")) {
        setState(() {
          _lastTransmissionStatus = "Erro ao finalizar transmissão";
        });
        return false;
      }
      
      setState(() {
        _lastTransmissionStatus = "Foto enviada! Aguardando confirmação...";
      });
      
      print('Foto enviada com sucesso!');
      return true;
    } catch (e) {
      print('Erro durante o envio: $e');
      return false;
    }
  }

  Future<void> _sendPhotoToServer(String filePath, String fileName) async {
    int tentativas = 0;
    const maxTentativas = 3;
    

    while (tentativas < maxTentativas) {
      tentativas++;
      
      try {

        File imageFile = File(filePath);
        if (!await imageFile.exists()) {
          print('Arquivo de imagem não encontrado: $filePath');
          setState(() {
            _lastTransmissionStatus = "Erro: Arquivo de imagem não encontrado";
          });
          return;
        }
        

        if (_socket == null) {
          print('Servidor não conectado. Tentando reconectar... (Tentativa $tentativas de $maxTentativas)');
          bool connected = await _connectToServer();
          
          if (!connected || _socket == null) {
            if (tentativas >= maxTentativas) {
              print('Não foi possível conectar ao servidor para enviar a foto.');
              setState(() {
                _lastTransmissionStatus = "Erro: Não foi possível conectar ao servidor";
              });
              return;
            }

            await Future.delayed(Duration(seconds: 2));
            continue;
          }
        }
        

        bool success = await _enviarFotoComTentativas(filePath, fileName);
        if (success) {
          return;
        } else if (tentativas < maxTentativas) {

          await Future.delayed(Duration(seconds: 2));
          _socket = null;
          await _connectToServer();
          continue;
        } else {
          setState(() {
            _lastTransmissionStatus = "Falha ao enviar foto após $maxTentativas tentativas";
          });
          return;
        }
        
      } catch (e) {
        print('Erro geral ao enviar foto (tentativa $tentativas): $e');
        
        if (tentativas >= maxTentativas) {
          setState(() {
            _lastTransmissionStatus = "Erro: $e";
          });
          return;
        }
        

        await Future.delayed(Duration(seconds: 2));
      }
    }
  }


  Future<bool> _connectToServer() async {
    if (_socket != null) {
      try {

        _socket!.add(utf8.encode("PING\n"));
        return true;
      } catch (e) {
        print("Conexão existente com falha: $e");
        _socket = null;
      }
    }

    setState(() {
      _lastTransmissionStatus = "Conectando ao servidor...";
    });

    try {


      final List<String> possibleIps = [
        "192.168.1.28",    // IP original
        "localhost",       // Nome simbólico
        "127.0.0.1",       // localhost numérico
        //"10.0.2.2",        // Emulador Android -> localhost
      ];
      
      final List<int> possiblePorts = [5000, 5001, 8000];
      bool connected = false;
      

      for (String serverIp in possibleIps) {
        if (connected) break;
        
        for (int serverPort in possiblePorts) {
          try {
            print("Tentando conectar ao servidor $serverIp:$serverPort...");

            _socket = await Socket.connect(
              serverIp, 
              serverPort,
              timeout: Duration(seconds: 5)
            );
            
            if (_socket != null) {
              print("Conectado ao servidor em $serverIp:$serverPort!");
              connected = true;

              _socket!.add(utf8.encode("HELLO\n"));
              await _socket!.flush();
              

              await Future.delayed(Duration(milliseconds: 300));
              

              _socket!.listen(
                (List<int> data) {
                  _handleServerResponse(String.fromCharCodes(data).trim());
                },
                onError: (error) {
                  print("Erro na conexão: $error");
                  _socket = null;
                  setState(() {
                    _lastTransmissionStatus = "Conexão perdida com o servidor: $error";
                  });
                },
                onDone: () {
                  print("Conexão com servidor fechada");
                  _socket = null;
                  setState(() {
                    _lastTransmissionStatus = "Conexão com servidor fechada";
                  });
                }
              );
              
              break;
            }
          } catch (error) {
            print("Não foi possível conectar a $serverIp:$serverPort - $error");
            _socket = null;
          }
        }
      }
      
      if (!connected) {
        setState(() {
          _lastTransmissionStatus = "Não foi possível conectar ao servidor em nenhum endereço";
        });
        return false;
      }
      
      return true;
    } catch (e) {
      print("Erro ao conectar ao servidor: $e");
      _socket = null;
      setState(() {
        _lastTransmissionStatus = "Não foi possível conectar ao servidor: $e";
      });
      return false;
    }
  }


  void _handleServerResponse(String response) {
    try {
      print("Resposta do servidor: $response");


      List<String> lines = response.split('\n');

      for (String line in lines) {
        if (line.isEmpty) continue;


        if (line == "WELCOME" || line == "HELLO_ACK") {
          print("Confirmação de conexão recebida: $line");
          setState(() {
            _lastTransmissionStatus = "Conexão estabelecida com o servidor";
          });
          continue;
        }
        

        if (line == "PONG") {
          print("PONG recebido do servidor (keepalive confirmado)");
          continue;
        }

        if (line.startsWith("PHOTO_STORED:")) {

          String fileName = line.substring("PHOTO_STORED:".length);


          bool alreadyStored = _storedPhotos.any((photo) => photo['filename'] == fileName);

          if (!alreadyStored) {
            setState(() {
              _storedPhotos.add({
                'filename': fileName,
                'timestamp': DateTime.now().toIso8601String(),
              });
              _lastTransmissionStatus = "Foto $fileName armazenada com sucesso no servidor!";
            });
            print("Confirmação de armazenamento recebida para: $fileName");
          } else {
            print("Foto $fileName já está na lista de armazenadas");
          }
        } else if (line.startsWith("ERROR:")) {
          setState(() {
            _lastTransmissionStatus = "Erro no servidor: ${line.substring("ERROR:".length)}";
          });
          print("Erro reportado pelo servidor: ${line.substring("ERROR:".length)}");
        } else if (line.startsWith("STORED_PHOTOS_LIST:")) {

          try {
            String jsonStr = line.substring("STORED_PHOTOS_LIST:".length);
            List<dynamic> photosList = jsonDecode(jsonStr);

            setState(() {
              _storedPhotos = List<Map<String, dynamic>>.from(photosList);
            });

            print("Lista de fotos armazenadas atualizada: ${_storedPhotos.length} fotos");
          } catch (e) {
            print("Erro ao processar lista de fotos: $e");
          }
        } else {
          print("ℹMensagem não reconhecida do servidor: $line");
        }
      }
    } catch (e) {
      print("Erro ao processar resposta do servidor: $e");
    }
  }


  Future<bool> _sendSafeCommand(String command) async {
    if (_socket == null) return false;
    
    try {
      _socket!.add(utf8.encode(command + '\n'));
      await _socket!.flush();
      return true;
    } catch (e) {
      print("Erro ao enviar comando '$command': $e");

      _socket = null;
      return false;
    }
  }
  

  void _requestStoredPhotosList() async {
    if (_socket == null) {
      print('Servidor não conectado. Tentando reconectar...');
      bool connected = await _connectToServer();


      if (connected) {
        Future.delayed(Duration(seconds: 1), () {
          _requestStoredPhotosList();
        });
      } else {
        print('Não foi possível conectar ao servidor para solicitar a lista de fotos.');
      }
      return;
    }

    try {

      bool sent = await _sendSafeCommand("GET_STORED_PHOTOS_LIST");
      if (sent) {
        print("Solicitando lista de fotos armazenadas no servidor...");
      } else {
        setState(() {
          _lastTransmissionStatus = "Falha ao solicitar lista de fotos";
        });
      }
    } catch (e) {
      print("Erro ao solicitar lista de fotos: $e");
      _socket = null;

      setState(() {
        _lastTransmissionStatus = "Erro ao solicitar lista de fotos";
      });
    }
  }

  void _toggleSensor() {
    if (_isSensorActive) {

      ProximitySensor.events.drain();

      _cameraController?.dispose();
      _isCameraInitialized = false;
      print("Sensor desativado e câmera liberada");
    } else {

      if (!_isCameraInitialized && _hasPermissions) {
        _initializeCamera().then((_) {
          _startProximitySensor();
        });
      } else {
        _startProximitySensor();
      }
    }

    setState(() {
      _isSensorActive = !_isSensorActive;
    });
  }


  void _startProximitySensor() {
    ProximitySensor.events.listen((int event) {
      setState(() {
        _status = (event == 1) ? "Perto" : "Longe";
      });

      if (event == 1) {
        print("Movimento detectado! Capturando foto...");
        _takePicture();
      }

      _sendData(event);
    });
  }


  void _sendData(int valorSensor) {
    try {
      if (_socket != null) {
        _socket!.add(utf8.encode("$valorSensor\n"));
        print("Dado enviado: $valorSensor");
      } else {
        print("Servidor não conectado!");
      }
    } catch (e) {
      print("Erro ao enviar dados para o servidor: $e");
      _socket = null;
      

      Future.delayed(Duration(seconds: 2), () {
        _connectToServer();
      });
    }
  }

  void _sendKeepAlive() {
    try {
      if (_socket != null) {
        _socket!.add(utf8.encode("PING\n"));
        print("Enviado keep-alive para o servidor");
        

        Timer(Duration(seconds: 3), () {
          if (_socket != null) {

            try {
              _socket!.add(utf8.encode(" "));
            } catch (e) {
              print("Socket inválido detectado no timeout de PONG: $e");
              _socket = null;
              _lastTransmissionStatus = "Conexão com servidor perdida (sem PONG)";
              _connectToServer();
            }
          }
        });
      }
    } catch (e) {
      print("Erro ao enviar keep-alive: $e");
      _socket = null;
      setState(() {
        _lastTransmissionStatus = "Erro ao enviar keep-alive: $e";
      });
    }
  }

  @override
  void dispose() {
    _socket?.close();
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        backgroundColor: Colors.indigo[100],
        appBar: AppBar(
          title: Text(
            "Sensor de Proximidade para Monitoramento Remoto",
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 14,
              color: Colors.white,
            ),
          ),
          backgroundColor: Colors.indigo,
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Card(
                  elevation: 4,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      children: [

                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              _socket != null ? Icons.cloud_done : Icons.cloud_off,
                              color: _socket != null ? Colors.green : Colors.red,
                              size: 16,
                            ),
                            SizedBox(width: 8),
                            Text(
                              _socket != null ? "Servidor conectado" : "Servidor desconectado",
                              style: TextStyle(
                                color: _socket != null ? Colors.green : Colors.red,
                                fontSize: 12,
                              ),
                            ),
                            Spacer(),
                            if (_socket == null)
                              TextButton.icon(
                                onPressed: () async {
                                  setState(() {
                                    _lastTransmissionStatus = "Tentando reconectar...";
                                  });
                                  bool connected = await _connectToServer();
                                  if (connected) {
                                    _requestStoredPhotosList();
                                  }
                                },
                                icon: Icon(Icons.refresh, size: 14),
                                label: Text("Reconectar", style: TextStyle(fontSize: 12)),
                                style: TextButton.styleFrom(
                                  padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  minimumSize: Size(60, 24),
                                ),
                              ),
                          ],
                        ),
                        SizedBox(height: 10),
                        Icon(
                          _isSensorActive ? Icons.sensors : Icons.sensors_off,
                          size: 48,
                          color: _isSensorActive ? Colors.green : Colors.red,
                        ),
                        SizedBox(height: 10),
                        Text(
                          "Status: $_status",
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            color: _status == "Perto" ? Colors.green : Colors.blue,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                SizedBox(height: 20),
                if (!_hasPermissions)
                  Card(
                    color: Colors.amber.shade100,
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        children: [
                          Icon(Icons.warning, color: Colors.orange, size: 32),
                          SizedBox(height: 8),
                          Text(
                            "Permissão necessária!",
                            style: TextStyle(
                              color: Colors.red, 
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          SizedBox(height: 10),
                          Text(
                            "Para capturar fotos discretamente, precisamos de acesso à câmera.",
                            textAlign: TextAlign.center,
                            style: TextStyle(fontSize: 14),
                          ),
                          SizedBox(height: 10),
                          ElevatedButton(
                            onPressed: _isRequestingPermission ? null : _requestPermissions,
                            child: Text(_isRequestingPermission ? "Solicitando..." : "Conceder Permissão"),
                          ),
                        ],
                      ),
                    ),
                  ),
                SizedBox(height: 20),
                if (_lastTransmissionStatus != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8.0),
                    child: Text(
                      _lastTransmissionStatus!,
                      style: TextStyle(
                        color: _lastTransmissionStatus!.startsWith("Erro")
                            ? Colors.red : Colors.green[800],
                        fontStyle: FontStyle.italic,
                        fontSize: 14,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                SizedBox(height: 20),

                SizedBox(height: 20),
                ElevatedButton.icon(
                  onPressed: _hasPermissions ? _toggleSensor : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isSensorActive ? Colors.red : Colors.green,
                    disabledBackgroundColor: Colors.grey,
                    padding: EdgeInsets.symmetric(horizontal: 30, vertical: 15),
                  ),
                  icon: Icon(
                    _isSensorActive ? Icons.stop_circle : Icons.play_circle,
                    color: Colors.white,
                  ),
                  label: Text(
                    _isSensorActive ? "Desativar Modo Segurança" : "Ativar Modo Segurança ",
                    style: TextStyle(fontSize: 14, color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _testarConexao() async {
    setState(() {
      _lastTransmissionStatus = "Testando conexão com o servidor...";
    });
    
    try {
      if (_socket == null) {
        bool conectado = await _connectToServer();
        if (conectado) {
          setState(() {
            _lastTransmissionStatus = "Conexão estabelecida com sucesso!";
          });
        } else {
          setState(() {
            _lastTransmissionStatus = "Não foi possível conectar ao servidor.";
          });
        }
      } else {

        bool sent = await _sendSafeCommand("PING");
        if (sent) {
          setState(() {
            _lastTransmissionStatus = "PING enviado, aguardando resposta...";
          });
          

          Timer(Duration(seconds: 3), () {
            setState(() {
              if (_socket != null) {
                _lastTransmissionStatus = "Conexão ativa, mas servidor pode não ter respondido ao PING em 3 segundos";
              } else {
                _lastTransmissionStatus = "Conexão perdida durante teste";
              }
            });
          });
        } else {
          setState(() {
            _lastTransmissionStatus = "Falha ao enviar PING, tentando reconectar...";
          });
          

          await _connectToServer();
        }
      }
    } catch (e) {
      setState(() {
        _lastTransmissionStatus = "Erro ao testar conexão: $e";
      });
    }
  }
}
