#include "audio/audio_codec.h"

#include "esp_log.h"

static const char *TAG = "audio_codec";

void AudioCodec::Start()
{
    ESP_LOGI(TAG, "audio codec started");
}

void AudioCodec::EnableInput(bool enable)
{
    input_enabled_ = enable;
}

void AudioCodec::EnableOutput(bool enable)
{
    output_enabled_ = enable;
}

void AudioCodec::SetOutputVolume(int volume)
{
    if (volume < 0) {
        volume = 0;
    } else if (volume > 100) {
        volume = 100;
    }
    output_volume_ = volume;
}

void AudioCodec::SetInputGain(float gain)
{
    input_gain_ = gain;
}

bool AudioCodec::InputData(std::vector<int16_t> &data)
{
    int count = Read(data.data(), static_cast<int>(data.size()));
    if (count <= 0) return false;
    data.resize(static_cast<size_t>(count));
    return true;
}

void AudioCodec::OutputData(std::vector<int16_t> &data)
{
    (void)Write(data.data(), static_cast<int>(data.size()));
}

void AudioCodec::FlushOutput()
{
}
