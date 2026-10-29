#include "app/usaki_servos.h"

#include <stdbool.h>

#include "board/usaki_board.h"
#include "drivers/pca9685.h"
#include "esp_check.h"

static const char *TAG = "usaki_servos";

static pca9685_handle_t s_pca9685;

static const usaki_servo_spec_t SERVO_SPECS[] = {
    {
        .id = USAKI_SERVO_LEFT_EAR,
        .name = "left_ear",
        .channel = USAKI_SERVO_LEFT_EAR_CHANNEL,
        .min_pulse_us = USAKI_SERVO_SG90_MIN_PULSE_US,
        .center_pulse_us = USAKI_SERVO_SG90_CENTER_PULSE_US,
        .max_pulse_us = USAKI_SERVO_SG90_MAX_PULSE_US,
    },
    {
        .id = USAKI_SERVO_RIGHT_EAR,
        .name = "right_ear",
        .channel = USAKI_SERVO_RIGHT_EAR_CHANNEL,
        .min_pulse_us = USAKI_SERVO_SG90_MIN_PULSE_US,
        .center_pulse_us = USAKI_SERVO_SG90_CENTER_PULSE_US,
        .max_pulse_us = USAKI_SERVO_SG90_MAX_PULSE_US,
    },
    {
        .id = USAKI_SERVO_LEFT_ARM,
        .name = "left_arm",
        .channel = USAKI_SERVO_LEFT_ARM_CHANNEL,
        .min_pulse_us = USAKI_SERVO_SG90_MIN_PULSE_US,
        .center_pulse_us = USAKI_SERVO_SG90_CENTER_PULSE_US,
        .max_pulse_us = USAKI_SERVO_SG90_MAX_PULSE_US,
    },
    {
        .id = USAKI_SERVO_RIGHT_ARM,
        .name = "right_arm",
        .channel = USAKI_SERVO_RIGHT_ARM_CHANNEL,
        .min_pulse_us = USAKI_SERVO_SG90_MIN_PULSE_US,
        .center_pulse_us = USAKI_SERVO_SG90_CENTER_PULSE_US,
        .max_pulse_us = USAKI_SERVO_SG90_MAX_PULSE_US,
    },
    {
        .id = USAKI_SERVO_TURNTABLE,
        .name = "turntable",
        .channel = USAKI_SERVO_TURNTABLE_CHANNEL,
        .min_pulse_us = USAKI_SERVO_MG996R_MIN_PULSE_US,
        .center_pulse_us = USAKI_SERVO_MG996R_CENTER_PULSE_US,
        .max_pulse_us = USAKI_SERVO_MG996R_MAX_PULSE_US,
    },
};

static const usaki_servo_spec_t *spec_for_id(usaki_servo_id_t id)
{
    for (size_t i = 0; i < sizeof(SERVO_SPECS) / sizeof(SERVO_SPECS[0]); ++i) {
        if (SERVO_SPECS[i].id == id) {
            return &SERVO_SPECS[i];
        }
    }
    return NULL;
}

static bool is_continuous_servo(usaki_servo_id_t id)
{
    return id == USAKI_SERVO_LEFT_EAR ||
           id == USAKI_SERVO_RIGHT_EAR ||
           id == USAKI_SERVO_LEFT_ARM ||
           id == USAKI_SERVO_RIGHT_ARM;
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

static int clamp_angle_for_servo(usaki_servo_id_t id, int angle_deg)
{
    angle_deg = clamp_int(angle_deg, 0, 180);
    if (is_continuous_servo(id)) {
        return USAKI_SERVO_CENTER_DEG;
    }
    return angle_deg;
}

static uint16_t pulse_for_angle(const usaki_servo_spec_t *spec, int angle_deg)
{
    angle_deg = clamp_int(angle_deg, 0, 180);
    const uint32_t span = (uint32_t)spec->max_pulse_us - spec->min_pulse_us;
    return spec->min_pulse_us + (uint16_t)((span * angle_deg + 90) / 180);
}

static uint16_t clamp_pulse_for_servo(const usaki_servo_spec_t *spec, uint16_t pulse_us)
{
    if (pulse_us < spec->min_pulse_us) {
        pulse_us = spec->min_pulse_us;
    }
    if (pulse_us > spec->max_pulse_us) {
        pulse_us = spec->max_pulse_us;
    }

    return pulse_us;
}

static esp_err_t ensure_pca9685(void)
{
    if (s_pca9685 != NULL) {
        return ESP_OK;
    }

    const pca9685_config_t config = {
        .i2c_port = USAKI_SERVO_I2C_PORT,
        .sda_gpio = USAKI_SERVO_I2C_SDA_GPIO,
        .scl_gpio = USAKI_SERVO_I2C_SCL_GPIO,
        .i2c_freq_hz = USAKI_SERVO_I2C_FREQ_HZ,
        .i2c_addr = USAKI_PCA9685_I2C_ADDR,
        .pwm_freq_hz = USAKI_SERVO_PWM_FREQ_HZ,
    };

    ESP_RETURN_ON_ERROR(pca9685_create(&config, &s_pca9685), TAG, "pca9685 init failed");
    return ESP_OK;
}

esp_err_t usaki_servos_init(void)
{
    ESP_RETURN_ON_ERROR(ensure_pca9685(), TAG, "pca9685 init failed");
    return usaki_servos_center_all();
}

esp_err_t usaki_servos_init_outputs_disabled(void)
{
    ESP_RETURN_ON_ERROR(ensure_pca9685(), TAG, "pca9685 init failed");
    return usaki_servos_disable_all();
}

esp_err_t usaki_servos_deinit(void)
{
    esp_err_t err = pca9685_destroy(s_pca9685);
    s_pca9685 = NULL;
    return err;
}

esp_err_t usaki_servos_set_pulse_us(usaki_servo_id_t id, uint16_t pulse_us)
{
    ESP_RETURN_ON_FALSE(s_pca9685 != NULL, ESP_ERR_INVALID_STATE, TAG, "servos are not initialized");

    const usaki_servo_spec_t *spec = spec_for_id(id);
    ESP_RETURN_ON_FALSE(spec != NULL, ESP_ERR_INVALID_ARG, TAG, "invalid servo id");

    pulse_us = clamp_pulse_for_servo(spec, pulse_us);
    return pca9685_set_servo_pulse_us(s_pca9685, spec->channel, pulse_us);
}

esp_err_t usaki_servos_set_angle(usaki_servo_id_t id, uint8_t angle_deg)
{
    const usaki_servo_spec_t *spec = spec_for_id(id);
    ESP_RETURN_ON_FALSE(spec != NULL, ESP_ERR_INVALID_ARG, TAG, "invalid servo id");

    const int limited_angle_deg = clamp_angle_for_servo(id, angle_deg);
    const uint16_t pulse_us = pulse_for_angle(spec, limited_angle_deg);
    return usaki_servos_set_pulse_us(id, pulse_us);
}

esp_err_t usaki_servos_center(usaki_servo_id_t id)
{
    const usaki_servo_spec_t *spec = spec_for_id(id);
    ESP_RETURN_ON_FALSE(spec != NULL, ESP_ERR_INVALID_ARG, TAG, "invalid servo id");
    return usaki_servos_set_pulse_us(id, spec->center_pulse_us);
}

esp_err_t usaki_servos_center_all(void)
{
    for (size_t i = 0; i < sizeof(SERVO_SPECS) / sizeof(SERVO_SPECS[0]); ++i) {
        ESP_RETURN_ON_ERROR(usaki_servos_center(SERVO_SPECS[i].id), TAG, "center servo failed");
    }
    return ESP_OK;
}

esp_err_t usaki_servos_disable(usaki_servo_id_t id)
{
    ESP_RETURN_ON_FALSE(s_pca9685 != NULL, ESP_ERR_INVALID_STATE, TAG, "servos are not initialized");

    const usaki_servo_spec_t *spec = spec_for_id(id);
    ESP_RETURN_ON_FALSE(spec != NULL, ESP_ERR_INVALID_ARG, TAG, "invalid servo id");
    return pca9685_set_channel_off(s_pca9685, spec->channel);
}

esp_err_t usaki_servos_disable_all(void)
{
    for (size_t i = 0; i < sizeof(SERVO_SPECS) / sizeof(SERVO_SPECS[0]); ++i) {
        ESP_RETURN_ON_ERROR(usaki_servos_disable(SERVO_SPECS[i].id), TAG, "disable servo failed");
    }
    return ESP_OK;
}

const usaki_servo_spec_t *usaki_servos_get_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SERVO_SPECS) / sizeof(SERVO_SPECS[0]);
    }
    return SERVO_SPECS;
}
