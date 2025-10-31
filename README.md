# ESP32 温度监控系统

一个基于 ESP32 的工业电柜温度监控系统，包含数据采集、存储、可视化看板和设备状态管理功能。

## 功能特性

- 📊 **实时温度监控**：ESP32 设备采集温度数据并上传到服务器
- 🗄️ **数据存储**：使用 PostgreSQL 数据库持久化存储传感器数据
- 📈 **可视化看板**：基于 Flask 和 Chart.js 的实时数据可视化界面，支持多设备同时监控
- 🔄 **设备状态管理**：自动检测设备在线/离线状态
- 🔐 **API 认证**：使用 API Key 保护数据接口
- 🚀 **多服务架构**：模块化设计，支持独立部署
- 🔧 **Web 配置**：ESP32 设备支持通过 Web 界面配置 WiFi、服务器地址等参数
- 📱 **OTA 升级**：支持通过 Web 界面进行固件 OTA 升级
- ⚡ **性能优化**：数据库连接池、内存缓存等性能优化机制

## 系统架构

```
ESP32 设备
    ↓ (WiFi + HTTP POST)
Flask API 服务 (lightweight_server.py)
    ↓
PostgreSQL 数据库
    ↑
设备状态更新服务 (device_status_updater.py)
    ↓
Web 监控看板 (dashboard.py)
```

## 环境要求

- Python 3.7+
- PostgreSQL 12+
- ESP32 开发板
- WiFi 网络

## 安装步骤

### 1. 克隆或下载项目

```bash
git clone <repository-url>
cd 0924_ESP32
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

创建 PostgreSQL 数据库并配置连接信息。

### 4. 配置环境变量

复制 `env_example.txt` 为 `.env` 并填写实际配置：

```bash
cp env_example.txt .env
```

编辑 `.env` 文件，配置以下内容：

```env
# 数据库连接字符串
PG_URI=postgresql://username:password@localhost:5432/database_name

# API认证密钥
API_KEY=your_secret_api_key_here

# 服务端口
PORT=5000

# 看板端口
DASHBOARD_PORT=8080

# 设备状态更新间隔（秒）
DEVICE_STATUS_UPDATE_INTERVAL=30

# 设备离线阈值（秒）
DEVICE_OFFLINE_THRESHOLD=300
```

### 5. 初始化数据库表

在 PostgreSQL 中执行以下 SQL 创建所需表结构：

```sql
-- 创建遥测数据表
CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    fw_version VARCHAR(32),
    ip INET,
    uptime_sec INTEGER,
    temp_c REAL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_telemetry_device_id ON telemetry(device_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp);

-- 创建设备状态表
CREATE TABLE IF NOT EXISTS device_status (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL UNIQUE,
    fw_version VARCHAR(32),
    ip INET,
    uptime_sec INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'offline',
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_device_status_device_id ON device_status(device_id);
CREATE INDEX IF NOT EXISTS idx_device_status_last_seen ON device_status(last_seen);
```

### 6. 上传 ESP32 固件

使用 Arduino IDE 或 PlatformIO 将 `0924_sketch_sep24a_OTA.ino` 上传到 ESP32 设备。

**注意**：需要修改固件中的以下配置：
- WiFi SSID 和密码（在代码中修改或通过 Web 配置页面 `/config` 设置）
- 服务器地址和端口（可通过 Web 配置页面设置）
- API Key（可通过 Web 配置页面设置）

**ESP32 固件功能**：
- `/` - 设备状态页面（自动刷新）
- `/api/status` - JSON 状态接口
- `/config` - Web 配置页面（Basic Auth，登录后可在 Web 界面配置参数）
- `/update` - Web OTA 固件升级页面
- 自动上传温度数据到服务器

> 💡 **提示**：除了在代码中修改，大部分配置也可以通过 Web 配置页面 `/config` 进行设置，设置后会自动保存到设备 NVS 中。

## 使用方法

### 启动所有服务（推荐）

使用启动脚本一次性启动所有服务：

```bash
python start_services.py
```

### 单独启动服务

#### 启动 API 服务

```bash
python lightweight_server.py
```

#### 启动设备状态更新服务

```bash
python device_status_updater.py
```

#### 启动监控看板

```bash
python dashboard.py
```

### 访问监控看板

启动服务后，在浏览器中访问：

```
http://localhost:8080
```

## 项目结构

```
0924_ESP32/
├── 0924_sketch_sep24a_OTA.ino  # ESP32 Arduino 固件
├── dashboard.py                 # Web 监控看板服务
├── lightweight_server.py        # API 数据接收服务
├── device_status_updater.py     # 设备状态更新服务
├── main.py                      # 主服务入口
├── start_services.py            # 服务启动脚本
├── env_example.txt              # 环境变量配置示例
├── requirements.txt             # Python 依赖列表
├── README.md                    # 项目说明文档
└── LICENSE                      # 开源许可证
```

## API 接口

### API 服务接口（lightweight_server.py，端口 5000）

#### 健康检查

```
GET /health
```

返回服务器状态、当前时间和数据库连接池状态。

**响应示例**：
```json
{
  "status": "ok",
  "time": "2024-01-01T12:00:00+08:00",
  "database": {
    "connection_pool": {
      "status": "healthy",
      "pool_size": 2
    },
    "stats": {
      "pool_size": 2,
      "active_connections": 0,
      "connection_errors": 0
    }
  }
}
```

#### 数据上传

```
POST /api/telemetry
Headers:
  X-API-Key: your_api_key
Content-Type: application/json

Body:
{
  "deviceId": "1234567890ABCDEF",
  "fwVersion": "1.4.0",
  "ip": "192.168.1.100",
  "uptimeSec": 3600,
  "tempC": 25.5
}
```

**注意**：`tempC` 可以为 `null`（当传感器读取失败时）。

**响应示例**：
```json
{
  "ok": true,
  "timestamp": "2024-01-01T12:00:00+08:00",
  "record_id": 12345
}
```

#### 数据库状态

```
GET /api/database/status
```

返回数据库连接池和性能监控统计信息。

### 监控看板接口（dashboard.py，端口 8080）

#### 设备状态列表

```
GET /api/device_status
```

返回所有设备的当前状态信息。

**响应示例**：
```json
[
  {
    "device_id": "1234567890ABCDEF",
    "fw_version": "1.4.0",
    "ip": "192.168.1.100",
    "uptime_sec": 3600,
    "status": "online",
    "last_seen": "2024-01-01T12:00:00+08:00"
  }
]
```

#### 最近温度数据

```
GET /api/telemetry_recent
```

返回每个设备最近 50 条温度数据（用于图表显示）。

**响应示例**：
```json
{
  "1234567890ABCDEF": {
    "temps": [25.5, 25.6, 25.7],
    "timestamps": ["12:00:00", "12:00:10", "12:00:20"],
    "full_timestamps": ["2024-01-01T12:00:00+08:00", ...]
  }
}
```

#### 看板健康检查

```
GET /health
```

返回看板服务状态。

## 开发说明

### 数据库表结构

#### telemetry 表
存储所有设备的遥测数据：
- `id` - 主键，自增
- `device_id` - 设备 ID（基于 ESP32 MAC 地址生成）
- `fw_version` - 固件版本号
- `ip` - 设备 IP 地址
- `uptime_sec` - 设备运行时间（秒）
- `temp_c` - 温度值（摄氏度），可为 NULL
- `timestamp` - 数据记录时间

#### device_status 表
存储设备当前状态：
- `id` - 主键，自增
- `device_id` - 设备 ID（唯一）
- `fw_version` - 固件版本号
- `ip` - 设备 IP 地址
- `uptime_sec` - 设备运行时间（秒）
- `status` - 设备状态（'online' 或 'offline'）
- `last_seen` - 最后见到设备的时间

### 日志文件

- `server.log`：API 服务（lightweight_server.py）的日志
- `device_status_updater.log`：设备状态更新服务的日志

### 时区设置

系统使用北京时区（UTC+8），所有时间戳按此时区处理。

### 性能优化

- **数据库连接池**：API 服务使用轻量级连接池管理数据库连接
- **内存缓存**：部分查询结果使用内存缓存以提高性能
- **性能监控**：内置数据库操作性能监控功能

## 故障排查

### 服务启动问题

1. **无法连接数据库**：
   - 检查 `.env` 文件中的 `PG_URI` 配置是否正确
   - 确认 PostgreSQL 服务已启动
   - 检查数据库用户权限

2. **服务启动失败**：
   - 查看服务日志文件（`server.log`、`device_status_updater.log`）
   - 确认所有 Python 依赖已正确安装
   - 检查端口是否被占用

### 设备连接问题

3. **API 认证失败**：
   - 确认 ESP32 固件中的 API Key 与服务器 `.env` 文件中的 `API_KEY` 一致
   - 检查请求头中的 `X-API-Key` 是否正确发送

4. **设备显示离线**：
   - 检查设备 WiFi 连接是否正常
   - 确认设备可以访问服务器地址和端口
   - 检查服务器日志查看是否有数据接收记录
   - 调整 `DEVICE_OFFLINE_THRESHOLD` 参数（如果设备上传间隔较长）

5. **设备无法连接 WiFi**：
   - 检查 ESP32 固件中的 WiFi 配置
   - 通过设备热点访问 `/config` 页面重新配置 WiFi
   - 查看设备串口输出调试信息

### 数据问题

6. **看板无数据**：
   - 确认数据库中有数据：`SELECT COUNT(*) FROM telemetry;`
   - 检查看板的时间范围设置
   - 确认设备正在上传数据（查看服务器日志）

7. **温度数据显示异常**：
   - 检查 DS18B20 传感器连接（ESP32 GPIO 4）
   - 查看设备状态页面确认传感器是否正常工作
   - 温度值为 `null` 表示传感器读取失败

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，请通过 Issue 联系。

---

**注意**：在生产环境中使用前，请务必：
- 修改默认的 API Key
- 配置安全的数据库连接
- 启用 HTTPS（如需要）
- 设置防火墙规则

