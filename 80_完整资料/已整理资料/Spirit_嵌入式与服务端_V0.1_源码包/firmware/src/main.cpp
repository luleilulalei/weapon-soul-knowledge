#include "app/robot.h"
#include "esp_log.h"
extern "C" void app_main(void)
{
    esp_err_t err = start_robot();
    if (err != ESP_OK) ESP_LOGE("spirit", "startup failed: %s", esp_err_to_name(err));
}
