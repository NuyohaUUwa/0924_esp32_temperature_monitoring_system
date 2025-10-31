/* ESP32 Web OTA + DS18B20 + 可配置上传 & 自动刷新
 * - /              状态页（自动刷新，间隔可在 /config 配）
 * - /api/status    返回 JSON（设备ID/版本/IP/Uptime/温度）
 * - /config        配置页（Basic Auth），保存到 NVS，立即生效
 * - /config/reset  恢复默认配置（需要确认）
 * - /update        Web OTA（Basic Auth）
 *
 * 依赖：OneWire、DallasTemperature
 */
#include <WiFi.h>
#include <WebServer.h>
#include <Update.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ESPmDNS.h>
#include <Preferences.h>

// ====== 必填：你的 Wi-Fi ======
const char* WIFI_SSID = "Your_WiFi_SSID";  // 修改为你的 WiFi 名称
const char* WIFI_PASS = "";                // 修改为你的 WiFi 密码（如无密码则留空）

// ====== 管理登录（用于 /config 与 /update）======
const char* AUTH_USER = "admin";
const char* AUTH_PASS = "change_me";       // 修改为强密码

// ====== 固件版本（升级时改它）======
const char* FW_VERSION = "1.4.0";

// ==== SoftAP（热点）设置 ====
const char* AP_PASS = "12345678";          // 修改为安全的密码  
const int   AP_CH   = 1;     // 先给个占位；连上路由后AP会跟随STA信道
const int   AP_HIDDEN = 0;   // 0 显示, 1 隐藏

// 硬件
const int ONEWIRE_PIN = 4;

// --- 运行参数（可在 /config 修改，并持久化到 NVS） ---
struct AppConfig {
  uint32_t refreshMs   = 2000;                  // 首页自动刷新间隔(ms)
  uint32_t uploadMs    = 10000;                 // 数据上传间隔(ms)
  char     apiHost[64] = "example.com";         // 服务器IP或域名（示例值，需修改）
  uint16_t apiPort     = 5000;                  // 服务器端口
  char     apiKey[64]  = "MY_SECRET_KEY";       // API Key（示例值，需修改）

  // 新增：可配置 STA Wi-Fi（默认用编译期常量）
  char     wifiSsid[33] = "";                   // 最长32字节+结尾
  char     wifiPass[65] = "";                   // 最长64字节+结尾
  AppConfig() {
    strlcpy(wifiSsid, WIFI_SSID, sizeof(wifiSsid));
    strlcpy(wifiPass, WIFI_PASS, sizeof(wifiPass)); // 允许为空字符串
  }
} cfg;

Preferences prefs;               // NVS
WebServer  server(80);
OneWire    oneWire(ONEWIRE_PIN);
DallasTemperature sensors(&oneWire);

float lastTempC = NAN;
unsigned long lastReadMs   = 0;
const unsigned long readInterval = 3000; // 传感器读取周期
unsigned long lastUploadMs = 0;

// ---- 上传状态（首页显示用）----
int lastPostCode = -1;
bool lastPostOk = false;
unsigned long lastPostAtMs = 0;

// --- 全局变量 ---
bool needReboot   = false;
unsigned long rebootAtMs = 0;

String chipId() {
  uint64_t mac = ESP.getEfuseMac();
  char s[17];
  snprintf(s, sizeof(s), "%04X%08X", (uint16_t)(mac>>32), (uint32_t)mac);
  return String(s);
}

String apSsid() {
  // 使用完整设备ID，若你只想后6位可用：chipId().substring(chipId().length()-6)
  return String("AE1_CEWEN_") + chipId();
}

// ---------- NVS 持久化 ----------
void loadConfig() {
  prefs.begin("cfg", true);

  cfg.refreshMs = prefs.getUInt("refresh_ms", cfg.refreshMs);
  cfg.uploadMs  = prefs.getUInt("upload_ms",  cfg.uploadMs);
  prefs.getString("api_host", cfg.apiHost, sizeof(cfg.apiHost));
  cfg.apiPort = prefs.getUShort("api_port", cfg.apiPort);
  prefs.getString("api_key",  cfg.apiKey,  sizeof(cfg.apiKey));

  // 新增：Wi-Fi STA 配置（读不到则保持默认值）
  prefs.getString("wifi_ssid", cfg.wifiSsid, sizeof(cfg.wifiSsid));
  prefs.getString("wifi_pass", cfg.wifiPass, sizeof(cfg.wifiPass));

  prefs.end();
}

void saveConfig() {
  prefs.begin("cfg", false);
  prefs.putUInt("refresh_ms", cfg.refreshMs);
  prefs.putUInt("upload_ms",  cfg.uploadMs);
  prefs.putString("api_host", cfg.apiHost);
  prefs.putUShort("api_port", cfg.apiPort);
  prefs.putString("api_key",  cfg.apiKey);

  // 新增：Wi-Fi STA 配置
  prefs.putString("wifi_ssid", cfg.wifiSsid);
  prefs.putString("wifi_pass", cfg.wifiPass);

  prefs.end();
}

void resetConfigToDefaults() {
  AppConfig def;           // 利用默认构造值
  cfg = def;
  saveConfig();
}

// ---------- 页面与接口 ----------
void guardAuth() {
  if (!server.authenticate(AUTH_USER, AUTH_PASS)) {
    server.requestAuthentication(); // 弹出浏览器认证框
  }
}

// 首页（嵌入当前刷新间隔）
void handleRoot() {
  String html =
    "<!doctype html><html><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
    "<style>body{font-family:system-ui;margin:20px}code{background:#eee;padding:2px 6px;border-radius:6px}</style>"
    "<h2>ESP32 温度节点（自动刷新）</h2>"
    "<p><b>设备ID:</b> <span id='id'>-</span></p>"
    "<p><b>固件版本:</b> <span id='ver'>-</span></p>"
    "<p><b>IP:</b> <span id='ip'>-</span></p>"
    "<p><b>Uptime:</b> <span id='up'>-</span> s</p>"
    "<p><b>温度:</b> <span id='t'>-</span> ℃</p>"
    "<p><b>上次上传:</b> <span id='upOk'>-</span> (HTTP <span id='upCode'>-</span>, <span id='upAge'>-</span>s 前)</p>"
    "<p><small>自动刷新：每 " + String(cfg.refreshMs/1000.0, 2) + " 秒 · "
    "<a href='/config'>配置</a> · <a href='/update'>OTA</a></small></p>"
    "<script>"
    "const interval=" + String(cfg.refreshMs) + ";"
    "async function pull(){"
    "  try{"
    "    const r=await fetch('/api/status',{cache:'no-store'});"
    "    const j=await r.json();"
    "    document.getElementById('id').textContent=j.id;"
    "    document.getElementById('ver').textContent=j.version;"
    "    document.getElementById('ip').textContent=j.ip;"
    "    document.getElementById('up').textContent=j.uptime;"
    "    document.getElementById('t').textContent=(j.tempC===null?'N/A':j.tempC.toFixed(2));"
    "    const u=j.upload||{};"
    "    document.getElementById('upOk').textContent=(u.ageSec===-1?'未上传':(u.ok?'成功':'失败'));"
    "    document.getElementById('upCode').textContent=(u.ageSec===-1?'-':u.code);"
    "    document.getElementById('upAge').textContent =(u.ageSec===-1?'-':u.ageSec);"
    "  }catch(e){console.log(e)}"
    "}"
    "pull(); setInterval(pull, interval);"
    "</script></html>";

  server.sendHeader("Cache-Control","no-store");
  server.send(200, "text/html", html);
}

// JSON 状态
void handleStatusJson() {
  String payload = "{";
  payload += "\"id\":\"" + chipId() + "\",";
  payload += "\"version\":\"" + String(FW_VERSION) + "\",";
  payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  payload += "\"uptime\":" + String(millis()/1000) + ",";
  if (isnan(lastTempC)) payload += "\"tempC\":null"; else payload += "\"tempC\":" + String(lastTempC,2);

  payload += ","; // ← 新增：给 upload 字段留逗号
  payload += "\"upload\":{";
  payload += "\"ok\":" + String(lastPostOk ? "true" : "false") + ",";
  payload += "\"code\":" + String(lastPostCode) + ",";
  if (lastPostAtMs == 0) payload += "\"ageSec\":-1";
  else payload += "\"ageSec\":" + String((millis() - lastPostAtMs) / 1000);
  payload += "}";

  payload += "}";
  server.sendHeader("Cache-Control","no-store");
  server.send(200, "application/json", payload);
}

// 配置页（GET）
void handleConfigPage() {
  guardAuth();
  String html =
    "<!doctype html><html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'/>"
    "<body style='font-family:system-ui;margin:20px'>"
    "<h2>配置（保存即生效）</h2>"
    "<form method='POST' action='/config'>"
      "<label>Wi-Fi SSID：</label><br>"
      "<input name='wifiSsid' maxlength='32' value='" + String(cfg.wifiSsid) + "' required><br><br>"
      "<label>Wi-Fi 密码（可留空）：</label><br>"
      "<input name='wifiPass' maxlength='64' value='" + String(cfg.wifiPass) + "'><br><br>"
      "<label>首页刷新间隔(ms)：</label><br>"
      "<input name='refreshMs' type='number' min='500' value='" + String(cfg.refreshMs) + "' required><br><br>"
      "<label>上传间隔(ms)：</label><br>"
      "<input name='uploadMs' type='number' min='1000' value='" + String(cfg.uploadMs) + "' required><br><br>"
      "<label>服务器 IP/域名：</label><br>"
      "<input name='apiHost' value='" + String(cfg.apiHost) + "' required><br><br>"
      "<label>服务器端口：</label><br>"
      "<input name='apiPort' type='number' min='1' max='65535' value='" + String(cfg.apiPort) + "' required><br><br>"
      "<label>API Key：</label><br>"
      "<input name='apiKey' value='" + String(cfg.apiKey) + "'><br><br>"
      "<button type='submit'>保存</button>"
    "</form>"
    "<p><a href='/'>&larr; 返回首页</a> · <a href='/update'>OTA</a></p>"
    "<hr><form method='POST' action='/config/reset' onsubmit='return confirm(\"确认恢复默认并重启？\")'>"
    "<button style='color:#b00'>恢复默认并重启</button></form>"
    "</body></html>";
  server.send(200, "text/html", html);
}

// 配置保存（POST）
void handleConfigSave() {
  guardAuth();

  long rMs = server.arg("refreshMs").toInt();
  long uMs = server.arg("uploadMs").toInt();
  if (rMs < 500)  rMs = 500;
  if (uMs < 1000) uMs = 1000;

  String apiHost = server.arg("apiHost");
  long   p       = server.arg("apiPort").toInt();
  if (p < 1) p = 1; if (p > 65535) p = 65535;

  String apiKey  = server.arg("apiKey");
  String wifiSsid = server.arg("wifiSsid");
  String wifiPass = server.arg("wifiPass"); // 允许为空

  bool wifiChanged = (wifiSsid != String(cfg.wifiSsid)) || (wifiPass != String(cfg.wifiPass));

  wifiSsid.toCharArray(cfg.wifiSsid, sizeof(cfg.wifiSsid));
  wifiPass.toCharArray(cfg.wifiPass, sizeof(cfg.wifiPass));

  // 更新到内存
  cfg.refreshMs = (uint32_t)rMs;
  cfg.uploadMs  = (uint32_t)uMs;
  apiHost.toCharArray(cfg.apiHost, sizeof(cfg.apiHost));
  cfg.apiPort = (uint16_t)p;
  apiKey.toCharArray(cfg.apiKey, sizeof(cfg.apiKey));

  // 持久化
  saveConfig();

  if (wifiChanged) {
    // 需要重启以使用新的 STA 参数
    needReboot = true;
    rebootAtMs = millis() + 2000;
    server.send(200, "text/html",
      "<!doctype html><meta charset='utf-8'>"
      "<p>Wi-Fi 参数已保存，设备将于 2 秒后重启以应用。</p>"
      "<meta http-equiv='refresh' content='3;url=/' />");
  } 
  else {
    server.send(200, "text/html",
      "<!doctype html><meta charset='utf-8'>"
      "<p>已保存并生效。<a href='/config'>返回</a> · <a href='/'>回首页</a></p>");
  }
}

// 恢复默认并重启
void handleConfigReset() {
  guardAuth();
  resetConfigToDefaults();
  String html =
    "<!doctype html><meta charset='utf-8'>"
    "<p>已恢复默认配置，设备将重启...</p>";
  server.send(200, "text/html", html);
  delay(800);
  ESP.restart();
}

// OTA 页面
void handleUpdatePage() {
  guardAuth();
  String html =
    "<!doctype html><html><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
    "<body style='font-family:system-ui;margin:20px'>"
    "<h2>固件升级（当前 " + String(FW_VERSION) + ")</h2>"
    "<form method='POST' action='/update' enctype='multipart/form-data'>"
    "<input type='file' name='update' accept='.bin' required>"
    "<input type='submit' value='上传并升级'>"
    "</form>"
    "<p><a href='/'>返回首页</a> · <a href='/config'>配置</a></p>"
    "</body></html>";
  server.send(200, "text/html", html);
}

// ---------- 上传到你的 Flask 服务 ----------
bool postTelemetry(float tempC) {
  if (WiFi.status() != WL_CONNECTED) return false;
  String url = "http://" + String(cfg.apiHost) + ":" + String(cfg.apiPort) + "/api/telemetry";

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", String(cfg.apiKey));

  String payload = "{";
  payload += "\"deviceId\":\"" + chipId() + "\",";
  payload += "\"fwVersion\":\"" + String(FW_VERSION) + "\",";
  payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  payload += "\"uptimeSec\":" + String(millis()/1000) + ",";
  if (isnan(tempC)) payload += "\"tempC\":null"; else payload += "\"tempC\":" + String(tempC,2);
  payload += "}";

  int code = http.POST(payload);
  String resp = http.getString();
  http.end();

  // 记录上传结果（给首页显示）
  lastPostAtMs = millis();
  lastPostCode = code;
  lastPostOk   = (code >= 200 && code < 300);

  Serial.printf("[POST] %s -> code=%d, resp=%s\n", url.c_str(), code, resp.c_str());
  return lastPostOk;
}

// ---------- 初始化 ----------
void setup() {
  Serial.begin(115200);
  delay(200);

  loadConfig(); // 先加载配置

  WiFi.mode(WIFI_AP_STA);
  if (strlen(cfg.wifiPass) == 0) {
    WiFi.begin(cfg.wifiSsid);
  } 
  else {
    WiFi.begin(cfg.wifiSsid, cfg.wifiPass);
  }

  Serial.printf("WiFi connecting to %s ...\n", WIFI_SSID);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis()-t0 < 15000) {delay(500); Serial.print(".");}
  Serial.printf("\nWiFi %s, IP=%s\n",
  WiFi.status()==WL_CONNECTED ? "OK" : "FAILED",
  WiFi.localIP().toString().c_str());

  Serial.printf("\nWiFi OK, IP=%s\n", WiFi.localIP().toString().c_str());

  String ssid = apSsid();
  bool apOk = WiFi.softAP(ssid.c_str(), AP_PASS, AP_CH, AP_HIDDEN, 4);
  Serial.printf
  (
    "SoftAP %s -> %s, AP IP=%s\n",
    ssid.c_str(), apOk ? "OK":"FAIL",
    WiFi.softAPIP().toString().c_str()
  );

  MDNS.begin(("esp32-" + chipId()).c_str());
  sensors.begin();

  // 路由
  server.on("/",            HTTP_GET,  handleRoot);
  server.on("/api/status",  HTTP_GET,  handleStatusJson);
  server.on("/config",      HTTP_GET,  handleConfigPage);
  server.on("/config",      HTTP_POST, handleConfigSave);
  server.on("/config/reset",HTTP_POST, handleConfigReset);
  server.on("/update",      HTTP_GET,  handleUpdatePage);

  // OTA 上传处理
  server.on("/update", HTTP_POST,
    [](){
      guardAuth();
      bool ok = !Update.hasError();

      // 成功：返回一个页面，告诉浏览器“已成功”，并3秒后跳首页
      server.sendHeader("Cache-Control","no-store");
      if (ok) {
        needReboot = true;
        rebootAtMs = millis() + 3000;  // 3秒后在 loop() 里重启
        server.send(200, "text/html",
          "<!doctype html><meta charset='utf-8'>"
          "<p>OTA 成功，设备将于 3 秒后自动重启…</p>"
          "<meta http-equiv='refresh' content='3;url=/' />");
      } else {
        server.send(200, "text/html",
          "<!doctype html><meta charset='utf-8'>"
          "<p>OTA 失败，请返回重试。</p>"
          "<p><a href='/update'>返回 OTA 页面</a></p>");
      }
    },
    [](){ 
      if(!server.authenticate(AUTH_USER,AUTH_PASS)) return;
          if (needReboot) {
            server.send(409, "text/plain", "Busy: rebooting");
            return;
          }
          HTTPUpload& up=server.upload();
          if(up.status==UPLOAD_FILE_START){
            Serial.printf("Update start: %s\n", up.filename.c_str());
            if(!Update.begin()) Update.printError(Serial);
          } else if(up.status==UPLOAD_FILE_WRITE){
            if(Update.write(up.buf, up.currentSize)!=up.currentSize) Update.printError(Serial);
          } else if(up.status==UPLOAD_FILE_END){
            if(Update.end(true)) Serial.printf("Update success: %u bytes\n", up.totalSize);
            else Update.printError(Serial);
          }
          });

  server.onNotFound([](){ server.send(404,"text/plain","Not found"); });
  server.begin();
  Serial.println("HTTP server started.");
}

// ---------- 主循环 ----------
void loop() {
  server.handleClient();

  // 定期读取温度（状态页使用）
  unsigned long now = millis();
  if (now - lastReadMs >= readInterval) {
    lastReadMs = now;
    sensors.requestTemperatures();
    lastTempC = sensors.getTempCByIndex(0);
    Serial.printf("T=%.2f C\n", lastTempC);
  }

  // 定期上传
  if (now - lastUploadMs >= cfg.uploadMs) {
    lastUploadMs = now;
    postTelemetry(lastTempC);
  }

  // 延迟重启：确保上一个HTTP响应已经完整发回浏览器
  if (needReboot && (long)(millis() - rebootAtMs) >= 0) {
    ESP.restart();
  }
}
