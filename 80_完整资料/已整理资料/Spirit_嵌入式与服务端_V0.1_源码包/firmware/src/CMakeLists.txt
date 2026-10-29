set(USAKI_SRCS
    "main.cpp"
    "spirit_peripherals/spirit_peripherals.c"
    "spirit_peripherals/vendor/bmi270/bmi2.c"
    "spirit_peripherals/vendor/bmi270/bmi270.c"
    "drivers/spirit_pdm.c"
    "app/spirit_privacy.cc"
    "app/spirit_link.cc"
    "drivers/max98357a.c"
    "drivers/gc9a01.c"
    "ui/usaki_eyes_anim.c"
    "ui/usaki_eyes.c"
    "ui/usaki_eyes_render.c"
    "app/robot.cpp"
    "app/protocol.c"
    "app/server_call.c"
    "app/voice_protocol_adapter.cc"
    "app/voice_runtime.cc"
    "app/wifi_station.c"
    "audio/audio_codec.cc"
    "audio/audio_service.cc"
    "audio/codecs/usaki_audio_codec.cc"
    "audio/processors/afe_audio_processor.cc"
    "audio/processors/no_audio_processor.cc"
    "audio/wake_words/afe_wake_word.cc"
    "audio/wake_words/no_wake_word.cc")

set(USAKI_REQUIRES
    esp_adc
    esp_rom
    esp_driver_gpio
    esp_driver_i2s
    esp_driver_i2c
    esp_driver_spi
    esp_event
    esp_http_client
    esp_netif
    esp_wifi
    esp_websocket_client
    esp_audio_codec
    mbedtls
    freertos
    heap
    nvs_flash
    esp_system
    esp_timer
    esp_lcd
    lvgl
    esp-sr)

idf_component_register(SRCS ${USAKI_SRCS}
                       INCLUDE_DIRS "."
                       REQUIRES ${USAKI_REQUIRES})
