#include "drivers/pca9685.h"

#include <math.h>
#include <stdlib.h>

#include "esp_check.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "pca9685";

#define PCA9685_MODE1 0x00
#define PCA9685_MODE2 0x01
#define PCA9685_LED0_ON_L 0x06
#define PCA9685_PRESCALE 0xFE

#define PCA9685_MODE1_RESTART 0x80
#define PCA9685_MODE1_SLEEP 0x10
#define PCA9685_MODE1_AI 0x20
#define PCA9685_MODE2_OUTDRV 0x04

#define PCA9685_OSC_CLOCK_HZ 25000000UL
#define PCA9685_TICKS_PER_CYCLE 4096
#define PCA9685_FULL_OFF 0x10

struct pca9685 {
    i2c_master_bus_handle_t bus;
    i2c_master_dev_handle_t dev;
    uint16_t pwm_freq_hz;
};

static esp_err_t write_reg(pca9685_handle_t handle, uint8_t reg, uint8_t value)
{
    uint8_t data[] = {reg, value};
    return i2c_master_transmit(handle->dev, data, sizeof(data), pdMS_TO_TICKS(100));
}

static esp_err_t read_reg(pca9685_handle_t handle, uint8_t reg, uint8_t *value)
{
    return i2c_master_transmit_receive(handle->dev, &reg, 1, value, 1, pdMS_TO_TICKS(100));
}

static uint8_t prescale_for_freq(uint16_t pwm_freq_hz)
{
    float prescale = (float)PCA9685_OSC_CLOCK_HZ;
    prescale /= (float)PCA9685_TICKS_PER_CYCLE;
    prescale /= (float)pwm_freq_hz;
    prescale -= 1.0f;
    return (uint8_t)(prescale + 0.5f);
}

esp_err_t pca9685_create(const pca9685_config_t *config, pca9685_handle_t *out_handle)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG, "config is null");
    ESP_RETURN_ON_FALSE(out_handle != NULL, ESP_ERR_INVALID_ARG, TAG, "out_handle is null");
    ESP_RETURN_ON_FALSE(config->pwm_freq_hz > 0, ESP_ERR_INVALID_ARG, TAG, "invalid pwm freq");

    pca9685_handle_t handle = calloc(1, sizeof(*handle));
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_NO_MEM, TAG, "alloc handle failed");
    handle->pwm_freq_hz = config->pwm_freq_hz;

    i2c_master_bus_config_t bus_config = {
        .i2c_port = config->i2c_port,
        .sda_io_num = config->sda_gpio,
        .scl_io_num = config->scl_gpio,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    esp_err_t ret = i2c_new_master_bus(&bus_config, &handle->bus);
    if (ret != ESP_OK) {
        free(handle);
        return ret;
    }

    i2c_device_config_t dev_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = config->i2c_addr,
        .scl_speed_hz = config->i2c_freq_hz,
    };
    ESP_GOTO_ON_ERROR(i2c_master_bus_add_device(handle->bus, &dev_config, &handle->dev),
                      fail,
                      TAG,
                      "add i2c device failed");

    uint8_t mode1 = 0;
    ESP_GOTO_ON_ERROR(read_reg(handle, PCA9685_MODE1, &mode1), fail, TAG, "read mode1 failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, PCA9685_MODE1, (mode1 & ~PCA9685_MODE1_RESTART) | PCA9685_MODE1_SLEEP),
                      fail,
                      TAG,
                      "sleep failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, PCA9685_PRESCALE, prescale_for_freq(config->pwm_freq_hz)),
                      fail,
                      TAG,
                      "set prescale failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, PCA9685_MODE2, PCA9685_MODE2_OUTDRV), fail, TAG, "set mode2 failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, PCA9685_MODE1, PCA9685_MODE1_AI), fail, TAG, "wake failed");
    vTaskDelay(pdMS_TO_TICKS(5));
    ESP_GOTO_ON_ERROR(write_reg(handle, PCA9685_MODE1, PCA9685_MODE1_AI | PCA9685_MODE1_RESTART),
                      fail,
                      TAG,
                      "restart failed");

    *out_handle = handle;
    return ESP_OK;

fail:
    if (handle->dev != NULL) {
        i2c_master_bus_rm_device(handle->dev);
    }
    if (handle->bus != NULL) {
        i2c_del_master_bus(handle->bus);
    }
    free(handle);
    return ret;
}

esp_err_t pca9685_set_pwm(pca9685_handle_t handle, uint8_t channel, uint16_t on_tick, uint16_t off_tick)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(channel < 16, ESP_ERR_INVALID_ARG, TAG, "invalid channel");
    ESP_RETURN_ON_FALSE(on_tick < PCA9685_TICKS_PER_CYCLE, ESP_ERR_INVALID_ARG, TAG, "invalid on tick");
    ESP_RETURN_ON_FALSE(off_tick < PCA9685_TICKS_PER_CYCLE, ESP_ERR_INVALID_ARG, TAG, "invalid off tick");

    uint8_t reg = PCA9685_LED0_ON_L + 4 * channel;
    uint8_t data[] = {
        reg,
        (uint8_t)(on_tick & 0xff),
        (uint8_t)(on_tick >> 8),
        (uint8_t)(off_tick & 0xff),
        (uint8_t)(off_tick >> 8),
    };
    return i2c_master_transmit(handle->dev, data, sizeof(data), pdMS_TO_TICKS(100));
}

esp_err_t pca9685_set_channel_off(pca9685_handle_t handle, uint8_t channel)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(channel < 16, ESP_ERR_INVALID_ARG, TAG, "invalid channel");

    uint8_t reg = PCA9685_LED0_ON_L + 4 * channel;
    uint8_t data[] = {
        reg,
        0,
        0,
        0,
        PCA9685_FULL_OFF,
    };
    return i2c_master_transmit(handle->dev, data, sizeof(data), pdMS_TO_TICKS(100));
}

esp_err_t pca9685_set_servo_pulse_us(pca9685_handle_t handle, uint8_t channel, uint16_t pulse_us)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");

    uint32_t off_tick = ((uint32_t)pulse_us * handle->pwm_freq_hz * PCA9685_TICKS_PER_CYCLE) / 1000000UL;
    if (off_tick >= PCA9685_TICKS_PER_CYCLE) {
        off_tick = PCA9685_TICKS_PER_CYCLE - 1;
    }
    return pca9685_set_pwm(handle, channel, 0, (uint16_t)off_tick);
}

esp_err_t pca9685_destroy(pca9685_handle_t handle)
{
    if (handle == NULL) {
        return ESP_OK;
    }
    esp_err_t ret = ESP_OK;
    if (handle->dev != NULL) {
        ret = i2c_master_bus_rm_device(handle->dev);
    }
    if (handle->bus != NULL) {
        esp_err_t bus_ret = i2c_del_master_bus(handle->bus);
        if (ret == ESP_OK) {
            ret = bus_ret;
        }
    }
    free(handle);
    return ret;
}
