const int trigPin = 9;
const int echoPin = 10;
const int connectionLedPin = 13;
const int statusLedPin = 12;
const int buzzerPin = 3;

unsigned long lastSignalTime = 0;
unsigned long lastBlinkTime = 0;
bool connectionLedState = false;
int measurementStatus = 1;
unsigned long lastStatusBlinkTime = 0;
bool statusLedActive = false;

int buzzerVolume = 10;

void setup() {
  Serial.begin(9600);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(connectionLedPin, OUTPUT);
  pinMode(statusLedPin, OUTPUT);
  pinMode(buzzerPin, OUTPUT);
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.peek();
    
    if (c == 'H' || c == '1' || c == '2' || c == '3') {
      c = Serial.read();
      if (c == 'H') lastSignalTime = millis();
      else if (c == '1') measurementStatus = 1;
      else if (c == '2') measurementStatus = 2;
      else if (c == '3') measurementStatus = 3;
    } 
    else if (c == 'V') {
      Serial.read();
      int readVolume = Serial.parseInt();
      if (readVolume >= 0 && readVolume <= 10) {
        buzzerVolume = readVolume;
      }
    } 
    else {
      Serial.read();
    }
  }

  if (millis() - lastSignalTime < 2000) { 
    digitalWrite(connectionLedPin, HIGH);
  } else { 
    if (millis() - lastBlinkTime >= 500) {
      lastBlinkTime = millis();
      connectionLedState = !connectionLedState;
      digitalWrite(connectionLedPin, connectionLedState);
    }
    measurementStatus = 1;
  }

  int pwmVolume = map(buzzerVolume, 0, 10, 0, 255);
  
  if (measurementStatus == 1) {
    digitalWrite(statusLedPin, LOW);
    analogWrite(buzzerPin, 0);
  } 
  else if (measurementStatus == 2) {
    if (millis() - lastStatusBlinkTime >= 50) {
      lastStatusBlinkTime = millis();
      statusLedActive = !statusLedActive;
      digitalWrite(statusLedPin, statusLedActive);
      
      if (statusLedActive) {
        analogWrite(buzzerPin, pwmVolume);
      } else {
        analogWrite(buzzerPin, 0);
      }
    }
  } 
  else if (measurementStatus == 3) {
    digitalWrite(statusLedPin, HIGH);
    analogWrite(buzzerPin, pwmVolume);
  }

  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH);
  int distance = duration * 0.036 / 2 +3;
  
  if (distance > 0 && distance <= 400) { 
    Serial.println(distance);
  }

  delay(100);
}
