#include "drivers/mpr121.h"

#include <stdlib.h>

#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "mpr121";

#define MPR121_TOUCH_STATUS_L 0x00
#define MPR121_FILTERED_DATA_L_BASE 0x04
#define MPR121_BASELINE_BASE 0x1E
#define MPR121_MHDR 0x2B
#define MPR121_NHDR 0x2C
#define MPR121_NCLR 0x2D
#define MPR121_FDLR 0x2E
#define MPR121_MHDF 0x2F
#define MPR121_NHDF 0x30
#define MPR121_NCLF 0x31
#define MPR121_FDLF 0x32
#define MPR121_NHDT 0x33
#define MPR121_NCLT 0x34
#define MPR121_FDLT 0x35
#define MPR121_TOUCH_THRESHOLD_BASE 0x41
#define MPR121_RELEASE_THRESHOLD_BASE 0x42
#define MPR121_DEBOUNCE 0x5B
#define MPR121_CONFIG1 0x5C
#define MPR121_CONFIG2 0x5D
#define MPR121_ELECTRODE_CONFIG 0x5E
#define MPR121_SOFTRESET 0x80
#define MPR121_ENABLED_ELECTRODES 8
#define MPR121_ELECTRODE_CONFIG_BASELINE_TRACKING 0x80

struct mpr121 {
    i2c_master_bus_handle_t bus;
    i2c_master_dev_handle_t dev;
};

static esp_err_t write_reg(mpr121_handle_t handle, uint8_t reg, uint8_t value)
{
    uint8_t data[] = {reg, value};
    return i2c_master_transmit(handle->dev, data, sizeof(data), 100);
}

static esp_err_t read_reg(mpr121_handle_t handle, uint8_t reg, uint8_t *value)
{
    return i2c_master_transmit_receive(handle->dev, &reg, 1, value, 1, 100);
}

static esp_err_t read_u16(mpr121_handle_t handle, uint8_t reg, uint16_t *value)
{
    uint8_t data[2] = {0};
    esp_err_t err = i2c_master_transmit_receive(handle->dev, &reg, 1, data, sizeof(data), 100);
    if (err != ESP_OK) {
        return err;
    }
    *value = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
    return ESP_OK;
}

esp_err_t mpr121_create(const mpr121_config_t *config, mpr121_handle_t *out_handle)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG, "config is null");
    ESP_RETURN_ON_FALSE(out_handle != NULL, ESP_ERR_INVALID_ARG, TAG, "out_handle is null");

    mpr121_handle_t handle = calloc(1, sizeof(*handle));
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_NO_MEM, TAG, "alloc handle failed");

    i2c_master_bus_config_t bus_config = {
        .i2c_port = config->i2c_port,
        .sda_io_num = config->sda_gpio,
        .scl_io_num = config->scl_gpio,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .trans_queue_depth = 0,
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

    ret = i2c_master_probe(handle->bus, config->i2c_addr, 100);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG,
                 "probe addr 0x%02x failed: %s. Check VCC=3.3V, GND, SDA=GPIO%d, SCL=GPIO%d, ADDR=GND.",
                 config->i2c_addr,
                 esp_err_to_name(ret),
                 config->sda_gpio,
                 config->scl_gpio);
        goto fail;
    }

    ret = write_reg(handle, MPR121_SOFTRESET, 0x63);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "soft reset failed: %s", esp_err_to_name(ret));
        goto fail;
    }
    vTaskDelay(pdMS_TO_TICKS(2));

    uint8_t config2 = 0;
    ESP_GOTO_ON_ERROR(read_reg(handle, MPR121_CONFIG2, &config2), fail, TAG, "probe failed");

    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_ELECTRODE_CONFIG, 0x00), fail, TAG, "stop electrodes failed");

    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_MHDR, 0x01), fail, TAG, "set MHDR failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_NHDR, 0x01), fail, TAG, "set NHDR failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_NCLR, 0x0E), fail, TAG, "set NCLR failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_FDLR, 0x00), fail, TAG, "set FDLR failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_MHDF, 0x01), fail, TAG, "set MHDF failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_NHDF, 0x05), fail, TAG, "set NHDF failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_NCLF, 0x01), fail, TAG, "set NCLF failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_FDLF, 0x00), fail, TAG, "set FDLF failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_NHDT, 0x00), fail, TAG, "set NHDT failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_NCLT, 0x00), fail, TAG, "set NCLT failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_FDLT, 0x00), fail, TAG, "set FDLT failed");

    for (uint8_t electrode = 0; electrode < 12; ++electrode) {
        ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_TOUCH_THRESHOLD_BASE + electrode * 2, 6),
                          fail,
                          TAG,
                          "set touch threshold failed");
        ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_RELEASE_THRESHOLD_BASE + electrode * 2, 3),
                          fail,
                          TAG,
                          "set release threshold failed");
    }

    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_DEBOUNCE, 0x11), fail, TAG, "set debounce failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_CONFIG1, 0x10), fail, TAG, "set config1 failed");
    ESP_GOTO_ON_ERROR(write_reg(handle, MPR121_CONFIG2, 0x20), fail, TAG, "set config2 failed");
    ESP_GOTO_ON_ERROR(write_reg(handle,
                                MPR121_ELECTRODE_CONFIG,
                                MPR121_ELECTRODE_CONFIG_BASELINE_TRACKING | MPR121_ENABLED_ELECTRODES),
                      fail,
                      TAG,
                      "enable electrodes failed");
    vTaskDelay(pdMS_TO_TICKS(500));

    *out_handle = handle;
    return ESP_OK;

fail:
    mpr121_destroy(handle);
    return ret;
}

esp_err_t mpr121_read_register(mpr121_handle_t handle, uint8_t reg, uint8_t *value)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(value != NULL, ESP_ERR_INVALID_ARG, TAG, "value is null");
    return read_reg(handle, reg, value);
}

esp_err_t mpr121_read_touched(mpr121_handle_t handle, uint16_t *touched_mask)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(touched_mask != NULL, ESP_ERR_INVALID_ARG, TAG, "touched_mask is null");

    uint16_t value = 0;
    ESP_RETURN_ON_ERROR(read_u16(handle, MPR121_TOUCH_STATUS_L, &value), TAG, "read touch status failed");
    *touched_mask = value & 0x0FFF;
    return ESP_OK;
}

esp_err_t mpr121_read_electrode(mpr121_handle_t handle, uint8_t electrode, uint16_t *filtered, uint8_t *baseline)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(electrode < 12, ESP_ERR_INVALID_ARG, TAG, "invalid electrode");

    if (filtered != NULL) {
        ESP_RETURN_ON_ERROR(read_u16(handle, MPR121_FILTERED_DATA_L_BASE + electrode * 2, filtered),
                            TAG,
                            "read filtered failed");
    }
    if (baseline != NULL) {
        ESP_RETURN_ON_ERROR(read_reg(handle, MPR121_BASELINE_BASE + electrode, baseline),
                            TAG,
                            "read baseline failed");
    }
    return ESP_OK;
}

esp_err_t mpr121_destroy(mpr121_handle_t handle)
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
