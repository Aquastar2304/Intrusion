/*
 * esp32_ids_demo.ino  —  5-class model (Benign, Flood, Mirai, Probe, Spoofing), LIVE DEMO build
 *
 * Same model and serial protocol as esp32_ids.ino, plus:
 *   - on-board LED (GPIO 2) shows the alert state, decided ON THE CHIP
 *   - alert = current flow classified as an attack (ALERT_W = ALERT_K = 1)
 *   - reply is "<class_idx>,<micros>,<alert 0/1>"
 *   - "RESET" clears the alert window
 *
 * On boot: runs the Stage 1 smoke test (five hard-coded rows, one per class), then prints
 * "READY" and waits for rows over serial.
 *
 * Serial protocol (115200 baud, newline-terminated lines):
 *   laptop -> board : "PING"                       board replies "READY"
 *   laptop -> board : 25 comma-separated floats    board replies "<class_idx>,<micros>"
 * Anything that does not parse into 25 numbers gets "ERR,<reason>".
 *
 * Board: classic ESP32 DevKit (ESP32-WROOM-32)
 *   Tools -> Board            : "ESP32 Dev Module"
 *   Tools -> Flash Size       : "4MB (32Mb)"
 *   Tools -> Partition Scheme : "Default 4MB with spiffs"
 *   Serial Monitor            : 115200 baud
 */

#include "model_rf5_n30_d10_f25.h"
#include <stdlib.h>
#include <string.h>

#define N_FEATURES 25
#define N_CLASSES   5
#define LINE_MAX   1024

#define LED_PIN     2      // blue on-board LED on ESP32 DevKit boards
#define ALERT_W     1      // 1 = LED follows every single flow, no smoothing
#define ALERT_K     1      // LED on as soon as the current flow is an attack
#define BENIGN_IDX  0

static uint8_t win[ALERT_W];
static int     winPos = 0;
static bool    alertOn = false;

static void resetAlert() {
  memset(win, 0, sizeof(win)); winPos = 0; alertOn = false;
  digitalWrite(LED_PIN, LOW);
}

static bool updateAlert(int pred) {
  win[winPos] = (pred != BENIGN_IDX); winPos = (winPos + 1) % ALERT_W;
  int k = 0; for (int i = 0; i < ALERT_W; i++) k += win[i];
  alertOn = (k >= ALERT_K);
  digitalWrite(LED_PIN, alertOn ? HIGH : LOW);
  return alertOn;
}

// Must match the LabelEncoder order used in training (alphabetical).
static const char *CLASS_NAMES[N_CLASSES] = {
  "Benign", "Flood", "Mirai", "Probe", "Spoofing"   // DDoS+DoS -> Flood, Recon+Web+BruteForce -> Probe
};

// Feature order = models/compressed/selected_features.json =
//   AVG, Max, Rate, IAT, Min, Number, Time_To_Live, Std, Header_Length, Variance,
//   ack_flag_number, HTTPS, psh_flag_number, Protocol Type, TCP, SSH, ack_count,
//   UDP, HTTP, ICMP, syn_flag_number, syn_count, DNS, rst_flag_number, fin_flag_number

// ---------------------------------------------------------------- stage 1 ----
struct SmokeRow { int csv_row; int true_label; int expected; float x[N_FEATURES]; };

static const SmokeRow SMOKE[] = {
  {     2, 0, 0, {77.9f,156.0f,102.4025f,0.011990095f,60.0f,10.0f,204.9f,28.551903f,27.2f,815.2111f,0.9f,0.7f,0.2f,6.0f,0.9f,0.0f,9.0f,0.1f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f} },
  {   402, 1, 1, {60.0f,60.0f,31094.254f,3.2160282e-05f,60.0f,100.0f,64.0f,0.0f,8.0f,0.0f,0.0f,0.0f,0.0f,17.0f,0.0f,0.0f,0.0f,1.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f} },
  {   802, 2, 2, {592.0f,592.0f,4858.117f,0.0002065301f,592.0f,100.0f,64.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,47.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f} },
  {  1202, 3, 3, {98.8f,330.0f,50.336197f,0.020457601f,66.0f,10.0f,80.1f,81.754105f,18.4f,6683.7334f,0.3f,0.3f,0.0f,17.0f,0.4f,0.0f,3.0f,0.5f,0.1f,0.1f,0.2f,2.0f,0.1f,0.0f,0.0f} },
  {  1602, 4, 4, {376.1f,1500.0f,146.76123f,0.006834197f,54.0f,10.0f,69.9f,530.7212f,20.4f,281665.0f,0.8f,0.3f,0.2f,6.0f,0.8f,0.0f,8.0f,0.1f,0.5f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f} },
};
static const int N_SMOKE = sizeof(SMOKE) / sizeof(SMOKE[0]);

static const char *className(int idx) {
  return (idx >= 0 && idx < N_CLASSES) ? CLASS_NAMES[idx] : "?";
}

static void runSmokeTest() {
  Serial.println();
  Serial.println("==== esp32_ids  stage 1 smoke test  (rf5_n30_d10_f25) ====");
  int pass = 0;
  for (int i = 0; i < N_SMOKE; i++) {
    const SmokeRow &r = SMOKE[i];
    uint32_t t0 = micros();
    volatile int32_t pred = model_rf5_n30_d10_f25_predict(r.x, N_FEATURES);
    uint32_t dt = micros() - t0;
    bool ok = (pred == r.expected);
    if (ok) pass++;
    Serial.printf("row %4d  expected=%-10s  got=%-10s  %s  %lu us\n",
                  r.csv_row, className(r.expected), className(pred),
                  ok ? "PASS" : "FAIL", (unsigned long)dt);
  }
  Serial.printf("RESULT: %d / %d  ->  %s\n", pass, N_SMOKE,
                (pass == N_SMOKE) ? "STAGE 1 PASS" : "STAGE 1 FAIL");
}

// ---------------------------------------------------------------- stage 2 ----
static char  lineBuf[LINE_MAX];
static int   lineLen = 0;

// Parse "f,f,f,...,f" (exactly N_FEATURES values; extra trailing fields ignored).
// Returns number of values parsed.
static int parseRow(char *s, float *out) {
  int n = 0;
  char *tok = strtok(s, ",");
  while (tok && n < N_FEATURES) {
    char *end;
    out[n] = (float)strtod(tok, &end);     // same double->float path as the laptop harness (atof)
    if (end == tok) return n;           // not a number
    n++;
    tok = strtok(NULL, ",");
  }
  return n;
}

static void handleLine(char *s) {
  // trim trailing CR / spaces
  int n = strlen(s);
  while (n > 0 && (s[n-1] == '\r' || s[n-1] == ' ' || s[n-1] == '\t')) s[--n] = 0;
  if (n == 0) return;

  if (strcmp(s, "PING") == 0)  { Serial.println("READY"); return; }
  if (strcmp(s, "SMOKE") == 0) { runSmokeTest(); Serial.println("READY"); return; }
  if (strcmp(s, "RESET") == 0) { resetAlert();   Serial.println("READY"); return; }

  float x[N_FEATURES];
  int got = parseRow(s, x);
  if (got != N_FEATURES) {
    Serial.printf("ERR,parsed %d of %d features\n", got, N_FEATURES);
    return;
  }

  uint32_t t0 = micros();
  volatile int32_t pred = model_rf5_n30_d10_f25_predict(x, N_FEATURES);
  uint32_t dt = micros() - t0;
  bool a = updateAlert((int)pred);
  Serial.printf("%ld,%lu,%d\n", (long)pred, (unsigned long)dt, a ? 1 : 0);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  for (int i = 0; i < 3; i++) { digitalWrite(LED_PIN, HIGH); delay(150); digitalWrite(LED_PIN, LOW); delay(150); }
  resetAlert();
  delay(1100);
  runSmokeTest();
  Serial.printf("free heap: %u bytes\n", ESP.getFreeHeap());
  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      lineBuf[lineLen] = 0;
      handleLine(lineBuf);
      lineLen = 0;
    } else if (lineLen < LINE_MAX - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;                        // overflow: drop the line
      Serial.println("ERR,line too long");
    }
  }
}
