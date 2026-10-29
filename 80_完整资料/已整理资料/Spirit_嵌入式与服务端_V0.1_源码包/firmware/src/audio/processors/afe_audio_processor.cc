#include "audio/processors/afe_audio_processor.h"

#if CONFIG_USAKI_USE_AFE_AUDIO_PROCESSOR

#include <cstddef>
#include <cstdint>
#include <string>

#include "board/usaki_board.h"
#include "esp_log.h"
#include "model_path.h"

static const char *TAG = "afe_audio_processor";
static constexpr EventBits_t kProcessorRunning = BIT0;
static constexpr int kVadSpeechConfirmFrames = USAKI_VOICE_CLIENT_UPLOAD_START_SOUND_FRAMES;
static constexpr int kVadSilenceConfirmFrames = USAKI_VOICE_CLIENT_UPLOAD_END_IDLE_FRAMES;
static constexpr TickType_t kVadStartGraceTicks = pdMS_TO_TICKS(USAKI_VOICE_CLIENT_VAD_START_GRACE_MS);
static constexpr TickType_t kVadGateLogIntervalTicks = pdMS_TO_TICKS(1000);

struct AfeAudioLevel {
    int32_t avg = 0;
    int32_t peak = 0;
};

static int32_t abs_i16(int16_t value)
{
    return value == INT16_MIN ? INT16_MAX : (value < 0 ? -value : value);
}

static AfeAudioLevel measure_audio_level(const int16_t *data, size_t samples)
{
    AfeAudioLevel level = {};
    if (data == nullptr || samples == 0) {
        return level;
    }

    int64_t sum = 0;
    int32_t peak = 0;
    for (size_t i = 0; i < samples; ++i) {
        int32_t value = abs_i16(data[i]);
        sum += value;
        if (value > peak) {
            peak = value;
        }
    }
    level.avg = static_cast<int32_t>(sum / samples);
    level.peak = peak;
    return level;
}

static bool level_passes_start_gate(const AfeAudioLevel &level)
{
    return level.avg >= USAKI_VOICE_CLIENT_UPLOAD_START_AVG_THRESHOLD ||
           (level.peak >= USAKI_VOICE_CLIENT_UPLOAD_START_PEAK_THRESHOLD &&
            level.avg >= USAKI_VOICE_CLIENT_UPLOAD_START_PEAK_MIN_AVG_THRESHOLD);
}

static bool level_passes_continue_gate(const AfeAudioLevel &level)
{
    return level.avg >= USAKI_VOICE_CLIENT_UPLOAD_CONTINUE_AVG_THRESHOLD ||
           (level.peak >= USAKI_VOICE_CLIENT_UPLOAD_CONTINUE_PEAK_THRESHOLD &&
            level.avg >= USAKI_VOICE_CLIENT_UPLOAD_CONTINUE_PEAK_MIN_AVG_THRESHOLD);
}

static bool level_passes_voice_gate(const AfeAudioLevel &level, bool already_speaking)
{
    return already_speaking ? level_passes_continue_gate(level) : level_passes_start_gate(level);
}

AfeAudioProcessor::AfeAudioProcessor()
{
    event_group_ = xEventGroupCreate();
}

AfeAudioProcessor::~AfeAudioProcessor()
{
    if (afe_data_ != nullptr && afe_iface_ != nullptr) {
        afe_iface_->destroy(afe_data_);
    }
    if (event_group_ != nullptr) {
        vEventGroupDelete(event_group_);
    }
}

void AfeAudioProcessor::Initialize(AudioCodec *codec, int frame_duration_ms, srmodel_list_t *models_list)
{
    codec_ = codec;
    frame_samples_ = frame_duration_ms * 16000 / 1000;
    output_buffer_.reserve(frame_samples_);

    const int ref_num = codec_->input_reference() ? 1 : 0;
    std::string input_format;
    for (int i = 0; i < codec_->input_channels() - ref_num; ++i) {
        input_format.push_back('M');
    }
    for (int i = 0; i < ref_num; ++i) {
        input_format.push_back('R');
    }

    srmodel_list_t *models = models_list != nullptr ? models_list : esp_srmodel_init("model");
    char *ns_model_name = models != nullptr ? esp_srmodel_filter(models, ESP_NSNET_PREFIX, nullptr) : nullptr;
    char *vad_model_name = models != nullptr ? esp_srmodel_filter(models, ESP_VADN_PREFIX, nullptr) : nullptr;

    afe_config_t *afe_config = afe_config_init(input_format.c_str(), nullptr, AFE_TYPE_VC, AFE_MODE_HIGH_PERF);
    afe_config->aec_mode = AEC_MODE_VOIP_HIGH_PERF;
    afe_config->vad_mode = VAD_MODE_2;
    afe_config->vad_min_noise_ms = 180;
    afe_config->vad_init = true;
    afe_config->aec_init = false;
    afe_config->agc_init = false;
    afe_config->memory_alloc_mode = AFE_MEMORY_ALLOC_MORE_PSRAM;
    if (vad_model_name != nullptr) {
        afe_config->vad_model_name = vad_model_name;
    }
    if (ns_model_name != nullptr) {
        afe_config->ns_init = true;
        afe_config->ns_model_name = ns_model_name;
        afe_config->afe_ns_mode = AFE_NS_MODE_NET;
    } else {
        afe_config->ns_init = false;
    }

    afe_iface_ = esp_afe_handle_from_config(afe_config);
    afe_data_ = afe_iface_->create_from_config(afe_config);

    BaseType_t ok = xTaskCreate([](void *arg) {
        static_cast<AfeAudioProcessor *>(arg)->ProcessorTask();
        vTaskDelete(nullptr);
    }, "afe_processor", 4096, this, 10, nullptr);
    if (ok != pdPASS) {
        ESP_LOGE(TAG, "create afe_processor failed");
        afe_iface_->destroy(afe_data_);
        afe_data_ = nullptr;
        afe_iface_ = nullptr;
        return;
    }

    ESP_LOGI(TAG,
             "initialized: input_format=%s feed_chunk=%d fetch_chunk=%d",
             input_format.c_str(),
             afe_iface_->get_feed_chunksize(afe_data_),
             afe_iface_->get_fetch_chunksize(afe_data_));
}

void AfeAudioProcessor::Feed(std::vector<int16_t> &&data)
{
    if (afe_data_ == nullptr || afe_iface_ == nullptr) {
        return;
    }

    std::lock_guard<std::mutex> lock(input_buffer_mutex_);
    if (!IsRunning()) {
        return;
    }

    input_buffer_.insert(input_buffer_.end(), data.begin(), data.end());
    const size_t chunk_size = afe_iface_->get_feed_chunksize(afe_data_) * codec_->input_channels();
    while (input_buffer_.size() >= chunk_size) {
        afe_iface_->feed(afe_data_, input_buffer_.data());
        input_buffer_.erase(input_buffer_.begin(), input_buffer_.begin() + chunk_size);
    }
}

void AfeAudioProcessor::Start()
{
    started_at_ticks_ = xTaskGetTickCount();
    xEventGroupSetBits(event_group_, kProcessorRunning);
}

void AfeAudioProcessor::Stop()
{
    xEventGroupClearBits(event_group_, kProcessorRunning);
    std::lock_guard<std::mutex> lock(input_buffer_mutex_);
    if (afe_data_ != nullptr) {
        afe_iface_->reset_buffer(afe_data_);
    }
    input_buffer_.clear();
    output_buffer_.clear();
    is_speaking_ = false;
    vad_speech_frames_ = 0;
    vad_silence_frames_ = 0;
    last_vad_gate_log_ = 0;
    started_at_ticks_ = 0;
}

bool AfeAudioProcessor::IsRunning()
{
    return (xEventGroupGetBits(event_group_) & kProcessorRunning) != 0;
}

void AfeAudioProcessor::OnOutput(std::function<void(std::vector<int16_t> &&data)> callback)
{
    output_callback_ = callback;
}

void AfeAudioProcessor::OnVadStateChange(std::function<void(bool speaking)> callback)
{
    vad_state_change_callback_ = callback;
}

size_t AfeAudioProcessor::GetFeedSize()
{
    return afe_data_ != nullptr && afe_iface_ != nullptr ? afe_iface_->get_feed_chunksize(afe_data_) : 0;
}

void AfeAudioProcessor::EnableDeviceAec(bool enable)
{
    if (afe_data_ == nullptr) {
        return;
    }
    if (enable) {
        afe_iface_->disable_vad(afe_data_);
        afe_iface_->enable_aec(afe_data_);
    } else {
        afe_iface_->disable_aec(afe_data_);
        afe_iface_->enable_vad(afe_data_);
    }
}

void AfeAudioProcessor::ProcessorTask()
{
    ESP_LOGI(TAG, "task started");
    while (true) {
        xEventGroupWaitBits(event_group_, kProcessorRunning, pdFALSE, pdTRUE, portMAX_DELAY);
        afe_fetch_result_t *res = afe_iface_->fetch_with_delay(afe_data_, portMAX_DELAY);
        if (!IsRunning() || res == nullptr || res->ret_value == ESP_FAIL) {
            continue;
        }

        const size_t samples = res->data_size / sizeof(int16_t);
        const AfeAudioLevel level = measure_audio_level(res->data, samples);
        const bool afe_speech = res->vad_state == VAD_SPEECH;
        const bool in_start_grace =
            started_at_ticks_ != 0 &&
            xTaskGetTickCount() - started_at_ticks_ < kVadStartGraceTicks;
        const bool gated_speech =
            !in_start_grace && afe_speech && level_passes_voice_gate(level, is_speaking_);

        if (afe_speech && !gated_speech) {
            TickType_t now = xTaskGetTickCount();
            if (last_vad_gate_log_ == 0 ||
                now - last_vad_gate_log_ >= kVadGateLogIntervalTicks) {
                ESP_LOGD(TAG,
                         "reject vad speech: avg=%ld peak=%ld speaking=%d grace=%d "
                         "start(avg=%d peak=%d peak_avg=%d) continue(avg=%d peak=%d peak_avg=%d)",
                         (long)level.avg,
                         (long)level.peak,
                         is_speaking_ ? 1 : 0,
                         in_start_grace ? 1 : 0,
                         USAKI_VOICE_CLIENT_UPLOAD_START_AVG_THRESHOLD,
                         USAKI_VOICE_CLIENT_UPLOAD_START_PEAK_THRESHOLD,
                         USAKI_VOICE_CLIENT_UPLOAD_START_PEAK_MIN_AVG_THRESHOLD,
                         USAKI_VOICE_CLIENT_UPLOAD_CONTINUE_AVG_THRESHOLD,
                         USAKI_VOICE_CLIENT_UPLOAD_CONTINUE_PEAK_THRESHOLD,
                         USAKI_VOICE_CLIENT_UPLOAD_CONTINUE_PEAK_MIN_AVG_THRESHOLD);
                last_vad_gate_log_ = now;
            }
        }

        if (vad_state_change_callback_) {
            if (gated_speech) {
                vad_speech_frames_++;
                vad_silence_frames_ = 0;
                if (!is_speaking_ && vad_speech_frames_ >= kVadSpeechConfirmFrames) {
                    is_speaking_ = true;
                    vad_state_change_callback_(true);
                }
            } else if (res->vad_state == VAD_SILENCE || afe_speech) {
                vad_silence_frames_++;
                vad_speech_frames_ = 0;
                if (is_speaking_ && vad_silence_frames_ >= kVadSilenceConfirmFrames) {
                    is_speaking_ = false;
                    vad_state_change_callback_(false);
                }
            } else {
                vad_speech_frames_ = 0;
                vad_silence_frames_ = 0;
            }
        }

        if (!IsRunning()) {
            continue;
        }

        if (!output_callback_) {
            continue;
        }

        output_buffer_.insert(output_buffer_.end(), res->data, res->data + samples);
        while (output_buffer_.size() >= static_cast<size_t>(frame_samples_)) {
            std::vector<int16_t> frame(output_buffer_.begin(),
                                       output_buffer_.begin() + frame_samples_);
            output_buffer_.erase(output_buffer_.begin(), output_buffer_.begin() + frame_samples_);
            output_callback_(std::move(frame));
        }
    }
}

#endif
