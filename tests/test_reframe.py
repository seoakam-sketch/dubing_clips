from worker.reframe import TARGET_H, TARGET_W, _center_crop_filter, _dynamic_crop_filter


def test_center_crop_filter_landscape_source():
    vf = _center_crop_filter(1920, 1080)
    assert vf.startswith("crop=607:1080:")
    assert f"scale={TARGET_W}:{TARGET_H}" in vf


def test_dynamic_crop_filter_keeps_face_in_frame():
    # Face near the right edge of a wide frame: crop window must clamp inside bounds.
    vf = _dynamic_crop_filter(1920, 1080, face_center_x=0.95)
    # crop width for a 1080-tall 9:16 window is 607; x must not exceed src_w - crop_w = 1313
    assert vf.startswith("crop=607:1080:1313:")
