#ifndef PINS_CONFIG_H
#define PINS_CONFIG_H

// 根据实际接线修改引脚号
#define PIN_RED     D1   // 红灯 GPIO5  (NodeMCU D1)
#define PIN_YELLOW  D2   // 黄灯 GPIO4  (NodeMCU D2)
#define PIN_GREEN   D7   // 绿灯 GPIO13 (NodeMCU D7) — 避开 GPIO0 启动脚

// 可选：内置 LED (ESP-12 系列通常为 GPIO2，用于调试)
#define PIN_BUILTIN_LED D4

#endif