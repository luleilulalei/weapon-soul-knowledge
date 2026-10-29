#include "app/usaki_motion.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "app/usaki_servos.h"
#include "board/usaki_board.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

static const char *TAG = "usaki_motion";

#define USAKI_MOTION_QUEUE_LEN 8
#define USAKI_MOTION_TASK_STACK_BYTES 4096
#define USAKI_MOTION_TASK_PRIORITY 4
#define USAKI_MOTION_PAUSE_MS 120
#define USAKI_MOTION_MAX_REPEAT 6
#define USAKI_MOTION_CONTINUOUS_STOP_SETTLE_MS 80
#define USAKI_MOTION_EAR_MAX_OFFSET_DEG 30
#define USAKI_MOTION_SLOW_SPEED_PERCENT 45
#define USAKI_MOTION_AUTO_STOP_TASK_STACK_BYTES 2048

typedef struct
{
    int count;
    usaki_protocol_body_action_item_t actions[USAKI_PROTOCOL_MAX_BODY_ACTIONS];
} usaki_motion_command_t;

typedef struct
{
    usaki_servo_id_t id;
    int duration_ms;
    uint32_t generation;
} usaki_motion_auto_stop_arg_t;

static QueueHandle_t s_motion_queue;
static TaskHandle_t s_motion_task;
static int s_body_angle = USAKI_MOTION_BODY_CENTER_DEG;
static uint32_t s_servo_generation[USAKI_SERVO_COUNT];

static bool streq(const char *a, const char *b)
{
    return a != NULL && b != NULL && strcmp(a, b) == 0;
}

static bool part_is_all(const char *part)
{
    return part == NULL || part[0] == '\0' || streq(part, "all");
}

static bool part_targets_left_arm(const char *part)
{
    return part_is_all(part) || streq(part, "left_arm") || streq(part, "left_hand") ||
           streq(part, "arms") || streq(part, "both_arms") || streq(part, "hands") ||
           streq(part, "both_hands");
}

static bool part_targets_right_arm(const char *part)
{
    return part_is_all(part) || streq(part, "right_arm") || streq(part, "right_hand") ||
           streq(part, "arms") || streq(part, "both_arms") || streq(part, "hands") ||
           streq(part, "both_hands");
}

static bool part_targets_left_ear(const char *part)
{
    return part_is_all(part) || streq(part, "left_ear") || streq(part, "ears") ||
           streq(part, "both_ears");
}

static bool part_targets_right_ear(const char *part)
{
    return part_is_all(part) || streq(part, "right_ear") || streq(part, "ears") ||
           streq(part, "both_ears");
}

static bool part_targets_body(const char *part)
{
    return part_is_all(part) || streq(part, "body") || streq(part, "turntable") ||
           streq(part, "base");
}

static bool servo_id_for_motion_item(const usaki_protocol_motion_servo_item_t *item,
                                     usaki_servo_id_t *out)
{
    if (item == NULL || out == NULL) {
        return false;
    }

    if (streq(item->part, "left_ear")) {
        *out = USAKI_SERVO_LEFT_EAR;
        return true;
    }
    if (streq(item->part, "right_ear")) {
        *out = USAKI_SERVO_RIGHT_EAR;
        return true;
    }
    if (streq(item->part, "left_arm") || streq(item->part, "left_hand")) {
        *out = USAKI_SERVO_LEFT_ARM;
        return true;
    }
    if (streq(item->part, "right_arm") || streq(item->part, "right_hand")) {
        *out = USAKI_SERVO_RIGHT_ARM;
        return true;
    }
    if (part_targets_body(item->part)) {
        *out = USAKI_SERVO_TURNTABLE;
        return true;
    }

    switch (item->channel) {
    case USAKI_SERVO_LEFT_EAR_CHANNEL:
        *out = USAKI_SERVO_LEFT_EAR;
        return true;
    case USAKI_SERVO_RIGHT_EAR_CHANNEL:
        *out = USAKI_SERVO_RIGHT_EAR;
        return true;
    case USAKI_SERVO_LEFT_ARM_CHANNEL:
        *out = USAKI_SERVO_LEFT_ARM;
        return true;
    case USAKI_SERVO_RIGHT_ARM_CHANNEL:
        *out = USAKI_SERVO_RIGHT_ARM;
        return true;
    case USAKI_SERVO_TURNTABLE_CHANNEL:
        *out = USAKI_SERVO_TURNTABLE;
        return true;
    default:
        return false;
    }
}

static int repeat_count_or_default(int count, int default_count)
{
    if (count <= 0) {
        count = default_count;
    }
    return count > USAKI_MOTION_MAX_REPEAT ? USAKI_MOTION_MAX_REPEAT : count;
}

static int duration_or_default(int duration_ms, int default_ms)
{
    return duration_ms > 0 ? duration_ms : default_ms;
}

static int abs_int(int value)
{
    return value < 0 ? -value : value;
}

static int clamp_int(int value, int min_value, int max_value)
{
    if (value < min_value) {
        return min_value;
    }
    if (value > max_value) {
        return max_value;
    }
    return value;
}

static int continuous_duration_for_degrees(int angle)
{
    int degrees = abs_int(angle);
    degrees = clamp_int(degrees, 1, 360);

    int duration_ms = (degrees * USAKI_SERVO_CONTINUOUS_MS_PER_90_DEG + 45) / 90;
    return clamp_int(duration_ms,
                     USAKI_SERVO_CONTINUOUS_MIN_ROTATE_MS,
                     USAKI_SERVO_CONTINUOUS_MAX_ROTATE_MS);
}

static void set_body_angle(int angle)
{
    s_body_angle = clamp_int(angle, 0, 180);
    (void)usaki_servos_set_angle(USAKI_SERVO_TURNTABLE, (uint8_t)s_body_angle);
}

static esp_err_t set_continuous(usaki_servo_id_t id, int direction, bool fast)
{
    uint16_t pulse = USAKI_SERVO_CONTINUOUS_STOP_PULSE_US;
    if (direction > 0) {
        pulse = fast ? USAKI_SERVO_CONTINUOUS_FAST_CW_PULSE_US : USAKI_SERVO_CONTINUOUS_SLOW_CW_PULSE_US;
    } else if (direction < 0) {
        pulse = fast ? USAKI_SERVO_CONTINUOUS_FAST_CCW_PULSE_US : USAKI_SERVO_CONTINUOUS_SLOW_CCW_PULSE_US;
    }
    return usaki_servos_set_pulse_us(id, pulse);
}

static bool is_ear_servo(usaki_servo_id_t id)
{
    return id == USAKI_SERVO_LEFT_EAR || id == USAKI_SERVO_RIGHT_EAR;
}

static uint32_t bump_servo_generation(usaki_servo_id_t id)
{
    if (id >= USAKI_SERVO_COUNT) {
        return 0;
    }
    return ++s_servo_generation[id];
}

static esp_err_t stop_continuous_servo(usaki_servo_id_t id)
{
    esp_err_t err = usaki_servos_set_pulse_us(id, USAKI_SERVO_CONTINUOUS_STOP_PULSE_US);
    if (err != ESP_OK) {
        return err;
    }
    vTaskDelay(pdMS_TO_TICKS(USAKI_MOTION_CONTINUOUS_STOP_SETTLE_MS));
    return usaki_servos_disable(id);
}

static int max_limited_continuous_duration_ms(bool fast)
{
    int duration_ms = (USAKI_MOTION_EAR_MAX_OFFSET_DEG * USAKI_SERVO_CONTINUOUS_MS_PER_90_DEG + 45) / 90;
    if (!fast) {
        duration_ms = (duration_ms * 100 + (USAKI_MOTION_SLOW_SPEED_PERCENT - 1)) / USAKI_MOTION_SLOW_SPEED_PERCENT;
    }
    return clamp_int(duration_ms,
                     USAKI_SERVO_CONTINUOUS_MIN_ROTATE_MS,
                     USAKI_SERVO_CONTINUOUS_MAX_ROTATE_MS);
}

static int safe_motion_drive_duration_ms(usaki_servo_id_t id, bool fast, int requested_ms)
{
    if (!is_ear_servo(id)) {
        return requested_ms > 0 ? requested_ms : 0;
    }

    int max_duration_ms = max_limited_continuous_duration_ms(fast);
    if (requested_ms <= 0) {
        return max_duration_ms;
    }
    return clamp_int(requested_ms, 1, max_duration_ms);
}

static void motion_auto_stop_task(void *ctx)
{
    usaki_motion_auto_stop_arg_t *arg = (usaki_motion_auto_stop_arg_t *)ctx;
    if (arg == NULL) {
        vTaskDelete(NULL);
        return;
    }

    vTaskDelay(pdMS_TO_TICKS(arg->duration_ms));
    if (arg->id < USAKI_SERVO_COUNT && s_servo_generation[arg->id] == arg->generation) {
        (void)stop_continuous_servo(arg->id);
    }
    free(arg);
    vTaskDelete(NULL);
}

static esp_err_t schedule_motion_auto_stop(usaki_servo_id_t id, int duration_ms, uint32_t generation)
{
    if (duration_ms <= 0) {
        return ESP_OK;
    }

    usaki_motion_auto_stop_arg_t *arg = (usaki_motion_auto_stop_arg_t *)calloc(1, sizeof(*arg));
    ESP_RETURN_ON_FALSE(arg != NULL, ESP_ERR_NO_MEM, TAG, "motion auto stop allocation failed");
    arg->id = id;
    arg->duration_ms = duration_ms;
    arg->generation = generation;

    BaseType_t ok = xTaskCreate(motion_auto_stop_task,
                                "motion_auto_stop",
                                USAKI_MOTION_AUTO_STOP_TASK_STACK_BYTES,
                                arg,
                                USAKI_MOTION_TASK_PRIORITY,
                                NULL);
    if (ok != pdPASS) {
        free(arg);
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

static esp_err_t apply_motion_servo(const usaki_protocol_motion_servo_item_t *item)
{
    if (item == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    usaki_servo_id_t id = USAKI_SERVO_COUNT;
    if (!servo_id_for_motion_item(item, &id)) {
        ESP_LOGW(TAG, "ignore motion servo with unknown target: part=%s channel=%d", item->part, item->channel);
        return ESP_ERR_INVALID_ARG;
    }

    ESP_LOGI(TAG,
             "motion servo: part=%s channel=%d kind=%s op=%s direction=%s speed=%s pulse_us=%d angle=%d ttl_ms=%d",
             item->part,
             item->channel,
             item->kind,
             item->op,
             item->direction,
             item->speed,
             item->pulse_us,
             item->angle,
             item->ttl_ms);

    if (streq(item->op, "disable")) {
        (void)bump_servo_generation(id);
        return usaki_servos_disable(id);
    }

    if (id == USAKI_SERVO_TURNTABLE || streq(item->kind, "positional") || streq(item->op, "set_angle")) {
        if (item->pulse_us > 0) {
            s_body_angle = clamp_int(item->angle, 0, 180);
            return usaki_servos_set_pulse_us(id, (uint16_t)item->pulse_us);
        }
        set_body_angle(item->angle);
        return ESP_OK;
    }

    if (streq(item->op, "stop")) {
        uint16_t pulse = item->pulse_us > 0 ? (uint16_t)item->pulse_us : USAKI_SERVO_CONTINUOUS_STOP_PULSE_US;
        (void)bump_servo_generation(id);
        esp_err_t err = usaki_servos_set_pulse_us(id, pulse);
        if (err != ESP_OK) {
            return err;
        }
        vTaskDelay(pdMS_TO_TICKS(USAKI_MOTION_CONTINUOUS_STOP_SETTLE_MS));
        return usaki_servos_disable(id);
    }

    if (streq(item->op, "drive")) {
        int direction = streq(item->direction, "ccw") ? -1 : 1;
        bool fast = !streq(item->speed, "slow");
        int duration_ms = safe_motion_drive_duration_ms(id, fast, item->duration_ms > 0 ? item->duration_ms : item->ttl_ms);
        uint32_t generation = bump_servo_generation(id);
        esp_err_t err = item->pulse_us > 0 ? usaki_servos_set_pulse_us(id, (uint16_t)item->pulse_us)
                                           : set_continuous(id, direction, fast);
        if (err != ESP_OK) {
            return err;
        }
        return schedule_motion_auto_stop(id, duration_ms, generation);
    }

    if (item->pulse_us > 0) {
        return usaki_servos_set_pulse_us(id, (uint16_t)item->pulse_us);
    }

    ESP_LOGW(TAG, "unsupported motion servo op: %s", item->op);
    return ESP_ERR_NOT_SUPPORTED;
}

static void stop_continuous_targets(const char *part)
{
    if (part_targets_left_arm(part)) {
        (void)bump_servo_generation(USAKI_SERVO_LEFT_ARM);
        (void)usaki_servos_disable(USAKI_SERVO_LEFT_ARM);
    }
    if (part_targets_right_arm(part)) {
        (void)bump_servo_generation(USAKI_SERVO_RIGHT_ARM);
        (void)usaki_servos_disable(USAKI_SERVO_RIGHT_ARM);
    }
    if (part_targets_left_ear(part)) {
        (void)bump_servo_generation(USAKI_SERVO_LEFT_EAR);
        (void)usaki_servos_disable(USAKI_SERVO_LEFT_EAR);
    }
    if (part_targets_right_ear(part)) {
        (void)bump_servo_generation(USAKI_SERVO_RIGHT_EAR);
        (void)usaki_servos_disable(USAKI_SERVO_RIGHT_EAR);
    }
}

static void center_targets(const char *part)
{
    stop_continuous_targets(part);
    if (part_targets_body(part)) {
        set_body_angle(USAKI_MOTION_BODY_CENTER_DEG);
    }
}

static void execute_arm_wave(const usaki_protocol_body_action_item_t *item)
{
    int count = repeat_count_or_default(item->count, 2);
    int duration_ms = duration_or_default(item->duration_ms, USAKI_MOTION_CONTINUOUS_STEP_MS);

    for (int i = 0; i < count; ++i) {
        int direction = (i % 2 == 0) ? 1 : -1;
        if (part_targets_left_arm(item->part)) {
            (void)set_continuous(USAKI_SERVO_LEFT_ARM, -direction, true);
        }
        if (part_targets_right_arm(item->part)) {
            (void)set_continuous(USAKI_SERVO_RIGHT_ARM, direction, true);
        }
        vTaskDelay(pdMS_TO_TICKS(duration_ms));
        stop_continuous_targets(item->part);
        vTaskDelay(pdMS_TO_TICKS(USAKI_MOTION_PAUSE_MS));
    }
}

static void execute_ear_wiggle(const usaki_protocol_body_action_item_t *item)
{
    int count = repeat_count_or_default(item->count, 2);
    int duration_ms = duration_or_default(item->duration_ms, USAKI_MOTION_CONTINUOUS_STEP_MS);

    for (int i = 0; i < count; ++i) {
        int direction = (i % 2 == 0) ? 1 : -1;
        if (part_targets_left_ear(item->part)) {
            (void)set_continuous(USAKI_SERVO_LEFT_EAR, direction, true);
        }
        if (part_targets_right_ear(item->part)) {
            (void)set_continuous(USAKI_SERVO_RIGHT_EAR, -direction, true);
        }
        vTaskDelay(pdMS_TO_TICKS(duration_ms));
        stop_continuous_targets(item->part);
        vTaskDelay(pdMS_TO_TICKS(USAKI_MOTION_PAUSE_MS));
    }
}

static void execute_continuous_rotate(const usaki_protocol_body_action_item_t *item, int direction)
{
    int duration_ms = duration_or_default(item->duration_ms, USAKI_MOTION_CONTINUOUS_STEP_MS);

    if (part_targets_left_arm(item->part)) {
        (void)set_continuous(USAKI_SERVO_LEFT_ARM, direction, false);
    }
    if (part_targets_right_arm(item->part)) {
        (void)set_continuous(USAKI_SERVO_RIGHT_ARM, direction, false);
    }
    if (part_targets_left_ear(item->part)) {
        (void)set_continuous(USAKI_SERVO_LEFT_EAR, direction, false);
    }
    if (part_targets_right_ear(item->part)) {
        (void)set_continuous(USAKI_SERVO_RIGHT_EAR, direction, false);
    }

    vTaskDelay(pdMS_TO_TICKS(duration_ms));
    stop_continuous_targets(item->part);
}

static void execute_continuous_rotate_degrees(const usaki_protocol_body_action_item_t *item)
{
    if (item->angle == 0) {
        ESP_LOGW(TAG, "ignore rotate_degrees with zero angle");
        return;
    }

    int direction = item->angle > 0 ? 1 : -1;
    int duration_ms = item->duration_ms > 0 ? item->duration_ms : continuous_duration_for_degrees(item->angle);

    ESP_LOGI(TAG,
             "continuous rotate degrees: part=%s angle=%d duration_ms=%d",
             item->part,
             item->angle,
             duration_ms);

    usaki_protocol_body_action_item_t timed = *item;
    timed.duration_ms = duration_ms;
    execute_continuous_rotate(&timed, direction);
}

static void execute_body_rotate(int angle, int duration_ms)
{
    set_body_angle(angle);
    if (duration_ms > 0) {
        vTaskDelay(pdMS_TO_TICKS(duration_ms));
        set_body_angle(USAKI_MOTION_BODY_CENTER_DEG);
    }
}

static void execute_body_rotate_degrees(const usaki_protocol_body_action_item_t *item)
{
    if (item->angle == 0) {
        ESP_LOGW(TAG, "ignore body rotate_degrees with zero angle");
        return;
    }

    int target_angle = clamp_int(s_body_angle + item->angle, 0, 180);
    ESP_LOGI(TAG,
             "body rotate degrees: current=%d delta=%d target=%d",
             s_body_angle,
             item->angle,
             target_angle);
    set_body_angle(target_angle);
}

static void execute_body_sway(const usaki_protocol_body_action_item_t *item)
{
    int count = repeat_count_or_default(item->count, 2);
    int duration_ms = duration_or_default(item->duration_ms, USAKI_MOTION_BODY_STEP_MS);

    for (int i = 0; i < count; ++i) {
        set_body_angle(USAKI_MOTION_BODY_LEFT_DEG);
        vTaskDelay(pdMS_TO_TICKS(duration_ms));
        set_body_angle(USAKI_MOTION_BODY_RIGHT_DEG);
        vTaskDelay(pdMS_TO_TICKS(duration_ms));
    }
    set_body_angle(USAKI_MOTION_BODY_CENTER_DEG);
}

static void execute_action(const usaki_protocol_body_action_item_t *item)
{
    if (item == NULL || item->action[0] == '\0') {
        return;
    }

    ESP_LOGI(TAG,
             "body action: part=%s action=%s angle=%d count=%d duration_ms=%d",
             item->part,
             item->action,
             item->angle,
             item->count,
             item->duration_ms);

    if (streq(item->action, "stop") || streq(item->action, "center")) {
        center_targets(item->part);
        return;
    }

    if (streq(item->action, "wave")) {
        execute_arm_wave(item);
        return;
    }

    if (streq(item->action, "wiggle")) {
        if (part_targets_left_ear(item->part) || part_targets_right_ear(item->part)) {
            execute_ear_wiggle(item);
        } else {
            execute_arm_wave(item);
        }
        return;
    }

    if (streq(item->action, "rotate_cw") || streq(item->action, "rotate_right")) {
        if (part_targets_body(item->part)) {
            execute_body_rotate(USAKI_MOTION_BODY_RIGHT_DEG,
                                duration_or_default(item->duration_ms, USAKI_MOTION_BODY_STEP_MS));
        } else {
            execute_continuous_rotate(item, 1);
        }
        return;
    }

    if (streq(item->action, "rotate_degrees")) {
        if (part_targets_body(item->part)) {
            execute_body_rotate_degrees(item);
        } else {
            execute_continuous_rotate_degrees(item);
        }
        return;
    }

    if (streq(item->action, "rotate_ccw") || streq(item->action, "rotate_left")) {
        if (part_targets_body(item->part)) {
            execute_body_rotate(USAKI_MOTION_BODY_LEFT_DEG,
                                duration_or_default(item->duration_ms, USAKI_MOTION_BODY_STEP_MS));
        } else {
            execute_continuous_rotate(item, -1);
        }
        return;
    }

    if (streq(item->action, "sway")) {
        if (part_targets_body(item->part)) {
            execute_body_sway(item);
        }
        return;
    }

    if (streq(item->action, "set_angle") && part_targets_body(item->part)) {
        int angle = item->angle;
        if (angle < 0) {
            angle = 0;
        }
        if (angle > 180) {
            angle = 180;
        }
        execute_body_rotate(angle, item->duration_ms);
        return;
    }

    if (streq(item->action, "dance")) {
        usaki_protocol_body_action_item_t ears = *item;
        strlcpy(ears.part, "both_ears", sizeof(ears.part));
        strlcpy(ears.action, "wiggle", sizeof(ears.action));
        ears.count = 2;
        execute_ear_wiggle(&ears);

        usaki_protocol_body_action_item_t arms = *item;
        strlcpy(arms.part, "both_arms", sizeof(arms.part));
        strlcpy(arms.action, "wave", sizeof(arms.action));
        arms.count = 2;
        execute_arm_wave(&arms);

        usaki_protocol_body_action_item_t body = *item;
        strlcpy(body.part, "body", sizeof(body.part));
        strlcpy(body.action, "sway", sizeof(body.action));
        body.count = 1;
        execute_body_sway(&body);
        return;
    }

    ESP_LOGW(TAG, "unsupported body action: part=%s action=%s", item->part, item->action);
}

static void motion_task(void *arg)
{
    (void)arg;

    while (true) {
        usaki_motion_command_t command = {0};
        if (xQueueReceive(s_motion_queue, &command, portMAX_DELAY) != pdPASS) {
            continue;
        }

        for (int i = 0; i < command.count; ++i) {
            execute_action(&command.actions[i]);
        }
    }
}

esp_err_t usaki_motion_init(void)
{
    if (s_motion_queue == NULL) {
        s_motion_queue = xQueueCreate(USAKI_MOTION_QUEUE_LEN, sizeof(usaki_motion_command_t));
        ESP_RETURN_ON_FALSE(s_motion_queue != NULL, ESP_ERR_NO_MEM, TAG, "create motion queue failed");
    }

    if (s_motion_task == NULL) {
        BaseType_t ok = xTaskCreate(
            motion_task,
            "usaki_motion",
            USAKI_MOTION_TASK_STACK_BYTES,
            NULL,
            USAKI_MOTION_TASK_PRIORITY,
            &s_motion_task);
        ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_ERR_NO_MEM, TAG, "create motion task failed");
    }

    center_targets("all");
    ESP_LOGI(TAG, "motion initialized");
    return ESP_OK;
}

esp_err_t usaki_motion_enqueue_body_action(const usaki_protocol_server_message_t *message)
{
    ESP_RETURN_ON_FALSE(message != NULL, ESP_ERR_INVALID_ARG, TAG, "message is null");
    ESP_RETURN_ON_FALSE(s_motion_queue != NULL, ESP_ERR_INVALID_STATE, TAG, "motion is not initialized");

    if (message->body_action_count <= 0) {
        return ESP_OK;
    }

    usaki_motion_command_t command = {0};
    command.count = message->body_action_count;
    if (command.count > USAKI_PROTOCOL_MAX_BODY_ACTIONS) {
        command.count = USAKI_PROTOCOL_MAX_BODY_ACTIONS;
    }
    memcpy(command.actions, message->body_actions, sizeof(command.actions));

    BaseType_t ok = xQueueSend(s_motion_queue, &command, 0);
    ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_ERR_TIMEOUT, TAG, "motion queue is full");
    return ESP_OK;
}

esp_err_t usaki_motion_apply_servo_batch(const usaki_protocol_server_message_t *message)
{
    ESP_RETURN_ON_FALSE(message != NULL, ESP_ERR_INVALID_ARG, TAG, "message is null");

    if (message->motion_servo_count <= 0) {
        return ESP_OK;
    }

    esp_err_t first_err = ESP_OK;
    int count = message->motion_servo_count;
    if (count > USAKI_PROTOCOL_MAX_MOTION_SERVOS) {
        count = USAKI_PROTOCOL_MAX_MOTION_SERVOS;
    }

    for (int i = 0; i < count; ++i) {
        esp_err_t err = apply_motion_servo(&message->motion_servos[i]);
        if (err != ESP_OK && first_err == ESP_OK) {
            first_err = err;
        }
    }
    return first_err;
}
