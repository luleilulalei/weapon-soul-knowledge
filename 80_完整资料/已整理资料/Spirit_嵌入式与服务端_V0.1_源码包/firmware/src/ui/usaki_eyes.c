#include "ui/usaki_eyes_internal.h"
#include "app/spirit_privacy.h"
#include "app/voice_runtime.h"

#include <stdbool.h>
#include <stdint.h>

#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

static const char *TAG = "usaki_eyes";

#define EYE_TASK_STACK_BYTES (14 * 1024)
#define EYE_TASK_PRIORITY 4
#define EYE_TASK_CORE 0
#define EYE_TICK_MS 1
#define EYE_FRAME_MS 10
#define EYE_RENDER_SKIP 1
#define EYE_COMMAND_QUEUE_LEN 16
#define EYE_COMMAND_POST_WAIT_MS 20

#define EYE_BLINK_CLOSE_MS 172
#define EYE_BLINK_HOLD_MS 44
#define EYE_BLINK_OPEN_MS 318
#define EYE_RANDOM_BLINK_MIN_MS 2200
#define EYE_RANDOM_BLINK_SPAN_MS 4200
#define EYE_NATURAL_GAZE_MIN_MS 650
#define EYE_NATURAL_GAZE_SPAN_MS 1200
#define EYE_NATURAL_GAZE_AFTER_BLINK_MS 140
#define EYE_NATURAL_GAZE_MAX_X 3
#define EYE_NATURAL_GAZE_MAX_Y 2

typedef enum {
    EYE_COMMAND_SET_BASE_EMOTION = 0,
    EYE_COMMAND_SET_TEMP_EMOTION,
    EYE_COMMAND_BLINK,
    EYE_COMMAND_SET_SPEAKING,
    EYE_COMMAND_SET_BATTERY,
} eye_command_type_t;

typedef struct {
    eye_command_type_t type;
    usaki_eye_emotion_t emotion;
    uint32_t duration_ms;
    bool speaking;
    uint8_t battery_percent;
} eye_command_t;

typedef struct {
    bool sleeping;
    bool speaking;
    usaki_eye_emotion_t emotion;
    usaki_eye_emotion_t base_emotion;
    bool emotion_override_active;
    uint32_t emotion_override_until_ms;
    bool blink_active;
    uint8_t blink_peak_closed;
    uint8_t battery_percent;
    uint32_t blink_started_ms;
    uint32_t blink_close_ms;
    uint32_t blink_hold_ms;
    uint32_t blink_open_ms;
    uint32_t blink_right_lag_ms;
    uint32_t next_blink_ms;
    uint32_t next_gaze_ms;
    QueueHandle_t command_queue;
    eye_disp_ctx_t left_disp;
    eye_disp_ctx_t right_disp;
    eye_widget_t left;
    eye_widget_t right;
} usaki_eyes_ctx_t;

static usaki_eyes_ctx_t s_eyes;
static esp_timer_handle_t s_lv_tick_timer;
static bool s_started;
static lv_obj_t *s_privacy_label;
static int s_privacy_display_state = -1;

static uint32_t now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
}

static uint32_t next_blink_delay_ms(void)
{
    return EYE_RANDOM_BLINK_MIN_MS + (esp_random() % EYE_RANDOM_BLINK_SPAN_MS);
}

static uint32_t next_gaze_delay_ms(void)
{
    return EYE_NATURAL_GAZE_MIN_MS + (esp_random() % EYE_NATURAL_GAZE_SPAN_MS);
}

static int32_t random_signed_offset(uint32_t r, int32_t max_abs)
{
    return (int32_t)(r % (uint32_t)(max_abs * 2 + 1)) - max_abs;
}

static void lv_tick_timer_cb(void *arg)
{
    (void)arg;
    lv_tick_inc(EYE_TICK_MS);
}

static bool post_eye_command(const eye_command_t *command)
{
    if (!s_started || s_eyes.command_queue == NULL || command == NULL) {
        return false;
    }
    if (xQueueSend(s_eyes.command_queue, command, pdMS_TO_TICKS(EYE_COMMAND_POST_WAIT_MS)) != pdTRUE) {
        ESP_LOGW(TAG, "drop eye command: %d", (int)command->type);
        return false;
    }
    return true;
}

static bool post_base_emotion_command(usaki_eye_emotion_t emotion)
{
    const eye_command_t command = {
        .type = EYE_COMMAND_SET_BASE_EMOTION,
        .emotion = emotion,
    };
    return post_eye_command(&command);
}

static bool post_blink_command(void)
{
    const eye_command_t command = {
        .type = EYE_COMMAND_BLINK,
    };
    return post_eye_command(&command);
}

static void lvgl_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_p)
{
    eye_disp_ctx_t *ctx = (eye_disp_ctx_t *)drv->user_data;
    esp_err_t err = gc9a01_draw_bitmap(ctx->panel,
                                       area->x1,
                                       area->y1,
                                       area->x2,
                                       area->y2,
                                       (const uint16_t *)color_p);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "flush failed: %s", esp_err_to_name(err));
    }
    lv_disp_flush_ready(drv);
}

static esp_err_t create_lcd_panel(const gc9a01_bus_config_t *bus_cfg,
                                  const gc9a01_config_t *panel_cfg,
                                  gc9a01_handle_t *out_panel)
{
    ESP_RETURN_ON_ERROR(gc9a01_bus_init(bus_cfg), TAG, "lcd bus init failed");
    ESP_RETURN_ON_ERROR(gc9a01_create(panel_cfg, out_panel), TAG, "lcd create failed");
    ESP_RETURN_ON_ERROR(gc9a01_display_on(*out_panel), TAG, "lcd display on failed");
    return ESP_OK;
}

static esp_err_t register_lvgl_display(eye_disp_ctx_t *ctx, lv_disp_t **out_disp)
{
    const size_t pixels = USAKI_LCD_WIDTH * USAKI_LCD_DMA_LINES;
    ctx->buf1 = heap_caps_malloc(pixels * sizeof(lv_color_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (ctx->buf1 == NULL) {
        ctx->buf1 = heap_caps_malloc(pixels * sizeof(lv_color_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    }
    ctx->buf2 = heap_caps_malloc(pixels * sizeof(lv_color_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (ctx->buf2 == NULL) {
        ctx->buf2 = heap_caps_malloc(pixels * sizeof(lv_color_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    }
    ESP_RETURN_ON_FALSE(ctx->buf1 != NULL && ctx->buf2 != NULL, ESP_ERR_NO_MEM, TAG, "alloc lvgl buffers failed");

    lv_disp_draw_buf_init(&ctx->draw_buf, ctx->buf1, ctx->buf2, pixels);

    static lv_disp_drv_t drv_left;
    static lv_disp_drv_t drv_right;
    lv_disp_drv_t *drv = (out_disp == &s_eyes.left.disp) ? &drv_left : &drv_right;

    lv_disp_drv_init(drv);
    drv->hor_res = USAKI_LCD_WIDTH;
    drv->ver_res = USAKI_LCD_HEIGHT;
    drv->flush_cb = lvgl_flush_cb;
    drv->draw_buf = &ctx->draw_buf;
    drv->user_data = ctx;
    *out_disp = lv_disp_drv_register(drv);
    ESP_RETURN_ON_FALSE(*out_disp != NULL, ESP_FAIL, TAG, "register lvgl display failed");
    return ESP_OK;
}

static void start_blink_locked(uint32_t t)
{
    if (s_eyes.sleeping || s_eyes.blink_active) {
        return;
    }
    const uint32_t r = esp_random();
    s_eyes.blink_active = true;
    s_eyes.blink_started_ms = t;
    s_eyes.blink_peak_closed = 100;
    s_eyes.blink_close_ms = EYE_BLINK_CLOSE_MS + ((r >> 8) % 12u);
    s_eyes.blink_hold_ms = EYE_BLINK_HOLD_MS + ((r >> 12) % 6u);
    s_eyes.blink_open_ms = EYE_BLINK_OPEN_MS + ((r >> 16) % 20u);
    s_eyes.blink_right_lag_ms = 6u + ((r >> 22) % 12u);
}

static float blink_value_for_elapsed(int32_t elapsed)
{
    if (elapsed <= 0) {
        return 0.0f;
    }
    const uint32_t e = (uint32_t)elapsed;
    const uint32_t close_ms = s_eyes.blink_close_ms > 0 ? s_eyes.blink_close_ms : EYE_BLINK_CLOSE_MS;
    const uint32_t hold_ms = s_eyes.blink_hold_ms > 0 ? s_eyes.blink_hold_ms : EYE_BLINK_HOLD_MS;
    const uint32_t open_ms = s_eyes.blink_open_ms > 0 ? s_eyes.blink_open_ms : EYE_BLINK_OPEN_MS;
    const int32_t peak = s_eyes.blink_peak_closed > 0 ? s_eyes.blink_peak_closed : 100;

    if (e < close_ms) {
        return (float)peak * usaki_eye_ease_smootherstep((float)e / (float)close_ms);
    }
    if (e < close_ms + hold_ms) {
        return (float)peak;
    }
    if (e < close_ms + hold_ms + open_ms) {
        const uint32_t open_elapsed = e - close_ms - hold_ms;
        return (float)peak * (1.0f - usaki_eye_ease_smootherstep((float)open_elapsed / (float)open_ms));
    }
    return 0.0f;
}

static void blink_tick_locked(uint32_t t)
{
    if (s_eyes.sleeping) {
        s_eyes.blink_active = false;
        s_eyes.left.blink_closed = 100;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
        s_eyes.right.blink_closed = 100;
#endif
        s_eyes.next_blink_ms = t + next_blink_delay_ms();
        return;
    }

    if (!s_eyes.blink_active) {
        if (t >= s_eyes.next_blink_ms) {
            start_blink_locked(t);
        }
        s_eyes.left.blink_closed = 0;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
        s_eyes.right.blink_closed = 0;
#endif
        return;
    }

    const uint32_t elapsed = t - s_eyes.blink_started_ms;
    const uint32_t total = s_eyes.blink_close_ms + s_eyes.blink_hold_ms + s_eyes.blink_open_ms + s_eyes.blink_right_lag_ms;
    if (elapsed >= total) {
        s_eyes.blink_active = false;
        s_eyes.next_blink_ms = t + next_blink_delay_ms();
        s_eyes.left.blink_closed = 0;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
        s_eyes.right.blink_closed = 0;
#endif
        return;
    }

    s_eyes.left.blink_closed = blink_value_for_elapsed((int32_t)elapsed);
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    s_eyes.right.blink_closed = blink_value_for_elapsed((int32_t)elapsed - (int32_t)s_eyes.blink_right_lag_ms);
#endif
}

static void natural_gaze_tick_locked(uint32_t t)
{
    if (s_eyes.sleeping) {
        usaki_eye_set_gaze(&s_eyes.left, 0, 0);
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
        usaki_eye_set_gaze(&s_eyes.right, 0, 0);
#endif
        s_eyes.next_gaze_ms = t + next_gaze_delay_ms();
        return;
    }

    if (t < s_eyes.next_gaze_ms) {
        return;
    }

    if (s_eyes.blink_active || s_eyes.left.blink_closed > 0.01f || s_eyes.right.blink_closed > 0.01f) {
        s_eyes.next_gaze_ms = t + EYE_NATURAL_GAZE_AFTER_BLINK_MS;
        return;
    }

    const uint32_t r = esp_random();
    int32_t x = random_signed_offset(r, EYE_NATURAL_GAZE_MAX_X);
    int32_t y = random_signed_offset(r >> 8, EYE_NATURAL_GAZE_MAX_Y);
    if ((r & 0x0Fu) == 0u) {
        x = 0;
        y = 0;
    }

    usaki_eye_set_gaze(&s_eyes.left, x, y);
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    usaki_eye_set_gaze(&s_eyes.right, x, y);
#endif
    s_eyes.next_gaze_ms = t + next_gaze_delay_ms();
}

static void apply_emotion_locked(usaki_eye_emotion_t emotion)
{
    const bool was_sleeping = s_eyes.sleeping;
    s_eyes.emotion = emotion;
    s_eyes.sleeping = emotion == USAKI_EYE_EMOTION_SLEEP;
    s_eyes.left.emotion = emotion;
    s_eyes.left.base_ready = false;
    s_eyes.left.next_effect_ms = 0;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    s_eyes.right.emotion = emotion;
    s_eyes.right.base_ready = false;
    s_eyes.right.next_effect_ms = 0;
#endif
    if (s_eyes.sleeping) {
        s_eyes.blink_active = false;
        s_eyes.left.blink_closed = 100;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
        s_eyes.right.blink_closed = 100;
#endif
    } else if (was_sleeping) {
        s_eyes.left.blink_closed = 0;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
        s_eyes.right.blink_closed = 0;
#endif
        s_eyes.next_blink_ms = now_ms() + 260;
    }
}

static uint32_t normalize_override_duration_ms(uint32_t duration_ms)
{
    if (duration_ms == 0) {
        return 10000;
    }
    if (duration_ms < 8000) {
        return 8000;
    }
    if (duration_ms > 30000) {
        return 30000;
    }
    return duration_ms;
}

static void emotion_override_tick_locked(uint32_t t)
{
    if (!s_eyes.emotion_override_active) {
        return;
    }
    if (t < s_eyes.emotion_override_until_ms) {
        return;
    }
    s_eyes.emotion_override_active = false;
    apply_emotion_locked(s_eyes.base_emotion);
}

static void handle_eye_command(const eye_command_t *command, uint32_t t)
{
    switch (command->type) {
    case EYE_COMMAND_SET_BASE_EMOTION:
        s_eyes.base_emotion = command->emotion;
        if (command->emotion == USAKI_EYE_EMOTION_SLEEP ||
            command->emotion == USAKI_EYE_EMOTION_LOW_BATTERY) {
            s_eyes.emotion_override_active = false;
        }
        if (!s_eyes.emotion_override_active) {
            apply_emotion_locked(command->emotion);
        }
        break;
    case EYE_COMMAND_SET_TEMP_EMOTION:
        if (command->emotion == USAKI_EYE_EMOTION_IDLE ||
            command->emotion == USAKI_EYE_EMOTION_SLEEP) {
            s_eyes.base_emotion = command->emotion;
            s_eyes.emotion_override_active = false;
            apply_emotion_locked(command->emotion);
        } else {
            s_eyes.emotion_override_active = true;
            s_eyes.emotion_override_until_ms = t + normalize_override_duration_ms(command->duration_ms);
            apply_emotion_locked(command->emotion);
        }
        break;
    case EYE_COMMAND_BLINK:
        start_blink_locked(t);
        s_eyes.next_blink_ms = t + next_blink_delay_ms();
        break;
    case EYE_COMMAND_SET_SPEAKING:
        s_eyes.speaking = command->speaking;
        break;
    case EYE_COMMAND_SET_BATTERY:
        s_eyes.battery_percent = command->battery_percent > 100 ? 100 : command->battery_percent;
        break;
    default:
        break;
    }
}

static void drain_eye_commands(uint32_t t)
{
    eye_command_t command = {0};
    while (s_eyes.command_queue != NULL &&
           xQueueReceive(s_eyes.command_queue, &command, 0) == pdTRUE) {
        handle_eye_command(&command, t);
    }
}

static void usaki_eyes_task(void *arg)
{
    (void)arg;
    uint32_t frame = 0;
    uint32_t render_div = 0;
    TickType_t last_wake = xTaskGetTickCount();

    while (1) {
        const uint32_t t = now_ms();
        drain_eye_commands(t);
        emotion_override_tick_locked(t);
        blink_tick_locked(t);
        natural_gaze_tick_locked(t);
        if ((render_div++ % EYE_RENDER_SKIP) == 0) {
            usaki_eye_render(&s_eyes.left, frame, t);
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
            usaki_eye_render(&s_eyes.right, frame + 61, t);
#endif
        }

        // Independent persistent indicator; server eye emotions cannot hide it.
        const int privacy_state = spirit_privacy_muted() ? 0 :
            (voice_runtime_get_state() == USAKI_VOICE_RUNTIME_STATE_LISTENING ? 2 : 1);
        if (s_privacy_label && privacy_state != s_privacy_display_state) {
            s_privacy_display_state = privacy_state;
            lv_label_set_text(s_privacy_label, privacy_state == 0 ? "MIC MUTED" : privacy_state == 2 ? "LISTENING" : "MIC READY");
            lv_obj_set_style_text_color(s_privacy_label, lv_color_hex(privacy_state == 0 ? 0xffa040 : privacy_state == 2 ? 0xff5050 : 0x70d0b0), 0);
        }
        // Eye renderer has a direct-panel fast path; repaint the small label
        // region after each frame so that path cannot erase the privacy badge.
        if (s_privacy_label) lv_obj_invalidate(s_privacy_label);
        lv_timer_handler();
        lv_refr_now(s_eyes.left.disp);
        frame += EYE_FRAME_MS;
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(EYE_FRAME_MS));
    }
}

esp_err_t usaki_eyes_start(void)
{
    if (s_started) {
        return ESP_OK;
    }

    lv_init();

    const esp_timer_create_args_t tick_args = {
        .callback = lv_tick_timer_cb,
        .name = "lv_tick",
    };
    ESP_RETURN_ON_ERROR(esp_timer_create(&tick_args, &s_lv_tick_timer), TAG, "create lv tick timer failed");
    ESP_RETURN_ON_ERROR(esp_timer_start_periodic(s_lv_tick_timer, EYE_TICK_MS * 1000), TAG, "start lv tick failed");

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

    ESP_RETURN_ON_ERROR(create_lcd_panel(&left_bus_config, &left_config, &s_eyes.left_disp.panel), TAG, "left eye lcd failed");
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_RETURN_ON_ERROR(create_lcd_panel(&right_bus_config, &right_config, &s_eyes.right_disp.panel), TAG, "right eye lcd failed");
#endif
    ESP_RETURN_ON_ERROR(register_lvgl_display(&s_eyes.left_disp, &s_eyes.left.disp), TAG, "left lvgl display failed");
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_RETURN_ON_ERROR(register_lvgl_display(&s_eyes.right_disp, &s_eyes.right.disp), TAG, "right lvgl display failed");
#endif

    ESP_RETURN_ON_ERROR(usaki_eye_widget_create(&s_eyes.left,
                                                s_eyes.left.disp,
                                                s_eyes.left_disp.panel,
                                                0xA855F7,
                                                0xF472B6,
                                                0,
                                                -1),
                        TAG,
                        "left eye widget failed");
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_RETURN_ON_ERROR(usaki_eye_widget_create(&s_eyes.right,
                                                s_eyes.right.disp,
                                                s_eyes.right_disp.panel,
                                                0x8B5CF6,
                                                0xF0ABFC,
                                                230,
                                                1),
                        TAG,
                        "right eye widget failed");
#endif
    s_privacy_label = lv_label_create(lv_disp_get_scr_act(s_eyes.left.disp));
    lv_obj_align(s_privacy_label, LV_ALIGN_BOTTOM_MID, 0, -24);
    lv_obj_set_style_bg_color(s_privacy_label, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(s_privacy_label, LV_OPA_COVER, 0);
    lv_label_set_text(s_privacy_label, "MIC MUTED");
    s_eyes.sleeping = false;
    s_eyes.speaking = false;
    s_eyes.emotion = USAKI_EYE_EMOTION_IDLE;
    s_eyes.base_emotion = USAKI_EYE_EMOTION_IDLE;
    s_eyes.emotion_override_active = false;
    s_eyes.emotion_override_until_ms = 0;
    s_eyes.blink_peak_closed = 100;
    s_eyes.battery_percent = 100;
    s_eyes.blink_close_ms = EYE_BLINK_CLOSE_MS;
    s_eyes.blink_hold_ms = EYE_BLINK_HOLD_MS;
    s_eyes.blink_open_ms = EYE_BLINK_OPEN_MS;
    s_eyes.blink_right_lag_ms = 18;
    s_eyes.command_queue = xQueueCreate(EYE_COMMAND_QUEUE_LEN, sizeof(eye_command_t));
    ESP_RETURN_ON_FALSE(s_eyes.command_queue != NULL, ESP_ERR_NO_MEM, TAG, "create eye command queue failed");
    const uint32_t start_t = now_ms();
    s_eyes.next_blink_ms = start_t + 500;
    s_eyes.next_gaze_ms = start_t + 1200;

    BaseType_t ok = xTaskCreatePinnedToCore(usaki_eyes_task,
                                            "usaki_eyes",
                                            EYE_TASK_STACK_BYTES,
                                            NULL,
                                            EYE_TASK_PRIORITY,
                                            NULL,
                                            EYE_TASK_CORE);
    ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_FAIL, TAG, "create eye task failed");

    s_started = true;
#if USAKI_LCD_ENABLE_RIGHT_DISPLAY
    ESP_LOGI(TAG, "Usaki LVGL canvas dual eyes V2 started");
#else
    ESP_LOGI(TAG, "Usaki LVGL canvas single eye V2 started");
#endif
    return ESP_OK;
}

void usaki_eyes_set_emotion(usaki_eye_emotion_t emotion)
{
    (void)post_base_emotion_command(emotion);
}

bool usaki_eyes_set_emotion_name(const char *emotion)
{
    usaki_eye_emotion_t parsed = USAKI_EYE_EMOTION_IDLE;
    if (!usaki_eye_emotion_from_name(emotion, &parsed)) {
        return false;
    }
    return post_base_emotion_command(parsed);
}

bool usaki_eyes_set_emotion_name_for(const char *emotion, uint32_t duration_ms)
{
    usaki_eye_emotion_t parsed = USAKI_EYE_EMOTION_IDLE;
    if (!usaki_eye_emotion_from_name(emotion, &parsed)) {
        return false;
    }
    const eye_command_t command = {
        .type = EYE_COMMAND_SET_TEMP_EMOTION,
        .emotion = parsed,
        .duration_ms = duration_ms,
    };
    return post_eye_command(&command);
}

void usaki_eyes_wake(void)
{
    usaki_eyes_set_emotion(USAKI_EYE_EMOTION_IDLE);
}

void usaki_eyes_sleep(void)
{
    usaki_eyes_set_emotion(USAKI_EYE_EMOTION_SLEEP);
}

void usaki_eyes_blink(void)
{
    (void)post_blink_command();
}

bool usaki_eyes_play_animation_name(const char *name)
{
    if (usaki_eye_text_contains_token(name, "blink") || usaki_eye_text_contains_token(name, "眨眼")) {
        return post_blink_command();
    }
    if (usaki_eye_text_contains_token(name, "idle") || usaki_eye_text_contains_token(name, "normal")) {
        return post_base_emotion_command(USAKI_EYE_EMOTION_IDLE);
    }
    if (usaki_eye_text_contains_token(name, "sleep")) {
        return post_base_emotion_command(USAKI_EYE_EMOTION_SLEEP);
    }
    return usaki_eyes_set_emotion_name(name);
}

void usaki_eyes_set_speaking(bool speaking)
{
    const eye_command_t command = {
        .type = EYE_COMMAND_SET_SPEAKING,
        .speaking = speaking,
    };
    (void)post_eye_command(&command);
}

void usaki_eyes_set_battery(uint8_t percent)
{
    const eye_command_t command = {
        .type = EYE_COMMAND_SET_BATTERY,
        .battery_percent = percent,
    };
    (void)post_eye_command(&command);
}
