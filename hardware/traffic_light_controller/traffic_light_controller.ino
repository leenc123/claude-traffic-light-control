#include <ArduinoJson.h>  // JSON 解析库，需通过 Arduino 库管理器安装
#include <EEPROM.h>       // 状态持久化：复位后记住上次状态
#include "pins_config.h"

// 串口通信波特率
const unsigned long SERIAL_BAUD = 115200;

// 交通灯状态（语义化命名）
enum TrafficState {
    IDLE,             // 绿灯闪烁 — 空闲（60s 无操作自动进入）
    THINKING,         // 黄灯闪烁 — AI 思考中
    WAITING_USER,     // 红灯常亮 — 需要你确认
    TASK_COMPLETE,    // 绿灯常亮 — 任务完成
    TASK_FAILED,      // 红灯常亮 — 任务失败（预留）
    TOOL_ERROR        // 红灯闪烁 — 工具报错
};

// 闪烁参数
const unsigned long BLINK_INTERVAL = 500;  // 500ms 闪烁一次
unsigned long blink_timer = 0;
bool blink_state = false;

// 空闲超时
const unsigned long IDLE_TIMEOUT = 60000;        // 任务完成后 60 秒回空闲
const unsigned long WAIT_USER_TIMEOUT = 300000;  // 等待用户 5 分钟后回空闲
unsigned long last_command_time = 0;

// 当前状态
TrafficState current_state = IDLE;

void setup() {
    Serial.begin(SERIAL_BAUD);
    Serial.setTimeout(100);

    pinMode(PIN_RED, OUTPUT);
    pinMode(PIN_YELLOW, OUTPUT);
    pinMode(PIN_GREEN, OUTPUT);
    pinMode(PIN_BUILTIN_LED, OUTPUT);

    // 从 EEPROM 恢复上次状态（串口复位不丢灯）
    EEPROM.begin(16);
    uint8_t saved = EEPROM.read(0);
    if (saved >= IDLE && saved <= TOOL_ERROR) {
        current_state = (TrafficState)saved;
    } else {
        current_state = IDLE;
    }
    applyState(current_state, true);

    Serial.println("ESP8266 Traffic Light Ready");
    Serial.println("States: THINKING, WAITING_USER, TASK_COMPLETE, IDLE, TASK_FAILED, TOOL_ERROR");
}

void loop() {
    // 读取串口指令
    if (Serial.available() > 0) {
        StaticJsonDocument<200> doc;
        DeserializationError error = deserializeJson(doc, Serial);

        if (!error) {
            const char* state = doc["state"];
            if (state != nullptr) {
                handleState(state);
            } else {
                Serial.println("Error: Missing 'state' field");
            }
        } else {
            Serial.print("JSON parse failed: ");
            Serial.println(error.c_str());
            // 清空缓冲区（带上限防止死循环）
            for (int i = 0; i < 256; i++) {
                if (Serial.read() == -1) break;
            }
        }
    }

    // 空闲超时（不同状态不同时长）
    if (current_state == WAITING_USER || current_state == TASK_COMPLETE) {
        unsigned long now = millis();
        unsigned long limit = (current_state == WAITING_USER) ? WAIT_USER_TIMEOUT : IDLE_TIMEOUT;
        if (now - last_command_time >= limit) {
            applyState(IDLE, false);
            Serial.println("State: IDLE (timeout)");
        }
    }

    // 通用闪烁控制
    handleBlink();
}

/**
 * 处理接收到的状态指令
 */
void applyState(TrafficState st, bool force) {
    switch (st) {
        case THINKING:       setAll(LOW, LOW, LOW);  blink_state = false; blink_timer = millis(); break;
        case WAITING_USER:   setAll(HIGH, LOW, LOW); break;
        case TASK_COMPLETE:  setAll(LOW, LOW, HIGH); break;
        case IDLE:           setAll(LOW, LOW, HIGH); blink_state = true;  blink_timer = millis(); break;
        case TASK_FAILED:    setAll(HIGH, LOW, LOW); break;
        case TOOL_ERROR:     setAll(LOW, LOW, LOW);  blink_state = false; blink_timer = millis(); break;
        default:             setAll(LOW, LOW, HIGH); blink_state = true;  blink_timer = millis(); st = IDLE; break;
    }
    if (force || current_state != st) {
        current_state = st;
        EEPROM.write(0, (uint8_t)st);
        EEPROM.commit();
    }
}

void handleState(const char* state) {
    last_command_time = millis();

    if (strcmp(state, "THINKING") == 0) {
        applyState(THINKING, false);
        Serial.println("State: THINKING");
    }
    else if (strcmp(state, "WAITING_USER") == 0) {
        applyState(WAITING_USER, false);
        Serial.println("State: WAITING_USER");
    }
    else if (strcmp(state, "TASK_COMPLETE") == 0) {
        applyState(TASK_COMPLETE, false);
        Serial.println("State: TASK_COMPLETE");
    }
    else if (strcmp(state, "IDLE") == 0) {
        applyState(IDLE, false);
        Serial.println("State: IDLE");
    }
    else if (strcmp(state, "TASK_FAILED") == 0) {
        applyState(TASK_FAILED, false);
        Serial.println("State: TASK_FAILED");
    }
    else if (strcmp(state, "TOOL_ERROR") == 0) {
        applyState(TOOL_ERROR, false);
        Serial.println("State: TOOL_ERROR");
    }
    else {
        Serial.print("Unknown state: ");
        Serial.println(state);
        Serial.println("Supported: THINKING, WAITING_USER, TASK_COMPLETE, IDLE, TASK_FAILED, TOOL_ERROR");
    }
}

/**
 * 通用闪烁处理：根据当前状态决定哪个灯闪烁
 */
void handleBlink() {
    unsigned long now = millis();
    if (now - blink_timer >= BLINK_INTERVAL) {
        blink_timer = now;
        blink_state = !blink_state;

        switch (current_state) {
            case THINKING:
                digitalWrite(PIN_YELLOW, blink_state ? HIGH : LOW);
                break;
            case IDLE:
                digitalWrite(PIN_GREEN, blink_state ? HIGH : LOW);
                break;
            case TOOL_ERROR:
                digitalWrite(PIN_RED, blink_state ? HIGH : LOW);
                break;
            default:
                break;
        }
    }
}

// 底层控制
void setAll(int r, int y, int g) {
    digitalWrite(PIN_RED, r);
    digitalWrite(PIN_YELLOW, y);
    digitalWrite(PIN_GREEN, g);
}
