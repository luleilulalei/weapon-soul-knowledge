# LD0825BC-0169F motor bring-up — not factory calibration

The actual selected part is **Leader LD0825BC-0169F**. Manufacturer specification
Doc.No LEADER-0825BC-0169F, Rev02, 2023-11-10:

- Rated 1.2 ±0.05 Vrms AC sine; operating 0.1–1.25 Vrms AC.
- Resonance/input 240 ±10 Hz; current max 90 mArms under rated test conditions.
- Impedance 20 ±3 Ω at 25 °C.
- Source: https://atta.szlcsc.com/upload/public/pdf/source/20231116/6E8E24E2DD0A6A3BF17BC9D10915D8C6.pdf , pp.3–4.

These values identify the motor; they do **not** constitute calibration of the assembled unit.
The default firmware never energizes it. Do not copy generic 2V/175Hz LRA examples.

## Calculated starting points, to be checked on a current-limited bench

TI DRV2605L SLOS854D §8.5.2 Eq.5 (closed-loop LRA):

```
rated_code = Vrms * sqrt(1 - (4*sample_time_seconds + 300e-6)*frequency_Hz) / 0.02058
```

At sample time 300µs, 240Hz and 1.2Vrms this is 46.65; **floor 46 (0x2E)**
is a conservative initial nominal value (about 1.183Vrms by the equation).
The half-period drive-time starting point is 2.083ms; register DRIVE_TIME code
16 gives 2.1ms (`0.5ms + code*0.1ms`). Actual resonance is tracked in closed loop.

TI Eq.9 is **peak**, not RMS: `Vclamp_peak = 0.02122 * OD_CLAMP`.
Do not set this register using 1.25 as if it were an RMS coefficient. A sine peak
corresponding to 1.25Vrms is 1.768V, code floor83; however the motor sees a driven
waveform and transients, so **83 is a mathematical upper-bound starting calculation,
not authorization to use it without measured waveform/RMS/current verification**.
Begin at lower drive/clamp on the bench and measure; do not enable arbitrary overdrive.

## Per-unit calibration procedure

1. Confirm the fitted part, secure it in its final mechanical mounting, use a current-limited
   supply and measure differential motor voltage with an appropriate probe, RMS current,
   temperature and mechanical response. Scope ground must not short either H-bridge output.
2. Keep EN low until configuration is ready. Acquire HAPTIC boost ownership; raise EN.
3. Following TI §8.5.6, set mode0x07 (auto-cal), LRA selection, rated/clamp values,
   drive/sample/blanking/discharge timings and auto-cal duration. Use a separate bounded
   bench calibration procedure; normal `spirit_haptic_play_for()` is only for already calibrated effects.
4. Start GO, poll with a hard timeout, then require GO cleared and DIAG_RESULT clear;
   also reject overtemperature/overcurrent status. On any error drop EN immediately.
5. Read auto-cal compensation0x18, back-EMF0x19 and feedback0x1A; record them with exact
   motor/assembly identity and control1/2/3 settings. Do **not** program OTP in v0.1.
6. Populate `spirit_haptic_config_t` with the verified register set, call
   `spirit_haptic_configure`, then first test a short low-energy effect. Increase only after
   measuring voltage/current and checking temperature. Keep effects ≤1000ms.

An automated calibration command is deliberately not exposed to cloud commands, and no
unmeasured result is shipped as if calibrated. The firmware accepts a locally supplied,
verified register set; calibration UI/provisioning and persistence are future work.

TI source: https://www.ti.com/lit/ds/symlink/drv2605l.pdf
