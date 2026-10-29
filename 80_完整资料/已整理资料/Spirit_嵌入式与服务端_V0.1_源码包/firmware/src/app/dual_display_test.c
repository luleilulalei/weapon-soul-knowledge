#include "app/dual_display_test.h"

#include <stdio.h>

#include "board/usaki_board.h"
#include "drivers/gc9a01.h"
#include "esp_check.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#ifndef USAKI_LCD_ENABLE_RIGHT_DISPLAY
#define USAKI_LCD_ENABLE_RIGHT_DISPLAY 0
#endif

static esp_err_t draw_eye_test(gc9a01_handle_t eye, uint16_t bg, uint16_t pupil)
{
    ESP_RETURN_ON_ERROR(gc9a01_fill_screen(eye, bg), "dual_display", "fill screen failed");
    ESP_RETURN_ON_ERROR(gc9a01_fill_rect(eye, 86, 64, 68, 112, 0xffff), "dual_display", "draw sclera failed");
    ESP_RETURN_ON_ERROR(gc9a01_fill_rect(eye, 108, 94, 24, 52, pupil), "dual_display", "draw pupil failed");
    ESP_RETURN_ON_ERROR(gc9a01_fill_rect(eye, 114, 102, 8, 12, 0xffff), "dual_display", "draw highlight failed");
    return ESP_OK;
}

esp_err_t dual_display_test_run(void)
{
    const gc9a01_bus_config_t left_bus_config = {
        .host_id = USAKI_LCD_LEFT_SPI_HOST,
        .sclk_gpio = USAKI_LCD_LEFT_SCLK_GPIO,
        .mosi_gpio = USAKI_LCD_LEFT_MOSI_GPIO,
        .miso_gpio = GPIO_NUM_NC,
        .max_transfer_sz = USAKI_LCD_WIDTH * USAKI_LCD_DMA_LINES * sizeof(uint16_t),
    };

#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    const gc9a01_bus_config_t right_bus_config = {
        .host_id = USAKI_LCD_RIGHT_SPI_HOST,
        .sclk_gpio = USAKI_LCD_RIGHT_SCLK_GPIO,
        .mosi_gpio = USAKI_LCD_RIGHT_MOSI_GPIO,
        .miso_gpio = GPIO_NUM_NC,
        .max_transfer_sz = USAKI_LCD_WIDTH * USAKI_LCD_DMA_LINES * sizeof(uint16_t),
    };
#endif

    const gc9a01_config_t left_config = {
        .host_id = USAKI_LCD_LEFT_SPI_HOST,
        .cs_gpio = USAKI_LCD_LEFT_CS_GPIO,
        .dc_gpio = USAKI_LCD_LEFT_DC_GPIO,
        .reset_gpio = USAKI_LCD_LEFT_RST_GPIO,
        .pixel_clock_hz = USAKI_LCD_PIXEL_CLOCK_HZ,
        .madctl = USAKI_LCD_MADCTL,
    };

#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    const gc9a01_config_t right_config = {
        .host_id = USAKI_LCD_RIGHT_SPI_HOST,
        .cs_gpio = USAKI_LCD_RIGHT_CS_GPIO,
        .dc_gpio = USAKI_LCD_RIGHT_DC_GPIO,
        .reset_gpio = USAKI_LCD_RIGHT_RST_GPIO,
        .pixel_clock_hz = USAKI_LCD_PIXEL_CLOCK_HZ,
        .madctl = USAKI_LCD_MADCTL,
    };
#endif

    gc9a01_handle_t left_eye = NULL;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    gc9a01_handle_t right_eye = NULL;
#endif

    printf("GC9A01 display test starting.\n");
    ESP_RETURN_ON_ERROR(gc9a01_bus_init(&left_bus_config), "dual_display", "left lcd bus init failed");
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_RETURN_ON_ERROR(gc9a01_bus_init(&right_bus_config), "dual_display", "right lcd bus init failed");
#endif
    ESP_RETURN_ON_ERROR(gc9a01_create(&left_config, &left_eye), "dual_display", "left eye init failed");
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_RETURN_ON_ERROR(gc9a01_create(&right_config, &right_eye), "dual_display", "right eye init failed");
#endif

    ESP_RETURN_ON_ERROR(draw_eye_test(left_eye, 0x001f, 0x0000), "dual_display", "draw left failed");
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_RETURN_ON_ERROR(draw_eye_test(right_eye, 0xf800, 0x0000), "dual_display", "draw right failed");
#endif
    ESP_RETURN_ON_ERROR(gc9a01_display_on(left_eye), "dual_display", "left display on failed");
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_RETURN_ON_ERROR(gc9a01_display_on(right_eye), "dual_display", "right display on failed");
#endif
    printf("GC9A01 eye displayed.\n");

    uint32_t heartbeat = 0;
    while (1) {
        printf("GC9A01 heartbeat %lu\n", (unsigned long)heartbeat++);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
