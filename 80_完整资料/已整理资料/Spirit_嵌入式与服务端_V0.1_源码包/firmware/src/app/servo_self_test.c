#include "app/servo_self_test.h"

#include <stdio.h>

#include "app/usaki_servos.h"
#include "board/usaki_board.h"
#include "esp_check.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "servo_self_test";

static esp_err_t set_servo_angle(const usaki_servo_spec_t *spec, uint8_t angle_deg)
{
    printf("CH%d %-10s angle: %u deg\n", spec->channel, spec->name, angle_deg);
    return usaki_servos_set_angle(spec->id, angle_deg);
}

static int clamp_angle(int angle_deg)
{
    if (angle_deg < 0) {
        return 0;
    }
    if (angle_deg > 180) {
        return 180;
    }
    return angle_deg;
}

static esp_err_t set_ear_angles(int left_deg, int right_deg)
{
    left_deg = clamp_angle(left_deg);
    right_deg = clamp_angle(right_deg);

    printf("ears left=%d deg right=%d deg\n", left_deg, right_deg);
    ESP_RETURN_ON_ERROR(usaki_servos_set_angle(USAKI_SERVO_LEFT_EAR, (uint8_t)left_deg),
                        TAG,
                        "set left ear failed");
    return usaki_servos_set_angle(USAKI_SERVO_RIGHT_EAR, (uint8_t)right_deg);
}

static esp_err_t set_arm_angles(int left_deg, int right_deg)
{
    left_deg = clamp_angle(left_deg);
    right_deg = clamp_angle(right_deg);

    printf("arms left=%d deg right=%d deg\n", left_deg, right_deg);
    ESP_RETURN_ON_ERROR(usaki_servos_set_angle(USAKI_SERVO_LEFT_ARM, (uint8_t)left_deg),
                        TAG,
                        "set left arm failed");
    return usaki_servos_set_angle(USAKI_SERVO_RIGHT_ARM, (uint8_t)right_deg);
}

static int step_toward(int current, int target)
{
    const int step = USAKI_EAR_SWING_TEST_STEP_DEG > 0 ? USAKI_EAR_SWING_TEST_STEP_DEG : 1;

    if (current < target) {
        current += step;
        return current > target ? target : current;
    }
    if (current > target) {
        current -= step;
        return current < target ? target : current;
    }
    return current;
}

static esp_err_t ramp_ears_to(int *left_deg, int *right_deg, int target_left_deg, int target_right_deg)
{
    target_left_deg = clamp_angle(target_left_deg);
    target_right_deg = clamp_angle(target_right_deg);

    while (*left_deg != target_left_deg || *right_deg != target_right_deg) {
        *left_deg = step_toward(*left_deg, target_left_deg);
        *right_deg = step_toward(*right_deg, target_right_deg);
        ESP_RETURN_ON_ERROR(set_ear_angles(*left_deg, *right_deg), TAG, "set ear ramp failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_EAR_SWING_TEST_STEP_DELAY_MS));
    }

    return ESP_OK;
}

static int step_arm_toward(int current, int target)
{
    const int step = USAKI_ARM_SWING_TEST_STEP_DEG > 0 ? USAKI_ARM_SWING_TEST_STEP_DEG : 1;

    if (current < target) {
        current += step;
        return current > target ? target : current;
    }
    if (current > target) {
        current -= step;
        return current < target ? target : current;
    }
    return current;
}

static esp_err_t ramp_arms_to(int *left_deg, int *right_deg, int target_left_deg, int target_right_deg)
{
    target_left_deg = clamp_angle(target_left_deg);
    target_right_deg = clamp_angle(target_right_deg);

    while (*left_deg != target_left_deg || *right_deg != target_right_deg) {
        *left_deg = step_arm_toward(*left_deg, target_left_deg);
        *right_deg = step_arm_toward(*right_deg, target_right_deg);
        ESP_RETURN_ON_ERROR(set_arm_angles(*left_deg, *right_deg), TAG, "set arm ramp failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_ARM_SWING_TEST_STEP_DELAY_MS));
    }

    return ESP_OK;
}

static esp_err_t set_body_angle(int angle_deg)
{
    angle_deg = clamp_angle(angle_deg);

    printf("body angle=%d deg\n", angle_deg);
    return usaki_servos_set_angle(USAKI_SERVO_TURNTABLE, (uint8_t)angle_deg);
}

static int step_body_toward(int current, int target)
{
    const int step = USAKI_BODY_SWING_TEST_STEP_DEG > 0 ? USAKI_BODY_SWING_TEST_STEP_DEG : 1;

    if (current < target) {
        current += step;
        return current > target ? target : current;
    }
    if (current > target) {
        current -= step;
        return current < target ? target : current;
    }
    return current;
}

static esp_err_t ramp_body_to(int *angle_deg, int target_angle_deg)
{
    target_angle_deg = clamp_angle(target_angle_deg);

    while (*angle_deg != target_angle_deg) {
        *angle_deg = step_body_toward(*angle_deg, target_angle_deg);
        ESP_RETURN_ON_ERROR(set_body_angle(*angle_deg), TAG, "set body ramp failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_BODY_SWING_TEST_STEP_DELAY_MS));
    }

    return ESP_OK;
}

esp_err_t servo_self_test_run_ear_reset(void)
{
    const int center = USAKI_SERVO_CENTER_DEG;

    printf("PCA9685 ear reset test starting...\n");
    printf("I2C: SDA=GPIO%d, SCL=GPIO%d, addr=0x%02x\n",
           USAKI_SERVO_I2C_SDA_GPIO,
           USAKI_SERVO_I2C_SCL_GPIO,
           USAKI_PCA9685_I2C_ADDR);
    printf("Left ear CH%d, right ear CH%d, reset angle=%d deg\n",
           USAKI_SERVO_LEFT_EAR_CHANNEL,
           USAKI_SERVO_RIGHT_EAR_CHANNEL,
           center);

    ESP_RETURN_ON_ERROR(usaki_servos_init_outputs_disabled(), TAG, "servos init failed");
    printf("Only ear outputs are enabled; arms and turntable stay disabled.\n");
    ESP_RETURN_ON_ERROR(set_ear_angles(center, center), TAG, "reset ears failed");

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

esp_err_t servo_self_test_run_ear_swing_30(void)
{
    const int center = USAKI_SERVO_CENTER_DEG;
    const int offset = USAKI_EAR_SWING_TEST_OFFSET_DEG;
#if USAKI_EAR_SWING_TEST_MIRROR_RIGHT
    const int forward_left = center - offset;
    const int forward_right = center + offset;
    const int back_left = center + offset;
    const int back_right = center - offset;
#else
    const int forward_left = center - offset;
    const int forward_right = center - offset;
    const int back_left = center + offset;
    const int back_right = center + offset;
#endif

    printf("PCA9685 ear swing 30-degree test starting...\n");
    printf("I2C: SDA=GPIO%d, SCL=GPIO%d, addr=0x%02x\n",
           USAKI_SERVO_I2C_SDA_GPIO,
           USAKI_SERVO_I2C_SCL_GPIO,
           USAKI_PCA9685_I2C_ADDR);
    printf("Left ear CH%d, right ear CH%d, center=%d deg, offset=+/- %d deg\n",
           USAKI_SERVO_LEFT_EAR_CHANNEL,
           USAKI_SERVO_RIGHT_EAR_CHANNEL,
           center,
           offset);

    ESP_RETURN_ON_ERROR(usaki_servos_init_outputs_disabled(), TAG, "servos init failed");
    printf("Only ear outputs are enabled during this test; arms and turntable stay disabled.\n");

    int left_deg = center;
    int right_deg = center;
    ESP_RETURN_ON_ERROR(set_ear_angles(left_deg, right_deg), TAG, "center ears failed");
    vTaskDelay(pdMS_TO_TICKS(USAKI_EAR_SWING_TEST_HOLD_MS));

    while (1) {
        printf("ear swing: forward 30 deg\n");
        ESP_RETURN_ON_ERROR(ramp_ears_to(&left_deg, &right_deg, forward_left, forward_right),
                            TAG,
                            "forward swing failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_EAR_SWING_TEST_HOLD_MS));

        printf("ear swing: center\n");
        ESP_RETURN_ON_ERROR(ramp_ears_to(&left_deg, &right_deg, center, center), TAG, "center failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_EAR_SWING_TEST_CENTER_HOLD_MS));

        printf("ear swing: back 30 deg\n");
        ESP_RETURN_ON_ERROR(ramp_ears_to(&left_deg, &right_deg, back_left, back_right),
                            TAG,
                            "back swing failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_EAR_SWING_TEST_HOLD_MS));

        printf("ear swing: center\n");
        ESP_RETURN_ON_ERROR(ramp_ears_to(&left_deg, &right_deg, center, center), TAG, "center failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_EAR_SWING_TEST_HOLD_MS));
    }
}

esp_err_t servo_self_test_run_arm_swing(void)
{
    const int center = USAKI_SERVO_CENTER_DEG;
    const int offset = USAKI_ARM_SWING_TEST_OFFSET_DEG;
#if USAKI_ARM_SWING_TEST_MIRROR_RIGHT
    const int forward_left = center - offset;
    const int forward_right = center + offset;
    const int back_left = center + offset;
    const int back_right = center - offset;
#else
    const int forward_left = center - offset;
    const int forward_right = center - offset;
    const int back_left = center + offset;
    const int back_right = center + offset;
#endif

    printf("PCA9685 arm swing test starting...\n");
    printf("I2C: SDA=GPIO%d, SCL=GPIO%d, addr=0x%02x\n",
           USAKI_SERVO_I2C_SDA_GPIO,
           USAKI_SERVO_I2C_SCL_GPIO,
           USAKI_PCA9685_I2C_ADDR);
    printf("Left arm CH%d, right arm CH%d, center=%d deg, offset=+/- %d deg\n",
           USAKI_SERVO_LEFT_ARM_CHANNEL,
           USAKI_SERVO_RIGHT_ARM_CHANNEL,
           center,
           offset);

    ESP_RETURN_ON_ERROR(usaki_servos_init_outputs_disabled(), TAG, "servos init failed");
    printf("Only arm outputs are enabled during this test; ears and turntable stay disabled.\n");

    int left_deg = center;
    int right_deg = center;
    ESP_RETURN_ON_ERROR(set_arm_angles(left_deg, right_deg), TAG, "center arms failed");
    vTaskDelay(pdMS_TO_TICKS(USAKI_ARM_SWING_TEST_HOLD_MS));

    while (1) {
        printf("arm swing: forward\n");
        ESP_RETURN_ON_ERROR(ramp_arms_to(&left_deg, &right_deg, forward_left, forward_right),
                            TAG,
                            "forward swing failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_ARM_SWING_TEST_HOLD_MS));

        printf("arm swing: center\n");
        ESP_RETURN_ON_ERROR(ramp_arms_to(&left_deg, &right_deg, center, center), TAG, "center failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_ARM_SWING_TEST_CENTER_HOLD_MS));

        printf("arm swing: back\n");
        ESP_RETURN_ON_ERROR(ramp_arms_to(&left_deg, &right_deg, back_left, back_right),
                            TAG,
                            "back swing failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_ARM_SWING_TEST_HOLD_MS));

        printf("arm swing: center\n");
        ESP_RETURN_ON_ERROR(ramp_arms_to(&left_deg, &right_deg, center, center), TAG, "center failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_ARM_SWING_TEST_HOLD_MS));
    }
}

esp_err_t servo_self_test_run_body_swing(void)
{
    const int center = USAKI_SERVO_CENTER_DEG;
    const int left = USAKI_BODY_SWING_TEST_LEFT_DEG;
    const int right = USAKI_BODY_SWING_TEST_RIGHT_DEG;

    printf("PCA9685 body swing test starting...\n");
    printf("I2C: SDA=GPIO%d, SCL=GPIO%d, addr=0x%02x\n",
           USAKI_SERVO_I2C_SDA_GPIO,
           USAKI_SERVO_I2C_SCL_GPIO,
           USAKI_PCA9685_I2C_ADDR);
    printf("Body turntable CH%d, center=%d deg, left=%d deg, right=%d deg\n",
           USAKI_SERVO_TURNTABLE_CHANNEL,
           center,
           left,
           right);
    printf("Body relative swing offset=+/- %d deg\n", USAKI_BODY_SWING_TEST_OFFSET_DEG);

    ESP_RETURN_ON_ERROR(usaki_servos_init_outputs_disabled(), TAG, "servos init failed");
    printf("Only body output is enabled during this test; ears and arms stay disabled.\n");

    int angle_deg = center;
    ESP_RETURN_ON_ERROR(set_body_angle(angle_deg), TAG, "center body failed");
    vTaskDelay(pdMS_TO_TICKS(USAKI_BODY_SWING_TEST_HOLD_MS));

    while (1) {
        printf("body swing: left\n");
        ESP_RETURN_ON_ERROR(ramp_body_to(&angle_deg, left), TAG, "left swing failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_BODY_SWING_TEST_HOLD_MS));

        printf("body swing: center\n");
        ESP_RETURN_ON_ERROR(ramp_body_to(&angle_deg, center), TAG, "center failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_BODY_SWING_TEST_CENTER_HOLD_MS));

        printf("body swing: right\n");
        ESP_RETURN_ON_ERROR(ramp_body_to(&angle_deg, right), TAG, "right swing failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_BODY_SWING_TEST_HOLD_MS));

        printf("body swing: center\n");
        ESP_RETURN_ON_ERROR(ramp_body_to(&angle_deg, center), TAG, "center failed");
        vTaskDelay(pdMS_TO_TICKS(USAKI_BODY_SWING_TEST_HOLD_MS));
    }
}

esp_err_t servo_self_test_run(void)
{
    printf("PCA9685 5-servo self-test starting...\n");
    printf("I2C: SDA=GPIO%d, SCL=GPIO%d, addr=0x%02x\n",
           USAKI_SERVO_I2C_SDA_GPIO,
           USAKI_SERVO_I2C_SCL_GPIO,
           USAKI_PCA9685_I2C_ADDR);
    printf("CH0-CH3: SG90 ears/arms, CH4: MG996R turntable.\n");

    ESP_RETURN_ON_ERROR(usaki_servos_init(), TAG, "servos init failed");

    ESP_RETURN_ON_ERROR(usaki_servos_center_all(), TAG, "center all failed");
    vTaskDelay(pdMS_TO_TICKS(1500));

    size_t count = 0;
    const usaki_servo_spec_t *specs = usaki_servos_get_specs(&count);

    while (1) {
        for (size_t i = 0; i < count; ++i) {
            ESP_RETURN_ON_ERROR(set_servo_angle(&specs[i], 75), TAG, "left sweep failed");
            vTaskDelay(pdMS_TO_TICKS(500));
            ESP_RETURN_ON_ERROR(set_servo_angle(&specs[i], USAKI_SERVO_CENTER_DEG), TAG, "center failed");
            vTaskDelay(pdMS_TO_TICKS(500));
            ESP_RETURN_ON_ERROR(set_servo_angle(&specs[i], 105), TAG, "right sweep failed");
            vTaskDelay(pdMS_TO_TICKS(500));
            ESP_RETURN_ON_ERROR(set_servo_angle(&specs[i], USAKI_SERVO_CENTER_DEG), TAG, "center failed");
            vTaskDelay(pdMS_TO_TICKS(800));
        }
    }
}
