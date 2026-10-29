#include "ui/usaki_eyes_internal.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"

static const char *TAG = "usaki_eyes_render";

static uint8_t clamp_u8(int32_t v)
{
    if (v < 0) {
        return 0;
    }
    if (v > 255) {
        return 255;
    }
    return (uint8_t)v;
}

static int32_t clamp_i32(int32_t v, int32_t lo, int32_t hi)
{
    if (v < lo) {
        return lo;
    }
    if (v > hi) {
        return hi;
    }
    return v;
}

static uint8_t color_r(uint32_t c)
{
    return (uint8_t)((c >> 16) & 0xFF);
}

static uint8_t color_g(uint32_t c)
{
    return (uint8_t)((c >> 8) & 0xFF);
}

static uint8_t color_b(uint32_t c)
{
    return (uint8_t)(c & 0xFF);
}

static uint32_t rgb_u32(uint8_t r, uint8_t g, uint8_t b)
{
    return ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
}

static uint32_t mix_color(uint32_t a, uint32_t b, uint8_t t)
{
    const uint16_t inv = 255 - t;
    return rgb_u32((uint8_t)((color_r(a) * inv + color_r(b) * t) / 255),
                   (uint8_t)((color_g(a) * inv + color_g(b) * t) / 255),
                   (uint8_t)((color_b(a) * inv + color_b(b) * t) / 255));
}

static uint32_t add_color(uint32_t base, uint32_t add, uint8_t amount)
{
    return rgb_u32(clamp_u8(color_r(base) + (color_r(add) * amount) / 255),
                   clamp_u8(color_g(base) + (color_g(add) * amount) / 255),
                   clamp_u8(color_b(base) + (color_b(add) * amount) / 255));
}

static lv_color_t lv_color_from_u32(uint32_t c)
{
    return lv_color_make(color_r(c), color_g(c), color_b(c));
}

static void put_px(eye_widget_t *eye, int x, int y, uint32_t c)
{
    if ((unsigned)x >= EYE_W || (unsigned)y >= EYE_H) {
        return;
    }
    eye->canvas_buf[y * EYE_W + x] = lv_color_from_u32(c);
}

static uint32_t get_px(eye_widget_t *eye, int x, int y)
{
    if ((unsigned)x >= EYE_W || (unsigned)y >= EYE_H) {
        return 0;
    }
    lv_color_t px = eye->canvas_buf[y * EYE_W + x];
    return rgb_u32(px.ch.red << 3, px.ch.green << 2, px.ch.blue << 3);
}

static void blend_px(eye_widget_t *eye, int x, int y, uint32_t c, uint8_t alpha)
{
    if ((unsigned)x >= EYE_W || (unsigned)y >= EYE_H || alpha == 0) {
        return;
    }
    if (alpha >= 250) {
        put_px(eye, x, y, c);
        return;
    }
    put_px(eye, x, y, mix_color(get_px(eye, x, y), c, alpha));
}

static void blend_px_in_band(eye_widget_t *eye, int x, int y, int y0, int y1, uint32_t c, uint8_t alpha)
{
    if (y < y0 || y > y1) {
        return;
    }
    blend_px(eye, x, y, c, alpha);
}

static uint32_t hash_xy(int x, int y, uint32_t seed)
{
    uint32_t h = (uint32_t)x * 374761393u + (uint32_t)y * 668265263u + seed * 2246822519u;
    h = (h ^ (h >> 13)) * 1274126177u;
    return h ^ (h >> 16);
}

static bool point_in_ellipse(int x, int y, int cx, int cy, int rx, int ry)
{
    const float nx = ((float)x - (float)cx) / (float)rx;
    const float ny = ((float)y - (float)cy) / (float)ry;
    return nx * nx + ny * ny <= 1.0f;
}

static void clear_canvas(eye_widget_t *eye, uint32_t frame)
{
    for (int y = 0; y < EYE_H; ++y) {
        const int32_t dy = y - EYE_CY;
        for (int x = 0; x < EYE_W; ++x) {
            const int32_t dx = x - EYE_CX;
            const int dist = (int)sqrtf((float)(dx * dx + dy * dy));
            uint32_t c = 0xF3F7FF;

            if (y < 82) {
                c = mix_color(c, 0xD3DBEA, (uint8_t)clamp_i32(78 - y / 2, 0, 78));
            } else if (y > 164) {
                c = mix_color(c, 0xCAD7E9, (uint8_t)clamp_i32((y - 164) * 2, 0, 112));
            }
            if (dist > 104) {
                c = mix_color(c, 0x9BA9BD, (uint8_t)clamp_i32((dist - 104) * 6, 0, 116));
            } else {
                const uint8_t glow = (uint8_t)clamp_i32(32 - dist / 5, 0, 32);
                c = add_color(c, eye->accent_color, glow / 2);
            }

            const float sweep = sinf((float)frame * 0.004f + (float)x * 0.018f + eye->phase * 0.01f);
            c = add_color(c, 0xFFFFFF, (uint8_t)(8 + (sweep > 0.0f ? sweep * 6.0f : 0.0f)));
            put_px(eye, x, y, c);
        }
    }
}

static void draw_disc(eye_widget_t *eye, int cx, int cy, int r, uint32_t c, uint8_t alpha)
{
    const int r2 = r * r;
    for (int y = cy - r; y <= cy + r; ++y) {
        for (int x = cx - r; x <= cx + r; ++x) {
            const int dx = x - cx;
            const int dy = y - cy;
            if (dx * dx + dy * dy <= r2) {
                blend_px(eye, x, y, c, alpha);
            }
        }
    }
}

static void draw_line(eye_widget_t *eye, int x0, int y0, int x1, int y1, uint32_t c, uint8_t alpha, int thickness)
{
    int dx = abs(x1 - x0);
    int sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0);
    int sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    while (true) {
        draw_disc(eye, x0, y0, thickness, c, alpha);
        if (x0 == x1 && y0 == y1) {
            break;
        }
        int e2 = 2 * err;
        if (e2 >= dy) {
            err += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            err += dx;
            y0 += sy;
        }
    }
}

static void draw_disc_clipped_y(eye_widget_t *eye, int cx, int cy, int r, int y0, int y1, uint32_t c, uint8_t alpha)
{
    const int r2 = r * r;
    const int draw_y0 = cy - r > y0 ? cy - r : y0;
    const int draw_y1 = cy + r < y1 ? cy + r : y1;
    for (int y = draw_y0; y <= draw_y1; ++y) {
        for (int x = cx - r; x <= cx + r; ++x) {
            const int dx = x - cx;
            const int dy = y - cy;
            if (dx * dx + dy * dy <= r2) {
                blend_px(eye, x, y, c, alpha);
            }
        }
    }
}

static void draw_line_clipped_y(eye_widget_t *eye,
                                int x0,
                                int y0,
                                int x1,
                                int y1,
                                uint32_t c,
                                uint8_t alpha,
                                int thickness,
                                int clip_y0,
                                int clip_y1)
{
    int dx = abs(x1 - x0);
    int sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0);
    int sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    while (true) {
        draw_disc_clipped_y(eye, x0, y0, thickness, clip_y0, clip_y1, c, alpha);
        if (x0 == x1 && y0 == y1) {
            break;
        }
        int e2 = 2 * err;
        if (e2 >= dy) {
            err += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            err += dx;
            y0 += sy;
        }
    }
}

static void draw_ellipse(eye_widget_t *eye, int cx, int cy, int rx, int ry, uint32_t c, uint8_t alpha)
{
    const float rx_f = rx > 0 ? (float)rx : 1.0f;
    const float ry_f = ry > 0 ? (float)ry : 1.0f;
    for (int y = cy - ry; y <= cy + ry; ++y) {
        for (int x = cx - rx; x <= cx + rx; ++x) {
            const float nx = ((float)x - (float)cx) / rx_f;
            const float ny = ((float)y - (float)cy) / ry_f;
            const float d2 = nx * nx + ny * ny;
            if (d2 > 1.0f) {
                continue;
            }
            uint8_t a = alpha;
            if (d2 > 0.86f) {
                const float fade = (1.0f - d2) / 0.14f;
                a = (uint8_t)((float)alpha * usaki_eye_clamp_f(fade, 0.0f, 1.0f));
            }
            blend_px(eye, x, y, c, a);
        }
    }
}

static void draw_ellipse_ring(eye_widget_t *eye, int cx, int cy, int rx, int ry, int width, uint32_t c, uint8_t alpha)
{
    const int bx = rx + width;
    const int by = ry + width;
    const float rx_f = rx > 0 ? (float)rx : 1.0f;
    const float ry_f = ry > 0 ? (float)ry : 1.0f;
    const float band = (float)width / (float)((rx + ry) / 2);
    for (int y = cy - by; y <= cy + by; ++y) {
        for (int x = cx - bx; x <= cx + bx; ++x) {
            const float nx = ((float)x - (float)cx) / rx_f;
            const float ny = ((float)y - (float)cy) / ry_f;
            const float d = sqrtf(nx * nx + ny * ny);
            const float edge = fabsf(1.0f - d);
            if (edge > band) {
                continue;
            }
            const float fade = 1.0f - edge / band;
            blend_px(eye, x, y, c, (uint8_t)((float)alpha * fade));
        }
    }
}

static void draw_sparkle(eye_widget_t *eye, int cx, int cy, int size, uint32_t c, uint8_t alpha)
{
    draw_line(eye, cx - size, cy, cx + size, cy, c, alpha, 1);
    draw_line(eye, cx, cy - size, cx, cy + size, c, alpha, 1);
    draw_disc(eye, cx, cy, 2, 0xFFFFFF, alpha);
}

static bool point_in_polygon_float(int px, int py, const float *xs, const float *ys, int count)
{
    bool inside = false;
    for (int i = 0, j = count - 1; i < count; j = i++) {
        const bool crosses = ((ys[i] > (float)py) != (ys[j] > (float)py));
        if (!crosses) {
            continue;
        }
        const float x_at_y = (xs[j] - xs[i]) * ((float)py - ys[i]) / (ys[j] - ys[i]) + xs[i];
        if ((float)px < x_at_y) {
            inside = !inside;
        }
    }
    return inside;
}

static void draw_star_shape(eye_widget_t *eye,
                            int cx,
                            int cy,
                            int outer_r,
                            int inner_r,
                            uint32_t c,
                            uint8_t alpha)
{
    float xs[10];
    float ys[10];
    for (int i = 0; i < 10; ++i) {
        const float r = (i & 1) ? (float)inner_r : (float)outer_r;
        const float a = -((float)M_PI / 2.0f) + ((float)i * (float)M_PI / 5.0f);
        xs[i] = (float)cx + cosf(a) * r;
        ys[i] = (float)cy + sinf(a) * r;
    }

    for (int y = cy - outer_r; y <= cy + outer_r; ++y) {
        for (int x = cx - outer_r; x <= cx + outer_r; ++x) {
            if (point_in_polygon_float(x, y, xs, ys, 10)) {
                blend_px(eye, x, y, c, alpha);
            }
        }
    }
}

static void draw_heart_shape(eye_widget_t *eye, int cx, int cy, int scale, uint32_t c, uint8_t alpha)
{
    const int bx = scale * 2;
    const int by = scale * 2;
    for (int y = cy - by; y <= cy + by; ++y) {
        for (int x = cx - bx; x <= cx + bx; ++x) {
            const float nx = ((float)x - (float)cx) / (float)scale;
            const float ny = -(((float)y - (float)cy) / (float)scale);
            const float q = nx * nx + ny * ny - 1.0f;
            const float v = q * q * q - nx * nx * ny * ny * ny;
            if (v <= 0.0f) {
                blend_px(eye, x, y, c, alpha);
            }
        }
    }
}

static void draw_flame_shape(eye_widget_t *eye, int cx, int cy, int h, uint32_t c, uint8_t alpha)
{
    const int y_top = cy - h;
    const int y_bottom = cy + h / 2;
    for (int y = y_top; y <= y_bottom; ++y) {
        const float t = usaki_eye_clamp_f(((float)y - (float)y_top) / (float)(y_bottom - y_top), 0.0f, 1.0f);
        const float width = sinf(t * (float)M_PI) * (0.30f + 0.58f * t) * (float)h;
        const float curl = sinf(t * 8.4f + (float)eye->phase * 0.03f) * (1.0f - t) * 9.0f;
        if (width <= 0.5f) {
            continue;
        }
        const int x0 = (int)floorf((float)cx + curl - width);
        const int x1 = (int)ceilf((float)cx + curl + width);
        for (int x = x0; x <= x1; ++x) {
            const float nx = ((float)x - ((float)cx + curl)) / width;
            if (nx * nx <= 1.0f) {
                const uint8_t a = (uint8_t)clamp_i32((int32_t)((1.0f - nx * nx) * (float)alpha), 0, alpha);
                blend_px(eye, x, y, c, a);
            }
        }
    }
}

static void draw_iris_gradient(eye_widget_t *eye, uint32_t frame)
{
    const int cx = EYE_CX + eye->gaze_x;
    const int cy = EYE_CY + eye->gaze_y + 4;
    const int rx = 78;
    const int ry = 90;
    const uint32_t iris_base = mix_color(eye->iris_color, 0xE85DFF, 88);
    const uint32_t iris_dark = mix_color(0x050314, eye->iris_color, 36);
    const uint32_t iris_hot = mix_color(0xFF4FB8, eye->accent_color, 74);
    const uint32_t iris_blue = mix_color(0x7DD3FC, eye->iris_color, 82);
    const float pulse = sinf((float)frame * 0.0055f + (float)eye->phase * 0.01f) * 0.5f + 0.5f;

    for (int y = cy - ry; y <= cy + ry; ++y) {
        for (int x = cx - rx; x <= cx + rx; ++x) {
            const float nx = ((float)x - (float)cx) / (float)rx;
            const float ny = ((float)y - (float)cy) / (float)ry;
            const float d2 = nx * nx + ny * ny;
            if (d2 > 1.0f) {
                continue;
            }
            const float d = sqrtf(d2);
            uint32_t c = mix_color(iris_dark, iris_base, (uint8_t)clamp_i32((int32_t)((1.0f - d) * 180.0f), 0, 180));
            c = add_color(c, 0xD7F1FF, (uint8_t)clamp_i32((int32_t)((0.22f - ny) * 170.0f), 0, 70));

            const float left_blob = 1.0f - sqrtf(((float)x - (float)(cx - 38)) * ((float)x - (float)(cx - 38)) / (32.0f * 32.0f) +
                                                 ((float)y - (float)(cy + 26)) * ((float)y - (float)(cy + 26)) / (42.0f * 42.0f));
            if (left_blob > 0.0f) {
                c = add_color(c, iris_hot, (uint8_t)clamp_i32((int32_t)(left_blob * 118.0f), 0, 118));
            }

            const float right_dx = ((float)x - (float)(cx + 34)) / 36.0f;
            const float right_dy = ((float)y - (float)(cy - 24)) / 36.0f;
            const float right_blob = 1.0f - sqrtf(right_dx * right_dx + right_dy * right_dy);
            if (right_blob > 0.0f) {
                c = add_color(c, iris_blue, (uint8_t)clamp_i32((int32_t)(right_blob * 82.0f), 0, 82));
            }

            const float spoke = sinf((nx * 20.0f) + (ny * 12.0f) + (float)frame * 0.012f + (float)eye->phase * 0.03f);
            if (spoke > 0.62f && d < 0.82f) {
                c = add_color(c, 0xFFFFFF, (uint8_t)((spoke - 0.62f) * 62.0f));
            }
            if (d > 0.82f) {
                c = mix_color(c, 0x141229, (uint8_t)clamp_i32((int32_t)((d - 0.82f) * 520.0f), 0, 150));
                c = add_color(c, eye->accent_color, (uint8_t)clamp_i32((int32_t)((d - 0.82f) * 180.0f), 0, 70));
            }
            const uint32_t h = hash_xy(x, y, (uint32_t)eye->phase);
            if ((h & 0x3FFu) > 1008u && d < 0.80f && y < cy + 45) {
                c = add_color(c, ((h >> 10) & 1u) ? 0xFFFFFF : 0xFF95D6,
                              (uint8_t)(88 + (int)(pulse * 56.0f)));
            }
            put_px(eye, x, y, c);
        }
    }

    draw_ellipse(eye, cx - 34, cy + 30, 27, 22, 0xFF54C8, (uint8_t)(54 + pulse * 42.0f));
    draw_ellipse(eye, cx + 30, cy - 22, 24, 20, 0xA78BFA, 58);
    draw_ellipse_ring(eye, cx, cy, rx + 4, ry + 4, 6, 0x0F142B, 170);
    draw_ellipse_ring(eye, cx, cy, rx - 7, ry - 7, 2, 0xFFFFFF, 42);
    draw_ellipse_ring(eye, cx, cy, rx + 8, ry + 8, 3, 0xD9E7FF, 72);

    for (int i = 0; i < 18; ++i) {
        const uint32_t h = hash_xy(i * 19, eye->phase + i * 7, 0xA5u);
        const int sx = cx - 58 + (int)(h % 116u);
        const int sy = cy - 54 + (int)((h >> 8) % 104u);
        if (point_in_ellipse(sx, sy, cx, cy, rx - 10, ry - 12)) {
            draw_disc(eye, sx, sy, ((h >> 16) % 5u) == 0u ? 2 : 1,
                      ((h >> 25) & 1u) ? 0xFFFFFF : 0xFF8BD6,
                      (uint8_t)(70 + ((h >> 20) % 85u)));
        }
    }
}

static void draw_glass_highlights(eye_widget_t *eye, uint32_t frame)
{
    const int cx = EYE_CX + eye->gaze_x;
    const int cy = EYE_CY + eye->gaze_y + 4;
    const uint8_t shimmer = (uint8_t)(170 + 38 * (sinf((float)frame * 0.010f + eye->phase) * 0.5f + 0.5f));

    draw_ellipse(eye, cx - 30, cy - 45, 23, 12, 0xFFFFFF, 138);
    draw_disc(eye, cx - 42, cy - 48, 8, 0xFFFFFF, shimmer);
    draw_disc(eye, cx - 20, cy - 57, 4, 0xFFFFFF, 185);
    draw_disc(eye, cx + 36, cy - 44, 10, 0xFFFFFF, 190);
    draw_disc(eye, cx + 48, cy - 28, 4, 0xFFFFFF, 150);
    draw_ellipse(eye, cx - 47, cy - 26, 10, 28, 0xBEEBFF, 64);
    draw_sparkle(eye, cx + 18, cy - 18, 5, 0xFFFFFF, 118);
}

static uint32_t upper_lid_surface(int y, float edge)
{
    const int depth = clamp_i32((int32_t)(edge - (float)y), 0, 96);
    uint32_t c = mix_color(0xDCE3EE, 0x8994A9, (uint8_t)clamp_i32(y + 18, 0, 160));
    if (y < 34) {
        c = mix_color(c, 0x9EA8BA, (uint8_t)clamp_i32((34 - y) * 3, 0, 80));
    } else if (y > EYE_CY - 8) {
        c = mix_color(c, 0x6F7B93, (uint8_t)clamp_i32((y - (EYE_CY - 8)) * 2, 0, 72));
    }
    if (depth < 24) {
        c = mix_color(c, 0x3B344E, (uint8_t)clamp_i32((24 - depth) * 5, 0, 112));
    }
    return c;
}

static uint32_t lower_lid_surface(int y, float edge)
{
    const int depth = clamp_i32((int32_t)((float)y - edge), 0, 96);
    uint32_t c = mix_color(0xD7E4F2, 0x697D9C, (uint8_t)clamp_i32(y - (EYE_CY - 18), 0, 176));
    if (y > EYE_CY + 82) {
        c = mix_color(c, 0x253047, (uint8_t)clamp_i32((y - (EYE_CY + 82)) * 6, 0, 160));
    }
    if (depth < 20) {
        c = mix_color(c, 0x38435A, (uint8_t)clamp_i32((20 - depth) * 4, 0, 84));
    }
    return c;
}

static uint32_t closed_lid_surface(eye_widget_t *eye, int y, float seam)
{
    const int dist = clamp_i32((int32_t)fabsf((float)y - seam), 0, 96);
    uint32_t c = mix_color(0xC5DDF2, eye->iris_color, 58);
    if ((float)y < seam) {
        c = mix_color(c, 0xDBECFA, (uint8_t)clamp_i32((int32_t)(seam - (float)y), 0, 58));
    } else {
        c = mix_color(c, 0x6D83A7, (uint8_t)clamp_i32((int32_t)(((float)y - seam) * 2.0f), 0, 96));
    }
    if (dist < 26) {
        c = add_color(c, 0xEAF6FF, (uint8_t)clamp_i32(28 - dist, 0, 28));
    }
    if (dist > 58) {
        c = mix_color(c, 0x34455F, (uint8_t)clamp_i32((dist - 58) * 3, 0, 72));
    }
    return c;
}

static float blink_closed_fraction(float closed_percent)
{
    return usaki_eye_clamp_f(closed_percent / 100.0f, 0.0f, 1.0f);
}

static void eyelid_bases_for_closed(float closed, float *top_base, float *bottom_base)
{
    const float seal = usaki_eye_ease_smootherstep((closed - 0.82f) / 0.18f);
    *top_base = 16.0f + closed * 124.0f + seal * 20.0f;
    *bottom_base = 225.0f - closed * 82.0f - seal * 8.0f;
}

static float eyelid_nx_for_x(int x)
{
    return ((float)x - (float)EYE_CX) / 120.0f;
}

static float upper_lid_edge_for_x(float top_base, int x)
{
    const float nx = eyelid_nx_for_x(x);
    return top_base + 18.0f * nx * nx + 2.0f * nx;
}

static float lower_lid_edge_for_x(float bottom_base, int x)
{
    const float nx = eyelid_nx_for_x(x);
    return bottom_base - 18.0f * nx * nx - 3.5f * nx;
}

static void draw_upper_lashes_region(eye_widget_t *eye, float closed, float top_base, int y0, int y1)
{
    const float visibility = 1.0f - usaki_eye_clamp_f(closed / 0.48f, 0.0f, 1.0f);
    if (visibility <= 0.0f) {
        return;
    }

    for (int x = 30; x <= EYE_W - 30; x += 18) {
        const float nx = eyelid_nx_for_x(x);
        const float side = fabsf(nx);
        const float edge = upper_lid_edge_for_x(top_base, x);
        const int start_y = (int)roundf(edge + 1.0f);
        const int outward = x < EYE_CX ? -1 : 1;
        const int length = 7 + (int)(side * 7.0f) + ((x / 18) & 1);
        const int end_x = x + outward * (4 + (int)(side * 6.0f));
        const int end_y = start_y - length;
        const uint8_t alpha = (uint8_t)clamp_i32((int32_t)((128.0f + side * 72.0f) * visibility), 0, 210);
        draw_line_clipped_y(eye, x, start_y, end_x, end_y, 0x050713, alpha, 1, y0, y1);
    }
}

static void eyelid_edge_ranges(float closed_percent,
                               float *top_min,
                               float *top_max,
                               float *bottom_min,
                               float *bottom_max)
{
    const float closed = blink_closed_fraction(closed_percent);
    float top_base = 0.0f;
    float bottom_base = 0.0f;
    eyelid_bases_for_closed(closed, &top_base, &bottom_base);

    *top_min = top_base - 20.0f;
    *top_max = top_base + 24.0f;
    *bottom_min = bottom_base - 23.0f;
    *bottom_max = bottom_base + 8.0f;
}

static void dirty_band_from_ranges(float a_min, float a_max, float b_min, float b_max, int *y0, int *y1)
{
    const float min_y = fminf(a_min, b_min) - (float)EYE_BLINK_DIRTY_PAD;
    const float max_y = fmaxf(a_max, b_max) + (float)EYE_BLINK_DIRTY_PAD;
    *y0 = clamp_i32((int32_t)floorf(min_y), 0, EYE_H - 1);
    *y1 = clamp_i32((int32_t)ceilf(max_y), 0, EYE_H - 1);
}

static void restore_base_band(eye_widget_t *eye, int y0, int y1)
{
    if (y0 > y1 || eye->base_buf == NULL) {
        return;
    }
    const size_t offset = (size_t)y0 * EYE_W;
    const size_t pixels = (size_t)(y1 - y0 + 1) * EYE_W;
    memcpy(&eye->canvas_buf[offset], &eye->base_buf[offset], pixels * sizeof(lv_color_t));
}

static void flush_eye_band(eye_widget_t *eye, int y0, int y1)
{
    if (y0 > y1 || eye->panel == NULL) {
        return;
    }
    esp_err_t err = gc9a01_draw_bitmap(eye->panel,
                                       0,
                                       y0,
                                       EYE_W - 1,
                                       y1,
                                       (const uint16_t *)&eye->canvas_buf[(size_t)y0 * EYE_W]);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "eye band flush failed y=%d..%d: %s", y0, y1, esp_err_to_name(err));
    }
}

static void draw_eyelid_mask_region(eye_widget_t *eye, float closed_percent, int y0, int y1)
{
    if (y0 > y1) {
        return;
    }
    y0 = clamp_i32(y0, 0, EYE_H - 1);
    y1 = clamp_i32(y1, 0, EYE_H - 1);

    const float closed = blink_closed_fraction(closed_percent);
    float top_base = 0.0f;
    float bottom_base = 0.0f;
    eyelid_bases_for_closed(closed, &top_base, &bottom_base);
    const float lid_line_softness = 1.85f;

    for (int y = y0; y <= y1; ++y) {
        for (int x = 0; x < EYE_W; ++x) {
            const float nx = eyelid_nx_for_x(x);
            const float top_edge = upper_lid_edge_for_x(top_base, x);
            const float bottom_edge = lower_lid_edge_for_x(bottom_base, x);
            const float yf = (float)y;
            const float top_cover = top_edge - yf;
            const float bottom_cover = yf - bottom_edge;
            const float lid_gap = bottom_edge - top_edge;
            const bool sealing = closed >= 0.84f || lid_gap <= 18.0f;
            const float seam = (top_edge + bottom_edge) * 0.5f;

            if (top_cover > 0.0f) {
                uint8_t a = 255;
                if (top_cover < lid_line_softness) {
                    a = (uint8_t)clamp_i32((int32_t)(top_cover * 255.0f / lid_line_softness), 24, 255);
                }
                blend_px(eye, x, y, sealing ? closed_lid_surface(eye, y, seam) : upper_lid_surface(y, top_edge), a);
            }
            if (bottom_cover > 0.0f) {
                uint8_t a = 255;
                if (bottom_cover < lid_line_softness) {
                    a = (uint8_t)clamp_i32((int32_t)(bottom_cover * 255.0f / lid_line_softness), 24, 255);
                }
                blend_px(eye, x, y, sealing ? closed_lid_surface(eye, y, seam) : lower_lid_surface(y, bottom_edge), a);
            }

            if (!sealing && closed < 0.68f) {
                const float upper_smoke = yf - top_edge;
                if (upper_smoke >= -2.0f && upper_smoke <= 18.0f) {
                    const float fade = 1.0f - usaki_eye_clamp_f(upper_smoke / 18.0f, 0.0f, 1.0f);
                    const uint8_t a = (uint8_t)clamp_i32((int32_t)((74.0f + fabsf(nx) * 42.0f) * fade), 0, 118);
                    blend_px(eye, x, y, mix_color(0x050713, eye->accent_color, 34), a);
                }

                const float lower_smoke = bottom_edge - yf;
                if (lower_smoke >= -1.5f && lower_smoke <= 12.0f) {
                    const float fade = 1.0f - usaki_eye_clamp_f(lower_smoke / 12.0f, 0.0f, 1.0f);
                    const uint8_t a = (uint8_t)clamp_i32((int32_t)((34.0f + fabsf(nx) * 22.0f) * fade), 0, 62);
                    blend_px(eye, x, y, 0x182033, a);
                }
            }

            if (sealing) {
                const float fill_pad = 2.4f + usaki_eye_clamp_f((18.0f - lid_gap) * 0.28f, 0.0f, 7.5f);
                if (yf >= fminf(top_edge, bottom_edge) - fill_pad && yf <= fmaxf(top_edge, bottom_edge) + fill_pad) {
                    blend_px(eye, x, y, closed_lid_surface(eye, y, seam), 255);
                }
                const float seam_dist = fabsf(yf - seam);
                if (seam_dist <= 2.4f) {
                    blend_px(eye, x, y, 0x050713,
                             (uint8_t)clamp_i32((int32_t)(214.0f - seam_dist * 66.0f), 42, 214));
                }
            } else {
                const float top_edge_dist = fabsf(yf - top_edge);
                if (top_edge_dist <= 2.6f) {
                    blend_px(eye, x, y, 0x050713,
                             (uint8_t)clamp_i32((int32_t)(218.0f - top_edge_dist * 48.0f), 46, 218));
                    blend_px_in_band(eye, x, y + 2, y0, y1, 0x564765, 42);
                }
                const float bottom_edge_dist = fabsf(yf - bottom_edge);
                if (bottom_edge_dist <= 2.5f) {
                    blend_px(eye, x, y, 0x121A2D,
                             (uint8_t)clamp_i32((int32_t)(162.0f - bottom_edge_dist * 42.0f), 34, 162));
                    blend_px_in_band(eye, x, y - 2, y0, y1, 0xAAB4C9, 16);
                }
            }
        }
    }

    draw_upper_lashes_region(eye, closed, top_base, y0, y1);
}

static void draw_slanted_upper_lid(eye_widget_t *eye, float severity, uint32_t edge_color)
{
    const int inner_dir = -eye->side_sign;
    int prev_x = 0;
    int prev_y = 0;
    bool have_prev = false;

    for (int x = 0; x < EYE_W; ++x) {
        const float nx = eyelid_nx_for_x(x);
        const float inner = usaki_eye_clamp_f((float)inner_dir * nx, -1.0f, 1.0f);
        const float edge = 28.0f + severity * (36.0f + inner * 34.0f + nx * nx * 14.0f);
        const int y_edge = clamp_i32((int32_t)roundf(edge), 0, EYE_H - 1);
        for (int y = 0; y <= y_edge; ++y) {
            blend_px(eye, x, y, upper_lid_surface(y, edge), 255);
        }
        if (have_prev) {
            draw_line(eye, prev_x, prev_y, x, y_edge, edge_color, 172, 1);
        }
        prev_x = x;
        prev_y = y_edge;
        have_prev = true;
    }
}

static void draw_droopy_upper_lid(eye_widget_t *eye, float amount)
{
    for (int x = 0; x < EYE_W; ++x) {
        const float nx = eyelid_nx_for_x(x);
        const float center_drop = (1.0f - usaki_eye_clamp_f(fabsf(nx), 0.0f, 1.0f));
        const float edge = 34.0f + amount * (36.0f + center_drop * 42.0f + nx * nx * 10.0f);
        const int y_edge = clamp_i32((int32_t)roundf(edge), 0, EYE_H - 1);
        for (int y = 0; y <= y_edge; ++y) {
            blend_px(eye, x, y, upper_lid_surface(y, edge), 242);
        }
        if ((x % 2) == 0) {
            blend_px(eye, x, y_edge + 1, 0xF8FAFF, 102);
        }
    }
}

static void draw_sleepy_lid(eye_widget_t *eye)
{
    for (int x = 0; x < EYE_W; ++x) {
        const float nx = eyelid_nx_for_x(x);
        const float edge = 83.0f + 10.0f * nx * nx;
        const int y_edge = clamp_i32((int32_t)roundf(edge), 0, EYE_H - 1);
        for (int y = 0; y <= y_edge; ++y) {
            blend_px(eye, x, y, upper_lid_surface(y, edge), 248);
        }
        blend_px(eye, x, y_edge + 1, 0xF8FAFF, 118);
    }
}

static void draw_expression_static_overlay(eye_widget_t *eye, uint32_t frame)
{
    const int cx = EYE_CX + eye->gaze_x;
    const int cy = EYE_CY + eye->gaze_y + 4;
    switch (eye->emotion) {
    case USAKI_EYE_EMOTION_ANGRY:
        draw_slanted_upper_lid(eye, 1.0f, 0xFFF0FF);
        break;
    case USAKI_EYE_EMOTION_FIRE:
        draw_ellipse_ring(eye, cx, cy, 86, 94, 5, 0xFF4E68, 132);
        draw_flame_shape(eye, cx + eye->side_sign * 18, cy + 10, 30 + (int)((frame / 90u) & 3u), 0xFF4E68, 126);
        draw_flame_shape(eye, cx + eye->side_sign * 12, cy + 13, 19, 0xFFD36A, 126);
        draw_slanted_upper_lid(eye, 1.12f, 0xFF7181);
        break;
    case USAKI_EYE_EMOTION_WRONGED:
        draw_droopy_upper_lid(eye, 0.76f);
        draw_ellipse_ring(eye, cx, cy + 36, 58, 22, 3, 0xBEEBFF, 86);
        draw_heart_shape(eye, cx + eye->side_sign * 44, cy + 70, 9, 0x75DDFF, 150);
        break;
    case USAKI_EYE_EMOTION_SLEEPY:
        draw_sleepy_lid(eye);
        break;
    case USAKI_EYE_EMOTION_SCAN:
        draw_ellipse_ring(eye, cx, cy, 42, 46, 2, 0xFFFFFF, 84);
        draw_line(eye, cx - 54, cy, cx + 54, cy, eye->accent_color, 116, 1);
        draw_line(eye, cx, cy - 58, cx, cy + 58, eye->accent_color, 116, 1);
        break;
    case USAKI_EYE_EMOTION_LOW_BATTERY:
        draw_ellipse_ring(eye, cx, cy, 52, 60, 4, 0xFF4E68, 118);
        draw_line(eye, cx - 18, cy + 20, cx, cy - 26, 0xFF4E68, 190, 3);
        draw_line(eye, cx, cy - 26, cx + 19, cy + 20, 0xFF4E68, 190, 3);
        draw_line(eye, cx - 10, cy + 4, cx + 10, cy + 4, 0xFF4E68, 190, 2);
        break;
    default:
        break;
    }
}

static void draw_pupil_and_highlight(eye_widget_t *eye, uint32_t frame)
{
    const int cx = EYE_CX + eye->gaze_x;
    const int cy = EYE_CY + eye->gaze_y + 8;
    const int pupil = eye->pupil_size;

    if (eye->emotion == USAKI_EYE_EMOTION_STAR ||
        eye->emotion == USAKI_EYE_EMOTION_SURPRISED) {
        const uint8_t pulse = (uint8_t)(146 + 34 * (sinf((float)frame * 0.014f + (float)eye->phase) * 0.5f + 0.5f));
        draw_ellipse(eye, cx + 1, cy + 2, pupil + 17, pupil + 22, 0x02020A, 230);
        draw_star_shape(eye, cx, cy, pupil + 17, pupil - 5, eye->accent_color, 210);
        draw_star_shape(eye, cx, cy, pupil + 3, pupil / 2, 0xFFFFFF, pulse);
        draw_sparkle(eye, cx - 47, cy - 45, 5, 0xFFFFFF, 134);
        draw_sparkle(eye, cx + 48, cy - 31, 4, eye->accent_color, 126);
        draw_glass_highlights(eye, frame);
        return;
    }

    if (eye->emotion == USAKI_EYE_EMOTION_HEART) {
        const uint8_t pulse = (uint8_t)(160 + 34 * (sinf((float)frame * 0.010f + (float)eye->phase) * 0.5f + 0.5f));
        draw_ellipse(eye, cx + 2, cy + 5, pupil + 20, pupil + 22, 0x02020A, 222);
        draw_heart_shape(eye, cx, cy + 7, pupil + 5, mix_color(eye->accent_color, 0xFF4FB8, 96), 220);
        draw_heart_shape(eye, cx - 3, cy + 2, pupil - 9, 0xFFFFFF, pulse);
        draw_disc(eye, cx + 30, cy + 22, 5, eye->accent_color, 118);
        draw_glass_highlights(eye, frame);
        return;
    }

    if (eye->emotion == USAKI_EYE_EMOTION_ANGRY) {
        draw_ellipse(eye, cx + 2, cy + 2, pupil + 13, pupil + 20, 0x02020A, 250);
        draw_ellipse_ring(eye, cx + 2, cy + 2, pupil + 16, pupil + 23, 4, 0xFF78D9, 86);
        draw_line(eye, cx - eye->side_sign * 40, cy + 19, cx + eye->side_sign * 42, cy - 24, 0xF8FCFF, 232, 4);
        draw_line(eye, cx - eye->side_sign * 35, cy + 18, cx + eye->side_sign * 36, cy - 20, eye->accent_color, 150, 2);
        draw_glass_highlights(eye, frame);
        return;
    }

    if (eye->emotion == USAKI_EYE_EMOTION_FIRE) {
        const uint8_t hot = (uint8_t)(144 + 54 * (sinf((float)frame * 0.018f + (float)eye->phase) * 0.5f + 0.5f));
        draw_ellipse(eye, cx + 2, cy + 2, pupil + 14, pupil + 22, 0x12040A, 246);
        draw_ellipse_ring(eye, cx + 2, cy + 2, pupil + 18, pupil + 26, 4, 0xFF4E68, 118);
        draw_flame_shape(eye, cx, cy + 16, 42, 0xFF4E68, hot);
        draw_flame_shape(eye, cx + eye->side_sign * 5, cy + 18, 25, 0xFFD36A, 172);
        draw_line(eye, cx - eye->side_sign * 42, cy + 21, cx + eye->side_sign * 44, cy - 26, 0xFFEDAA, 220, 3);
        draw_glass_highlights(eye, frame);
        return;
    }

    if (eye->emotion == USAKI_EYE_EMOTION_WRONGED) {
        draw_ellipse(eye, cx + 2, cy + 14, pupil + 16, pupil + 28, 0x02020A, 242);
        draw_ellipse_ring(eye, cx + 2, cy + 14, pupil + 19, pupil + 31, 3, 0xBEEBFF, 84);
        draw_disc(eye, cx - 23, cy - 7, 12, 0xFFFFFF, 226);
        draw_disc(eye, cx + 17, cy + 12, 6, 0xC9F5FF, 178);
        draw_disc(eye, cx - 3, cy + 32, 4, eye->accent_color, 96);
        draw_glass_highlights(eye, frame);
        return;
    }

    draw_ellipse(eye, cx + 2, cy + 2, pupil + 11, pupil + 18, 0x02020A, 248);
    draw_ellipse_ring(eye, cx + 2, cy + 2, pupil + 14, pupil + 21, 3, 0xFFFFFF, 28);
    draw_ellipse(eye, cx - 6, cy + 17, pupil - 2, pupil / 2 + 9, 0x301049, 56);

    for (int i = 0; i < 10; ++i) {
        const uint32_t h = hash_xy(i * 23, eye->phase + i * 17, 0x5Cu);
        const int sx = cx - pupil + (int)(h % (uint32_t)(pupil * 2 + 1));
        const int sy = cy - pupil + (int)((h >> 8) % (uint32_t)(pupil * 2 + 1));
        if (!point_in_ellipse(sx, sy, cx + 2, cy + 2, pupil + 6, pupil + 12)) {
            continue;
        }
        draw_disc(eye, sx, sy, 1, ((h >> 20) & 1u) ? 0xFFFFFF : 0xFF7AD9, (uint8_t)(62 + ((h >> 24) & 63u)));
    }

    draw_disc(eye, cx + 30, cy + 24, 5, eye->accent_color, 118);
    draw_glass_highlights(eye, frame);
}

static void render_eye_band(eye_widget_t *eye, float closed_percent, int y0, int y1)
{
    y0 = clamp_i32(y0, 0, EYE_H - 1);
    y1 = clamp_i32(y1, 0, EYE_H - 1);
    if (y0 > y1) {
        return;
    }

    restore_base_band(eye, y0, y1);
    draw_eyelid_mask_region(eye, closed_percent, y0, y1);
    flush_eye_band(eye, y0, y1);
}

void usaki_eye_set_gaze(eye_widget_t *eye, int32_t x, int32_t y)
{
    if (eye->gaze_x == x && eye->gaze_y == y) {
        return;
    }
    eye->gaze_x = x;
    eye->gaze_y = y;
    eye->base_ready = false;
}

static void rebuild_eye_base(eye_widget_t *eye, uint32_t frame)
{
    eye->pupil_size = 27;

    clear_canvas(eye, frame + (uint32_t)eye->phase);
    draw_iris_gradient(eye, frame + (uint32_t)eye->phase);
    draw_pupil_and_highlight(eye, frame + (uint32_t)eye->phase);
    draw_expression_static_overlay(eye, frame + (uint32_t)eye->phase);
    memcpy(eye->base_buf, eye->canvas_buf, EYE_CANVAS_PIXELS * sizeof(lv_color_t));

    const float current = usaki_eye_clamp_f(eye->blink_closed, 0.0f, 100.0f);
    draw_eyelid_mask_region(eye, current, 0, EYE_H - 1);
    flush_eye_band(eye, 0, EYE_H - 1);

    eye->drawn_blink_closed = current;
    eye->base_ready = true;
}

static uint32_t expression_effect_interval_ms(usaki_eye_emotion_t emotion)
{
    switch (emotion) {
    case USAKI_EYE_EMOTION_STAR:
    case USAKI_EYE_EMOTION_SURPRISED:
        return 260;
    case USAKI_EYE_EMOTION_HEART:
        return 320;
    case USAKI_EYE_EMOTION_FIRE:
        return 420;
    case USAKI_EYE_EMOTION_SCAN:
        return 180;
    case USAKI_EYE_EMOTION_LOW_BATTERY:
        return 640;
    case USAKI_EYE_EMOTION_WRONGED:
        return 0;
    default:
        return 0;
    }
}

void usaki_eye_render(eye_widget_t *eye, uint32_t frame, uint32_t t)
{
    const uint32_t effect_interval = expression_effect_interval_ms(eye->emotion);
    if (effect_interval > 0 && eye->base_ready && t >= eye->next_effect_ms) {
        eye->base_ready = false;
        eye->next_effect_ms = t + effect_interval;
    }

    if (!eye->base_ready) {
        if (effect_interval > 0 && eye->next_effect_ms == 0) {
            eye->next_effect_ms = t + effect_interval;
        }
        rebuild_eye_base(eye, frame);
        return;
    }

    const float previous = usaki_eye_clamp_f(eye->drawn_blink_closed, 0.0f, 100.0f);
    const float current = usaki_eye_clamp_f(eye->blink_closed, 0.0f, 100.0f);
    if (fabsf(current - previous) < 0.01f) {
        return;
    }

    float prev_top_min = 0.0f;
    float prev_top_max = 0.0f;
    float prev_bottom_min = 0.0f;
    float prev_bottom_max = 0.0f;
    float curr_top_min = 0.0f;
    float curr_top_max = 0.0f;
    float curr_bottom_min = 0.0f;
    float curr_bottom_max = 0.0f;
    eyelid_edge_ranges(previous, &prev_top_min, &prev_top_max, &prev_bottom_min, &prev_bottom_max);
    eyelid_edge_ranges(current, &curr_top_min, &curr_top_max, &curr_bottom_min, &curr_bottom_max);

    int top_y0 = 0;
    int top_y1 = 0;
    int bottom_y0 = 0;
    int bottom_y1 = 0;
    dirty_band_from_ranges(prev_top_min, prev_top_max, curr_top_min, curr_top_max, &top_y0, &top_y1);
    dirty_band_from_ranges(prev_bottom_min, prev_bottom_max, curr_bottom_min, curr_bottom_max, &bottom_y0, &bottom_y1);

    if (top_y1 + 1 >= bottom_y0) {
        render_eye_band(eye, current, top_y0 < bottom_y0 ? top_y0 : bottom_y0, top_y1 > bottom_y1 ? top_y1 : bottom_y1);
    } else {
        render_eye_band(eye, current, top_y0, top_y1);
        render_eye_band(eye, current, bottom_y0, bottom_y1);
    }

    eye->drawn_blink_closed = current;
}

esp_err_t usaki_eye_widget_create(eye_widget_t *eye,
                                  lv_disp_t *disp,
                                  gc9a01_handle_t panel,
                                  uint32_t iris_color,
                                  uint32_t accent_color,
                                  int32_t phase,
                                  int32_t side_sign)
{
    eye->disp = disp;
    eye->panel = panel;
    eye->iris_color = iris_color;
    eye->accent_color = accent_color;
    eye->phase = phase;
    eye->side_sign = side_sign < 0 ? -1 : 1;
    eye->emotion = USAKI_EYE_EMOTION_IDLE;
    eye->blink_closed = 0;
    eye->drawn_blink_closed = 0;
    eye->pupil_size = 27;
    eye->gaze_x = 0;
    eye->gaze_y = 0;
    eye->next_effect_ms = 0;
    eye->base_ready = false;

    lv_disp_set_default(disp);
    eye->screen = lv_obj_create(NULL);
    lv_obj_set_size(eye->screen, EYE_W, EYE_H);
    lv_obj_set_style_bg_color(eye->screen, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(eye->screen, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(eye->screen, 0, 0);
    lv_obj_clear_flag(eye->screen, LV_OBJ_FLAG_SCROLLABLE);

    eye->canvas_buf = heap_caps_malloc(EYE_CANVAS_PIXELS * sizeof(lv_color_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (eye->canvas_buf == NULL) {
        eye->canvas_buf = heap_caps_malloc(EYE_CANVAS_PIXELS * sizeof(lv_color_t), MALLOC_CAP_8BIT);
    }
    ESP_RETURN_ON_FALSE(eye->canvas_buf != NULL, ESP_ERR_NO_MEM, TAG, "alloc eye canvas failed");

    eye->base_buf = heap_caps_malloc(EYE_CANVAS_PIXELS * sizeof(lv_color_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (eye->base_buf == NULL) {
        eye->base_buf = heap_caps_malloc(EYE_CANVAS_PIXELS * sizeof(lv_color_t), MALLOC_CAP_8BIT);
    }
    ESP_RETURN_ON_FALSE(eye->base_buf != NULL, ESP_ERR_NO_MEM, TAG, "alloc eye base failed");

    eye->canvas = lv_canvas_create(eye->screen);
    lv_canvas_set_buffer(eye->canvas, eye->canvas_buf, EYE_W, EYE_H, LV_IMG_CF_TRUE_COLOR);
    lv_obj_center(eye->canvas);
    lv_disp_load_scr(eye->screen);
    return ESP_OK;
}
