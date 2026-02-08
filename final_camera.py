"""
OpenMV thermal camera module for body temperature measurement.
The system uses Lepton thermal camera for face detection
and temperature measurement with obstruction compensation (bangs, glasses).
"""

import sensor
import image
import time
from pyb import UART, LED

# ============================================================================
# COMMUNICATION INTERFACE CONFIGURATION
# ============================================================================
# UART is used to transmit measurement data to ESP32 module
uart = UART(3, 115200)
uart.init(115200, bits=8, parity=None, stop=1)

# ============================================================================
# STATUS VISUALIZATION CONFIGURATION
# ============================================================================
# LED indicates system activity by blinking
blue_led = LED(3)  # 1=Red, 2=Green, 3=Blue, 4=Infrared
last_blink_time = time.ticks_ms()
BLINK_INTERVAL = 500  # Blink interval in milliseconds (0.5 seconds)

# ============================================================================
# TEMPERATURE MEASUREMENT CALIBRATION PARAMETERS
# ============================================================================
BASE_TEMP = 36.6  # Base body temperature in degrees Celsius
ALARM_TEMP = 37.5  # Temperature alarm threshold (fever)
GAIN = 0.15  # Thermal signal gain coefficient
TARGET_DIFF = 68  # Target pixel value difference for correct measurement

# ============================================================================
# OBJECT DETECTION PARAMETERS
# ============================================================================
# Reference region for background measurement (x, y, w, h)
ANCHOR_ROI = (140, 0, 20, 20)
NOISE_MARGIN = 20  # Noise margin for object detection
FACE_TOP_RATIO = 0.50  # Head height to total body height ratio
BODY_MIN_PIXELS = 80  # Minimum number of pixels for body detection

# ============================================================================
# OBSTRUCTION COMPENSATION PARAMETERS
# ============================================================================
OBSTRUCTION_THRESHOLD = 28  # Obstruction detection threshold (bangs/glasses)
OFFSET_BANGS = 0.2  # Temperature compensation for bangs [°C]
OFFSET_GLASSES = 0.5  # Temperature compensation for glasses [°C]

# ============================================================================
# THERMAL CAMERA INITIALIZATION
# ============================================================================
sensor.reset()
sensor.ioctl(sensor.IOCTL_LEPTON_SET_MODE, True)  # Activate Lepton mode
sensor.set_pixformat(sensor.GRAYSCALE)  # Image format: grayscale
sensor.set_framesize(sensor.QQVGA)  # Resolution: 160x120
sensor.set_vflip(True)  # Vertical flip
sensor.set_hmirror(True)  # Horizontal mirror
sensor.skip_frames(time=2000)  # Camera stabilization (2 seconds)

# ============================================================================
# MEASUREMENT VARIABLES INITIALIZATION
# ============================================================================
clock = time.clock()  # Timer for FPS measurement
# Filtered temperature difference (low-pass filter)
delta_filtered = 0


def extract_face(img, body_blob):
    """
    Extract face region from detected body object.

    The function analyzes the upper part of the detected body (head) and
    identifies the face region based on statistical analysis of thermal image.

    Args:
        img: Image from thermal camera
        body_blob: Detected object representing body

    Returns:
        Blob object representing face or None if not found
    """
    # Calculate head region height (top 50% of body)
    head_h = int(body_blob.h() * FACE_TOP_RATIO)
    roi = (body_blob.x(), body_blob.y(), body_blob.w(), head_h)

    # Statistical analysis of head region to determine detection threshold
    stats = img.get_statistics(roi=roi)
    face_threshold = int(stats.mean() + 5)

    # Detect thermal objects in head region
    faces = img.find_blobs(
        [(face_threshold, 255)], roi=roi, pixels_threshold=15, merge=True
    )

    if not faces:
        return None

    # Filter: only faces with appropriate proportions (width/height)
    valid_faces = [f for f in faces if 0.5 <= (f.w() / f.h()) <= 1.4]
    # Return largest face (most pixels)
    return max(valid_faces, key=lambda b: b.pixels()) if valid_faces else None


def analyze_features(img, face_blob):
    """
    Analyze face obstructions affecting temperature measurement.

    The function detects presence of bangs (covering forehead) and glasses
    (covering eyes) by comparing thermal values of different face regions.

    Args:
        img: Image from thermal camera
        face_blob: Detected object representing face

    Returns:
        Tuple (has_bangs, has_glasses):
        - has_bangs: True if bangs detected
        - has_glasses: True if glasses detected
    """
    fx, fy, fw, fh = face_blob.rect()

    # Define regions: forehead (top 25%) and eyes (next 25%)
    forehead_roi = (fx, fy, fw, int(fh * 0.25))
    eyes_roi = (fx, fy + int(fh * 0.25), fw, int(fh * 0.25))

    # Get thermal values for analysis
    face_max = img.get_statistics(roi=face_blob.rect()).max()
    forehead_mean = img.get_statistics(roi=forehead_roi).mean()
    eyes_mean = img.get_statistics(roi=eyes_roi).mean()

    # Detect obstructions: large value difference indicates obstruction
    has_bangs = (face_max - forehead_mean) > OBSTRUCTION_THRESHOLD
    has_glasses = (face_max - eyes_mean) > OBSTRUCTION_THRESHOLD

    return has_bangs, has_glasses


# ============================================================================
# MAIN PROCESSING LOOP
# ============================================================================
while True:
    clock.tick()

    # LED blinking handling (non-blocking)
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_blink_time) > BLINK_INTERVAL:
        blue_led.toggle()
        last_blink_time = current_time

    # Capture thermal image and get FPA temperature
    img = sensor.snapshot()
    fpa_temp = sensor.ioctl(sensor.IOCTL_LEPTON_GET_FPA_TEMP)

    # Measure background level in reference region
    anchor_stats = img.get_statistics(roi=ANCHOR_ROI)
    bg_level = anchor_stats.mean()

    # Calculate thermal object detection threshold
    # (background + noise margin)
    detection_threshold = min(int(bg_level + NOISE_MARGIN), 254)

    # Detect thermal objects (human body)
    bodies = img.find_blobs(
        [(detection_threshold, 255)],
        pixels_threshold=BODY_MIN_PIXELS,
        merge=True
    )
    # Visualize reference region
    img.draw_rectangle(ANCHOR_ROI, color=127)

    face_found = False

    if bodies:
        # Select largest detected object (most likely body)
        main_body = max(bodies, key=lambda b: b.pixels())
        face = extract_face(img, main_body)

        if face:
            face_found = True

            # Analyze face obstructions
            bangs, glasses = analyze_features(img, face)

            # Measure face thermal value
            face_stats = img.get_statistics(roi=face.rect())
            max_val = face_stats.max()

            # Calculate thermal difference relative to background
            real_diff = max_val - bg_level
            temp_change = real_diff - TARGET_DIFF

            # Low-pass filtering for measurement stabilization
            delta_filtered = (delta_filtered * 0.8) + (temp_change * 0.2)

            # Convert thermal difference to body temperature
            raw_temp = BASE_TEMP + (delta_filtered * GAIN)
            final_temp = raw_temp

            # Compensate for obstructions affecting measurement
            warning_msg_parts = []
            if bangs:
                final_temp += OFFSET_BANGS
                warning_msg_parts.append("GRZYWKA")
            if glasses:
                final_temp += OFFSET_GLASSES
                warning_msg_parts.append("OKULARY")

            # Limit temperature range to physiologically sensible values
            final_temp = max(32.0, min(42.0, final_temp))

            # Convert thermal image to color palette
            img.to_rainbow(color_palette=image.PALETTE_IRONBOW)

            # Determine color and status text based on temperature
            if final_temp > ALARM_TEMP:
                color = (255, 0, 0)  # Red - alarm
                status_text = "ALARM: %.1f C" % final_temp
            else:
                color = (0, 255, 0)  # Green - normal temperature
                status_text = "%.1f C" % final_temp

            # Send measurement data to ESP32 via UART
            # Format: "body_temperature;matrix_temperature\n"
            uart.write("%.2f;%.2f\n" % (final_temp, fpa_temp))

            # Visualize detected face on image
            img.draw_rectangle(face.rect(), color=color, thickness=2)
            img.draw_cross(face.cx(), face.cy(), color=color)
            img.draw_string(
                face.x(), face.y()-12, status_text,
                color=(255, 255, 255), mono_space=False
            )

            # Display obstruction warnings
            if warning_msg_parts:
                warning_msg = " ".join(warning_msg_parts)
                img.draw_string(
                    face.x(), face.y()-22, warning_msg,
                    color=(0, 0, 255), mono_space=False
                )
                print("T: %.2f (Raw: %.2f) | %s" %
                      (final_temp, raw_temp, warning_msg))
            else:
                print("T: %.2f (Raw: %.2f)" % (final_temp, raw_temp))

    # Handle case when no face is detected
    if not face_found:
        img.to_rainbow(color_palette=image.PALETTE_IRONBOW)
        # Gradually fade filtered value (low-pass filter)
        delta_filtered = delta_filtered * 0.95
        # Send IDLE signal to ESP32 with matrix temperature info
        uart.write("IDLE;FPA:%.2f;OBS:0\n" % fpa_temp)
