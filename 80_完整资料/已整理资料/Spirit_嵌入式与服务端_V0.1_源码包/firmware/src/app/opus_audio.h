#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define USAKI_OPUS_SAMPLE_RATE_HZ 16000
#define USAKI_OPUS_CHANNELS 1
#define USAKI_OPUS_SAMPLE_BITS 16
#define USAKI_OPUS_FRAME_DURATION_MS 20
#define USAKI_OPUS_FRAME_SAMPLES (USAKI_OPUS_SAMPLE_RATE_HZ * USAKI_OPUS_FRAME_DURATION_MS / 1000)
#define USAKI_OPUS_MAX_PACKET_BYTES 1500

typedef void (*usaki_opus_packet_cb_t)(const uint8_t *data, size_t len, void *user_ctx);

esp_err_t usaki_opus_audio_init(void);
void usaki_opus_audio_reset_encoder(void);
void usaki_opus_audio_reset_decoder(void);

esp_err_t usaki_opus_audio_encode_pcm(const int16_t *samples,
                                      size_t sample_count,
                                      usaki_opus_packet_cb_t callback,
                                      void *user_ctx);

esp_err_t usaki_opus_audio_flush_encoder(usaki_opus_packet_cb_t callback, void *user_ctx);

esp_err_t usaki_opus_audio_decode_packet(const uint8_t *data,
                                         size_t len,
                                         int16_t *out_samples,
                                         size_t out_capacity_samples,
                                         size_t *out_sample_count);

#ifdef __cplusplus
}
#endif
