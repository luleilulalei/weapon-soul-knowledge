#include "app/opus_audio.h"

#include <string.h>

#include "esp_audio_enc.h"
#include "esp_audio_types.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_opus_dec.h"
#include "esp_opus_enc.h"

static const char *TAG = "usaki_opus";

#define OPUS_FRAME_DURATION_ENUM ESP_OPUS_ENC_FRAME_DURATION_20_MS
#define OPUS_DEC_FRAME_DURATION_ENUM ESP_OPUS_DEC_FRAME_DURATION_20_MS

static void *s_encoder;
static void *s_decoder;
static int s_encoder_outbuf_size;
static int16_t s_encode_frame[USAKI_OPUS_FRAME_SAMPLES];
static size_t s_encode_pending_samples;
static uint8_t s_encode_packet[USAKI_OPUS_MAX_PACKET_BYTES];

static esp_err_t ensure_encoder(void)
{
    if (s_encoder != NULL)
    {
        return ESP_OK;
    }

    esp_opus_enc_config_t config = {
        .sample_rate = ESP_AUDIO_SAMPLE_RATE_16K,
        .channel = ESP_AUDIO_MONO,
        .bits_per_sample = ESP_AUDIO_BIT16,
        .bitrate = ESP_OPUS_BITRATE_AUTO,
        .frame_duration = OPUS_FRAME_DURATION_ENUM,
        .application_mode = ESP_OPUS_ENC_APPLICATION_AUDIO,
        .complexity = 0,
        .enable_fec = false,
        .enable_dtx = true,
        .enable_vbr = true,
    };

    int ret = esp_opus_enc_open(&config, sizeof(config), &s_encoder);
    ESP_RETURN_ON_FALSE(s_encoder != NULL, ESP_FAIL, TAG, "opus encoder open failed: %d", ret);

    int encoder_frame_bytes = 0;
    esp_opus_enc_get_frame_size(s_encoder, &encoder_frame_bytes, &s_encoder_outbuf_size);
    if (s_encoder_outbuf_size > USAKI_OPUS_MAX_PACKET_BYTES)
    {
        ESP_LOGW(TAG,
                 "opus out buffer %d is larger than local packet buffer %d",
                 s_encoder_outbuf_size,
                 USAKI_OPUS_MAX_PACKET_BYTES);
        s_encoder_outbuf_size = USAKI_OPUS_MAX_PACKET_BYTES;
    }
    ESP_LOGI(TAG,
             "opus encoder ready: frame_bytes=%d outbuf_size=%d packet_buffer=%d",
             encoder_frame_bytes,
             s_encoder_outbuf_size,
             USAKI_OPUS_MAX_PACKET_BYTES);
    s_encode_pending_samples = 0;
    return ESP_OK;
}

static esp_err_t ensure_decoder(void)
{
    if (s_decoder != NULL)
    {
        return ESP_OK;
    }

    esp_opus_dec_cfg_t config = {
        .sample_rate = USAKI_OPUS_SAMPLE_RATE_HZ,
        .channel = ESP_AUDIO_MONO,
        .frame_duration = OPUS_DEC_FRAME_DURATION_ENUM,
        .self_delimited = false,
    };

    int ret = esp_opus_dec_open(&config, sizeof(config), &s_decoder);
    ESP_RETURN_ON_FALSE(s_decoder != NULL, ESP_FAIL, TAG, "opus decoder open failed: %d", ret);
    ESP_LOGI(TAG, "opus decoder ready: sample_rate=%d channels=%d frame_ms=%d",
             USAKI_OPUS_SAMPLE_RATE_HZ,
             USAKI_OPUS_CHANNELS,
             USAKI_OPUS_FRAME_DURATION_MS);
    return ESP_OK;
}

esp_err_t usaki_opus_audio_init(void)
{
    ESP_RETURN_ON_ERROR(ensure_encoder(), TAG, "encoder init failed");
    ESP_RETURN_ON_ERROR(ensure_decoder(), TAG, "decoder init failed");
    return ESP_OK;
}

void usaki_opus_audio_reset_encoder(void)
{
    s_encode_pending_samples = 0;
}

void usaki_opus_audio_reset_decoder(void)
{
    if (s_decoder != NULL)
    {
        esp_opus_dec_reset(s_decoder);
    }
}

static esp_err_t encode_one_frame(usaki_opus_packet_cb_t callback, void *user_ctx)
{
    ESP_RETURN_ON_FALSE(callback != NULL, ESP_ERR_INVALID_ARG, TAG, "callback is null");
    ESP_RETURN_ON_ERROR(ensure_encoder(), TAG, "encoder not ready");

    esp_audio_enc_in_frame_t in = {
        .buffer = (uint8_t *)s_encode_frame,
        .len = (uint32_t)(USAKI_OPUS_FRAME_SAMPLES * sizeof(int16_t)),
    };
    esp_audio_enc_out_frame_t out = {
        .buffer = s_encode_packet,
        .len = (uint32_t)s_encoder_outbuf_size,
        .encoded_bytes = 0,
    };

    int ret = esp_opus_enc_process(s_encoder, &in, &out);
    ESP_RETURN_ON_FALSE(ret == ESP_AUDIO_ERR_OK, ESP_FAIL, TAG, "opus encode failed: %d", ret);
    if (out.encoded_bytes > 0)
    {
        callback(s_encode_packet, out.encoded_bytes, user_ctx);
    }
    return ESP_OK;
}

esp_err_t usaki_opus_audio_encode_pcm(const int16_t *samples,
                                      size_t sample_count,
                                      usaki_opus_packet_cb_t callback,
                                      void *user_ctx)
{
    ESP_RETURN_ON_FALSE(samples != NULL, ESP_ERR_INVALID_ARG, TAG, "samples is null");

    size_t offset = 0;
    while (offset < sample_count)
    {
        size_t room = USAKI_OPUS_FRAME_SAMPLES - s_encode_pending_samples;
        size_t to_copy = sample_count - offset;
        if (to_copy > room)
        {
            to_copy = room;
        }

        memcpy(&s_encode_frame[s_encode_pending_samples],
               &samples[offset],
               to_copy * sizeof(int16_t));
        s_encode_pending_samples += to_copy;
        offset += to_copy;

        if (s_encode_pending_samples == USAKI_OPUS_FRAME_SAMPLES)
        {
            ESP_RETURN_ON_ERROR(encode_one_frame(callback, user_ctx), TAG, "encode frame failed");
            s_encode_pending_samples = 0;
        }
    }

    return ESP_OK;
}

esp_err_t usaki_opus_audio_flush_encoder(usaki_opus_packet_cb_t callback, void *user_ctx)
{
    if (s_encode_pending_samples == 0)
    {
        return ESP_OK;
    }

    memset(&s_encode_frame[s_encode_pending_samples],
           0,
           (USAKI_OPUS_FRAME_SAMPLES - s_encode_pending_samples) * sizeof(int16_t));
    ESP_RETURN_ON_ERROR(encode_one_frame(callback, user_ctx), TAG, "flush encode frame failed");
    s_encode_pending_samples = 0;
    return ESP_OK;
}

esp_err_t usaki_opus_audio_decode_packet(const uint8_t *data,
                                         size_t len,
                                         int16_t *out_samples,
                                         size_t out_capacity_samples,
                                         size_t *out_sample_count)
{
    ESP_RETURN_ON_FALSE(data != NULL, ESP_ERR_INVALID_ARG, TAG, "data is null");
    ESP_RETURN_ON_FALSE(out_samples != NULL, ESP_ERR_INVALID_ARG, TAG, "out_samples is null");
    ESP_RETURN_ON_FALSE(out_sample_count != NULL, ESP_ERR_INVALID_ARG, TAG, "out_sample_count is null");
    ESP_RETURN_ON_FALSE(out_capacity_samples >= USAKI_OPUS_FRAME_SAMPLES,
                        ESP_ERR_INVALID_SIZE,
                        TAG,
                        "decode output buffer is too small");
    ESP_RETURN_ON_ERROR(ensure_decoder(), TAG, "decoder not ready");

    esp_audio_dec_in_raw_t raw = {
        .buffer = (uint8_t *)data,
        .len = (uint32_t)len,
        .consumed = 0,
        .frame_recover = ESP_AUDIO_DEC_RECOVERY_NONE,
    };
    esp_audio_dec_out_frame_t out = {
        .buffer = (uint8_t *)out_samples,
        .len = (uint32_t)(out_capacity_samples * sizeof(int16_t)),
        .decoded_size = 0,
    };
    esp_audio_dec_info_t info = {0};

    int ret = esp_opus_dec_decode(s_decoder, &raw, &out, &info);
    ESP_RETURN_ON_FALSE(ret == ESP_AUDIO_ERR_OK, ESP_FAIL, TAG, "opus decode failed: %d", ret);

    *out_sample_count = out.decoded_size / sizeof(int16_t);
    return ESP_OK;
}
