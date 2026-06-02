#!/usr/bin/env python3
import serial
import serial.tools.list_ports
import sys
import json
import time
import os
from pathlib import Path

# --- 配置区域 ---
SERIAL_BAUD = 115200
ESP_VID = "10C4"              # CP210x 的 VID
ESP_PID = "EA60"              # CP210x 的 PID
SIMULATE = False              # 设置为 True 时只写日志，不实际发送串口命令

# 日志文件路径（模拟模式用）
LOG_FILE = Path(__file__).parent / "hook_log.txt"

# 事件→状态映射文件（修改颜色映射只需改此 JSON，不动代码）
HOOK_MAPPING_FILE = Path(__file__).parent / "hook_mapping.json"

# ----------------------------------
# 防抖：PreToolUse 高频触发时的最小发送间隔（秒）
_DEBOUNCE_INTERVAL = 0.5
_last_send_time = 0
# 会话活跃标志文件（Stop 后忽略 Notification）
_SESSION_FLAG = Path(__file__).resolve().parent.parent / "debug_tools" / "session_active.flag"
# ----------------------------------

def find_esp8266_port():
    """自动查找连接的 ESP8266 端口（Windows/Linux/macOS）"""
    ports = serial.tools.list_ports.comports()
    
    # 方法1：根据 VID/PID 精确匹配
    if ESP_VID and ESP_PID:
        for port in ports:
            if port.vid and port.pid:
                if (port.vid == int(ESP_VID, 16) and 
                    port.pid == int(ESP_PID, 16)):
                    print(f"[INFO] Found ESP8266 by VID/PID: {port.device}", file=sys.stderr)
                    return port.device
    
    # 方法2：根据描述关键字匹配
    for port in ports:
        desc = port.description.lower()
        if any(keyword in desc for keyword in ['ch340', 'cp210', 'usb serial', 'uart']):
            print(f"[INFO] Found ESP8266 by description: {port.device} ({port.description})", file=sys.stderr)
            return port.device
    
    # 方法3：Windows 环境下尝试常见 COM 口（3-10）
    for i in range(3, 11):
        candidate = f"COM{i}"
        try:
            # 尝试打开端口，如果能打开说明存在且可用
            s = serial.Serial(candidate, timeout=0.1)
            s.close()
            print(f"[INFO] Found candidate port: {candidate}", file=sys.stderr)
            return candidate
        except (serial.SerialException, FileNotFoundError):
            continue
    
    # 方法4：Linux/macOS 下的回退
    fallback = "/dev/ttyUSB0"
    if sys.platform.startswith('linux') or sys.platform == 'darwin':
        print(f"[WARN] No ESP8266 found, using fallback {fallback}", file=sys.stderr)
        return fallback
    else:
        # Windows 回退为 COM3（假设存在）
        print(f"[WARN] No ESP8266 found, using fallback COM3", file=sys.stderr)
        return "COM3"

def send_serial_command(state):
    """通过串口向 ESP8266 发送 JSON 命令"""
    if SIMULATE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {state}\n")
            return True
        except Exception:
            return False

    port = find_esp8266_port()

    try:
        with serial.Serial(port, SERIAL_BAUD, timeout=2) as ser:
            ser.write((json.dumps({"state": state}) + "\n").encode("utf-8"))
            time.sleep(0.1)
            while ser.in_waiting:
                ser.readline()  # 读回 Arduino 响应，确保数据已处理
        return True
    except Exception:
        return False

def load_hook_mapping():
    """加载事件→状态映射文件"""
    try:
        with open(HOOK_MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[WARN] {HOOK_MAPPING_FILE} not found, using defaults", file=sys.stderr)
        return {}
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid mapping JSON: {e}", file=sys.stderr)
        return {}


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return

        event_data = json.loads(input_data)
        event_type = event_data.get("hook_event_name", "")

        # 从映射文件读取状态
        mapping = load_hook_mapping()
        state = mapping.get(event_type)
        _log = r"D:\claude-traffic-light-control\debug_tools\hook_debug.log"
        lines = []
        try:
            with open(_log, "r", encoding="utf-8") as _f:
                lines = _f.readlines()
        except FileNotFoundError:
            pass
        lines.append(f"{time.strftime('%H:%M:%S')} | {event_type} → {state}\n")
        with open(_log, "w", encoding="utf-8") as _f:
            _f.writelines(lines[-20:])

        # 事件处理
        if event_type == "PreToolUse":
            _SESSION_FLAG.write_text("1")  # 标记会话活跃
            global _last_send_time
            now = time.time()
            if now - _last_send_time >= _DEBOUNCE_INTERVAL:
                if state:
                    send_serial_command(state)
                _last_send_time = now
            print(json.dumps({"continue": True}))

        elif event_type == "UserPromptSubmit":
            _SESSION_FLAG.write_text("1")
            if state:
                send_serial_command(state)

        elif event_type == "PermissionRequest":
            if state:
                send_serial_command(state)
            print(json.dumps({"continue": True}))

        elif event_type == "Notification":
            # 只在会话活跃时响应（Stop 后忽略）
            if state and _SESSION_FLAG.exists():
                send_serial_command(state)

        elif event_type == "Stop":
            if state:
                send_serial_command(state)
            _SESSION_FLAG.unlink(missing_ok=True)

    except json.JSONDecodeError:
        pass  # 忽略非 JSON 输入
    except Exception as e:
        print(f"[ERROR] Hook error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()