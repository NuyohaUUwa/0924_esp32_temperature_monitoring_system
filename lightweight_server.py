# 轻量级优化版Flask服务器
# 文件名: lightweight_server.py

import os
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
import json

import psycopg2
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 定义北京时区（UTC+8）
BEIJING_TZ = timezone(timedelta(hours=8))

# 配置
PG_URI = os.getenv("PG_URI")
API_KEY = os.getenv("API_KEY")
PORT = int(os.getenv("PORT", "5000"))

# 创建Flask应用
app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 禁用Flask的HTTP请求日志
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# 数据库连接池（轻量级）
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
        logger.info(f"初始化数据库连接池 - 连接数: {min_conn}")
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
    
    def get_stats(self):
        """获取连接池统计信息"""
        with self.lock:
            return {
                'pool_size': len(self.pool),
                'active_connections': self.stats['active_connections'],
                'connection_errors': self.stats['connection_errors']
            }
    
    def health_check(self):
        """检查连接池健康状态"""
        try:
            with self.lock:
                if not self.pool:
                    return {'status': 'warning', 'message': '连接池为空'}
                
                # 测试第一个连接
                test_conn = self.pool[0]
                with test_conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                
                return {
                    'status': 'healthy',
                    'pool_size': len(self.pool),
                    'active_connections': self.stats['active_connections']
                }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

# 简化的内存缓存
class MemoryCache:
    def __init__(self, max_size=100):
        self.cache = {}
        self.max_size = max_size
        self.lock = threading.Lock()
    
    def get(self, key):
        with self.lock:
            data = self.cache.get(key)
            if data and data['expires'] > time.time():
                return data['value']
            return None
    
    def set(self, key, value, ttl=300):
        with self.lock:
            if len(self.cache) >= self.max_size:
                # 删除最旧的条目
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            
            self.cache[key] = {
                'value': value,
                'expires': time.time() + ttl
            }
    
    def cleanup_expired(self):
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, data in self.cache.items()
                if data['expires'] < current_time
            ]
            for key in expired_keys:
                del self.cache[key]

# 简化的性能监控
class DatabasePerformanceMonitor:
    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.lock = threading.Lock()
    
    def record_operation(self, operation_type, duration, success=True):
        """记录数据库操作性能"""
        with self.lock:
            if success:
                self.success_count += 1
            else:
                self.error_count += 1
    
    def get_performance_stats(self):
        """获取性能统计"""
        with self.lock:
            total = self.success_count + self.error_count
            return {
                'total_operations': total,
                'successful_operations': self.success_count,
                'failed_operations': self.error_count,
                'success_rate': (self.success_count / total * 100) if total > 0 else 0
            }

# 简化的内存缓存（仅用于临时数据）
class SimpleMemoryCache:
    def __init__(self, max_size=100):
        self.cache = {}
        self.max_size = max_size
        self.lock = threading.Lock()
    
    def get(self, key):
        with self.lock:
            data = self.cache.get(key)
            if data and data['expires'] > time.time():
                return data['value']
            return None
    
    def set(self, key, value, ttl=300):
        with self.lock:
            if len(self.cache) >= self.max_size:
                # 删除最旧的条目
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            
            self.cache[key] = {
                'value': value,
                'expires': time.time() + ttl
            }
    
    def cleanup_expired(self):
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, data in self.cache.items()
                if data['expires'] < current_time
            ]
            for key in expired_keys:
                del self.cache[key]

# 全局对象
db_pool = SimpleConnectionPool(PG_URI)
memory_cache = SimpleMemoryCache()
performance_monitor = DatabasePerformanceMonitor()

# 后台任务
def background_tasks():
    """后台清理任务"""
    while True:
        try:
            # 清理过期缓存
            memory_cache.cleanup_expired()
            
            time.sleep(60)  # 每分钟执行一次
        except Exception as e:
            logger.error(f"Background task error: {e}")
            time.sleep(60)

# 启动后台任务
background_thread = threading.Thread(target=background_tasks, daemon=True)
background_thread.start()

# API路由
@app.route("/health")
def health():
    """健康检查接口"""
    # 检查数据库连接池状态
    db_pool_health = db_pool.health_check()
    db_pool_stats = db_pool.get_stats()
    
    return jsonify({
        "status": "ok",
        "time": datetime.now(BEIJING_TZ).isoformat(),
        "database": {
            "connection_pool": db_pool_health,
            "stats": db_pool_stats
        }
    })

@app.route("/api/telemetry", methods=["POST"])
def telemetry():
    """遥测数据接收接口"""
    # API Key验证
    if request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    
    # 数据验证
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "invalid JSON"}), 400
        
        required_fields = ["deviceId", "fwVersion", "ip", "uptimeSec", "tempC"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"error": "missing fields", "fields": missing_fields}), 400
        
        device_id = data["deviceId"]
        fw_version = data["fwVersion"]
        ip = data["ip"]
        uptime_sec = int(data["uptimeSec"])
        temp_c = float(data["tempC"]) if data["tempC"] is not None else None
        
        # 数据验证
        if temp_c is not None and (temp_c < -50 or temp_c > 100):
            return jsonify({"error": "invalid temperature"}), 400
        
    except (ValueError, TypeError) as e:
        logger.error(f"Data validation error: {e}")
        return jsonify({"error": "invalid data format"}), 400
    
    # 数据库操作
    conn = None
    try:
        # 获取数据库连接
        conn = db_pool.get_connection()
        
        with conn.cursor() as cur:
            # 执行插入操作
            cur.execute("""
                INSERT INTO telemetry (device_id, fw_version, ip, uptime_sec, temp_c)
                VALUES (%s, %s, %s, %s, %s)
            """, (device_id, fw_version, ip, uptime_sec, temp_c))
            
            # 获取插入的记录ID
            cur.execute("SELECT lastval()")
            record_id = cur.fetchone()[0]
        
        # 提交事务
        conn.commit()
        
        # 打印和记录温度信息
        if temp_c is not None:
            temp_info = f"设备 {device_id} 温度: {temp_c}°C (IP: {ip}, 运行时间: {uptime_sec}秒)"
            print(temp_info)  # 控制台打印
            logger.info(temp_info)  # 写入日志
        else:
            device_info = f"设备 {device_id} 数据上传成功 (IP: {ip}, 运行时间: {uptime_sec}秒, 无温度数据)"
            print(device_info)
            logger.info(device_info)
        
        # 记录性能监控数据
        performance_monitor.record_operation("telemetry_insert", 0, True)
        
        return jsonify({
            "ok": True, 
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "record_id": record_id
        })
        
    except Exception as e:
        logger.error(f"数据库操作失败 - 设备: {device_id}, 错误: {str(e)}")
        
        # 记录失败的性能监控数据
        performance_monitor.record_operation("telemetry_insert", 0, False)
        
        # 回滚事务（如果有连接）
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.error(f"事务回滚失败: {rollback_error}")
        
        return jsonify({
            "ok": False, 
            "error": "database error"
        }), 500
    finally:
        if conn:
            try:
                db_pool.return_connection(conn)
            except Exception as return_error:
                logger.error(f"归还连接失败: {return_error}")


@app.route("/api/database/status")
def get_database_status():
    """获取数据库状态和统计信息"""
    try:
        # 获取连接池状态
        pool_health = db_pool.health_check()
        pool_stats = db_pool.get_stats()
        
        # 获取性能监控统计
        performance_stats = performance_monitor.get_performance_stats()
        
        return jsonify({
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "connection_pool": {
                "health": pool_health,
                "statistics": pool_stats
            },
            "performance": performance_stats
        })
        
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        return jsonify({"error": "internal error"}), 500

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"内部服务器错误: {error}")
    return jsonify({"error": "internal server error"}), 500

@app.errorhandler(psycopg2.Error)
def database_error(error):
    """数据库错误处理"""
    logger.error(f"数据库错误: {error}")
    performance_monitor.record_operation("database_error", 0, False)
    return jsonify({"error": "database error"}), 500

def startup_self_check():
    """服务启动自检"""
    logger.info("=" * 50)
    logger.info("开始服务启动自检...")
    
    # 1. 检查环境变量
    logger.info("1. 检查环境变量...")
    if not PG_URI:
        logger.error("❌ 环境变量 PG_URI 未设置")
        return False
    else:
        logger.info("✅ 环境变量 PG_URI 已设置")
    
    if not API_KEY:
        logger.error("❌ 环境变量 API_KEY 未设置")
        return False
    else:
        logger.info("✅ 环境变量 API_KEY 已设置")
    
    logger.info(f"✅ 服务端口: {PORT}")
    
    # 2. 检查数据库连接
    logger.info("2. 检查数据库连接...")
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
    
    # 3. 检查连接池状态
    logger.info("3. 检查连接池状态...")
    pool_stats = db_pool.get_stats()
    logger.info(f"✅ 连接池状态 - 可用连接: {pool_stats['pool_size']}, 活跃连接: {pool_stats['active_connections']}")
    
    # 4. 检查内存缓存
    logger.info("4. 检查内存缓存...")
    try:
        memory_cache.set("test_key", "test_value", ttl=1)
        test_value = memory_cache.get("test_key")
        if test_value == "test_value":
            logger.info("✅ 内存缓存功能正常")
        else:
            logger.error("❌ 内存缓存功能异常")
            return False
    except Exception as e:
        logger.error(f"❌ 内存缓存测试失败: {e}")
        return False
    
    # 5. 检查性能监控
    logger.info("5. 检查性能监控...")
    try:
        performance_monitor.record_operation("test_operation", 0, True)
        perf_stats = performance_monitor.get_performance_stats()
        if perf_stats['total_operations'] >= 1:
            logger.info("✅ 性能监控功能正常")
        else:
            logger.error("❌ 性能监控功能异常")
            return False
    except Exception as e:
        logger.error(f"❌ 性能监控测试失败: {e}")
        return False
    
    logger.info("✅ 所有自检项目通过，服务准备就绪！")
    logger.info("=" * 50)
    return True

def startup_with_retry(max_retries=3, retry_delay=5):
    """带重试机制的服务启动自检"""
    for attempt in range(1, max_retries + 1):
        logger.info(f"🔄 第 {attempt} 次自检尝试...")
        
        if startup_self_check():
            logger.info(f"✅ 第 {attempt} 次自检成功！")
            return True
        else:
            if attempt < max_retries:
                logger.warning(f"⚠️ 第 {attempt} 次自检失败，{retry_delay}秒后重试...")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ 第 {attempt} 次自检失败，已达到最大重试次数")
    
    return False

if __name__ == "__main__":
    logger.info(f"正在启动轻量级服务器，端口: {PORT}")
    
    # 执行带重试机制的启动自检
    if startup_with_retry(max_retries=3, retry_delay=5):
        logger.info(f"🚀 服务器启动成功，监听端口: {PORT}")
        app.run(host="0.0.0.0", port=PORT, threaded=True, debug=False)
    else:
        logger.error("❌ 启动自检失败，已达到最大重试次数，服务无法启动")
        exit(1)
