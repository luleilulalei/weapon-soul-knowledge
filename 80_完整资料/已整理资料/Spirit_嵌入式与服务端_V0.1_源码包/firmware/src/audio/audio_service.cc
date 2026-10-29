#include "app/spirit_privacy.h"
#include "audio/audio_service.h"

#include <cstring>

#include "sdkconfig.h"

#if CONFIG_USAKI_USE_AFE_AUDIO_PROCESSOR
#include "audio/processors/afe_audio_processor.h"
#else
#include "audio/processors/no_audio_processor.h"
#endif
#include "esp_audio_enc.h"
#include "esp_audio_types.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_opus_dec.h"
#include "esp_opus_enc.h"
#if CONFIG_USAKI_WAKE_WORD_USE_AFE
#include "audio/wake_words/afe_wake_word.h"
#else
#include "audio/wake_words/no_wake_word.h"
#endif

static const char *TAG = "audio_service";
static constexpr EventBits_t kInputExited = BIT2;
static constexpr EventBits_t kOutputExited = BIT3;
static constexpr EventBits_t kOpusExited = BIT4;

#define AS_OPUS_ENC_FRAME_DURATION(duration_ms)                   \
    ((duration_ms) == 60 ? ESP_OPUS_ENC_FRAME_DURATION_60_MS :    \
     (duration_ms) == 40 ? ESP_OPUS_ENC_FRAME_DURATION_40_MS :    \
     (duration_ms) == 20 ? ESP_OPUS_ENC_FRAME_DURATION_20_MS :    \
     (duration_ms) == 10 ? ESP_OPUS_ENC_FRAME_DURATION_10_MS :    \
     ESP_OPUS_ENC_FRAME_DURATION_60_MS)

#define AS_OPUS_DEC_FRAME_DURATION(duration_ms)                   \
    ((duration_ms) == 60 ? ESP_OPUS_DEC_FRAME_DURATION_60_MS :    \
     (duration_ms) == 40 ? ESP_OPUS_DEC_FRAME_DURATION_40_MS :    \
     (duration_ms) == 20 ? ESP_OPUS_DEC_FRAME_DURATION_20_MS :    \
     (duration_ms) == 10 ? ESP_OPUS_DEC_FRAME_DURATION_10_MS :    \
     ESP_OPUS_DEC_FRAME_DURATION_60_MS)

AudioService::AudioService()
{
    event_group_ = xEventGroupCreate();
}

AudioService::~AudioService()
{
    Stop();
    if (opus_encoder_ != nullptr) {
        esp_opus_enc_close(opus_encoder_);
        opus_encoder_ = nullptr;
    }
    if (opus_decoder_ != nullptr) {
        esp_opus_dec_close(opus_decoder_);
        opus_decoder_ = nullptr;
    }
    if (event_group_ != nullptr) {
        vEventGroupDelete(event_group_);
        event_group_ = nullptr;
    }
}

esp_err_t AudioService::Initialize(AudioCodec *codec)
{
    ESP_RETURN_ON_FALSE(codec != nullptr, ESP_ERR_INVALID_ARG, TAG, "codec is null");
    ESP_RETURN_ON_FALSE(event_group_ != nullptr, ESP_ERR_NO_MEM, TAG, "event group allocation failed");
    codec_ = codec;
    codec_->Start();

    esp_opus_enc_config_t enc_config = {
        .sample_rate = ESP_AUDIO_SAMPLE_RATE_16K,
        .channel = ESP_AUDIO_MONO,
        .bits_per_sample = ESP_AUDIO_BIT16,
        .bitrate = ESP_OPUS_BITRATE_AUTO,
        .frame_duration = AS_OPUS_ENC_FRAME_DURATION(OPUS_FRAME_DURATION_MS),
        .application_mode = ESP_OPUS_ENC_APPLICATION_AUDIO,
        .complexity = 0,
        .enable_fec = false,
        .enable_dtx = true,
        .enable_vbr = true,
    };

    int ret = esp_opus_enc_open(&enc_config, sizeof(enc_config), &opus_encoder_);
    ESP_RETURN_ON_FALSE(opus_encoder_ != nullptr, ESP_FAIL, TAG, "opus encoder open failed: %d", ret);
    esp_opus_enc_get_frame_size(opus_encoder_, &encoder_frame_size_, &encoder_outbuf_size_);
    encoder_frame_size_ /= sizeof(int16_t);

    esp_opus_dec_cfg_t dec_config = {
        .sample_rate = static_cast<uint32_t>(codec_->output_sample_rate()),
        .channel = ESP_AUDIO_MONO,
        .frame_duration = AS_OPUS_DEC_FRAME_DURATION(OPUS_FRAME_DURATION_MS),
        .self_delimited = false,
    };

    ret = esp_opus_dec_open(&dec_config, sizeof(dec_config), &opus_decoder_);
    ESP_RETURN_ON_FALSE(opus_decoder_ != nullptr, ESP_FAIL, TAG, "opus decoder open failed: %d", ret);
    decoder_sample_rate_ = codec_->output_sample_rate();
    decoder_frame_size_ = decoder_sample_rate_ * OPUS_FRAME_DURATION_MS / 1000;

#if CONFIG_USAKI_USE_AFE_AUDIO_PROCESSOR
    audio_processor_ = std::make_unique<AfeAudioProcessor>();
#else
    audio_processor_ = std::make_unique<NoAudioProcessor>();
#endif
#if CONFIG_USAKI_WAKE_WORD_USE_AFE
    wake_word_ = std::make_unique<AfeWakeWord>();
#else
    wake_word_ = std::make_unique<NoWakeWord>();
#endif
    audio_processor_->OnOutput([this](std::vector<int16_t> &&data) {
        PushTaskToEncodeQueue(std::move(data));
    });
    audio_processor_->OnVadStateChange([this](bool speaking) {
        voice_detected_ = speaking;
        if (callbacks_.on_vad_change) {
            callbacks_.on_vad_change(speaking);
        }
    });
    wake_word_->OnWakeWordDetected([this](const std::string &wake_word) {
        ESP_LOGI(TAG, "wake word detected: %s", wake_word.c_str());
        if (callbacks_.on_wake_word_detected) {
            callbacks_.on_wake_word_detected(wake_word);
        }
    });

    ESP_LOGI(TAG,
             "initialized: encoder_frame=%d samples decoder_frame=%d samples",
             encoder_frame_size_,
             decoder_frame_size_);
    return ESP_OK;
}

esp_err_t AudioService::Start()
{
    ESP_RETURN_ON_FALSE(codec_ != nullptr, ESP_ERR_INVALID_STATE, TAG, "service is not initialized");
    if (!service_stopped_) {
        return ESP_OK;
    }

    service_stopped_ = false;
    xEventGroupClearBits(event_group_, kInputExited | kOutputExited | kOpusExited);
    xEventGroupClearBits(event_group_, AS_EVENT_AUDIO_PROCESSOR_RUNNING | AS_EVENT_WAKE_WORD_RUNNING);

    BaseType_t ok = xTaskCreate([](void *arg) {
        static_cast<AudioService *>(arg)->AudioInputTask();
        vTaskDelete(nullptr);
    }, "audio_input", 6144, this, 8, &audio_input_task_handle_);
    ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_ERR_NO_MEM, TAG, "create audio_input failed");

    ok = xTaskCreate([](void *arg) {
        static_cast<AudioService *>(arg)->AudioOutputTask();
        vTaskDelete(nullptr);
    }, "audio_output", 4096, this, 4, &audio_output_task_handle_);
    ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_ERR_NO_MEM, TAG, "create audio_output failed");

    ok = xTaskCreate([](void *arg) {
        static_cast<AudioService *>(arg)->OpusCodecTask();
        vTaskDelete(nullptr);
    }, "opus_codec", 24576, this, 3, &opus_codec_task_handle_);
    ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_ERR_NO_MEM, TAG, "create opus_codec failed");

    ESP_LOGI(TAG, "started");
    return ESP_OK;
}

void AudioService::Stop()
{
    if (service_stopped_) {
        return;
    }

    {
        std::lock_guard<std::mutex> lock(audio_queue_mutex_);
        service_stopped_ = true;
    }
    xEventGroupSetBits(event_group_, AS_EVENT_AUDIO_PROCESSOR_RUNNING | AS_EVENT_WAKE_WORD_RUNNING);
    audio_queue_cv_.notify_all();
    EventBits_t wait = 0;
    if (audio_input_task_handle_) wait |= kInputExited;
    if (audio_output_task_handle_) wait |= kOutputExited;
    if (opus_codec_task_handle_) wait |= kOpusExited;
    if (wait) xEventGroupWaitBits(event_group_, wait, pdFALSE, pdTRUE, portMAX_DELAY);
    audio_input_task_handle_ = audio_output_task_handle_ = opus_codec_task_handle_ = nullptr;
    if (codec_) { codec_->EnableInput(false); codec_->EnableOutput(false); }
}

void AudioService::SetCallbacks(const AudioServiceCallbacks &callbacks)
{
    callbacks_ = callbacks;
}

void AudioService::EnableVoiceProcessing(bool enable)
{
    if (enable && spirit_privacy_muted()) return;
    if (audio_processor_ == nullptr || codec_ == nullptr) {
        return;
    }

    if (enable) {
        if (!audio_processor_initialized_) {
            audio_processor_->Initialize(codec_, OPUS_FRAME_DURATION_MS, nullptr);
            audio_processor_initialized_ = true;
        }
        ResetDecoder();
        codec_->EnableInput(true);
        audio_processor_->Start();
        xEventGroupSetBits(event_group_, AS_EVENT_AUDIO_PROCESSOR_RUNNING);
    } else {
        xEventGroupClearBits(event_group_, AS_EVENT_AUDIO_PROCESSOR_RUNNING);
        audio_processor_->Stop();
        if (!IsWakeWordRunning()) codec_->EnableInput(false);
        voice_detected_ = false;
    }
}

void AudioService::EnableDeviceAec(bool enable)
{
    if (audio_processor_ != nullptr) {
        audio_processor_->EnableDeviceAec(enable);
    }
}

esp_err_t AudioService::EnableWakeWordDetection(bool enable)
{
    if (enable && spirit_privacy_muted()) return ESP_ERR_INVALID_STATE;
    if (wake_word_ == nullptr || codec_ == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }

    if (enable) {
#if CONFIG_USAKI_ENABLE_WAKE_WORD
        if (!wake_word_initialized_) {
            ESP_RETURN_ON_ERROR(wake_word_->Initialize(codec_), TAG, "wake word init failed");
            wake_word_initialized_ = true;
        }
        codec_->EnableInput(true);
        wake_word_->Start();
        if (!wake_word_->IsRunning()) {
            ESP_LOGW(TAG, "wake word implementation did not enter running state");
            return ESP_ERR_NOT_SUPPORTED;
        }
        xEventGroupSetBits(event_group_, AS_EVENT_WAKE_WORD_RUNNING);
        ESP_LOGI(TAG, "wake word detection enabled");
        return ESP_OK;
#else
        ESP_LOGW(TAG, "wake word detection requested but CONFIG_USAKI_ENABLE_WAKE_WORD is disabled");
        return ESP_ERR_NOT_SUPPORTED;
#endif
    }

    wake_word_->Stop();
    if (!IsAudioProcessorRunning()) codec_->EnableInput(false);
    xEventGroupClearBits(event_group_, AS_EVENT_WAKE_WORD_RUNNING);
    ESP_LOGI(TAG, "wake word detection disabled");
    return ESP_OK;
}

bool AudioService::IsAudioProcessorRunning() const
{
    return (xEventGroupGetBits(event_group_) & AS_EVENT_AUDIO_PROCESSOR_RUNNING) != 0;
}

bool AudioService::IsWakeWordRunning() const
{
    return (xEventGroupGetBits(event_group_) & AS_EVENT_WAKE_WORD_RUNNING) != 0;
}

bool AudioService::IsAfeWakeWord() const
{
    return wake_word_ != nullptr && wake_word_->IsAfeWakeWord();
}

const std::string &AudioService::GetLastWakeWord() const
{
    static const std::string empty;
    return wake_word_ != nullptr ? wake_word_->GetLastDetectedWakeWord() : empty;
}

bool AudioService::IsIdle()
{
    std::lock_guard<std::mutex> lock(audio_queue_mutex_);
    return audio_encode_queue_.empty() &&
           audio_playback_queue_.empty() &&
           audio_decode_queue_.empty() &&
           audio_send_queue_.empty();
}

void AudioService::WaitForPlaybackQueueEmpty()
{
    std::unique_lock<std::mutex> lock(audio_queue_mutex_);
    audio_queue_cv_.wait(lock, [this]() {
        return service_stopped_ ||
               (audio_decode_queue_.empty() && audio_playback_queue_.empty() && !playback_active_);
    });
}

void AudioService::FlushOutput()
{
    if (codec_ != nullptr) {
        codec_->FlushOutput();
    }
}

bool AudioService::PlayLocalPcm(std::vector<int16_t> &&pcm, bool interrupt)
{
    if (pcm.empty()) {
        return false;
    }

    auto task = std::make_unique<AudioTask>();
    task->type = AudioTaskType::DecodeToPlaybackQueue;
    task->pcm = std::move(pcm);

    std::lock_guard<std::mutex> lock(audio_queue_mutex_);
    if (service_stopped_) {
        return false;
    }

    if (interrupt) {
        if (opus_decoder_ != nullptr) {
            esp_opus_dec_reset(opus_decoder_);
        }
        audio_decode_queue_.clear();
        audio_playback_queue_.clear();
    } else if (audio_playback_queue_.size() >= MAX_PLAYBACK_TASKS_IN_QUEUE) {
        return false;
    }

    audio_playback_queue_.push_back(std::move(task));
    audio_queue_cv_.notify_all();
    return true;
}

bool AudioService::PushPacketToDecodeQueue(std::unique_ptr<AudioStreamPacket> packet, bool wait)
{
    if (packet == nullptr) {
        return false;
    }

    std::unique_lock<std::mutex> lock(audio_queue_mutex_);
    if (wait) {
        audio_queue_cv_.wait(lock, [this]() {
            return service_stopped_ || audio_decode_queue_.size() < MAX_DECODE_PACKETS_IN_QUEUE;
        });
    } else if (audio_decode_queue_.size() >= MAX_DECODE_PACKETS_IN_QUEUE) {
        return false;
    }

    audio_decode_queue_.push_back(std::move(packet));
    audio_queue_cv_.notify_all();
    return true;
}

std::unique_ptr<AudioStreamPacket> AudioService::PopPacketFromSendQueue()
{
    std::lock_guard<std::mutex> lock(audio_queue_mutex_);
    if (audio_send_queue_.empty()) {
        return nullptr;
    }

    auto packet = std::move(audio_send_queue_.front());
    audio_send_queue_.pop_front();
    audio_queue_cv_.notify_all();
    return packet;
}

size_t AudioService::TrimSendQueueTo(size_t max_packets)
{
    std::lock_guard<std::mutex> lock(audio_queue_mutex_);
    size_t dropped = 0;
    while (audio_send_queue_.size() > max_packets) {
        audio_send_queue_.pop_front();
        dropped++;
    }
    if (dropped > 0) {
        audio_queue_cv_.notify_all();
    }
    return dropped;
}

size_t AudioService::PendingInputAudioCount() const
{
    std::lock_guard<std::mutex> lock(audio_queue_mutex_);
    return audio_encode_queue_.size() + audio_send_queue_.size() + input_encode_in_flight_;
}

size_t AudioService::DiscardPendingInputAudio()
{
    std::lock_guard<std::mutex> lock(audio_queue_mutex_);
    size_t dropped = audio_encode_queue_.size() + audio_send_queue_.size() + input_encode_in_flight_;
    input_audio_generation_++;
    audio_encode_queue_.clear();
    audio_send_queue_.clear();
    if (dropped > 0) {
        audio_queue_cv_.notify_all();
    }
    return dropped;
}

void AudioService::ResetDecoder()
{
    std::lock_guard<std::mutex> lock(audio_queue_mutex_);
    std::lock_guard<std::mutex> decoder_lock(decoder_mutex_);
    if (opus_decoder_ != nullptr) {
        esp_opus_dec_reset(opus_decoder_);
    }
    audio_decode_queue_.clear();
    audio_playback_queue_.clear();
    playback_active_ = false;
    audio_queue_cv_.notify_all();
}

void AudioService::AudioInputTask()
{
    while (!service_stopped_) {
        EventBits_t bits = xEventGroupWaitBits(event_group_,
                                               AS_EVENT_AUDIO_PROCESSOR_RUNNING | AS_EVENT_WAKE_WORD_RUNNING,
                                               pdFALSE,
                                               pdFALSE,
                                               portMAX_DELAY);
        if (service_stopped_) {
            break;
        }

        const uint32_t capture_epoch = spirit_privacy_epoch();
        std::vector<int16_t> data(160 * codec_->input_channels());
        if (codec_->InputData(data)) {
            std::lock_guard<std::recursive_mutex> privacy_lock(spirit_privacy_gate());
            if (spirit_privacy_muted() || capture_epoch != spirit_privacy_epoch()) continue;
            if ((bits & AS_EVENT_WAKE_WORD_RUNNING) && wake_word_ != nullptr) {
                wake_word_->Feed(data);
            }
            if ((bits & AS_EVENT_AUDIO_PROCESSOR_RUNNING) && audio_processor_ != nullptr) {
                audio_processor_->Feed(std::move(data));
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }

    ESP_LOGI(TAG, "audio input task stopped");
    xEventGroupSetBits(event_group_, kInputExited);
}

void AudioService::AudioOutputTask()
{
    while (true) {
        std::unique_lock<std::mutex> lock(audio_queue_mutex_);
        audio_queue_cv_.wait(lock, [this]() {
            return service_stopped_ || !audio_playback_queue_.empty();
        });
        if (service_stopped_) {
            break;
        }

        auto task = std::move(audio_playback_queue_.front());
        audio_playback_queue_.pop_front();
        playback_active_ = true;
        audio_queue_cv_.notify_all();
        lock.unlock();

        codec_->OutputData(task->pcm);
        lock.lock();
        playback_active_ = false;
        audio_queue_cv_.notify_all();
        lock.unlock();
    }

    ESP_LOGI(TAG, "audio output task stopped");
    xEventGroupSetBits(event_group_, kOutputExited);
}

void AudioService::OpusCodecTask()
{
    while (true) {
        std::unique_lock<std::mutex> lock(audio_queue_mutex_);
        audio_queue_cv_.wait(lock, [this]() {
            return service_stopped_ ||
                   (!audio_encode_queue_.empty() && audio_send_queue_.size() < MAX_SEND_PACKETS_IN_QUEUE) ||
                   (!audio_decode_queue_.empty() && audio_playback_queue_.size() < MAX_PLAYBACK_TASKS_IN_QUEUE);
        });
        if (service_stopped_) {
            break;
        }

        if (!audio_decode_queue_.empty() && audio_playback_queue_.size() < MAX_PLAYBACK_TASKS_IN_QUEUE) {
            auto packet = std::move(audio_decode_queue_.front());
            audio_decode_queue_.pop_front();
            lock.unlock();

            std::unique_lock<std::mutex> decoder_lock(decoder_mutex_);
            SetDecodeFormat(packet->sample_rate, packet->frame_duration);

            auto task = std::make_unique<AudioTask>();
            task->type = AudioTaskType::DecodeToPlaybackQueue;
            task->timestamp = packet->timestamp;
            task->pcm.resize(decoder_frame_size_);

            esp_audio_dec_in_raw_t raw = {
                .buffer = packet->payload.data(),
                .len = static_cast<uint32_t>(packet->payload.size()),
                .consumed = 0,
                .frame_recover = ESP_AUDIO_DEC_RECOVERY_NONE,
            };
            esp_audio_dec_out_frame_t out = {};
            out.buffer = reinterpret_cast<uint8_t *>(task->pcm.data());
            out.len = static_cast<uint32_t>(task->pcm.size() * sizeof(int16_t));
            esp_audio_dec_info_t info = {};

            int ret = esp_opus_dec_decode(opus_decoder_, &raw, &out, &info);
            decoder_lock.unlock();
            if (ret == ESP_AUDIO_ERR_OK) {
                task->pcm.resize(out.decoded_size / sizeof(int16_t));
                lock.lock();
                audio_playback_queue_.push_back(std::move(task));
                audio_queue_cv_.notify_all();
            } else {
                ESP_LOGW(TAG,
                         "opus decode failed: ret=%d packet_len=%u sample_rate=%d frame_ms=%d",
                         ret,
                         static_cast<unsigned>(packet->payload.size()),
                         packet->sample_rate,
                         packet->frame_duration);
                lock.lock();
            }
        }

        if (!audio_encode_queue_.empty() && audio_send_queue_.size() < MAX_SEND_PACKETS_IN_QUEUE) {
            auto task = std::move(audio_encode_queue_.front());
            audio_encode_queue_.pop_front();
            input_encode_in_flight_++;
            lock.unlock();

            if (static_cast<int>(task->pcm.size()) != encoder_frame_size_) {
                ESP_LOGW(TAG, "skip invalid encode frame: got=%u expected=%d",
                         static_cast<unsigned>(task->pcm.size()),
                         encoder_frame_size_);
                lock.lock();
                input_encode_in_flight_--;
                audio_queue_cv_.notify_all();
                continue;
            }

            std::vector<uint8_t> encoded(encoder_outbuf_size_);
            esp_audio_enc_in_frame_t in = {
                .buffer = reinterpret_cast<uint8_t *>(task->pcm.data()),
                .len = static_cast<uint32_t>(task->pcm.size() * sizeof(int16_t)),
            };
            esp_audio_enc_out_frame_t out = {};
            out.buffer = encoded.data();
            out.len = static_cast<uint32_t>(encoded.size());

            int ret = esp_opus_enc_process(opus_encoder_, &in, &out);
            if (ret == ESP_AUDIO_ERR_OK && out.encoded_bytes > 0) {
                encoded.resize(out.encoded_bytes);
                auto packet = std::make_unique<AudioStreamPacket>();
                packet->sample_rate = 16000;
                packet->frame_duration = OPUS_FRAME_DURATION_MS;
                packet->timestamp = task->timestamp;
                packet->payload = std::move(encoded);

                bool queued_packet = false;
                lock.lock();
                input_encode_in_flight_--;
                if (task->generation == input_audio_generation_) {
                    audio_send_queue_.push_back(std::move(packet));
                    queued_packet = true;
                }
                audio_queue_cv_.notify_all();
                lock.unlock();

                if (queued_packet && callbacks_.on_send_queue_available) {
                    callbacks_.on_send_queue_available();
                }
                lock.lock();
            } else {
                ESP_LOGW(TAG, "opus encode failed: %d", ret);
                lock.lock();
                input_encode_in_flight_--;
                audio_queue_cv_.notify_all();
            }
        }
    }

    ESP_LOGI(TAG, "opus codec task stopped");
    xEventGroupSetBits(event_group_, kOpusExited);
}

void AudioService::PushTaskToEncodeQueue(std::vector<int16_t> &&pcm)
{
    auto task = std::make_unique<AudioTask>();
    task->type = AudioTaskType::EncodeToSendQueue;
    task->pcm = std::move(pcm);

    std::unique_lock<std::mutex> lock(audio_queue_mutex_);
    if (service_stopped_) {
        return;
    }
    task->generation = input_audio_generation_;
    if (audio_encode_queue_.size() >= MAX_ENCODE_TASKS_IN_QUEUE) {
        dropped_encode_frames_++;
        TickType_t now = xTaskGetTickCount();
        if (last_encode_drop_log_ == 0 ||
            now - last_encode_drop_log_ >= pdMS_TO_TICKS(1000)) {
            ESP_LOGW(TAG,
                     "drop mic frame: encode queue full (dropped=%lu send_queue=%u)",
                     (unsigned long)dropped_encode_frames_,
                     (unsigned)audio_send_queue_.size());
            dropped_encode_frames_ = 0;
            last_encode_drop_log_ = now;
        }
        return;
    }

    audio_encode_queue_.push_back(std::move(task));
    audio_queue_cv_.notify_all();
}

void AudioService::SetDecodeFormat(int sample_rate, int frame_duration)
{
    if (sample_rate <= 0) {
        sample_rate = codec_->output_sample_rate();
    }
    if (frame_duration <= 0) {
        frame_duration = OPUS_FRAME_DURATION_MS;
    }
    if (sample_rate == decoder_sample_rate_ &&
        decoder_frame_size_ == sample_rate * frame_duration / 1000) {
        return;
    }

    if (opus_decoder_ != nullptr) {
        esp_opus_dec_close(opus_decoder_);
        opus_decoder_ = nullptr;
    }

    esp_opus_dec_cfg_t dec_config = {
        .sample_rate = static_cast<uint32_t>(sample_rate),
        .channel = ESP_AUDIO_MONO,
        .frame_duration = AS_OPUS_DEC_FRAME_DURATION(frame_duration),
        .self_delimited = false,
    };

    int ret = esp_opus_dec_open(&dec_config, sizeof(dec_config), &opus_decoder_);
    if (opus_decoder_ == nullptr) {
        ESP_LOGE(TAG, "opus decoder reopen failed: %d", ret);
        return;
    }

    decoder_sample_rate_ = sample_rate;
    decoder_frame_size_ = sample_rate * frame_duration / 1000;
}
