#include "audio/wake_words/no_wake_word.h"

#include "esp_err.h"

esp_err_t NoWakeWord::Initialize(AudioCodec *codec)
{
    (void)codec;
    return ESP_OK;
}

void NoWakeWord::Start()
{
}

void NoWakeWord::Stop()
{
}

void NoWakeWord::Feed(const std::vector<int16_t> &data)
{
    (void)data;
}

size_t NoWakeWord::GetFeedSize() const
{
    return 0;
}

bool NoWakeWord::IsRunning() const
{
    return false;
}

const std::string &NoWakeWord::GetLastDetectedWakeWord() const
{
    return last_detected_wake_word_;
}

void NoWakeWord::OnWakeWordDetected(std::function<void(const std::string &wake_word)> callback)
{
    wake_word_detected_callback_ = callback;
}
