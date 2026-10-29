#pragma once

#include <cstddef>
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"

#include "audio/audio_codec.h"
#include "audio/audio_processor.h"
#include "audio/wake_word.h"

#define OPUS_FRAME_DURATION_MS 60
#define MAX_ENCODE_TASKS_IN_QUEUE 2
#define MAX_PLAYBACK_TASKS_IN_QUEUE 2
#define MAX_DECODE_PACKETS_IN_QUEUE (2400 / OPUS_FRAME_DURATION_MS)
#define MAX_SEND_PACKETS_IN_QUEUE (2400 / OPUS_FRAME_DURATION_MS)

#define AS_EVENT_AUDIO_PROCESSOR_RUNNING (1 << 0)
#define AS_EVENT_WAKE_WORD_RUNNING (1 << 1)

struct AudioStreamPacket {
    int sample_rate = 16000;
    int frame_duration = OPUS_FRAME_DURATION_MS;
    uint32_t timestamp = 0;
    std::vector<uint8_t> payload;
};

struct AudioServiceCallbacks {
    std::function<void(void)> on_send_queue_available;
    std::function<void(bool)> on_vad_change;
    std::function<void(const std::string &)> on_wake_word_detected;
};

class AudioService {
public:
    AudioService();
    ~AudioService();

    esp_err_t Initialize(AudioCodec *codec);
    esp_err_t Start();
    void Stop();

    void SetCallbacks(const AudioServiceCallbacks &callbacks);
    void EnableVoiceProcessing(bool enable);
    void EnableDeviceAec(bool enable);
    esp_err_t EnableWakeWordDetection(bool enable);
    bool IsAudioProcessorRunning() const;
    bool IsWakeWordRunning() const;
    bool IsAfeWakeWord() const;
    bool IsVoiceDetected() const { return voice_detected_; }
    const std::string &GetLastWakeWord() const;
    bool IsIdle();
    void WaitForPlaybackQueueEmpty();
    void FlushOutput();
    bool PlayLocalPcm(std::vector<int16_t> &&pcm, bool interrupt = false);

    bool PushPacketToDecodeQueue(std::unique_ptr<AudioStreamPacket> packet, bool wait = false);
    std::unique_ptr<AudioStreamPacket> PopPacketFromSendQueue();
    size_t TrimSendQueueTo(size_t max_packets);
    size_t PendingInputAudioCount() const;
    size_t DiscardPendingInputAudio();
    void ResetDecoder();

private:
    enum class AudioTaskType {
        EncodeToSendQueue,
        DecodeToPlaybackQueue,
    };

    struct AudioTask {
        AudioTaskType type;
        std::vector<int16_t> pcm;
        uint32_t timestamp = 0;
        uint32_t generation = 0;
    };

    AudioCodec *codec_ = nullptr;
    AudioServiceCallbacks callbacks_;
    std::unique_ptr<AudioProcessor> audio_processor_;
    std::unique_ptr<WakeWord> wake_word_;
    void *opus_encoder_ = nullptr;
    void *opus_decoder_ = nullptr;
    int encoder_frame_size_ = 0;
    int encoder_outbuf_size_ = 0;
    int decoder_sample_rate_ = 16000;
    int decoder_frame_size_ = 0;

    EventGroupHandle_t event_group_ = nullptr;
    TaskHandle_t audio_input_task_handle_ = nullptr;
    TaskHandle_t audio_output_task_handle_ = nullptr;
    TaskHandle_t opus_codec_task_handle_ = nullptr;

    mutable std::mutex audio_queue_mutex_;
    std::mutex decoder_mutex_;
    std::condition_variable audio_queue_cv_;
    std::deque<std::unique_ptr<AudioTask>> audio_encode_queue_;
    std::deque<std::unique_ptr<AudioTask>> audio_playback_queue_;
    std::deque<std::unique_ptr<AudioStreamPacket>> audio_decode_queue_;
    std::deque<std::unique_ptr<AudioStreamPacket>> audio_send_queue_;

    std::atomic<bool> service_stopped_{true};
    bool audio_processor_initialized_ = false;
    bool wake_word_initialized_ = false;
    bool voice_detected_ = false;
    bool playback_active_ = false;
    size_t input_encode_in_flight_ = 0;
    uint32_t input_audio_generation_ = 0;
    uint32_t dropped_encode_frames_ = 0;
    TickType_t last_encode_drop_log_ = 0;

    void AudioInputTask();
    void AudioOutputTask();
    void OpusCodecTask();
    void PushTaskToEncodeQueue(std::vector<int16_t> &&pcm);
    void SetDecodeFormat(int sample_rate, int frame_duration);
};
