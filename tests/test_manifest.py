import json

from physiosync.store.manifest import Manifest, StreamInfo, read_manifest, write_manifest


def _manifest() -> Manifest:
    return Manifest(
        uuid="3f6c0c5e-0000-4000-8000-000000000000",
        study_id=3,
        participant_id="P07",
        scenario_id=2,
        take_index=2,
        app_version="0.1.0",
        created_utc=1774477250.482,
        reference_stream="tobii.gaze",
        streams={
            "tobii.gaze": StreamInfo(
                channels=["gaze2d_x", "gaze2d_y"],
                nominal_hz=100,
                epoch_utc=1774477258.390783,
                epoch_method="derived:min(local_ts-device_ts)",
                epoch_uncertainty_s=0.0008,
                coverage=(1774477258.39, 1774477562.11),
                n_samples=30412,
            ),
            # Epoch not yet derived, capture still open: everything nullable stays None.
            "tobii.imu": StreamInfo(nominal_hz=100),
            "bitalino.main": StreamInfo(
                channels=["A1", "A2"],
                nominal_hz=100,
                epoch_utc=1774477264.901,
                epoch_method="host:t_start",
            ),
        },
        usable_window=(1774477264.901, 1774477560.02),
        warnings=["tobii.ntp_not_synchronized"],
    )


def test_round_trip(tmp_path):
    p = tmp_path / "manifest.json"
    m = _manifest()
    write_manifest(p, m)
    assert read_manifest(p) == m
    assert not p.with_name("manifest.json.tmp").exists()


def test_json_shape_and_floats(tmp_path):
    p = tmp_path / "manifest.json"
    write_manifest(p, _manifest())
    raw = json.loads(p.read_text())
    assert isinstance(raw["created_utc"], float)
    assert raw["streams"]["tobii.imu"]["epoch_utc"] is None
    assert raw["usable_window"] == [1774477264.901, 1774477560.02]
