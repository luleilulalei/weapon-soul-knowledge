#include "audio/codecs/usaki_audio_codec.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>

#include "board/usaki_board.h"
#include "drivers/spirit_pdm.h"
#include "app/spirit_privacy.h"
#include "esp_log.h"
#include "spirit_peripherals/spirit_peripherals.h"

static const char *TAG = "usaki_audio_codec";
static constexpr uint32_t kWriteTimeoutMs = USAKI_VOICE_CLIENT_PLAYBACK_TIMEOUT_MS;

static int16_t clamp_i16(int32_t value)
{
    if (value > INT16_MAX) {
        return INT16_MAX;
    }
    if (value < INT16_MIN) {
        return INT16_MIN;
    }
    return static_cast<int16_t>(value);
}

UsakiAudioCodec::UsakiAudioCodec()
{
    duplex_ = true;
    input_reference_ = false;
    input_sample_rate_ = USAKI_MIC_SAMPLE_RATE_HZ;
    output_sample_rate_ = USAKI_AMP_SAMPLE_RATE_HZ;
    input_channels_ = 1;
    output_channels_ = 1;
    output_volume_ = USAKI_AMP_OUTPUT_VOLUME;
}

UsakiAudioCodec::~UsakiAudioCodec()
{
    if (amp_ != nullptr) {
        (void)max98357a_destroy(amp_);
        amp_ = nullptr;
    }
    spirit_pdm_deinit();
    gpio_set_level(SPIRIT_AMP_EN_GPIO, 0);
    (void)spirit_boost_request(SPIRIT_BOOST_AUDIO, false);
}

void UsakiAudioCodec::Start()
{
    if (started_) {
        return;
    }

    esp_err_t err = spirit_pdm_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "mic init failed: %s", esp_err_to_name(err));
        return;
    }

    max98357a_config_t amp_config = {
        .i2s_port = USAKI_AMP_I2S_PORT,
        .bclk_gpio = USAKI_AMP_BCLK_GPIO,
        .ws_gpio = USAKI_AMP_LRC_GPIO,
        .data_gpio = USAKI_AMP_DIN_GPIO,
        .sample_rate_hz = USAKI_AMP_SAMPLE_RATE_HZ,
        .dma_desc_num = USAKI_AMP_DMA_DESC_NUM,
        .dma_frame_num = USAKI_AMP_DMA_FRAME_NUM,
    };
    err = max98357a_create(&amp_config, &amp_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "amp init failed: %s", esp_err_to_name(err));
        spirit_pdm_deinit();
        return;
    }

    gpio_config_t en = {};
    en.pin_bit_mask = 1ULL << SPIRIT_AMP_EN_GPIO;
    en.mode = GPIO_MODE_OUTPUT;
    if (gpio_config(&en) != ESP_OK) { spirit_pdm_deinit(); return; }
    output_stereo_.resize(USAKI_AMP_DMA_FRAME_NUM * 2);
    started_ = true;
    EnableInput(false);
    EnableOutput(true);
    ESP_LOGI(TAG, "codec started: input=%dHz mono output=%dHz mono",
             input_sample_rate_,
             output_sample_rate_);
    ESP_LOGI(TAG, "output volume: %d%%", output_volume_);
}

void UsakiAudioCodec::EnableInput(bool enable)
{
    std::lock_guard<std::recursive_mutex> lock(spirit_privacy_gate());
    enable = enable && !spirit_privacy_muted();
    input_enabled_ = (spirit_pdm_enable(enable) == ESP_OK) && enable;
    ESP_LOGI(TAG, "input %s", enable ? "enabled" : "disabled");
}

void UsakiAudioCodec::EnableOutput(bool enable)
{
    if (enable) {
        esp_err_t err = spirit_boost_request(SPIRIT_BOOST_AUDIO, true);
        if (err != ESP_OK) { output_enabled_ = false; ESP_LOGE(TAG, "boost unavailable: %s", esp_err_to_name(err)); return; }
        gpio_set_level(SPIRIT_AMP_EN_GPIO, 1);
    } else {
        gpio_set_level(SPIRIT_AMP_EN_GPIO, 0);
        (void)spirit_boost_request(SPIRIT_BOOST_AUDIO, false);
    }
    output_enabled_ = enable;
    ESP_LOGI(TAG, "output %s", enable ? "enabled" : "disabled");
}

void UsakiAudioCodec::FlushOutput()
{
    if (!started_ || amp_ == nullptr) {
        return;
    }

    const size_t silence_frames = static_cast<size_t>(output_sample_rate_ / 5);
    esp_err_t err = max98357a_write_silence(amp_, silence_frames, kWriteTimeoutMs);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "flush output failed: %s", esp_err_to_name(err));
    }
}

int UsakiAudioCodec::Read(int16_t *dest, int samples)
{
    std::lock_guard<std::recursive_mutex> lock(spirit_privacy_gate());
    if (!started_ || !input_enabled_ || spirit_privacy_muted() || dest == nullptr || samples <= 0) return 0;
    size_t frames_read = 0;
    esp_err_t err = spirit_pdm_read(dest, static_cast<size_t>(samples), &frames_read);
    return err == ESP_OK ? static_cast<int>(frames_read) : 0;
}

int UsakiAudioCodec::Write(const int16_t *data, int samples)
{
    if (!started_ || !output_enabled_ || amp_ == nullptr || data == nullptr || samples <= 0) {
        return 0;
    }

    size_t written_samples = 0;
    while (written_samples < static_cast<size_t>(samples)) {
        const size_t mono_now = std::min(static_cast<size_t>(samples) - written_samples,
                                         output_stereo_.size() / 2);
        for (size_t i = 0; i < mono_now; ++i) {
            int16_t sample = clamp_i16(static_cast<int32_t>(data[written_samples + i]) *
                                       output_volume_ / 100);
            output_stereo_[i * 2] = sample;
            output_stereo_[i * 2 + 1] = sample;
        }

        esp_err_t err = max98357a_write_interleaved_i16(amp_,
                                                        output_stereo_.data(),
                                                        mono_now * 2,
                                                        kWriteTimeoutMs);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "amp write failed: %s", esp_err_to_name(err));
            break;
        }
        written_samples += mono_now;
    }

    return static_cast<int>(written_samples);
}
