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

  @override
  void initState() {
    super.initState();
  }

  // Função para ativar e desativar o sensor
  void _toggleSensor() {
    if (_isSensorActive) {
      // Desativa o sensor
      ProximitySensor.events.drain(); // Para de escutar o sensor
    } else {
      // Ativa o sensor
      ProximitySensor.events.listen((int event) {
        setState(() {
          _status = (event == 1) ? "Perto" : "Longe"; // Atualiza o status
        });
      });
    }

    setState(() {
      _isSensorActive = !_isSensorActive; // Alterna o estado do sensor
    });
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
