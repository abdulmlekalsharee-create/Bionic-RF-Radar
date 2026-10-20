#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h> // Low-level Wi-Fi control (needed to fix the radio channel)

// Broadcast address: every ESP-NOW receiver in range can hear the packets
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

typedef struct struct_message {
  uint32_t packet_id;
} struct_message;

struct_message myData;
unsigned long lastTime = 0;
const unsigned long timerDelay = 10; // 10 ms = 100 packets per second

void setup() {
  Serial.begin(115200);
  
  // 1. Disconnect from any router and run as a standalone transmitter
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  // 2. Fix the channel: force the radio to stay on channel 1 (must match the receiver)
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  // 3. Initialise the ESP-NOW protocol
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // 4. Register the broadcast peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 1;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer");
    return;
  }
  
  myData.packet_id = 0;
  Serial.println("Transmitter Ready: Bombarding the room at 100Hz on Channel 1...");
}

void loop() {
  // Send packets at a fixed rate using the internal millis() timer
  if (millis() - lastTime >= timerDelay) {
    lastTime = millis();
    esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
    myData.packet_id++;
  }
}