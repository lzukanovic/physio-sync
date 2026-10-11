# 0015 — Live decimation is per channel, not per stream

Amends the **Decimation** bullet of ADR 0013.

**Context.** ADR 0013 decimated each stream by one rule: keep a sample once the stream's
own clock is ≥ 50 ms past the last kept one. That assumes every row carries every channel.
The Tobii IMU stream does not: it interleaves accelerometer/gyroscope rows at ~120 Hz with
magnetometer rows at ~10 Hz, each null in the other's columns (1,773 of 23,481 rows in
`fixtures/live-capture/tobii_imu.csv` carry mag). The Glasses 3 developer guide says the
same of real hardware: an IMU sample may carry readings from only some sensors. Decimating
the combined stream to 20 Hz kept about one row in six, of which ~7.5% carried mag: ~1.5
mag values a second, ~0.66 s apart. Found by hand in the Task 01 capture page: selecting
any `mag_*` channel drew nothing for the whole fixture, because the chart broke the line
at every gap over 0.5 s and every surviving point stood alone.

**Decision.** The decimation unit is the channel. Each stream keeps a last-kept time per
channel, and a row is kept if any channel it carries (not null, not NaN) is ≥ 1/MAX_HZ past
that channel's last kept value. A kept row updates the last-kept time of every channel it
carries. A stream with no declared channels decimates on its time column, as before.

For uniform streams (BITalino, Tobii gaze) every row carries every channel, so the output
is unchanged. For the IMU, accel/gyro are decimated to 20 Hz and every mag row is kept: the
device samples mag evenly at ~10 Hz, under the 20 Hz cap.

The fixture as first prepared hid this. Its mag `DeviceTS` had been interpolated from
arrival time, which baked WebSocket batching (~8–10 rows a few ms apart every ~0.92 s)
into the device clock, so even after this fix the chart drew about one dot a second. The
original 7 s capture shows the device clock is regular (101.6 ms median gap, none under
5 ms); the batching is transport and belongs in `local_ts` only. The fixture was corrected
(`fixtures/README.md`), and mag now draws as a continuous line.

The chart follows the same rule. A row without the selected channel is skipped, not
treated as a break. A break is a time gap since that channel's own last value. A point
with no neighbour is drawn as a dot, so a sparse or intermittent channel never shows as
an empty pane.

**Consequences.** `tick` loops over each row's channels: gaze has 19, against ≤ 2 s of
buffered samples per stream, every 100 ms, on the event loop. Negligible at the rates
measured; it is display path only either way. A gaze null of under 0.5 s (a blink) is now
bridged by the line rather than broken; longer losses still break it.
