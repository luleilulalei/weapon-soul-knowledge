#include "app/touch_self_test.h"

#include <stdio.h>

#include "board/usaki_board.h"
#include "driver/i2c_master.h"
#include "drivers/mpr121.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "touch_self_test";

static void print_mpr121_reg(mpr121_handle_t touch, uint8_t reg, const char *name)
{
    uint8_t value = 0;
    esp_err_t err = mpr121_read_register(touch, reg, &value);
    if (err == ESP_OK) {
        printf("MPR121 reg %-10s 0x%02x = 0x%02x\n", name, reg, value);
    } else {
        printf("MPR121 reg %-10s 0x%02x read failed: %s\n", name, reg, esp_err_to_name(err));
    }
}

static void scan_i2c_bus(i2c_port_num_t port, gpio_num_t sda_gpio, gpio_num_t scl_gpio, const char *label)
{
    i2c_master_bus_handle_t bus = NULL;
    const i2c_master_bus_config_t bus_config = {
        .i2c_port = port,
        .sda_io_num = sda_gpio,
        .scl_io_num = scl_gpio,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .trans_queue_depth = 0,
        .flags.enable_internal_pullup = true,
    };

    esp_err_t err = i2c_new_master_bus(&bus_config, &bus);
    if (err != ESP_OK) {
        printf("I2C scan %s: create bus failed: %s\n", label, esp_err_to_name(err));
        return;
    }

    printf("I2C scan %s: SDA=GPIO%d SCL=GPIO%d\n", label, sda_gpio, scl_gpio);
    bool found = false;
    for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
        err = i2c_master_probe(bus, addr, 50);
        if (err == ESP_OK) {
            printf("  found device at 0x%02x%s\n",
                   addr,
                   (addr >= 0x5A && addr <= 0x5D) ? "  <-- possible MPR121" : "");
            found = true;
        }
    }
    if (!found) {
        printf("  no I2C device found\n");
    }

    esp_err_t del_err = i2c_del_master_bus(bus);
    if (del_err != ESP_OK) {
        ESP_LOGW(TAG, "delete scan bus failed: %s", esp_err_to_name(del_err));
    }
}

esp_err_t touch_self_test_run(void)
{
    const mpr121_config_t config = {
        .i2c_port = USAKI_TOUCH_I2C_PORT,
        .sda_gpio = USAKI_TOUCH_I2C_SDA_GPIO,
        .scl_gpio = USAKI_TOUCH_I2C_SCL_GPIO,
        .i2c_freq_hz = USAKI_TOUCH_I2C_FREQ_HZ,
        .i2c_addr = USAKI_TOUCH_I2C_ADDR,
    };

    printf("MPR121 touch self-test starting...\n");
    printf("Wiring: VCC=3.3V, GND=GND, SDA=GPIO%d, SCL=GPIO%d, IRQ=GPIO%d, ADDR=GND(addr=0x%02x)\n",
           USAKI_TOUCH_I2C_SDA_GPIO,
           USAKI_TOUCH_I2C_SCL_GPIO,
           USAKI_TOUCH_IRQ_GPIO,
           USAKI_TOUCH_I2C_ADDR);
    printf("Connect your first copper foil pad to ELE%d through a 100 ohm series resistor.\n",
           USAKI_TOUCH_HEAD_FRONT_ELECTRODE);

    scan_i2c_bus(USAKI_TOUCH_I2C_PORT,
                 USAKI_TOUCH_I2C_SDA_GPIO,
                 USAKI_TOUCH_I2C_SCL_GPIO,
                 "normal wiring");
    scan_i2c_bus(USAKI_TOUCH_I2C_PORT,
                 USAKI_TOUCH_I2C_SCL_GPIO,
                 USAKI_TOUCH_I2C_SDA_GPIO,
                 "SDA/SCL swapped check");

    mpr121_handle_t touch = NULL;
    ESP_RETURN_ON_ERROR(mpr121_create(&config, &touch), TAG, "mpr121 init failed");

    printf("Waiting 2 seconds for MPR121 ELE0 baseline to settle...\n");
    vTaskDelay(pdMS_TO_TICKS(2000));
    print_mpr121_reg(touch, 0x5E, "ELE_CFG");
    print_mpr121_reg(touch, 0x5C, "CONFIG1");
    print_mpr121_reg(touch, 0x5D, "CONFIG2");
    print_mpr121_reg(touch, 0x41, "ELE0_TTH");
    print_mpr121_reg(touch, 0x42, "ELE0_RTH");
    print_mpr121_reg(touch, 0x02, "OOR_L");
    print_mpr121_reg(touch, 0x03, "OOR_H");

    bool last_touched = false;
    uint32_t heartbeat = 0;
    while (1) {
        uint16_t touched_mask = 0;
        uint16_t filtered = 0;
        uint8_t baseline = 0;
        ESP_RETURN_ON_ERROR(mpr121_read_touched(touch, &touched_mask), TAG, "read touched failed");
        ESP_RETURN_ON_ERROR(mpr121_read_electrode(touch,
                                                  USAKI_TOUCH_HEAD_FRONT_ELECTRODE,
                                                  &filtered,
                                                  &baseline),
                            TAG,
                            "read electrode failed");

        const bool touched = (touched_mask & (1U << USAKI_TOUCH_HEAD_FRONT_ELECTRODE)) != 0;
        if (touched != last_touched) {
            printf("ELE%d %s  filtered=%u baseline=%u raw_mask=0x%03x\n",
                   USAKI_TOUCH_HEAD_FRONT_ELECTRODE,
                   touched ? "TOUCHED" : "released",
                   filtered,
                   baseline,
                   touched_mask);
            last_touched = touched;
        }

        if ((heartbeat++ % 10) == 0) {
            printf("ELE%d state=%d filtered=%u baseline_raw=%u baseline=%u delta=%d raw_mask=0x%03x\n",
                   USAKI_TOUCH_HEAD_FRONT_ELECTRODE,
                   touched ? 1 : 0,
                   filtered,
                   baseline,
                   (uint16_t)baseline << 2,
                   (int)((uint16_t)baseline << 2) - (int)filtered,
                   touched_mask);
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
