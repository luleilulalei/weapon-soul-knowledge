#include "drivers/spirit_pdm.h"
#include "board/usaki_board.h"
#include "driver/i2s_pdm.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
static i2s_chan_handle_t rx;
static SemaphoreHandle_t lock;
static bool enabled;
esp_err_t spirit_pdm_init(void) {
    if (rx) return ESP_OK;
    if (!lock) lock = xSemaphoreCreateMutex();
    if (!lock) return ESP_ERR_NO_MEM;
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    chan.dma_desc_num = USAKI_MIC_DMA_DESC_NUM;
    chan.dma_frame_num = USAKI_MIC_READ_FRAMES;
    esp_err_t err = i2s_new_channel(&chan, NULL, &rx);
    if (err != ESP_OK) return err;
    i2s_pdm_rx_config_t cfg = {
        .clk_cfg = I2S_PDM_RX_CLK_DEFAULT_CONFIG(USAKI_MIC_SAMPLE_RATE_HZ),
        .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.clk = USAKI_MIC_BCLK_GPIO, .din = USAKI_MIC_DATA_GPIO, .invert_flags = {.clk_inv = false}},
    };
    // L/R strap/clock-edge selection must be confirmed on the production PCB.
    err = i2s_channel_init_pdm_rx_mode(rx, &cfg);
    if (err != ESP_OK) { i2s_del_channel(rx); rx = NULL; }
    return err;
}
esp_err_t spirit_pdm_enable(bool value) {
    if (!rx) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(lock, portMAX_DELAY);
    esp_err_t err = ESP_OK;
    if (value != enabled) {
        err = value ? i2s_channel_enable(rx) : i2s_channel_disable(rx);
        if (err == ESP_OK) enabled = value;
    }
    xSemaphoreGive(lock);
    return err;
}
esp_err_t spirit_pdm_read(int16_t *samples, size_t count, size_t *read_count) {
    if (!rx || !samples || !read_count) return ESP_ERR_INVALID_ARG;
    *read_count = 0;
    xSemaphoreTake(lock, portMAX_DELAY);
    size_t bytes = 0;
    esp_err_t err = enabled ? i2s_channel_read(rx, samples, count * sizeof(int16_t), &bytes, 100) : ESP_ERR_INVALID_STATE;
    *read_count = bytes / sizeof(int16_t);
    xSemaphoreGive(lock);
    return err;
}
void spirit_pdm_deinit(void) {
    if (!rx) return;
    (void)spirit_pdm_enable(false);
    i2s_del_channel(rx); rx = NULL;
}
