import 'dart:io';
import 'package:flutter/material.dart';
import 'package:proximity_sensor/proximity_sensor.dart';

void main() {
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

  @override
  void initState() {
    super.initState();
    _connectToServer(); // Conectar ao servidor quando o app inicia
  }

  // Função para conectar ao servidor
  void _connectToServer() async {
    try {
      _socket = await Socket.connect("192.168.1.28", 5000);
      print("✅ Conectado ao servidor!");
    } catch (e) {
      print("❌ Erro ao conectar ao servidor: $e");
    }
  }

  // Função para ativar/desativar o sensor
  void _toggleSensor() {
    if (_isSensorActive) {
      ProximitySensor.events.drain(); // Para de escutar o sensor
    } else {
      ProximitySensor.events.listen((int event) {
        setState(() {
          _status = (event == 1) ? "Perto" : "Longe";
        });

        // ✅ Enviar dados via socket
        _sendData(event);
      });
    }

    setState(() {
      _isSensorActive = !_isSensorActive;
    });
  }

  // Função para enviar dados via socket
  void _sendData(int valorSensor) {
    if (_socket != null) {
      _socket!.write("$valorSensor\n"); // Envia o valor do sensor
      print("📡 Dado enviado: $valorSensor");
    } else {
      print("⚠️ Servidor não conectado!");
    }
  }

  @override
  void dispose() {
    _socket?.close(); // Fecha a conexão ao sair do app
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        appBar: AppBar(title: Text("Sensor de Proximidade")),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                "Status: $_status",
                style: TextStyle(fontSize: 24),
              ),
              SizedBox(height: 20),
              ElevatedButton(
                onPressed: _toggleSensor,
                child: Text(_isSensorActive ? "Desligar Sensor" : "Ligar Sensor"),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
