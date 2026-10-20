#include <WiFi.h>
#include <esp_wifi.h>

// 1. CSI callback: runs every time a packet is received
void wifi_csi_cb(void *ctx, wifi_csi_info_t *data) {
  wifi_csi_info_t d = data[0]; 
  
  // Print the signal strength (RSSI) and start the data array
  Serial.printf("RSSI:%d,DATA:", d.rx_ctrl.rssi);

  // 2. Dump the CSI bytes (an imaginary/real pair per subcarrier)
  int8_t *csi_data = d.buf;
  for (int i = 0; i < d.len; i++) {
    Serial.printf("%d,", csi_data[i]); 
  }
  Serial.println();
}

void setup() {
  // 3. High baud rate: the serial link is the bottleneck, a slow rate would stall the CSI stream
  Serial.begin(921600); 
  
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);
  
  esp_wifi_set_csi(1);

  wifi_csi_config_t csi_config = {
      .lltf_en = 1,
      .htltf_en = 1,
      .stbc_htltf2_en = 1,
      .ltf_merge_en = 1,
      .channel_filter_en = 1,
      .manu_scale = 0,
      .shift = 0
  };
  esp_wifi_set_csi_config(&csi_config);
  
  // Register the CSI callback
  esp_wifi_set_csi_rx_cb(&wifi_csi_cb, NULL);
}

void loop() {
  // All work happens in the callback; loop() only idles
  delay(1000); 
}