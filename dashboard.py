# 设备监控看板
# 文件名: dashboard.py

import os
import logging
import psycopg2
from flask import Flask, render_template_string, jsonify
from dotenv import load_dotenv

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
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .header h1 {
            color: #333;
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #666;
            font-size: 0.9em;
        }
        
        .controls {
            background: rgba(255, 255, 255, 0.95);
            padding: 15px 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .control-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .control-group label {
            font-weight: 600;
            color: #333;
            font-size: 0.9em;
        }
        
        .control-group input[type="number"] {
            padding: 8px 12px;
            border: 2px solid #667eea;
            border-radius: 8px;
            font-size: 0.9em;
            width: 80px;
        }
        
        .control-group input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        
        .control-group input[type="datetime-local"] {
            padding: 8px 12px;
            border: 2px solid #667eea;
            border-radius: 8px;
            font-size: 0.9em;
        }
        
        .control-group button {
            padding: 8px 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 600;
            transition: transform 0.2s ease;
        }
        
        .control-group button:hover {
            transform: scale(1.05);
        }
        
        .control-group button:active {
            transform: scale(0.98);
        }
        
        .time-filter-section {
            background: rgba(230, 230, 250, 0.3);
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .time-filter-title {
            font-size: 1em;
            font-weight: 600;
            color: #333;
            margin-bottom: 10px;
        }
        
        .time-filter-controls {
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .section {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .section-title {
            font-size: 1.5em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        
        .device-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .device-card {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 3px solid transparent;
            transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
        }
        
        .device-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }
        
        .device-card.alerting {
            border-color: #ef4444;
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
            animation: alertBorderPulse 2s infinite;
            /* 确保背景色不变 */
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        }
        
        .device-card.alerting:hover {
            box-shadow: 0 4px 16px rgba(239, 68, 68, 0.5);
            /* 悬停时背景色也不变 */
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        }
        
        @keyframes alertBorderPulse {
            0%, 100% {
                border-color: #ef4444;
                box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
            }
            50% {
                border-color: #dc2626;
                box-shadow: 0 2px 12px rgba(239, 68, 68, 0.5);
            }
        }
        
        .device-id {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
            word-break: break-all;
        }
        
        .device-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .info-item {
            display: flex;
            flex-direction: column;
        }
        
        .info-label {
            font-size: 0.8em;
            color: #666;
            margin-bottom: 5px;
        }
        
        .info-value {
            font-size: 1em;
            font-weight: 600;
            color: #333;
        }
        
        .info-value a {
            color: #667eea;
            text-decoration: none;
            transition: color 0.2s ease;
        }
        
        .info-value a:hover {
            color: #764ba2;
            text-decoration: underline;
        }
        
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
        }
        
        .status-online {
            background: #10b981;
            color: white;
        }
        
        .status-offline {
            background: #ef4444;
            color: white;
        }
        
        .device-filter {
            background: rgba(245, 247, 250, 0.8);
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .filter-header {
            font-size: 1em;
            font-weight: 600;
            color: #333;
            margin-bottom: 10px;
        }
        
        .filter-checkboxes {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .filter-item {
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 5px 10px;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.2s ease;
        }
        
        .filter-item:hover {
            background: #e0e7ff;
        }
        
        .filter-item input[type="checkbox"] {
            cursor: pointer;
        }
        
        .refresh-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease;
        }
        
        .refresh-btn:hover {
            transform: scale(1.05);
        }
        
        .refresh-btn:active {
            transform: scale(0.98);
        }
        
        .chart-container {
            position: relative;
            height: 400px;
            margin: 20px 0;
        }
        
        .chart-title {
            font-size: 1.1em;
            color: #333;
            margin-bottom: 10px;
            text-align: center;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .info-item-full {
            grid-column: 1 / -1;
        }
        
        .alert-settings {
            background: rgba(255, 248, 220, 0.9);
            border: 2px solid #ff9800;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .alert-settings-title {
            font-size: 1em;
            font-weight: 600;
            color: #e65100;
            margin-bottom: 10px;
        }
        
        .alert-popup {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
            color: white;
            padding: 30px 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            z-index: 10000;
            min-width: 400px;
            max-width: 600px;
            animation: alertPulse 2s infinite;
        }
        
        @keyframes alertPulse {
            0%, 100% {
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            }
            50% {
                box-shadow: 0 10px 50px rgba(255, 107, 107, 0.6);
            }
        }
        
        .alert-popup.hidden {
            display: none;
        }
        
        .alert-popup-title {
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 15px;
            text-align: center;
        }
        
        .alert-popup-content {
            font-size: 1.1em;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        
        .alert-popup-device {
            background: rgba(255, 255, 255, 0.2);
            padding: 10px;
            border-radius: 8px;
            margin: 5px 0;
        }
        
        .alert-popup-close {
            background: rgba(255, 255, 255, 0.3);
            color: white;
            border: 2px solid white;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            width: 100%;
            transition: background 0.3s ease;
        }
        
        .alert-popup-close:hover {
            background: rgba(255, 255, 255, 0.5);
        }
        
        .alert-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 9999;
        }
        
        .alert-overlay.hidden {
            display: none;
        }
        
        .alert-icon {
            font-size: 3em;
            text-align: center;
            margin-bottom: 15px;
        }
        
        .device-config-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
            font-weight: 600;
            margin-top: 10px;
            width: 100%;
            transition: transform 0.2s ease;
        }
        
        .device-config-btn:hover {
            transform: scale(1.02);
        }
        
        .config-modal {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            z-index: 10001;
            min-width: 400px;
            max-width: 500px;
        }
        
        .config-modal.hidden {
            display: none;
        }
        
        .config-modal-title {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .config-form-group {
            margin-bottom: 20px;
        }
        
        .config-form-group label {
            display: block;
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
        }
        
        .config-form-group input {
            width: 100%;
            padding: 10px;
            border: 2px solid #667eea;
            border-radius: 8px;
            font-size: 1em;
        }
        
        .config-modal-buttons {
            display: flex;
            gap: 10px;
            margin-top: 25px;
        }
        
        .config-modal-btn {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        
        .config-modal-btn-save {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .config-modal-btn-cancel {
            background: #e0e0e0;
            color: #333;
        }
        
        .config-modal-btn:hover {
            transform: scale(1.02);
        }
        
        .config-info {
            font-size: 0.85em;
            color: #666;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 设备监控看板</h1>
            <p>实时监控设备状态和温度历史</p>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <button class="refresh-btn" onclick="loadDashboard()">🔄 刷新数据</button>
            </div>
            <div class="control-group">
                <label for="refreshInterval">自动刷新(秒):</label>
                <input type="number" id="refreshInterval" min="5" max="300" value="10" onchange="updateRefreshInterval()">
            </div>
        </div>
        
        <!-- 设备信息部分 -->
        <div class="section">
            <h2 class="section-title">📱 设备信息 (device_info)</h2>
            <div id="device-info-container" class="device-grid">
                <div class="loading">正在加载设备信息...</div>
            </div>
            <div class="device-filter">
                <div class="filter-header">🔍 筛选温度图表设备:</div>
                <div id="device-filter-container" class="filter-checkboxes">
                    <div class="loading">正在加载设备列表...</div>
                </div>
            </div>
        </div>
        
        <!-- 温度历史部分 -->
        <div class="section">
            <h2 class="section-title">🌡️ 温度历史 (his_temperature)</h2>
            <div class="time-filter-section">
                <div class="time-filter-title">⏰ 时间筛选:</div>
                <div class="time-filter-controls">
                    <div class="control-group">
                        <label for="startTime">开始时间:</label>
                        <input type="datetime-local" id="startTime">
                    </div>
                    <div class="control-group">
                        <label for="endTime">结束时间:</label>
                        <input type="datetime-local" id="endTime">
                    </div>
                    <div class="control-group">
                        <button onclick="applyTimeFilter()">应用筛选</button>
                    </div>
                    <div class="control-group">
                        <button onclick="clearTimeFilter()">清除筛选</button>
                    </div>
                </div>
            </div>
            <div id="temperature-charts-container">
                <div class="loading">正在加载温度数据...</div>
            </div>
        </div>
    </div>
    
    <!-- 设备配置弹窗 -->
    <div id="configOverlay" class="alert-overlay hidden" onclick="closeConfigModal()"></div>
    <div id="configModal" class="config-modal hidden">
        <div class="config-modal-title">⚙️ 设备报警配置</div>
        <div id="configModalDeviceId" style="text-align: center; color: #666; margin-bottom: 20px; font-size: 1.1em;"></div>
        <div class="config-form-group">
            <label for="configDeviceAlias">设备备注名:</label>
            <input type="text" id="configDeviceAlias" maxlength="50" placeholder="例如: 1号、A区设备等">
            <div class="config-info">为设备设置一个易于识别的备注名，将在显示中使用</div>
        </div>
        <div class="config-form-group">
            <label for="configTempThreshold">温度阈值 (°C):</label>
            <input type="number" id="configTempThreshold" min="0" max="150" step="0.1" value="50">
            <div class="config-info">当设备温度超过此值时开始计时</div>
        </div>
        <div class="config-form-group">
            <label for="configAlertDuration">持续时长 (秒):</label>
            <input type="number" id="configAlertDuration" min="1" max="300" value="10">
            <div class="config-info">温度超过阈值后持续此时长将触发报警</div>
        </div>
        <div class="config-modal-buttons">
            <button class="config-modal-btn config-modal-btn-save" onclick="saveDeviceConfig()">保存配置</button>
            <button class="config-modal-btn config-modal-btn-cancel" onclick="closeConfigModal()">取消</button>
        </div>
    </div>
    
    <!-- 报警弹窗 -->
    <div id="alertOverlay" class="alert-overlay hidden" onclick="closeAlert()"></div>
    <div id="alertPopup" class="alert-popup hidden">
        <div class="alert-icon">🔥</div>
        <div class="alert-popup-title">⚠️ 温度过高报警</div>
        <div class="alert-popup-content" id="alertContent">
            <!-- 报警内容将动态填充 -->
        </div>
        <button class="alert-popup-close" onclick="closeAlert()">确认</button>
    </div>
    
    <script>
        let allDevices = [];
        let allTelemetryData = {};
        let selectedDevices = [];
        let refreshIntervalId = null;
        let currentRefreshInterval = 10000; // 默认10秒
        
        // 报警相关变量
        let deviceConfigs = {}; // 每个设备的配置 {deviceId: {threshold: 50, duration: 10}}
        let deviceAlertStatus = {}; // 记录每个设备的报警状态 {deviceId: {startTime: timestamp, alerted: boolean}}
        let alertCheckInterval = null; // 报警检查定时器
        let currentConfigDeviceId = null; // 当前正在配置的设备ID
        
        // 从localStorage加载设备配置
        function loadDeviceConfigs() {
            const saved = localStorage.getItem('deviceAlertConfigs');
            if (saved) {
                deviceConfigs = JSON.parse(saved);
                // 确保旧数据兼容性：为没有alias字段的配置添加默认值
                Object.keys(deviceConfigs).forEach(deviceId => {
                    if (!deviceConfigs[deviceId].hasOwnProperty('alias')) {
                        deviceConfigs[deviceId].alias = '';
                    }
                });
            }
        }
        
        // 保存设备配置到localStorage
        function saveDeviceConfigs() {
            localStorage.setItem('deviceAlertConfigs', JSON.stringify(deviceConfigs));
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
                
                // 检查温度报警（数据更新后立即检查）
                checkTemperatureAlerts();
            } catch (error) {
                console.error('加载数据失败:', error);
                const errorMessage = error.message || '未知错误';
                document.getElementById('device-info-container').innerHTML = 
                    `<div class="loading">❌ 加载失败，请检查服务器连接<br><small>${errorMessage}</small></div>`;
                document.getElementById('temperature-charts-container').innerHTML = 
                    `<div class="loading">❌ 加载失败，请检查服务器连接<br><small>${errorMessage}</small></div>`;
            }
        }
        
        // 渲染设备信息
        function renderDeviceInfo(devices) {
            const container = document.getElementById('device-info-container');
            
            if (!devices || devices.length === 0) {
                container.innerHTML = '<div class="loading">暂无设备数据</div>';
                return;
            }
            
            container.innerHTML = devices.map(device => {
                const config = getDeviceConfig(device.device_id);
                const displayName = formatDeviceName(device.device_id);
                
                // 检查设备是否处于报警状态
                const isAlerting = deviceAlertStatus[device.device_id]?.alerted === true;
                
                return `
                <div class="device-card ${isAlerting ? 'alerting' : ''}">
                    <div class="device-id">🔌 ${displayName}</div>
                    <div class="device-info">
                        <div class="info-item">
                            <span class="info-label">固件版本</span>
                            <span class="info-value">${device.fw_version}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">IP地址</span>
                            <span class="info-value">
                                <a href="http://${device.ip}" target="_blank">${device.ip}</a>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">运行时间</span>
                            <span class="info-value">${formatUptime(device.uptime_sec)}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">状态</span>
                            <span class="status-badge ${device.status === 'online' ? 'status-online' : 'status-offline'}">
                                ${device.status === 'online' ? '🟢 在线' : '🔴 离线'}
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">实时温度</span>
                            <span class="info-value" style="font-size: 1.1em; font-weight: bold; color: ${device.status === 'online' && device.current_temp !== null && device.current_temp !== undefined ? '#667eea' : '#999'}">
                                ${device.status === 'online' && device.current_temp !== null && device.current_temp !== undefined ? device.current_temp.toFixed(2) + '°C' : '--'}
                            </span>
                        </div>
                        <div class="info-item info-item-full">
                            <span class="info-label">最后更新</span>
                            <span class="info-value">${device.last_seen ? formatDateTime(device.last_seen) : '未知'}</span>
                        </div>
                        <div class="info-item info-item-full">
                            <span class="info-label">报警配置</span>
                            <span class="info-value" style="font-size: 0.9em;">
                                阈值: ${config.threshold}°C | 时长: ${config.duration}秒
                            </span>
                        </div>
                        <div class="info-item info-item-full">
                            <button class="device-config-btn" onclick="openConfigModal('${device.device_id}')">⚙️ 配置</button>
                        </div>
                    </div>
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
        
        // 渲染温度历史图表
        function renderTemperatureCharts(telemetryData) {
            const container = document.getElementById('temperature-charts-container');
            
            if (!telemetryData || Object.keys(telemetryData).length === 0) {
                container.innerHTML = '<div class="loading">暂无可显示的温度数据</div>';
                return;
            }
            
            // 清空现有图表
            const existingCharts = document.querySelectorAll('.temperature-chart');
            existingCharts.forEach(chart => chart.remove());
            
            container.innerHTML = '';
            
            // 为每个选中的设备创建图表
            Object.keys(telemetryData).forEach(deviceId => {
                const data = telemetryData[deviceId];
                
                // 跳过没有数据的设备
                if (!data.temps || data.temps.length === 0) {
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
                const ctx = document.getElementById(`chart-${deviceId}`).getContext('2d');
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.timestamps,
                        datasets: [{
                            label: '温度 (°C)',
                            data: data.temps,
                            borderColor: '#667eea',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointRadius: 3,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: false,
                                title: {
                                    display: true,
                                    text: '温度 (°C)'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: '时间'
                                }
                            }
                        }
                    }
                });
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
            
            document.getElementById('configModalDeviceId').textContent = `设备: ${deviceId}`;
            document.getElementById('configDeviceAlias').value = config.alias || '';
            document.getElementById('configTempThreshold').value = config.threshold;
            document.getElementById('configAlertDuration').value = config.duration;
            
            document.getElementById('configModal').classList.remove('hidden');
            document.getElementById('configOverlay').classList.remove('hidden');
        }
        
        // 关闭配置弹窗
        function closeConfigModal() {
            document.getElementById('configModal').classList.add('hidden');
            document.getElementById('configOverlay').classList.add('hidden');
            currentConfigDeviceId = null;
        }
        
        // 保存设备配置
        function saveDeviceConfig() {
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
            
            deviceConfigs[currentConfigDeviceId] = {
                threshold: threshold,
                duration: duration,
                alias: alias
            };
            
            saveDeviceConfigs();
            
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
            const alertPopup = document.getElementById('alertPopup');
            const alertOverlay = document.getElementById('alertOverlay');
            
            // 构建报警内容
            let content = `<p>以下设备温度持续超过设定阈值已达设定时长：</p>`;
            
            devices.forEach(device => {
                const displayName = formatDeviceName(device.deviceId);
                content += `
                    <div class="alert-popup-device">
                        <strong>设备 ${displayName}</strong><br>
                        当前温度: <strong>${device.temperature.toFixed(2)}°C</strong><br>
                        阈值: <strong>${device.threshold}°C</strong> | 持续时长: <strong>${device.duration}秒</strong>
                    </div>
                `;
            });
            
            alertContent.innerHTML = content;
            
            // 显示弹窗
            alertPopup.classList.remove('hidden');
            alertOverlay.classList.remove('hidden');
            
            // 弹窗显示后，更新设备信息以显示红色边框（延迟执行，确保弹窗先显示）
            if (allDevices.length > 0) {
                setTimeout(() => {
                    renderDeviceInfo(allDevices);
                }, 100);
            }
            
            // 播放提示音（浏览器需要用户交互才能播放声音，这里仅显示）
            const deviceNames = devices.map(d => formatDeviceName(d.deviceId)).join(', ');
            console.warn(`温度报警触发！设备: ${deviceNames}`, devices);
        }
        
        // 关闭报警弹窗
        function closeAlert() {
            const alertPopup = document.getElementById('alertPopup');
            const alertOverlay = document.getElementById('alertOverlay');
            
            alertPopup.classList.add('hidden');
            alertOverlay.classList.add('hidden');
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
            // 从localStorage加载设备配置
            loadDeviceConfigs();
            
            loadDashboard();
            
            // 设置默认的刷新间隔
            refreshIntervalId = setInterval(loadDashboard, currentRefreshInterval);
            
            // 启动报警监控
            startAlertMonitoring();
        });
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
                        # 格式化时间戳
                        ts = row[1]
                        timestamps.append(ts.strftime('%H:%M:%S'))
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
    
    logger.info(f"🚀 看板服务器启动成功，监听端口: {PORT}")
    logger.info(f"📍 访问地址: http://localhost:{PORT}")
    
    app.run(host="0.0.0.0", port=PORT, debug=False)