# 设备监控看板
# 文件名: dashboard.py

import os
import logging
import psycopg2
from flask import Flask, render_template_string, jsonify, request
from dotenv import load_dotenv

from dingtalk_notifier import send_dingtalk_text

# 加载环境变量
load_dotenv()

# 配置
PG_URI = os.getenv("PG_URI")
PORT = int(os.getenv("DASHBOARD_PORT", "8080"))

# 创建Flask应用
app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(PG_URI)

def init_device_config_table():
    """初始化设备配置表（如果不存在则创建）"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS device_config (
                    device_id VARCHAR(50) PRIMARY KEY,
                    alias VARCHAR(100) DEFAULT '',
                    threshold DECIMAL(5,2) DEFAULT 50.0,
                    duration INTEGER DEFAULT 10,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("设备配置表已就绪")
    except Exception as e:
        logger.error(f"初始化设备配置表失败: {e}")
    finally:
        if conn:
            conn.close()

@app.route("/")
def dashboard():
    """AE1科电柜温度监控看板主页"""
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AE1科电柜温度监控看板</title>
    <style>
        :root {
            --primary: #4f46e5;
            --primary-light: #818cf8;
            --primary-dark: #3730a3;
            --success: #10b981;
            --danger: #f43f5e;
            --warning: #f59e0b;
            --bg-main: #f8fafc;
            --bg-card: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            min-height: 100vh;
            line-height: 1.6;
        }
        
        .navbar {
            background-color: #1e293b;
            color: white;
            padding: 0.75rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: var(--shadow);
        }

        .navbar-brand {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.25rem;
            font-weight: 700;
            color: white;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 1.5rem;
        }
        
        .controls-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            background: white;
            padding: 1rem 1.5rem;
            border-radius: 0.75rem;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid transparent;
            white-space: nowrap;
        }

        .btn-primary {
            background-color: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background-color: var(--primary-dark);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
        }

        .btn-outline {
            background-color: white;
            border-color: var(--border-color);
            color: var(--text-main);
        }

        .btn-outline:hover {
            background-color: var(--bg-main);
            border-color: var(--primary-light);
            color: var(--primary);
        }

        .input {
            padding: 0.5rem 0.75rem;
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            font-size: 0.875rem;
            color: var(--text-main);
            background-color: white;
            transition: all 0.2s;
        }

        .input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }

        .card {
            background-color: var(--bg-card);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--border-color);
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: #1e293b;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .device-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.25rem;
        }
        
        .device-card {
            background: white;
            border-radius: 0.75rem;
            padding: 1.25rem;
            border: 1px solid var(--border-color);
            transition: all 0.3s ease;
            position: relative;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        
        .device-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow);
            border-color: var(--primary-light);
        }
        
        .device-card.alerting {
            border-color: var(--danger);
            background-color: #fff1f2;
            animation: alertPulse 2s infinite;
        }
        
        @keyframes alertPulse {
            0% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(244, 63, 94, 0); }
            100% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); }
        }
        
        .device-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .device-id {
            font-weight: 700;
            font-size: 1rem;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .status-badge {
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .status-online {
            background-color: #dcfce7;
            color: #15803d;
        }
        
        .status-offline {
            background-color: #fee2e2;
            color: #b91c1c;
        }
        
        .device-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.75rem;
        }
        
        .info-item {
            display: flex;
            flex-direction: column;
        }

        .info-item-full {
            grid-column: span 2;
        }
        
        .info-label {
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        
        .info-value {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-main);
        }

        .temp-val {
            font-size: 1.5rem;
            font-weight: 800;
            color: var(--primary);
            line-height: 1;
        }

        .device-config-btn {
            width: 100%;
            margin-top: 0.5rem;
            padding: 0.4rem;
            background: #f1f5f9;
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .device-config-btn:hover {
            background: #e2e8f0;
            border-color: #cbd5e1;
        }

        .filter-section {
            margin-top: 1.5rem;
            padding: 1rem;
            background: #f1f5f9;
            border-radius: 0.75rem;
        }

        .filter-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
        }

        .filter-item {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
        }

        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 1.5rem;
        }

        .temperature-chart {
            background: white;
            border-radius: 0.75rem;
            padding: 1.25rem;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-sm);
        }

        .chart-title {
            font-size: 0.9rem;
            font-weight: 700;
            margin-bottom: 1rem;
            color: #475569;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .chart-container {
            height: 250px;
            position: relative;
        }

        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .modal {
            background: white;
            border-radius: 1rem;
            width: 90%;
            max-width: 450px;
            box-shadow: var(--shadow-lg);
            overflow: hidden;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .modal-header {
            padding: 1.25rem;
            background: #f8fafc;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-body {
            padding: 1.5rem;
        }

        .modal-footer {
            padding: 1.25rem;
            border-top: 1px solid var(--border-color);
            display: flex;
            gap: 0.75rem;
        }

        .alert-modal {
            border: 2px solid var(--danger);
        }

        .alert-modal .modal-header {
            background: #fff1f2;
            color: var(--danger);
        }

        .alert-popup-device {
            background: #fef2f2;
            border: 1px solid #fecaca;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-top: 0.75rem;
        }

        .loading-spinner {
            grid-column: 1 / -1;
            padding: 4rem;
            text-align: center;
            color: var(--text-muted);
            font-weight: 500;
        }

        .hidden { display: none !important; }

        @media (max-width: 768px) {
            .container { padding: 1rem; }
            .chart-grid { grid-template-columns: 1fr; }
            .controls-bar { flex-direction: column; align-items: stretch; }
        }
    </style>
    <script src="/static/chart.umd.js"></script>
</head>
<body>
    <nav class="navbar">
        <div class="navbar-brand">
            <span style="font-size: 1.75rem;">⚡</span>
            <span>AE1 科电柜温度监控看板</span>
        </div>
        <div style="display: flex; align-items: center; gap: 1.25rem;">
            <div id="connectionStatus" class="status-badge status-online">● 服务器在线</div>
            <button class="btn btn-primary" onclick="loadDashboard()">
                <span>🔄</span> 立即刷新
            </button>
        </div>
    </nav>

    <div class="container">
        <div class="controls-bar">
            <div style="display: flex; align-items: center; gap: 1.5rem;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span class="info-label" style="font-weight: 700; color: var(--text-main);">自动刷新频率</span>
                    <input type="number" id="refreshInterval" class="input" style="width: 65px; text-align: center;" min="5" max="300" value="10" onchange="updateRefreshInterval()">
                    <span class="info-label">秒</span>
                </div>
                <div style="height: 20px; width: 1px; background: var(--border-color);"></div>
                <div id="lastUpdated" class="info-label" style="font-weight: 600;">最后更新: --:--:--</div>
            </div>
            <div>
                <!-- 预留次要操作区域 -->
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">
                    <span style="color: var(--primary);">📊</span>
                    实时设备状态
                </h2>
            </div>
            <div id="device-info-container" class="device-grid">
                <div class="loading-spinner">正在初始化设备...</div>
            </div>
            
            <div class="filter-section">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div class="info-label" style="font-weight: 700;">🔍 筛选显示图表的设备:</div>
                    <div class="filter-item" style="cursor: pointer; user-select: none;" onclick="toggleOfflineCharts()">
                        <input type="checkbox" id="showOfflineToggle" style="pointer-events: none;">
                        <label style="cursor: pointer; font-weight: 600;">显示离线设备图表</label>
                    </div>
                </div>
                <div id="device-filter-container" class="filter-grid" style="margin-top: 0.75rem;">
                    <!-- 复选框 -->
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">
                    <span style="color: var(--primary);">📈</span>
                    温度趋势分析
                </h2>
                <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="info-label">从</span>
                        <input type="datetime-local" id="startTime" class="input">
                    </div>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="info-label">至</span>
                        <input type="datetime-local" id="endTime" class="input">
                    </div>
                    <button class="btn btn-primary" style="padding: 0.4rem 0.8rem;" onclick="applyTimeFilter()">查询筛选</button>
                    <button class="btn btn-outline" style="padding: 0.4rem 0.8rem;" onclick="clearTimeFilter()">重置</button>
                </div>
            </div>
            <div id="temperature-charts-container" class="chart-grid">
                <div class="loading-spinner">正在准备数据可视化...</div>
            </div>
        </div>
    </div>
    
    <!-- Modal: Config -->
    <div id="configOverlay" class="modal-overlay hidden">
        <div id="configModal" class="modal">
            <div class="modal-header">
                <h3 class="card-title">⚙️ 报警参数配置</h3>
                <button class="btn btn-outline" style="padding: 4px 8px;" onclick="closeConfigModal()">✕</button>
            </div>
            <div class="modal-body">
                <div id="configModalDeviceId" style="margin-bottom: 1.5rem; color: var(--text-muted); font-weight: 600;"></div>
                
                <div style="margin-bottom: 1.25rem;">
                    <label class="info-label" style="display: block; margin-bottom: 0.5rem;">设备备注名称</label>
                    <input type="text" id="configDeviceAlias" class="input" style="width: 100%;" placeholder="例如: 1号主控柜">
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                    <div>
                        <label class="info-label" style="display: block; margin-bottom: 0.5rem;">温度阈值 (°C)</label>
                        <input type="number" id="configTempThreshold" class="input" style="width: 100%;" min="0" max="150" step="0.1">
                    </div>
                    <div>
                        <label class="info-label" style="display: block; margin-bottom: 0.5rem;">持续报警时长 (秒)</label>
                        <input type="number" id="configAlertDuration" class="input" style="width: 100%;" min="1" max="300">
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" style="flex: 1;" onclick="saveDeviceConfig()">保存设置</button>
                <button class="btn btn-outline" style="flex: 1;" onclick="closeConfigModal()">取消</button>
            </div>
        </div>
    </div>
    
    <!-- Modal: Alert -->
    <div id="alertOverlay" class="modal-overlay hidden">
        <div id="alertPopup" class="modal alert-modal">
            <div class="modal-header" style="border-bottom: none;">
                <h3 class="card-title" style="color: var(--danger); font-size: 1.5rem;">⚠️ 紧急温度警报</h3>
            </div>
            <div class="modal-body" id="alertContent">
                <!-- Alert content -->
            </div>
            <div class="modal-footer" style="border-top: none;">
                <button class="btn btn-primary" style="background: var(--danger); border: none; width: 100%;" onclick="closeAlert()">我已确认</button>
            </div>
        </div>
    </div>
    
    <script>
        let allDevices = [];
        let allTelemetryData = {};
        let selectedDevices = [];
        let showOfflineCharts = false; // 默认不显示离线设备图表
        let refreshIntervalId = null;
        let currentRefreshInterval = 10000; // 默认10秒
        
        // 报警相关变量
        let deviceConfigs = {}; // 每个设备的配置 {deviceId: {threshold: 50, duration: 10}}
        let deviceAlertStatus = {}; // 记录每个设备的报警状态 {deviceId: {startTime: timestamp, alerted: boolean}}
        let alertCheckInterval = null; // 报警检查定时器
        let currentConfigDeviceId = null; // 当前正在配置的设备ID
        
        // 从服务器加载设备配置
        async function loadDeviceConfigs() {
            try {
                const response = await fetch('/api/device_config');
                if (response.ok) {
                    const serverConfigs = await response.json();
                    // 合并服务器配置到本地
                    Object.keys(serverConfigs).forEach(deviceId => {
                        deviceConfigs[deviceId] = serverConfigs[deviceId];
                    });
                    console.log('设备配置已从服务器加载');
                }
            } catch (error) {
                console.error('加载设备配置失败:', error);
            }
        }
        
        // 保存单个设备配置到服务器
        async function saveDeviceConfigToServer(deviceId, config) {
            try {
                const response = await fetch(`/api/device_config/${deviceId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(config)
                });
                
                if (response.ok) {
                    console.log(`设备 ${deviceId} 配置已保存到服务器`);
                    return true;
                } else {
                    const errorData = await response.json();
                    console.error('保存配置失败:', errorData.error);
                    alert('保存配置失败: ' + (errorData.error || '未知错误'));
                    return false;
                }
            } catch (error) {
                console.error('保存配置请求失败:', error);
                alert('保存配置失败，请检查网络连接');
                return false;
            }
        }
        
        // 获取设备配置（如果不存在则使用默认值）
        function getDeviceConfig(deviceId) {
            if (!deviceConfigs[deviceId]) {
                deviceConfigs[deviceId] = {
                    threshold: 50,
                    duration: 10,
                    alias: ''  // 备注名
                };
            }
            return deviceConfigs[deviceId];
        }
        
        // 格式化设备显示名称
        function formatDeviceName(deviceId) {
            const config = getDeviceConfig(deviceId);
            if (config.alias && config.alias.trim() !== '') {
                return `${deviceId}(${config.alias})`;
            }
            return deviceId;
        }
        
        // 加载看板数据
        async function loadDashboard() {
            try {
                // 加载设备信息
                const deviceInfoResponse = await fetch('/api/device_status');
                if (!deviceInfoResponse.ok) {
                    const errorData = await deviceInfoResponse.json().catch(() => ({error: '未知错误'}));
                    throw new Error(`设备信息加载失败: ${errorData.error || deviceInfoResponse.statusText}`);
                }
                const deviceInfo = await deviceInfoResponse.json();
                
                // 验证返回的数据格式
                if (!Array.isArray(deviceInfo)) {
                    throw new Error('设备信息格式错误：期望数组');
                }
                
                allDevices = deviceInfo;
                
                // 初始化筛选列表（默认全选）
                if (selectedDevices.length === 0) {
                    selectedDevices = deviceInfo.map(d => d.device_id);
                }
                
                renderDeviceInfo(deviceInfo);
                renderDeviceFilter(deviceInfo);
                
                // 加载温度历史
                const tempHistoryResponse = await fetch('/api/telemetry_recent');
                if (!tempHistoryResponse.ok) {
                    const errorData = await tempHistoryResponse.json().catch(() => ({error: '未知错误'}));
                    throw new Error(`温度历史加载失败: ${errorData.error || tempHistoryResponse.statusText}`);
                }
                const tempHistory = await tempHistoryResponse.json();
                
                // 验证返回的数据格式
                if (typeof tempHistory !== 'object' || tempHistory === null) {
                    throw new Error('温度历史格式错误：期望对象');
                }
                
                allTelemetryData = tempHistory;
                
                renderTemperatureCharts(tempHistory);
                
                // 更新最后更新时间
                const now = new Date();
                document.getElementById('lastUpdated').textContent = `最后更新: ${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
                
                // 检查温度报警（数据更新后立即检查）
                checkTemperatureAlerts();
            } catch (error) {
                console.error('加载数据失败:', error);
                const errorMessage = error.message || '未知错误';
                document.getElementById('device-info-container').innerHTML = 
                    `<div class="loading-spinner" style="color: var(--danger);">❌ 连接失败<br><small>${errorMessage}</small></div>`;
                document.getElementById('temperature-charts-container').innerHTML = 
                    `<div class="loading-spinner" style="color: var(--danger);">❌ 连接失败<br><small>${errorMessage}</small></div>`;
            }
        }
        
        // 渲染设备信息
        function renderDeviceInfo(devices) {
            const container = document.getElementById('device-info-container');
            
            if (!devices || devices.length === 0) {
                container.innerHTML = '<div class="loading-spinner">暂无设备数据</div>';
                return;
            }
            
            container.innerHTML = devices.map(device => {
                const config = getDeviceConfig(device.device_id);
                const displayName = formatDeviceName(device.device_id);
                const isAlerting = deviceAlertStatus[device.device_id]?.alerted === true;
                const isOnline = device.status === 'online';
                const temp = (isOnline && device.current_temp !== null) ? device.current_temp.toFixed(1) : '--';
                
                return `
                <div class="device-card ${isAlerting ? 'alerting' : ''}">
                    <div class="device-card-header">
                        <div class="device-id">
                            <span style="font-size: 1.2rem;">🔌</span>
                            <span>${displayName}</span>
                        </div>
                        <span class="status-badge ${isOnline ? 'status-online' : 'status-offline'}">
                            ${isOnline ? '在线' : '离线'}
                        </span>
                    </div>

                    <div style="text-align: center; padding: 0.5rem 0;">
                        <div class="info-label" style="margin-bottom: 0.25rem;">当前实时温度</div>
                        <div class="temp-val">${temp}<small style="font-size: 0.8rem; margin-left: 2px;">°C</small></div>
                    </div>

                    <div class="device-info">
                        <div class="info-item">
                            <span class="info-label">固件版本</span>
                            <span class="info-value">${isOnline ? (device.fw_version || 'v1.0') : '--'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">IP 地址</span>
                            <span class="info-value">
                                ${isOnline ? `<a href="http://${device.ip}" target="_blank" style="color: var(--primary); text-decoration: none;">${device.ip}</a>` : '--'}
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">运行时间</span>
                            <span class="info-value">${isOnline ? formatUptime(device.uptime_sec) : '--'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">报警阈值</span>
                            <span class="info-value">${isOnline ? config.threshold + '°C' : '--'}</span>
                        </div>
                        <div class="info-item info-item-full">
                            <span class="info-label">最后通信时间</span>
                            <span class="info-value">${device.last_seen ? formatDateTime(device.last_seen) : '从未通信'}</span>
                        </div>
                    </div>

                    <button class="device-config-btn" onclick="openConfigModal('${device.device_id}')">
                        ⚙️ 配置报警参数
                    </button>
                </div>
            `;
            }).join('');
        }
        
        // 渲染设备筛选器
        function renderDeviceFilter(devices) {
            const container = document.getElementById('device-filter-container');
            
            if (!devices || devices.length === 0) {
                container.innerHTML = '<div class="loading">暂无设备数据</div>';
                return;
            }
            
            container.innerHTML = devices.map(device => {
                const displayName = formatDeviceName(device.device_id);
                return `
                <div class="filter-item">
                    <input 
                        type="checkbox" 
                        id="filter-${device.device_id}" 
                        value="${device.device_id}"
                        ${selectedDevices.includes(device.device_id) ? 'checked' : ''}
                        onchange="updateSelectedDevices()"
                    >
                    <label for="filter-${device.device_id}">${displayName}</label>
                </div>
            `;
            }).join('');
        }
        
        // 应用时间筛选
        function applyTimeFilter() {
            const startTime = document.getElementById('startTime').value;
            const endTime = document.getElementById('endTime').value;
            
            if (!startTime || !endTime) {
                alert('请选择开始时间和结束时间');
                return;
            }
            
            const startDate = new Date(startTime);
            const endDate = new Date(endTime);
            
            if (startDate >= endDate) {
                alert('开始时间必须早于结束时间');
                return;
            }
            
            // 筛选选中的设备数据
            const filteredData = {};
            selectedDevices.forEach(deviceId => {
                if (allTelemetryData[deviceId]) {
                    const deviceData = allTelemetryData[deviceId];
                    const filteredTemps = [];
                    const filteredTimestamps = [];
                    
                    // 根据时间范围筛选数据
                    if (deviceData.full_timestamps) {
                        for (let i = 0; i < deviceData.full_timestamps.length; i++) {
                            const dataTime = new Date(deviceData.full_timestamps[i]);
                            if (dataTime >= startDate && dataTime <= endDate) {
                                filteredTemps.push(deviceData.temps[i]);
                                filteredTimestamps.push(deviceData.timestamps[i]);
                            }
                        }
                    } else {
                        // 如果没有完整时间戳，使用原始数据
                        filteredTemps.push(...deviceData.temps);
                        filteredTimestamps.push(...deviceData.timestamps);
                    }
                    
                    if (filteredTemps.length > 0) {
                        filteredData[deviceId] = {
                            temps: filteredTemps,
                            timestamps: filteredTimestamps
                        };
                    }
                }
            });
            
            renderTemperatureCharts(filteredData);
        }
        
        // 清除时间筛选
        function clearTimeFilter() {
            document.getElementById('startTime').value = '';
            document.getElementById('endTime').value = '';
            
            // 重新应用设备筛选
            const filteredData = {};
            selectedDevices.forEach(deviceId => {
                if (allTelemetryData[deviceId]) {
                    filteredData[deviceId] = allTelemetryData[deviceId];
                }
            });
            
            renderTemperatureCharts(filteredData);
        }
        
        // 更新选中的设备
        function updateSelectedDevices() {
            const checkboxes = document.querySelectorAll('#device-filter-container input[type="checkbox"]');
            selectedDevices = Array.from(checkboxes)
                .filter(cb => cb.checked)
                .map(cb => cb.value);
            
            // 重新渲染温度图表
            const filteredData = {};
            selectedDevices.forEach(deviceId => {
                if (allTelemetryData[deviceId]) {
                    filteredData[deviceId] = allTelemetryData[deviceId];
                }
            });
            
            renderTemperatureCharts(filteredData);
        }
        
        // 切换离线设备图表显示
        function toggleOfflineCharts() {
            showOfflineCharts = !showOfflineCharts;
            document.getElementById('showOfflineToggle').checked = showOfflineCharts;
            
            // 重新渲染温度图表
            const filteredData = {};
            selectedDevices.forEach(deviceId => {
                if (allTelemetryData[deviceId]) {
                    filteredData[deviceId] = allTelemetryData[deviceId];
                }
            });
            
            renderTemperatureCharts(filteredData);
        }
        
        // 渲染温度历史图表
        function renderTemperatureCharts(telemetryData) {
            const container = document.getElementById('temperature-charts-container');
            
            // 检查Chart.js是否已加载
            if (typeof Chart === 'undefined') {
                container.innerHTML = '<div class="loading-spinner">❌ Chart.js库加载失败<br><small>正在尝试重新加载...</small></div>';
                // 尝试重新加载Chart.js
                setTimeout(() => {
                    loadChartJS().then(() => {
                        renderTemperatureCharts(telemetryData);
                    }).catch(() => {
                        container.innerHTML = '<div class="loading-spinner">❌ Chart.js库加载失败，请检查本地文件或刷新页面</div>';
                    });
                }, 2000);
                return;
            }
            
            if (!telemetryData || Object.keys(telemetryData).length === 0) {
                container.innerHTML = '<div class="loading-spinner">暂无可显示的温度数据</div>';
                return;
            }
            
            // 清空现有图表
            const existingCharts = document.querySelectorAll('.temperature-chart');
            existingCharts.forEach(chart => chart.remove());
            
            container.innerHTML = '';
            
            // 为每个选中的设备创建图表
            Object.keys(telemetryData).forEach(deviceId => {
                const data = telemetryData[deviceId];
                
                // 检查设备是否在线
                const deviceStatus = allDevices.find(d => d.device_id === deviceId);
                const isOnline = deviceStatus && deviceStatus.status === 'online';
                
                // 过滤条件：有数据，且 (设备在线 或 用户选择显示离线图表)
                if (!data.temps || data.temps.length === 0 || (!isOnline && !showOfflineCharts)) {
                    return;
                }
                
                const chartDiv = document.createElement('div');
                chartDiv.className = 'temperature-chart';
                const displayName = formatDeviceName(deviceId);
                chartDiv.innerHTML = `
                    <div class="chart-title">🌡️ 设备 ${displayName} - 最近温度历史</div>
                    <div class="chart-container">
                        <canvas id="chart-${deviceId}"></canvas>
                    </div>
                `;
                container.appendChild(chartDiv);
                
                // 创建图表
                try {
                    const ctx = document.getElementById(`chart-${deviceId}`).getContext('2d');
                    new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: data.timestamps,
                            datasets: [{
                                label: '温度 (°C)',
                                data: data.temps,
                                borderColor: '#4f46e5',
                                backgroundColor: 'rgba(79, 70, 229, 0.05)',
                                borderWidth: 2.5,
                                fill: true,
                                tension: 0.4,
                                pointRadius: 2,
                                pointHoverRadius: 5,
                                pointBackgroundColor: '#4f46e5',
                                pointBorderColor: '#fff',
                                pointBorderWidth: 2
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            interaction: {
                                mode: 'index',
                                intersect: false,
                            },
                            plugins: {
                                legend: {
                                    display: false
                                },
                                tooltip: {
                                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                                    padding: 10,
                                    titleFont: { size: 12, weight: 'bold' },
                                    bodyFont: { size: 14 },
                                    displayColors: false,
                                    callbacks: {
                                        label: function(context) {
                                            return context.parsed.y.toFixed(2) + ' °C';
                                        }
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: false,
                                    grid: { color: '#f1f5f9' },
                                    ticks: {
                                        font: { size: 10 },
                                        callback: value => value + '°C'
                                    }
                                },
                                x: {
                                    grid: { display: false },
                                    ticks: {
                                        font: { size: 9 },
                                        maxRotation: 45,
                                        minRotation: 0,
                                        autoSkip: true,
                                        maxTicksLimit: 6
                                    }
                                }
                            }
                        }
                    });
                } catch (error) {
                    console.error(`创建设备 ${deviceId} 的图表失败:`, error);
                    chartDiv.innerHTML = `<div class="loading">❌ 图表加载失败: ${error.message}</div>`;
                }
            });
        }
        
        // 加载Chart.js库（已在页面头部从本地加载）
        function loadChartJS() {
            return new Promise((resolve, reject) => {
                // 检查Chart.js是否已加载
                if (typeof Chart !== 'undefined') {
                    console.log('Chart.js已从本地加载');
                    resolve();
                    return;
                }
                
                // 如果本地加载失败，尝试动态重新加载
                const script = document.createElement('script');
                script.src = '/static/chart.umd.js';
                script.onload = () => {
                    if (typeof Chart !== 'undefined') {
                        console.log('Chart.js动态加载成功');
                        resolve();
                    } else {
                        reject(new Error('Chart.js加载失败'));
                    }
                };
                script.onerror = () => {
                    reject(new Error('本地Chart.js文件加载失败'));
                };
                document.head.appendChild(script);
            });
        }
        
        // 格式化运行时间
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            
            if (hours > 0) {
                return `${hours}时${minutes}分${secs}秒`;
            } else if (minutes > 0) {
                return `${minutes}分${secs}秒`;
            } else {
                return `${secs}秒`;
            }
        }
        
        // 格式化日期时间
        function formatDateTime(dateTimeStr) {
            if (!dateTimeStr) return '未知';
            
            const date = new Date(dateTimeStr);
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');
            
            return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        }
        
        // 更新刷新频率
        function updateRefreshInterval() {
            const intervalInput = document.getElementById('refreshInterval');
            const seconds = parseInt(intervalInput.value);
            
            if (seconds >= 5 && seconds <= 300) {
                currentRefreshInterval = seconds * 1000;
                
                // 清除旧的定时器
                if (refreshIntervalId) {
                    clearInterval(refreshIntervalId);
                }
                
                // 设置新的定时器
                refreshIntervalId = setInterval(loadDashboard, currentRefreshInterval);
                
                console.log(`自动刷新间隔已设置为 ${seconds} 秒`);
            } else {
                alert('刷新间隔必须在5-300秒之间');
                intervalInput.value = Math.floor(currentRefreshInterval / 1000);
            }
        }
        
        // 打开配置弹窗
        function openConfigModal(deviceId) {
            currentConfigDeviceId = deviceId;
            const config = getDeviceConfig(deviceId);
            
            document.getElementById('configModalDeviceId').textContent = `设备 ID: ${deviceId}`;
            document.getElementById('configDeviceAlias').value = config.alias || '';
            document.getElementById('configTempThreshold').value = config.threshold;
            document.getElementById('configAlertDuration').value = config.duration;
            
            document.getElementById('configOverlay').classList.remove('hidden');
        }
        
        // 关闭配置弹窗
        function closeConfigModal() {
            document.getElementById('configOverlay').classList.add('hidden');
            currentConfigDeviceId = null;
        }
        
        // 保存设备配置
        async function saveDeviceConfig() {
            if (!currentConfigDeviceId) return;
            
            const alias = document.getElementById('configDeviceAlias').value.trim();
            const threshold = parseFloat(document.getElementById('configTempThreshold').value);
            const duration = parseInt(document.getElementById('configAlertDuration').value);
            
            if (isNaN(threshold) || threshold < 0 || threshold > 150) {
                alert('温度阈值必须在0-150°C之间');
                return;
            }
            
            if (isNaN(duration) || duration < 1 || duration > 300) {
                alert('持续时长必须在1-300秒之间');
                return;
            }
            
            const config = {
                threshold: threshold,
                duration: duration,
                alias: alias
            };
            
            // 保存到服务器
            const success = await saveDeviceConfigToServer(currentConfigDeviceId, config);
            
            if (success) {
                // 更新本地缓存
                deviceConfigs[currentConfigDeviceId] = config;
                
                // 重置该设备的报警状态
                if (deviceAlertStatus[currentConfigDeviceId]) {
                    delete deviceAlertStatus[currentConfigDeviceId];
                }
                
                // 刷新设备信息显示
                renderDeviceInfo(allDevices);
                
                // 刷新设备筛选器
                renderDeviceFilter(allDevices);
                
                closeConfigModal();
                
                const aliasText = alias ? `, 备注名: ${alias}` : '';
                const displayName = formatDeviceName(currentConfigDeviceId);
                console.log(`设备 ${displayName} 配置已更新: 温度阈值=${threshold}°C, 持续时长=${duration}秒${aliasText}`);
            }
        }
        
        // 检查温度报警
        function checkTemperatureAlerts() {
            const currentTime = Date.now();
            const alertingDevices = [];
            let needUpdateDisplay = false; // 标记是否需要更新显示
            
            // 遍历所有设备
            Object.keys(allTelemetryData).forEach(deviceId => {
                const deviceData = allTelemetryData[deviceId];
                
                if (!deviceData.temps || deviceData.temps.length === 0) {
                    return;
                }
                
                // 获取该设备的配置
                const config = getDeviceConfig(deviceId);
                const threshold = config.threshold;
                const duration = config.duration;
                
                // 获取最新温度（最后一条记录）
                const latestTemp = deviceData.temps[deviceData.temps.length - 1];
                
                // 记录之前的报警状态
                const wasAlerting = deviceAlertStatus[deviceId]?.alerted === true;
                
                if (latestTemp > threshold) {
                    // 温度超过阈值
                    if (!deviceAlertStatus[deviceId]) {
                        // 开始记录报警状态
                        deviceAlertStatus[deviceId] = {
                            startTime: currentTime,
                            alerted: false,
                            threshold: threshold,
                            duration: duration
                        };
                    } else {
                        // 检查是否已持续超过设定时长
                        const elapsed = (currentTime - deviceAlertStatus[deviceId].startTime) / 1000; // 转换为秒
                        
                        if (elapsed >= duration && !deviceAlertStatus[deviceId].alerted) {
                            // 触发报警
                            deviceAlertStatus[deviceId].alerted = true;
                            alertingDevices.push({
                                deviceId: deviceId,
                                temperature: latestTemp,
                                threshold: threshold,
                                duration: duration
                            });
                        }
                    }
                } else {
                    // 温度已降低，清除报警状态
                    if (deviceAlertStatus[deviceId]) {
                        delete deviceAlertStatus[deviceId];
                        // 如果之前是报警状态，现在需要更新显示以移除红色边框
                        if (wasAlerting) {
                            needUpdateDisplay = true;
                        }
                    }
                }
            });
            
            // 如果有设备需要报警，显示弹窗
            if (alertingDevices.length > 0) {
                showAlert(alertingDevices);
            } else if (needUpdateDisplay && allDevices.length > 0) {
                // 如果有设备从报警状态恢复，更新显示以移除红色边框
                renderDeviceInfo(allDevices);
            }
        }
        
        // 显示报警弹窗
        function showAlert(devices) {
            const alertContent = document.getElementById('alertContent');
            const alertOverlay = document.getElementById('alertOverlay');
            
            // 构建报警内容
            let content = `<p style="margin-bottom: 1rem;">以下设备温度已超过阈值并持续达到设定时长：</p>`;
            
            devices.forEach(device => {
                const displayName = formatDeviceName(device.deviceId);
                content += `
                    <div class="alert-popup-device">
                        <strong>${displayName}</strong><br>
                        <span style="color: var(--danger); font-size: 1.1rem; font-weight: 800;">
                            ${device.temperature.toFixed(2)}°C
                        </span>
                        <span style="color: var(--text-muted); font-size: 0.8rem; margin-left: 8px;">
                            (报警阈值: ${device.threshold}°C)
                        </span>
                    </div>
                `;
            });
            
            alertContent.innerHTML = content;
            alertOverlay.classList.remove('hidden');
            
            if (allDevices.length > 0) {
                setTimeout(() => {
                    renderDeviceInfo(allDevices);
                }, 100);
            }
            
            const deviceNames = devices.map(d => formatDeviceName(d.deviceId)).join(', ');
            console.warn(`温度警报触发！设备: ${deviceNames}`, devices);
            
            // 触发后端钉钉通知（异步，不阻塞前端弹窗）
            try {
                notifyDingtalk(devices);
            } catch (e) {
                console.error('调用钉钉通知失败:', e);
            }
        }
        
        // 关闭报警弹窗
        function closeAlert() {
            const alertOverlay = document.getElementById('alertOverlay');
            alertOverlay.classList.add('hidden');
        }

        // 调用后端接口，通知钉钉
        async function notifyDingtalk(devices) {
            if (!devices || devices.length === 0) {
                return;
            }

            try {
                const payload = {
                    devices: devices.map(d => {
                        const config = getDeviceConfig(d.deviceId);
                        return {
                            device_id: d.deviceId,
                            alias: config.alias || '',
                            temperature: d.temperature,
                            threshold: d.threshold,
                            duration: d.duration
                        };
                    })
                };

                const resp = await fetch('/api/notify_alert', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    console.error('后端钉钉通知接口返回错误:', resp.status, err);
                } else {
                    const data = await resp.json().catch(() => ({}));
                    if (!data.success) {
                        console.warn('钉钉通知接口响应未标记为 success:', data);
                    } else {
                        console.log('已通过后端触发钉钉温度报警通知。');
                    }
                }
            } catch (error) {
                console.error('调用 /api/notify_alert 接口异常:', error);
            }
        }
        
        // 启动报警监控
        function startAlertMonitoring() {
            // 清除旧的监控定时器
            if (alertCheckInterval) {
                clearInterval(alertCheckInterval);
            }
            
            // 每1秒检查一次报警状态
            alertCheckInterval = setInterval(checkTemperatureAlerts, 1000);
        }
        
        // 页面加载时加载数据
        document.addEventListener('DOMContentLoaded', function() {
            // 确保Chart.js加载完成后再加载数据
            if (typeof Chart === 'undefined') {
                loadChartJS().then(() => {
                    initializeDashboard();
                }).catch((error) => {
                    console.error('Chart.js加载失败:', error);
                    document.getElementById('temperature-charts-container').innerHTML = 
                        '<div class="loading">❌ Chart.js库加载失败，请检查 /static/chart.umd.js 文件是否存在</div>';
                    // 即使Chart.js加载失败，也尝试加载其他数据
                    initializeDashboard();
                });
            } else {
                initializeDashboard();
            }
        });
        
        // 初始化看板
        async function initializeDashboard() {
            // 从服务器加载设备配置
            await loadDeviceConfigs();
            
            loadDashboard();
            
            // 设置默认的刷新间隔
            refreshIntervalId = setInterval(loadDashboard, currentRefreshInterval);
            
            // 启动报警监控
            startAlertMonitoring();
        }
    </script>
</body>
</html>
    """
    return render_template_string(html_content)

@app.route("/api/device_status")
def api_device_status():
    """API: 获取设备状态列表（包含实时温度）"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 查询所有设备的最近状态
            cur.execute("""
                SELECT DISTINCT ON (device_id)
                    device_id,
                    fw_version,
                    ip,
                    uptime_sec,
                    status,
                    last_seen
                FROM device_status
                ORDER BY device_id, last_seen DESC
            """)
            
            rows = cur.fetchall()
            devices = []
            for row in rows:
                device_id = row[0]
                
                # 获取该设备的最新温度
                cur.execute("""
                    SELECT temp_c, timestamp
                    FROM telemetry
                    WHERE device_id = %s AND temp_c IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (device_id,))
                
                temp_row = cur.fetchone()
                current_temp = None
                if temp_row:
                    current_temp = float(temp_row[0])
                
                devices.append({
                    'device_id': device_id,
                    'fw_version': row[1],
                    'ip': str(row[2]),  # 确保IP转换为字符串
                    'uptime_sec': row[3],
                    'status': row[4],
                    'last_seen': row[5].isoformat() if row[5] else None,
                    'current_temp': current_temp  # 实时温度
                })
            
            return jsonify(devices)
            
    except Exception as e:
        logger.error(f"获取设备状态失败: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"关闭数据库连接失败: {close_error}")

@app.route("/api/telemetry_recent")
def api_telemetry_recent():
    """API: 获取每个设备最近50条温度数据"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 获取所有设备的ID
            cur.execute("""
                SELECT DISTINCT device_id 
                FROM telemetry
                ORDER BY device_id
            """)
            device_ids = [row[0] for row in cur.fetchall()]
            
            telemetry_data = {}
            
            # 为每个设备获取最近50条数据
            for device_id in device_ids:
                cur.execute("""
                    SELECT temp_c, timestamp
                    FROM telemetry
                    WHERE device_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 50
                """, (device_id,))
                
                rows = cur.fetchall()
                # 反转数据，使时间从早到晚
                rows.reverse()
                
                temps = []
                timestamps = []
                full_timestamps = []
                
                for row in rows:
                    if row[0] is not None:  # temp_c 不为 None
                        temps.append(float(row[0]))
                        # 格式化时间戳，包含年月日
                        ts = row[1]
                        timestamps.append(ts.strftime('%Y-%m-%d %H:%M:%S'))
                        # 保存完整的datetime用于时间筛选
                        full_timestamps.append(ts.isoformat())
                
                if len(temps) > 0:
                    telemetry_data[device_id] = {
                        'temps': temps,
                        'timestamps': timestamps,
                        'full_timestamps': full_timestamps
                    }
            
            return jsonify(telemetry_data)
            
    except Exception as e:
        logger.error(f"获取温度历史失败: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"关闭数据库连接失败: {close_error}")

@app.route("/api/device_config", methods=["GET"])
def api_get_device_config():
    """API: 获取所有设备的报警配置"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT device_id, alias, threshold, duration
                FROM device_config
            """)
            rows = cur.fetchall()
            
            configs = {}
            for row in rows:
                configs[row[0]] = {
                    'alias': row[1] or '',
                    'threshold': float(row[2]),
                    'duration': int(row[3])
                }
            
            return jsonify(configs)
            
    except Exception as e:
        logger.error(f"获取设备配置失败: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route("/api/device_config/<device_id>", methods=["POST"])
def api_save_device_config(device_id):
    """API: 保存单个设备的报警配置"""
    conn = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400
        
        alias = data.get('alias', '')
        threshold = float(data.get('threshold', 50.0))
        duration = int(data.get('duration', 10))
        
        # 验证参数
        if threshold < 0 or threshold > 150:
            return jsonify({'error': '温度阈值必须在0-150°C之间'}), 400
        if duration < 1 or duration > 300:
            return jsonify({'error': '持续时长必须在1-300秒之间'}), 400
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 使用 UPSERT 语法（INSERT ... ON CONFLICT）
            cur.execute("""
                INSERT INTO device_config (device_id, alias, threshold, duration, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (device_id) 
                DO UPDATE SET 
                    alias = EXCLUDED.alias,
                    threshold = EXCLUDED.threshold,
                    duration = EXCLUDED.duration,
                    updated_at = CURRENT_TIMESTAMP
            """, (device_id, alias, threshold, duration))
            conn.commit()
        
        logger.info(f"设备 {device_id} 配置已更新: 别名={alias}, 阈值={threshold}°C, 持续时长={duration}秒")
        return jsonify({'success': True, 'message': '配置保存成功'})
        
    except Exception as e:
        logger.error(f"保存设备配置失败: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/notify_alert", methods=["POST"])
def api_notify_alert():
    """
    API: 接收前端温度报警信息，并通过钉钉机器人推送到群里。

    期望请求体 JSON 示例:
    {
        "devices": [
            {
                "device_id": "AE1-01",
                "alias": "1号主控柜",
                "temperature": 78.5,
                "threshold": 60.0,
                "duration": 45
            }
        ]
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        devices = data.get("devices")

        if not isinstance(devices, list) or not devices:
            return jsonify({"error": "请求体中必须包含非空的 devices 列表"}), 400

        # 组装钉钉报警消息内容（多设备合并为一条消息）
        lines = ["【温度异常报警】检测到以下设备温度持续超过阈值："]
        for d in devices:
            device_id = d.get("device_id") or "未知设备"
            alias = d.get("alias") or ""
            temp = d.get("temperature")
            threshold = d.get("threshold")
            duration = d.get("duration")

            # 名称部分
            if alias:
                name = f"{device_id}({alias})"
            else:
                name = device_id

            detail_parts = []
            if isinstance(temp, (int, float)):
                detail_parts.append(f"当前 {temp:.2f}°C")
            if isinstance(threshold, (int, float)):
                detail_parts.append(f"阈值 {threshold:.2f}°C")
            if isinstance(duration, (int, float, int)):
                detail_parts.append(f"已持续 {int(duration)} 秒")

            detail = "，".join(detail_parts) if detail_parts else "具体数值未知"
            lines.append(f"- 设备 {name}: {detail}")

        content = "\n".join(lines)
        success = send_dingtalk_text(content)

        if not success:
            return jsonify({"error": "钉钉消息发送失败，请检查服务端日志和 DINGTALK 配置"}), 500

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"处理 /api/notify_alert 请求失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    """健康检查接口"""
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    logger.info(f"正在启动设备监控看板，端口: {PORT}")
    
    # 检查环境变量
    if not PG_URI:
        logger.error("❌ 环境变量 PG_URI 未设置")
        exit(1)
    
    # 初始化设备配置表
    init_device_config_table()
    
    logger.info(f"🚀 看板服务器启动成功，监听端口: {PORT}")
    logger.info(f"📍 访问地址: http://localhost:{PORT}")
    
    app.run(host="0.0.0.0", port=PORT, debug=False)