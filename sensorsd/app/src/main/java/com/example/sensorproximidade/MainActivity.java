package com.example.sensorproximidade;

import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.hardware.Camera;
import android.hardware.Camera.CameraInfo;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Bundle;
import android.provider.MediaStore;
import android.util.Log;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

import java.io.IOException;
import java.io.OutputStream;
import java.util.UUID;

public class MainActivity extends AppCompatActivity {

    // Criando as variáveis para TextView, SensorManager e o sensor de proximidade.
    TextView sensorStatusTV;
    SensorManager sensorManager;
    Sensor proximitySensor;

    // Constante para o código de requisição da câmera
    private static final int CAMERA_REQUEST_CODE = 1001;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        sensorStatusTV = findViewById(R.id.sensorStatusTV);

        // Obtendo o serviço de sensor.
        sensorManager = (SensorManager) getSystemService(Context.SENSOR_SERVICE);

        // Obtendo o sensor de proximidade.
        proximitySensor = sensorManager.getDefaultSensor(Sensor.TYPE_PROXIMITY);

        // Verificando se o sensor de proximidade está disponível no dispositivo.
        if (proximitySensor == null) {
            Toast.makeText(this, "Nenhum sensor de proximidade encontrado.", Toast.LENGTH_SHORT).show();
            finish();
        } else {
            // Registrando o listener para o sensor.
            sensorManager.registerListener(proximitySensorEventListener,
                    proximitySensor,
                    SensorManager.SENSOR_DELAY_NORMAL);
        }
    }

    // O listener do evento do sensor.
    SensorEventListener proximitySensorEventListener = new SensorEventListener() {
        @Override
        public void onAccuracyChanged(Sensor sensor, int accuracy) {
            // Esse método pode ser utilizado para checar mudanças na precisão do sensor (caso necessário).
        }

        @Override
        public void onSensorChanged(SensorEvent event) {
            // Verificando se o evento veio do sensor de proximidade.
            if (event.sensor.getType() == Sensor.TYPE_PROXIMITY) {
                float distance = event.values[0]; // Distância em centímetros
                float maxRange = proximitySensor.getMaximumRange(); // A distância máxima do sensor
                Log.d("SensorProximidade", "Distância detectada: " + distance + " cm");
                Log.d("SensorProximidade", "Distância máxima do sensor: " + maxRange + " cm");

                // Verificando o estado do sensor.
                if (distance == 0) {
                    // Quando o sensor detecta um objeto muito próximo.
                    sensorStatusTV.setText("Objeto perto!");

                    // Tirando uma foto com a câmera frontal
                    takePictureWithFrontCamera();
                } else if (distance == maxRange) {
                    // Quando o sensor não detecta nada, ou está no limite máximo de distância.
                    sensorStatusTV.setText("Objeto distante!");
                } else {
                    // Exibindo a distância medida pelo sensor.
                    sensorStatusTV.setText("Distância: " + distance + " cm");
                }
            }
        }
    };

    // Método para abrir a câmera frontal e tirar uma foto
    private void takePictureWithFrontCamera() {
        Intent cameraIntent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);

        // Verificando se há uma atividade para lidar com o intent da câmera
        if (cameraIntent.resolveActivity(getPackageManager()) != null) {
            startActivityForResult(cameraIntent, CAMERA_REQUEST_CODE);
        } else {
            Toast.makeText(this, "Nenhuma aplicação de câmera disponível.", Toast.LENGTH_SHORT).show();
        }
    }

    // Método para tratar o resultado da captura da foto
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == CAMERA_REQUEST_CODE && resultCode == RESULT_OK) {
            // Se a foto foi tirada com sucesso, obtém a imagem capturada
            Bitmap photo = (Bitmap) data.getExtras().get("data");

            // Salvando a imagem em armazenamento interno ou externo
            if (photo != null) {
                try {
                    // Cria um arquivo único para a imagem usando UUID
                    String imageFileName = UUID.randomUUID().toString() + ".jpg";
                    OutputStream outputStream = openFileOutput(imageFileName, Context.MODE_PRIVATE);
                    photo.compress(Bitmap.CompressFormat.JPEG, 100, outputStream);
                    outputStream.close();
                    Toast.makeText(this, "Foto salva com sucesso!", Toast.LENGTH_SHORT).show();
                    Log.d("SensorProximidade", "Foto salva como: " + imageFileName);
                } catch (IOException e) {
                    e.printStackTrace();
                    Toast.makeText(this, "Erro ao salvar foto.", Toast.LENGTH_SHORT).show();
                }
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Desregistrando o listener quando a Activity for destruída.
        sensorManager.unregisterListener(proximitySensorEventListener);
    }
}
