import sensor
import image
import time
from pyb import UART

uart = UART(3, 115200)
uart.init(115200, bits=8, parity=None, stop=1)

BASE_TEMP = 36.6
ALARM_TEMP = 37.5
GAIN = 0.15
TARGET_DIFF = 64

ANCHOR_ROI = (140, 0, 20, 20)
NOISE_MARGIN = 20
FACE_TOP_RATIO = 0.50
BODY_MIN_PIXELS = 80

OBSTRUCTION_THRESHOLD = 28
OFFSET_BANGS = 0.2
OFFSET_GLASSES = 0.5

sensor.reset()
sensor.ioctl(sensor.IOCTL_LEPTON_SET_MODE, True)
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QQVGA)
sensor.set_vflip(True)
sensor.set_hmirror(True)
sensor.skip_frames(time=2000)

clock = time.clock()
delta_filtered = 0


def extract_face(img, body_blob):
    # Extract head region from detected body
    head_h = int(body_blob.h() * FACE_TOP_RATIO)
    roi = (body_blob.x(), body_blob.y(), body_blob.w(), head_h)

    stats = img.get_statistics(roi=roi)
    face_threshold = int(stats.mean() + 5)
    faces = img.find_blobs(
        [(face_threshold, 255)], roi=roi, pixels_threshold=15, merge=True
    )

    if not faces:
        return None

    # Filter by aspect ratio to ensure face-like shape
    valid_faces = [f for f in faces if 0.5 <= (f.w() / f.h()) <= 1.4]

    return max(valid_faces, key=lambda b: b.pixels()) if valid_faces else None


def analyze_features(img, face_blob):
    fx, fy, fw, fh = face_blob.rect()
    forehead_roi = (fx, fy, fw, int(fh * 0.25))
    eyes_roi = (fx, fy + int(fh * 0.25), fw, int(fh * 0.25))

    face_max = img.get_statistics(roi=face_blob.rect()).max()
    forehead_mean = img.get_statistics(roi=forehead_roi).mean()
    eyes_mean = img.get_statistics(roi=eyes_roi).mean()

    has_bangs = (face_max - forehead_mean) > OBSTRUCTION_THRESHOLD
    has_glasses = (face_max - eyes_mean) > OBSTRUCTION_THRESHOLD

    return has_bangs, has_glasses


while True:
    clock.tick()
    img = sensor.snapshot()
    fpa_temp = sensor.ioctl(sensor.IOCTL_LEPTON_GET_FPA_TEMP)

    anchor_stats = img.get_statistics(roi=ANCHOR_ROI)
    bg_level = anchor_stats.mean()

    detection_threshold = min(int(bg_level + NOISE_MARGIN), 254)
    bodies = img.find_blobs(
        [(detection_threshold, 255)],
        pixels_threshold=BODY_MIN_PIXELS,
        merge=True
    )
    img.draw_rectangle(ANCHOR_ROI, color=127)

    face_found = False

    if bodies:
        main_body = max(bodies, key=lambda b: b.pixels())
        face = extract_face(img, main_body)

        if face:
            face_found = True
            bangs, glasses = analyze_features(img, face)

            face_stats = img.get_statistics(roi=face.rect())
            max_val = face_stats.max()

            real_diff = max_val - bg_level
            temp_change = real_diff - TARGET_DIFF
            # Low-pass filter for temperature smoothing
            delta_filtered = (delta_filtered * 0.8) + (temp_change * 0.2)

            raw_temp = BASE_TEMP + (delta_filtered * GAIN)
            final_temp = raw_temp

            # Apply compensation for obstructions
            warning_msg_parts = []
            if bangs:
                final_temp += OFFSET_BANGS
                warning_msg_parts.append("GRZYWKA")
            if glasses:
                final_temp += OFFSET_GLASSES
                warning_msg_parts.append("OKULARY")

            # Clamp to reasonable temperature range
            final_temp = max(32.0, min(42.0, final_temp))

            img.to_rainbow(color_palette=image.PALETTE_IRONBOW)

            if final_temp > ALARM_TEMP:
                color = (255, 0, 0)
                status_text = "ALARM: %.1f C" % final_temp
            else:
                color = (0, 255, 0)
                status_text = "%.1f C" % final_temp

            uart.write("%.2f;%.2f\n" % (final_temp, fpa_temp))

            img.draw_rectangle(face.rect(), color=color, thickness=2)
            img.draw_cross(face.cx(), face.cy(), color=color)
            img.draw_string(
                face.x(), face.y()-12, status_text,
                color=(255, 255, 255), mono_space=False
            )

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

    if not face_found:
        img.to_rainbow(color_palette=image.PALETTE_IRONBOW)
        delta_filtered = delta_filtered * 0.95
        uart.write("IDLE;FPA:%.2f;OBS:0\n" % fpa_temp)
