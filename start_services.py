#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
服务启动脚本
一次性启动 dashboard.py、device_status_updater.py、lightweight_server.py 三个服务
"""

import subprocess
import sys
import signal
import os
import time
from pathlib import Path

# 在Windows上设置标准输出为UTF-8编码
if sys.platform == "win32":
    try:
        # 尝试设置控制台编码为UTF-8
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # 如果设置失败，继续使用默认编码

# 服务进程列表
processes = []

def signal_handler(sig, frame):
    """处理 Ctrl+C 信号，优雅地关闭所有服务"""
    print("\n\n收到停止信号，正在关闭所有服务...")
    for process in processes:
        if process.poll() is None:  # 进程仍在运行
            print(f"正在停止进程 PID {process.pid}...")
            process.terminate()
    
    # 等待进程结束
    for process in processes:
        try:
            process.wait(timeout=5)
            print(f"进程 PID {process.pid} 已停止")
        except subprocess.TimeoutExpired:
            print(f"进程 PID {process.pid} 未响应，强制终止...")
            process.kill()
            process.wait()
            print(f"进程 PID {process.pid} 已强制终止")
    
    print("所有服务已停止")
    sys.exit(0)

def start_service(script_name, description):
    """启动一个Python服务"""
    print(f"\n{'='*60}")
    print(f"正在启动: {description}")
    print(f"脚本文件: {script_name}")
    print(f"{'='*60}")
    
    try:
        # 获取脚本的完整路径
        script_path = Path(__file__).parent / script_name
        
        if not script_path.exists():
            print(f"❌ 错误: 找不到文件 {script_path}")
            return None
        
        # 启动进程
        # 使用无缓冲模式以确保输出能够实时显示
        # 明确指定UTF-8编码以避免Windows上的GBK编码问题
        process = subprocess.Popen(
            [sys.executable, "-u", str(script_path)],  # -u 参数启用无缓冲模式
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',  # 明确使用UTF-8编码
            errors='replace',  # 遇到无法解码的字符时替换而不是报错
            bufsize=0  # 无缓冲
        )
        
        processes.append(process)
        print(f"✅ {description} 已启动 (PID: {process.pid})")
        
        return process
    except Exception as e:
        print(f"❌ 启动 {description} 时出错: {e}")
        return None

def monitor_processes():
    """监控所有进程，输出它们的日志"""
    import threading
    
    def read_output(process, name):
        """读取进程输出"""
        if process and process.stdout:
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        try:
                            # 确保输出使用UTF-8编码
                            cleaned_line = line.rstrip()
                            print(f"[{name}] {cleaned_line}")
                        except UnicodeDecodeError:
                            # 如果仍有编码问题，尝试替换无法解码的字符
                            try:
                                cleaned_line = line.encode('utf-8', errors='replace').decode('utf-8', errors='replace').rstrip()
                                print(f"[{name}] {cleaned_line}")
                            except Exception:
                                # 最后的备用方案：直接打印原始字节
                                print(f"[{name}] [编码错误: 无法解码此行]")
                process.stdout.close()
            except Exception as e:
                print(f"[{name}] 读取输出时出错: {e}")
    
    # 为每个进程创建读取线程
    threads = []
    service_names = ["仪表板", "状态更新器", "轻量服务器"]
    
    for i, process in enumerate(processes):
        if process:
            thread = threading.Thread(
                target=read_output,
                args=(process, service_names[i]),
                daemon=True
            )
            thread.start()
            threads.append(thread)
    
    # 主线程等待所有进程结束
    while True:
        all_dead = True
        for i, process in enumerate(processes):
            if process and process.poll() is None:
                all_dead = False
            elif process and process.poll() is not None:
                print(f"\n⚠️  {service_names[i]} (PID: {process.pid}) 已退出，退出码: {process.returncode}")
        
        if all_dead:
            print("\n所有服务已停止")
            break
        
        time.sleep(1)

def main():
    """主函数"""
    print("="*60)
    print("ESP32 服务启动器")
    print("="*60)
    print("正在启动以下服务:")
    print("  1. dashboard.py - 设备监控看板")
    print("  2. device_status_updater.py - 设备状态更新器")
    print("  3. lightweight_server.py - 轻量级服务器")
    print("="*60)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动三个服务
    print("\n开始启动服务...\n")
    
    # 先启动状态更新器（后台服务）
    start_service("device_status_updater.py", "设备状态更新器")
    time.sleep(2)  # 等待状态更新器初始化
    
    # 再启动服务器（API服务）
    start_service("lightweight_server.py", "轻量级服务器")
    time.sleep(2)  # 等待服务器初始化
    
    # 最后启动仪表板（Web界面）
    start_service("dashboard.py", "设备监控看板")
    
    # 检查是否所有服务都成功启动
    failed = [i for i, p in enumerate(processes) if p is None]
    if failed:
        print(f"\n❌ 有 {len(failed)} 个服务启动失败")
        signal_handler(None, None)
        return
    
    print("\n" + "="*60)
    print("✅ 所有服务已成功启动！")
    print("="*60)
    print("\n按 Ctrl+C 停止所有服务\n")
    
    # 监控进程并输出日志
    try:
        monitor_processes()
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()

