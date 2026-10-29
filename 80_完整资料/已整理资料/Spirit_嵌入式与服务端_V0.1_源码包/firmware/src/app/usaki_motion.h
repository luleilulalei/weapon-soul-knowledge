#pragma once

#include "app/protocol.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t usaki_motion_init(void);
esp_err_t usaki_motion_enqueue_body_action(const usaki_protocol_server_message_t *message);
esp_err_t usaki_motion_apply_servo_batch(const usaki_protocol_server_message_t *message);

#ifdef __cplusplus
}
#endif
