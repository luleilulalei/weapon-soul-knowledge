#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "board/usaki_board.h"
#include "drivers/gc9a01.h"
#include "esp_err.h"
#include "lvgl.h"
#include "ui/usaki_eyes.h"

#ifndef USAKI_LCD_ENABLE_RIGHT_DISPLAY
#define USAKI_LCD_ENABLE_RIGHT_DISPLAY 0
#endif

#define EYE_W USAKI_LCD_WIDTH
#define EYE_H USAKI_LCD_HEIGHT
#define EYE_CX (EYE_W / 2)
#define EYE_CY (EYE_H / 2)
#define EYE_CANVAS_PIXELS (EYE_W * EYE_H)
#define EYE_BLINK_DIRTY_PAD 7

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

typedef struct {
    gc9a01_handle_t panel;
    lv_disp_draw_buf_t draw_buf;
    lv_color_t *buf1;
    lv_color_t *buf2;
} eye_disp_ctx_t;

typedef struct {
    lv_disp_t *disp;
    lv_obj_t *screen;
    lv_obj_t *canvas;
    lv_color_t *canvas_buf;
    lv_color_t *base_buf;
    gc9a01_handle_t panel;
    uint32_t iris_color;
    uint32_t accent_color;
    int32_t phase;
    int32_t side_sign;
    usaki_eye_emotion_t emotion;
    float blink_closed;
    float drawn_blink_closed;
    int32_t pupil_size;
    int32_t gaze_x;
    int32_t gaze_y;
    uint32_t next_effect_ms;
    bool base_ready;
} eye_widget_t;

static inline float usaki_eye_clamp_f(float v, float lo, float hi)
{
    if (v < lo) {
        return lo;
    }
    if (v > hi) {
        return hi;
    }
    return v;
}

static inline float usaki_eye_ease_smootherstep(float t)
{
    t = usaki_eye_clamp_f(t, 0.0f, 1.0f);
    return t * t * t * (t * (t * 6.0f - 15.0f) + 10.0f);
}

esp_err_t usaki_eye_widget_create(eye_widget_t *eye,
                                  lv_disp_t *disp,
                                  gc9a01_handle_t panel,
                                  uint32_t iris_color,
                                  uint32_t accent_color,
                                  int32_t phase,
                                  int32_t side_sign);
void usaki_eye_render(eye_widget_t *eye, uint32_t frame, uint32_t t);
void usaki_eye_set_gaze(eye_widget_t *eye, int32_t x, int32_t y);

bool usaki_eye_text_contains_token(const char *text, const char *token);
bool usaki_eye_emotion_from_name(const char *name, usaki_eye_emotion_t *out);
