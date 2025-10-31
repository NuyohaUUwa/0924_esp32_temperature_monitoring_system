# 设备状态更新程序
# 文件名: device_status_updater.py

import os
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
import json
import subprocess
import platform

import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 定义北京时区（UTC+8）
BEIJING_TZ = timezone(timedelta(hours=8))

# 配置
PG_URI = os.getenv("PG_URI")
UPDATE_INTERVAL = int(os.getenv("DEVICE_STATUS_UPDATE_INTERVAL", "30"))  # 更新间隔（秒）
OFFLINE_THRESHOLD = int(os.getenv("DEVICE_OFFLINE_THRESHOLD", "300"))  # 离线阈值（秒）

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('device_status_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 禁用psycopg2的详细日志
logging.getLogger('psycopg2').setLevel(logging.WARNING)

# 数据库连接池
class SimpleConnectionPool:
    def __init__(self, uri, min_conn=2, max_conn=5):
        self.uri = uri
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.pool = []
        self.lock = threading.Lock()
        self.stats = {
            'active_connections': 0,
            'connection_errors': 0
        }
        
        # 初始化连接池
        logger.info(f"初始化设备状态更新器连接池 - 连接数: {min_conn}")
        for i in range(min_conn):
            try:
                conn = psycopg2.connect(uri)
                self.pool.append(conn)
            except Exception as e:
                logger.error(f"连接池初始化失败: {e}")
                self.stats['connection_errors'] += 1
        
        logger.info(f"连接池初始化完成 - 可用连接: {len(self.pool)}")
    
    def get_connection(self):
        with self.lock:
            if self.pool:
                conn = self.pool.pop()
                self.stats['active_connections'] += 1
                return conn
            else:
                try:
                    conn = psycopg2.connect(self.uri)
                    self.stats['active_connections'] += 1
                    return conn
                except Exception as e:
                    self.stats['connection_errors'] += 1
                    logger.error(f"创建数据库连接失败: {e}")
                    raise
    
    def return_connection(self, conn):
        with self.lock:
            try:
                if len(self.pool) < self.max_conn:
                    self.pool.append(conn)
                else:
                    conn.close()
                self.stats['active_connections'] -= 1
            except Exception as e:
                logger.error(f"归还连接失败: {e}")
                self.stats['connection_errors'] += 1

# 全局连接池
db_pool = SimpleConnectionPool(PG_URI)

def ping_host(ip):
    """
    使用ping命令检查主机是否在线
    返回: (is_online, response_time)
    """
    try:
        # 根据操作系统选择不同的ping命令参数
        system = platform.system().lower()
        if system == 'windows':
            cmd = ['ping', '-n', '1', '-w', '1000', ip]
        else:
            cmd = ['ping', '-c', '1', '-W', '1', ip]
        
        # 执行ping命令
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2
        )
        
        # 检查ping是否成功
        if result.returncode == 0:
            return True, 0  # 在线
        else:
            return False, -1  # 离线或超时
            
    except subprocess.TimeoutExpired:
        return False, -1
    except Exception as e:
        logger.warning(f"ping {ip} 失败: {e}")
        return False, -1

def update_device_status():
    """更新设备状态表 - 使用ping方式判断设备是否在线"""
    conn = None
    try:
        conn = db_pool.get_connection()
        
        with conn.cursor() as cur:
            # 获取所有设备及其IP地址
            cur.execute("""
                SELECT device_id, ip, fw_version, uptime_sec, temp_c 
                FROM device_status
            """)
            
            devices = cur.fetchall()
            
            if not devices:
                logger.info("未找到任何设备记录")
                return
            
            # 记录状态变化
            online_count = 0
            offline_count = 0
            status_changes = 0
            
            # 对每个设备执行ping检查
            for device_id, ip, fw_version, uptime_sec, temp_c in devices:
                if not ip:
                    logger.warning(f"设备 {device_id} 没有IP地址，跳过ping检查")
                    continue
                
                # 执行ping检查
                is_online, response_time = ping_host(ip)
                
                # 获取当前状态
                cur.execute("""
                    SELECT status FROM device_status WHERE device_id = %s
                """, (device_id,))
                result = cur.fetchone()
                current_status = result[0] if result else 'unknown'
                
                # 更新状态
                new_status = 'online' if is_online else 'offline'
                # 使用北京时间（UTC+8）
                current_time = datetime.now(BEIJING_TZ)
                
                if new_status != current_status:
                    status_changes += 1
                    logger.info(f"设备 {device_id} ({ip}) 状态变更: {current_status} -> {new_status}")
                
                # 更新数据库
                if is_online:
                    online_count += 1
                    # 如果设备在线，更新last_seen
                    cur.execute("""
                        UPDATE device_status 
                        SET status = 'online', last_seen = %s, ip = %s
                        WHERE device_id = %s
                    """, (current_time, ip, device_id))
                else:
                    offline_count += 1
                    cur.execute("""
                        UPDATE device_status 
                        SET status = 'offline'
                        WHERE device_id = %s
                    """, (device_id,))
            
            conn.commit()
            
            logger.info(f"设备状态更新完成 - 在线设备: {online_count}, 离线设备: {offline_count}, 状态变更: {status_changes}")
        
    except Exception as e:
        logger.error(f"更新设备状态失败: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.error(f"事务回滚失败: {rollback_error}")
    finally:
        if conn:
            try:
                db_pool.return_connection(conn)
            except Exception as return_error:
                logger.error(f"归还连接失败: {return_error}")

def device_status_worker():
    """设备状态更新工作线程"""
    logger.info(f"设备状态更新器启动 - 更新间隔: {UPDATE_INTERVAL}秒 (使用ping方式检测)")
    
    while True:
        try:
            update_device_status()
            time.sleep(UPDATE_INTERVAL)
        except Exception as e:
            logger.error(f"设备状态更新器错误: {e}")
            time.sleep(UPDATE_INTERVAL)

def startup_self_check():
    """启动自检"""
    logger.info("=" * 50)
    logger.info("开始设备状态更新器自检...")
    
    # 检查环境变量
    if not PG_URI:
        logger.error("❌ 环境变量 PG_URI 未设置")
        return False
    else:
        logger.info("✅ 环境变量 PG_URI 已设置")
    
    # 检查数据库连接
    try:
        conn = db_pool.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            if result:
                logger.info("✅ 数据库连接正常")
            else:
                logger.error("❌ 数据库连接测试失败")
                return False
        db_pool.return_connection(conn)
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        return False
    
    # 检查表是否存在
    try:
        conn = db_pool.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'device_status'
                )
            """)
            table_exists = cur.fetchone()[0]
            if table_exists:
                logger.info("✅ device_status表存在")
            else:
                logger.error("❌ device_status表不存在")
                return False
        db_pool.return_connection(conn)
    except Exception as e:
        logger.error(f"❌ 检查表存在性失败: {e}")
        return False
    
    logger.info("✅ 设备状态更新器自检通过")
    logger.info("=" * 50)
    return True

if __name__ == "__main__":
    logger.info("正在启动设备状态更新器...")
    
    # 执行启动自检
    if startup_self_check():
        logger.info("🚀 设备状态更新器启动成功")
        
        # 启动设备状态更新线程
        status_thread = threading.Thread(target=device_status_worker, daemon=True)
        status_thread.start()
        
        # 主线程保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭设备状态更新器...")
    else:
        logger.error("❌ 设备状态更新器自检失败，无法启动")
        exit(1)
