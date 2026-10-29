#include "drivers/gc9a01.h"

#include <stdlib.h>

#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_types.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

static const char *TAG = "gc9a01";

struct gc9a01 {
    esp_lcd_panel_io_handle_t io;
    gc9a01_config_t config;
    SemaphoreHandle_t color_done_sem;
    uint16_t *line_buffer;
    size_t line_buffer_pixels;
};

enum { GC9A01_LINES_PER_CHUNK = 20 };

typedef struct {
    uint8_t cmd;
    const uint8_t *data;
    uint8_t data_len;
    uint16_t delay_ms;
} gc9a01_init_cmd_t;

static uint16_t swap_rgb565(uint16_t color)
{
    return (uint16_t)((color << 8) | (color >> 8));
}

static esp_err_t tx_param(gc9a01_handle_t handle, uint8_t cmd, const void *data, size_t data_len)
{
    return esp_lcd_panel_io_tx_param(handle->io, cmd, data, data_len);
}

static bool on_color_trans_done(esp_lcd_panel_io_handle_t panel_io,
                                esp_lcd_panel_io_event_data_t *edata,
                                void *user_ctx)
{
    (void)panel_io;
    (void)edata;

    gc9a01_handle_t handle = (gc9a01_handle_t)user_ctx;
    BaseType_t need_yield = pdFALSE;
    xSemaphoreGiveFromISR(handle->color_done_sem, &need_yield);
    return need_yield == pdTRUE;
}

static esp_err_t set_window(gc9a01_handle_t handle, int x0, int y0, int x1, int y1)
{
    uint8_t caset[] = {
        (uint8_t)(x0 >> 8),
        (uint8_t)(x0 & 0xff),
        (uint8_t)(x1 >> 8),
        (uint8_t)(x1 & 0xff),
    };
    uint8_t raset[] = {
        (uint8_t)(y0 >> 8),
        (uint8_t)(y0 & 0xff),
        (uint8_t)(y1 >> 8),
        (uint8_t)(y1 & 0xff),
    };

    ESP_RETURN_ON_ERROR(tx_param(handle, 0x2A, caset, sizeof(caset)), TAG, "set column failed");
    ESP_RETURN_ON_ERROR(tx_param(handle, 0x2B, raset, sizeof(raset)), TAG, "set row failed");
    return ESP_OK;
}

static esp_err_t send_init_sequence(gc9a01_handle_t handle)
{
    const uint8_t eb[] = {0x14};
    const uint8_t c_84[] = {0x40};
    const uint8_t c_85[] = {0xff};
    const uint8_t c_86[] = {0xff};
    const uint8_t c_87[] = {0xff};
    const uint8_t c_88[] = {0x0a};
    const uint8_t c_89[] = {0x21};
    const uint8_t c_8a[] = {0x00};
    const uint8_t c_8b[] = {0x80};
    const uint8_t c_8c[] = {0x01};
    const uint8_t c_8d[] = {0x01};
    const uint8_t c_8e[] = {0xff};
    const uint8_t c_8f[] = {0xff};
    const uint8_t b6[] = {0x00, 0x00};
    const uint8_t madctl[] = {handle->config.madctl};
    const uint8_t colmod[] = {0x05};
    const uint8_t c_90[] = {0x08, 0x08, 0x08, 0x08};
    const uint8_t bd[] = {0x06};
    const uint8_t bc[] = {0x00};
    const uint8_t ff[] = {0x60, 0x01, 0x04};
    const uint8_t c3[] = {0x13};
    const uint8_t c4[] = {0x13};
    const uint8_t c9[] = {0x22};
    const uint8_t be[] = {0x11};
    const uint8_t e1[] = {0x10, 0x0e};
    const uint8_t df[] = {0x21, 0x0c, 0x02};
    const uint8_t f0[] = {0x45, 0x09, 0x08, 0x08, 0x26, 0x2a};
    const uint8_t f1[] = {0x43, 0x70, 0x72, 0x36, 0x37, 0x6f};
    const uint8_t f2[] = {0x45, 0x09, 0x08, 0x08, 0x26, 0x2a};
    const uint8_t f3[] = {0x43, 0x70, 0x72, 0x36, 0x37, 0x6f};
    const uint8_t ed[] = {0x1b, 0x0b};
    const uint8_t ae[] = {0x77};
    const uint8_t cd[] = {0x63};
    const uint8_t c_70[] = {0x07, 0x07, 0x04, 0x0e, 0x0f, 0x09, 0x07, 0x08, 0x03};
    const uint8_t e8[] = {0x34};
    const uint8_t c_62[] = {0x18, 0x0d, 0x71, 0xed, 0x70, 0x70, 0x18, 0x0f, 0x71, 0xef, 0x70, 0x70};
    const uint8_t c_63[] = {0x18, 0x11, 0x71, 0xf1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xf3, 0x70, 0x70};
    const uint8_t c_64[] = {0x28, 0x29, 0xf1, 0x01, 0xf1, 0x00, 0x07};
    const uint8_t c_66[] = {0x3c, 0x00, 0xcd, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00};
    const uint8_t c_67[] = {0x00, 0x3c, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98};
    const uint8_t c_74[] = {0x10, 0x85, 0x80, 0x00, 0x00, 0x4e, 0x00};
    const uint8_t c_98[] = {0x3e, 0x07};

    const gc9a01_init_cmd_t init[] = {
        {0xEF, NULL, 0, 0},
        {0xEB, eb, sizeof(eb), 0},
        {0xFE, NULL, 0, 0},
        {0xEF, NULL, 0, 0},
        {0x84, c_84, sizeof(c_84), 0},
        {0x85, c_85, sizeof(c_85), 0},
        {0x86, c_86, sizeof(c_86), 0},
        {0x87, c_87, sizeof(c_87), 0},
        {0x88, c_88, sizeof(c_88), 0},
        {0x89, c_89, sizeof(c_89), 0},
        {0x8A, c_8a, sizeof(c_8a), 0},
        {0x8B, c_8b, sizeof(c_8b), 0},
        {0x8C, c_8c, sizeof(c_8c), 0},
        {0x8D, c_8d, sizeof(c_8d), 0},
        {0x8E, c_8e, sizeof(c_8e), 0},
        {0x8F, c_8f, sizeof(c_8f), 0},
        {0xB6, b6, sizeof(b6), 0},
        {0x36, madctl, sizeof(madctl), 0},
        {0x3A, colmod, sizeof(colmod), 0},
        {0x90, c_90, sizeof(c_90), 0},
        {0xBD, bd, sizeof(bd), 0},
        {0xBC, bc, sizeof(bc), 0},
        {0xFF, ff, sizeof(ff), 0},
        {0xC3, c3, sizeof(c3), 0},
        {0xC4, c4, sizeof(c4), 0},
        {0xC9, c9, sizeof(c9), 0},
        {0xBE, be, sizeof(be), 0},
        {0xE1, e1, sizeof(e1), 0},
        {0xDF, df, sizeof(df), 0},
        {0xF0, f0, sizeof(f0), 0},
        {0xF1, f1, sizeof(f1), 0},
        {0xF2, f2, sizeof(f2), 0},
        {0xF3, f3, sizeof(f3), 0},
        {0xED, ed, sizeof(ed), 0},
        {0xAE, ae, sizeof(ae), 0},
        {0xCD, cd, sizeof(cd), 0},
        {0x70, c_70, sizeof(c_70), 0},
        {0xE8, e8, sizeof(e8), 0},
        {0x62, c_62, sizeof(c_62), 0},
        {0x63, c_63, sizeof(c_63), 0},
        {0x64, c_64, sizeof(c_64), 0},
        {0x66, c_66, sizeof(c_66), 0},
        {0x67, c_67, sizeof(c_67), 0},
        {0x74, c_74, sizeof(c_74), 0},
        {0x98, c_98, sizeof(c_98), 0},
        {0x21, NULL, 0, 0},
        {0x11, NULL, 0, 120},
        {0x29, NULL, 0, 20},
    };

    for (size_t i = 0; i < sizeof(init) / sizeof(init[0]); ++i) {
        ESP_RETURN_ON_ERROR(tx_param(handle, init[i].cmd, init[i].data, init[i].data_len),
                            TAG,
                            "init cmd failed");
        if (init[i].delay_ms > 0) {
            vTaskDelay(pdMS_TO_TICKS(init[i].delay_ms));
        }
    }
    return ESP_OK;
}

esp_err_t gc9a01_bus_init(const gc9a01_bus_config_t *config)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG, "config is null");

    spi_bus_config_t buscfg = {
        .sclk_io_num = config->sclk_gpio,
        .mosi_io_num = config->mosi_gpio,
        .miso_io_num = config->miso_gpio,
        .quadwp_io_num = GPIO_NUM_NC,
        .quadhd_io_num = GPIO_NUM_NC,
        .max_transfer_sz = config->max_transfer_sz,
    };

    esp_err_t err = spi_bus_initialize(config->host_id, &buscfg, SPI_DMA_CH_AUTO);
    if (err == ESP_ERR_INVALID_STATE) {
        ESP_LOGW(TAG, "SPI bus already initialized");
        return ESP_OK;
    }
    return err;
}

esp_err_t gc9a01_create(const gc9a01_config_t *config, gc9a01_handle_t *out_handle)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG, "config is null");
    ESP_RETURN_ON_FALSE(out_handle != NULL, ESP_ERR_INVALID_ARG, TAG, "out_handle is null");

    gc9a01_handle_t handle = calloc(1, sizeof(*handle));
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_NO_MEM, TAG, "alloc handle failed");
    handle->config = *config;
    handle->color_done_sem = xSemaphoreCreateBinary();
    if (handle->color_done_sem == NULL) {
        free(handle);
        return ESP_ERR_NO_MEM;
    }
    handle->line_buffer_pixels = GC9A01_WIDTH * GC9A01_LINES_PER_CHUNK;
    handle->line_buffer = heap_caps_malloc(handle->line_buffer_pixels * sizeof(handle->line_buffer[0]),
                                           MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (handle->line_buffer == NULL) {
        vSemaphoreDelete(handle->color_done_sem);
        free(handle);
        return ESP_ERR_NO_MEM;
    }

    esp_lcd_panel_io_spi_config_t io_config = {
        .cs_gpio_num = config->cs_gpio,
        .dc_gpio_num = config->dc_gpio,
        .spi_mode = 0,
        .pclk_hz = config->pixel_clock_hz,
        .trans_queue_depth = 4,
        .on_color_trans_done = on_color_trans_done,
        .user_ctx = handle,
        .lcd_cmd_bits = GC9A01_CMD_BITS,
        .lcd_param_bits = GC9A01_PARAM_BITS,
    };

    esp_err_t ret = esp_lcd_new_panel_io_spi(config->host_id, &io_config, &handle->io);
    if (ret != ESP_OK) {
        heap_caps_free(handle->line_buffer);
        vSemaphoreDelete(handle->color_done_sem);
        free(handle);
        return ret;
    }

    gpio_config_t rst_cfg = {
        .pin_bit_mask = 1ULL << config->reset_gpio,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_GOTO_ON_ERROR(gpio_config(&rst_cfg), fail, TAG, "reset gpio config failed");
    gpio_set_level(config->reset_gpio, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(config->reset_gpio, 1);
    vTaskDelay(pdMS_TO_TICKS(120));

    ESP_GOTO_ON_ERROR(send_init_sequence(handle), fail, TAG, "init sequence failed");
    *out_handle = handle;
    return ESP_OK;

fail:
    esp_lcd_panel_io_del(handle->io);
    heap_caps_free(handle->line_buffer);
    vSemaphoreDelete(handle->color_done_sem);
    free(handle);
    return ret;
}

esp_err_t gc9a01_fill_rect(gc9a01_handle_t handle, int x, int y, int width, int height, uint16_t rgb565)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(width > 0 && height > 0, ESP_ERR_INVALID_ARG, TAG, "invalid size");

    int x0 = x < 0 ? 0 : x;
    int y0 = y < 0 ? 0 : y;
    int x1 = x + width - 1;
    int y1 = y + height - 1;
    if (x1 >= GC9A01_WIDTH) {
        x1 = GC9A01_WIDTH - 1;
    }
    if (y1 >= GC9A01_HEIGHT) {
        y1 = GC9A01_HEIGHT - 1;
    }
    ESP_RETURN_ON_FALSE(x0 <= x1 && y0 <= y1, ESP_ERR_INVALID_ARG, TAG, "rect outside screen");

    const int clipped_width = x1 - x0 + 1;
    const int clipped_height = y1 - y0 + 1;
    const uint16_t wire_color = swap_rgb565(rgb565);

    for (int i = 0; i < clipped_width * GC9A01_LINES_PER_CHUNK; ++i) {
        handle->line_buffer[i] = wire_color;
    }

    for (int y_offset = 0; y_offset < clipped_height; y_offset += GC9A01_LINES_PER_CHUNK) {
        const int rows_left = clipped_height - y_offset;
        const int rows_now = rows_left > GC9A01_LINES_PER_CHUNK ? GC9A01_LINES_PER_CHUNK : rows_left;
        const int chunk_y0 = y0 + y_offset;
        const int chunk_y1 = chunk_y0 + rows_now - 1;

        ESP_RETURN_ON_ERROR(set_window(handle, x0, chunk_y0, x1, chunk_y1), TAG, "set window failed");
        xSemaphoreTake(handle->color_done_sem, 0);
        esp_err_t ret = esp_lcd_panel_io_tx_color(handle->io,
                                                  0x2C,
                                                  handle->line_buffer,
                                                  clipped_width * rows_now * sizeof(handle->line_buffer[0]));
        ESP_RETURN_ON_ERROR(ret, TAG, "tx color failed");
        xSemaphoreTake(handle->color_done_sem, portMAX_DELAY);
    }

    return ESP_OK;
}


esp_err_t gc9a01_draw_bitmap(gc9a01_handle_t handle, int x0, int y0, int x1, int y1, const uint16_t *rgb565_pixels)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(rgb565_pixels != NULL, ESP_ERR_INVALID_ARG, TAG, "pixels is null");
    ESP_RETURN_ON_FALSE(x0 >= 0 && y0 >= 0 && x1 < GC9A01_WIDTH && y1 < GC9A01_HEIGHT && x0 <= x1 && y0 <= y1,
                        ESP_ERR_INVALID_ARG,
                        TAG,
                        "invalid bitmap area");

    const int width = x1 - x0 + 1;
    const int height = y1 - y0 + 1;
    ESP_RETURN_ON_FALSE((size_t)width <= handle->line_buffer_pixels,
                        ESP_ERR_INVALID_ARG,
                        TAG,
                        "line is larger than internal DMA buffer");

    for (int row = 0; row < height; row += GC9A01_LINES_PER_CHUNK) {
        const int rows_left = height - row;
        const int rows_now = rows_left > GC9A01_LINES_PER_CHUNK ? GC9A01_LINES_PER_CHUNK : rows_left;
        const int pixels_now = width * rows_now;

        for (int i = 0; i < pixels_now; ++i) {
            handle->line_buffer[i] = swap_rgb565(rgb565_pixels[row * width + i]);
        }

        ESP_RETURN_ON_ERROR(set_window(handle, x0, y0 + row, x1, y0 + row + rows_now - 1), TAG, "set window failed");
        xSemaphoreTake(handle->color_done_sem, 0);
        esp_err_t ret = esp_lcd_panel_io_tx_color(handle->io,
                                                  0x2C,
                                                  handle->line_buffer,
                                                  pixels_now * sizeof(handle->line_buffer[0]));
        ESP_RETURN_ON_ERROR(ret, TAG, "tx bitmap failed");
        xSemaphoreTake(handle->color_done_sem, portMAX_DELAY);
    }

    return ESP_OK;
}

esp_err_t gc9a01_fill_screen(gc9a01_handle_t handle, uint16_t rgb565)
{
    return gc9a01_fill_rect(handle, 0, 0, GC9A01_WIDTH, GC9A01_HEIGHT, rgb565);
}

esp_err_t gc9a01_display_on(gc9a01_handle_t handle)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");

    ESP_RETURN_ON_ERROR(tx_param(handle, 0x29, NULL, 0), TAG, "display on failed");
    vTaskDelay(pdMS_TO_TICKS(20));
    return ESP_OK;
}

esp_err_t gc9a01_destroy(gc9a01_handle_t handle)
{
    if (handle == NULL) {
        return ESP_OK;
    }
    esp_err_t err = esp_lcd_panel_io_del(handle->io);
    heap_caps_free(handle->line_buffer);
    vSemaphoreDelete(handle->color_done_sem);
    free(handle);
    return err;
}
