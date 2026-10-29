#include "audio/processors/no_audio_processor.h"

#include "esp_log.h"

static const char *TAG = "no_audio_processor";

void NoAudioProcessor::Initialize(AudioCodec *codec, int frame_duration_ms, srmodel_list_t *models_list)
{
    (void)models_list;

    codec_ = codec;
    frame_samples_ = frame_duration_ms * 16000 / 1000;
    output_buffer_.clear();
    output_buffer_.reserve(frame_samples_);
}

void NoAudioProcessor::Feed(std::vector<int16_t> &&data)
{
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    if (!is_running_ || !output_callback_ || codec_ == nullptr) {
        return;
    }

    if (codec_->input_channels() == 2) {
        for (size_t i = 0; i + 1 < data.size(); i += 2) {
            output_buffer_.push_back(data[i]);
        }
    } else {
        output_buffer_.insert(output_buffer_.end(), data.begin(), data.end());
    }

    while (output_buffer_.size() >= static_cast<size_t>(frame_samples_)) {
        std::vector<int16_t> frame(output_buffer_.begin(),
                                   output_buffer_.begin() + frame_samples_);
        output_buffer_.erase(output_buffer_.begin(), output_buffer_.begin() + frame_samples_);
        output_callback_(std::move(frame));
    }
}

void NoAudioProcessor::Start()
{
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    output_buffer_.clear();
    is_running_ = true;
}

void NoAudioProcessor::Stop()
{
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    is_running_ = false;
    output_buffer_.clear();
}

bool NoAudioProcessor::IsRunning()
{
    return is_running_;
}

void NoAudioProcessor::OnOutput(std::function<void(std::vector<int16_t> &&data)> callback)
{
    output_callback_ = callback;
}

void NoAudioProcessor::OnVadStateChange(std::function<void(bool speaking)> callback)
{
    vad_state_change_callback_ = callback;
}

size_t NoAudioProcessor::GetFeedSize()
{
    return static_cast<size_t>(frame_samples_);
}

void NoAudioProcessor::EnableDeviceAec(bool enable)
{
    if (enable) {
        ESP_LOGW(TAG, "device AEC is not supported by NoAudioProcessor");
    }
}
