#!/usr/bin/env python3
import serial
import sys
import json
import time
from pathlib import Path

# 把 claude_hooks 加入模块搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "claude_hooks"))
from send_signal import find_esp8266_port  # 复用查找端口函数

def send_command(port, command):
    """发送单个 JSON 命令并读取返回"""
    with serial.Serial(port, 115200, timeout=2) as ser:
        ser.write((command + "\n").encode('utf-8'))
        time.sleep(0.1)
        # 读取ESP返回的调试信息
        while ser.in_waiting:
            line = ser.readline().decode('utf-8').strip()
            print(f"ESP: {line}")

VALID_STATES = {"THINKING", "WAITING_USER", "TASK_COMPLETE", "IDLE", "TASK_FAILED", "TOOL_ERROR"}

if __name__ == "__main__":
    port = find_esp8266_port()
    if len(sys.argv) > 1:
        state = sys.argv[1].upper()
        if state not in VALID_STATES:
            print(f"Error: Unknown state '{sys.argv[1]}'")
            print(f"Supported states: {', '.join(sorted(VALID_STATES))}")
            sys.exit(1)
        cmd = json.dumps({"state": state})
        print(f"Sending {cmd} to {port}")
        send_command(port, cmd)
    else:
        print("Usage: test_serial_command.py <STATE>")
        print("Example: test_serial_command.py THINKING")
        print(f"States: {', '.join(sorted(VALID_STATES))}")