"""
ESP32 module for display handling, communication with thermal camera
and transmission of measurement data to web server.
The system integrates temperature measurement from OpenMV camera with
OLED display and WiFi data transmission.
"""

from machine import UART, Pin, I2C
import time
from hcsr04 import HCSR04
import ssd1306
import network
import urequests
import json

# ============================================================================
# WIFI CONNECTION CONFIGURATION
# ============================================================================
WIFI_SSID = ""  # WiFi network name
WIFI_PASSWORD = ""  # WiFi network password


def connect_wifi():
    """
    Establish WiFi network connection.

    The function activates WiFi interface in station mode (STA) and attempts
    to connect to network with given parameters. Returns False after timeout
    if connection fails.

    Returns:
        True if connection was established, False otherwise
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("WiFi connected:", wlan.ifconfig())
        return True
    else:
        print("WiFi connection failed")
        return False


def send_measurement(temperature, distance):
    """
    Send measurement data to web server via HTTP POST.

    The function formats measurement data (temperature and distance) in JSON
    format and sends it to defined API endpoint. Handles connection errors
    and returns operation status.

    Args:
        temperature: Measured body temperature in degrees Celsius
        distance: Measured distance from sensor in centimeters

    Returns:
        True if data was successfully sent (status 200), False otherwise
    """
    try:
        url = "http://programowanie.org:8000/measurement"
        data = {
            "Temperature": round(temperature, 1),
            "Distance": int(round(distance))
        }
        json_data = json.dumps(data)
        headers = {"Content-Type": "application/json"}

        print("Sending data:", json_data)
        response = urequests.post(url, data=json_data, headers=headers)
        print("Response status:", response.status_code)

        if response.status_code != 200:
            print("Response body:", response.text)

        response.close()
        return response.status_code == 200
    except Exception as e:
        print("Failed to send measurement:", e)
        return False


# Establish WiFi connection at system startup
connect_wifi()


# ============================================================================
# HARDWARE INTERFACES INITIALIZATION
# ============================================================================
# Communication with OpenMV camera
uart = UART(2, baudrate=115200, tx=17, rx=16)
# Distance sensor
sensor = HCSR04(trigger_pin=5, echo_pin=18, echo_timeout_us=30000)
i2c = I2C(0, scl=22, sda=21)  # I2C interface for display
scr = ssd1306.SSD1306_I2C(128, 64, i2c)  # OLED display 128x64

# Initialize status LED indicators
led_a = Pin(2, Pin.OUT)  # LED A (green - normal temperature)
led_b = Pin(4, Pin.OUT)  # LED B (red - alarm)
led_a.value(0)
led_b.value(0)

print("System starting...")

# ============================================================================
# CONFIGURATION PARAMETERS
# ============================================================================
ALARM_THRESHOLD = 37.5  # Temperature alarm threshold [°C]
DISPLAY_HOLD_TIME = 5000  # Last measurement display time [ms]

# ============================================================================
# SYSTEM STATE VARIABLES
# ============================================================================
last_valid_body_temp = None  # Last correctly measured body temperature
lastitt = 0  # Time of last person detection

# ============================================================================
# DIGIT GRAPHICS DEFINITIONS FOR DISPLAY
# ============================================================================
# Each digit is represented as array of 7-bit rows (5x7 pixels)
DIGITS = {
    '0': [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    '1': [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    '2': [0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111],
    '3': [0b01110, 0b10001, 0b00001, 0b00110, 0b00001, 0b10001, 0b01110],
    '4': [0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010],
    '5': [0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110],
    '6': [0b01110, 0b10001, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110],
    '7': [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000],
    '8': [0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110],
    '9': [0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b10001, 0b01110],
    '.': [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00100],
    '-': [0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000]
}


def draw_large_digit(x, y, digit, scale=4, invert=False):
    """
    Draw single digit on display in enlarged scale.

    The function renders digit from bitmap definition DIGITS with ability
    to scale and invert colors for better readability.

    Args:
        x: X position of digit top-left corner
        y: Y position of digit top-left corner
        digit: Digit character to draw ('0'-'9', '.', '-')
        scale: Scaling coefficient (default 4)
        invert: True for color inversion (white on black background)
    """
    if digit not in DIGITS:
        return
    pattern = DIGITS[digit]
    color = 0 if invert else 1
    for row_idx, row in enumerate(pattern):
        for col_idx in range(5):
            if row & (0b10000 >> col_idx):
                px = x + col_idx * scale
                py = y + row_idx * scale
                scr.fill_rect(px, py, scale, scale, color)


def draw_large_number(x, y, number_str, scale=4, invert=False):
    """
    Draw number (sequence of digits) on display.

    The function renders full number by drawing consecutive digits
    with appropriate spacing between them.

    Args:
        x: X position of number start
        y: Y position of number start
        number_str: String representing number (e.g. "37.5")
        scale: Scaling coefficient
        invert: True for color inversion
    """
    x_offset = 0
    digit_width = 5 * scale + 3  # Digit width + spacing
    for char in number_str:
        draw_large_digit(x + x_offset, y, char, scale, invert)
        x_offset += digit_width


def update_display(mode, val=None):
    """
    Update OLED display according to system operation mode.

    The function manages information display on OLED screen and
    control of status LED indicators. Handles three modes:
    - IDLE: System ready, no measurement
    - MEASURE: Temperature measurement in progress
    - HOLD: Display last measurement after completion

    Args:
        mode: Display mode ('MEASURE', 'HOLD', 'IDLE')
        val: Temperature value to display (optional)
    """
    scr.fill(0)  # Clear screen

    if mode == 'IDLE':
        # Idle mode - display "SYSTEM GOTOWY" message
        idle_text = "SYSTEM GOTOWY"
        text_x = (128 - len(idle_text) * 8) // 2  # Center text
        text_y = (64 - 8) // 2
        scr.text(idle_text, text_x, text_y, 1)

        # Turn off all LEDs
        led_a.value(0)
        led_b.value(0)

    elif mode == 'MEASURE' or mode == 'HOLD':
        if val is not None:
            # Display temperature with large digits
            temp_str = f"{val:.1f}"
            scale = 4
            digit_width = 5 * scale + 3
            total_width = len(temp_str) * digit_width
            start_x = max(0, (128 - total_width) // 2)  # Center number

            # Y position depends on mode (HOLD - top, MEASURE - center)
            start_y = 8 if mode == 'HOLD' else (64 - (7 * scale)) // 2

            draw_large_number(start_x, start_y, temp_str, scale, invert=False)

            # Control LEDs based on temperature
            is_alarm = val >= ALARM_THRESHOLD
            led_a.value(0 if is_alarm else 1)  # Green - normal temperature
            led_b.value(1 if is_alarm else 0)  # Red - alarm

            if mode == 'HOLD':
                # Additional text in HOLD mode
                msg = "Ostatni pomiar"
                msg_x = (128 - len(msg) * 8) // 2
                scr.text(msg, msg_x, 56, 1)
        else:
            # Message while waiting for measurement
            scr.text("Pomiar...", 30, 30, 1)

    scr.show()  # Update display


def get_temperatures():
    """
    Read temperature data from OpenMV camera via UART.

    The function reads latest data line from UART buffer and parses
    body and ambient temperature information. Handles formats:
    - "body_temperature;ambient_temperature\\n" (measurement mode)
    - "IDLE;FPA:temperature;OBS:0\\n" (idle mode)

    Returns:
        Tuple (body_temp, ambient_temp):
        - body_temp: Body temperature in °C or None if no data
        - ambient_temp: Ambient temperature (FPA) in °C or None
    """
    if not uart.any():
        return None, None
    try:
        # Read all available lines, keep last one
        last_line = None
        while uart.any():
            temp_line = uart.readline()
            if temp_line:
                last_line = temp_line

        if not last_line:
            return None, None

        text = last_line.decode("utf-8").strip()

        # Check idle mode
        if "IDLE" in text:
            return None, None
        if ";" not in text:
            return None, None

        # Parse data
        parts = text.split(";")
        if len(parts) < 2:
            return None, None

        body = float(parts[0])

        # Handle different ambient temperature formats
        raw_amb = parts[1]
        if ":" in raw_amb:
            amb = float(raw_amb.split(":")[-1])
        else:
            amb = float(raw_amb)

        return body, amb

    except Exception:
        return None, None


# Initialize last detection time (with offset for correct startup)
lastitt = time.ticks_ms() - DISPLAY_HOLD_TIME - 1000

# ============================================================================
# MAIN PROCESSING LOOP
# ============================================================================
while True:
    try:
        current_time = time.ticks_ms()

        # Measure distance from ultrasonic sensor
        try:
            distance = sensor.distance_cm()
        except OSError:
            distance = 0  # Handle sensor errors

        print(distance)

        # Check if person is in measurement range (40-80 cm)
        is_person_in_range = (40 <= distance <= 80)

        # Read temperature data from camera
        t_body, t_amb = get_temperatures()
        print(t_amb)

        # Log diagnostic information
        if t_amb is not None:
            if is_person_in_range:
                print(f"POMIAR CIALA: {t_body:.1f} C (Otoczenie: {t_amb:.1f})")
            else:
                print(f"IDLE - Temp. kamery: {t_amb:.1f} C")

        if is_person_in_range:
            # Person in range - measurement mode
            lastitt = current_time

            if t_body is not None:
                # Update last valid temperature
                last_valid_body_temp = t_body
                update_display('MEASURE', last_valid_body_temp)
                # Send data to server
                send_measurement(t_body, distance)
            else:
                # No camera data - display last value or message
                if last_valid_body_temp is not None:
                    update_display('MEASURE', last_valid_body_temp)
                else:
                    update_display('MEASURE', None)

        else:
            # Person out of range - waiting mode
            time_passed = time.ticks_diff(current_time, lastitt)

            # Display last measurement for specified time (HOLD)
            if (time_passed < DISPLAY_HOLD_TIME and
                    last_valid_body_temp is not None):
                update_display('HOLD', last_valid_body_temp)
            else:
                # Switch to idle mode
                update_display('IDLE')

    except Exception as e:
        print("Error:", e)

    time.sleep(0.05)  # Delay for system stability (20 Hz)
