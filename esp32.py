from machine import UART, Pin, I2C
import time
from hcsr04 import HCSR04
import ssd1306

uart = UART(2, baudrate=115200, tx=17, rx=16)
sensor = HCSR04(trigger_pin=5, echo_pin=18, echo_timeout_us=30000)
i2c = I2C(0, scl=22, sda=21)
scr = ssd1306.SSD1306_I2C(128, 64, i2c)
led_a = Pin(2, Pin.OUT)  # green
led_b = Pin(4, Pin.OUT)  # red
led_a.value(0)
led_b.value(0)

print("System starting...")

ALARM_THRESHOLD = 37.5


def get_temperature():
    if not uart.any():
        return None, None

    try:
        line = uart.readline()
        if not line:
            return None, None

        text = line.decode("utf-8").strip()
        if ";" not in text:
            return None, None

        parts = text.split(";")
        if len(parts) < 2:
            return None, None

        try:
            final_temp = float(parts[0])
            if ":" in parts[1]:
                fpa_temp = float(parts[1].split(":")[-1])
            else:
                fpa_temp = float(parts[1])
            return final_temp, fpa_temp
        except (ValueError, IndexError):
            return None, None

    except Exception as e:
        print("Error with connection:", e)
        return None, None


while True:
    try:
        distance = sensor.distance_cm()
        print(distance)

        # Check distance range for valid measurement zone
        if 40 <= distance <= 80:
            temperature, camera_temp = get_temperature()
            if temperature is not None:
                print(f"actual temp {temperature}")
                scr.fill(0)
                scr.text(f'Temperature: {temperature}', 0, 0)
                scr.show()
                is_alarm = temperature >= ALARM_THRESHOLD

                if is_alarm:
                    led_a.value(0)
                    led_b.value(1)  # red
                else:
                    led_a.value(1)
                    led_b.value(0)  # green
        else:  # if there is no one in range
            scr.fill(0)
            scr.text(f'No one in range', 0, 0)
            scr.show()
            led_a.value(0)
            led_b.value(0)
    except Exception as e:
        print("chwilowy błąd", e)
        time.sleep(1)
    time.sleep(0.1)