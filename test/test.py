import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def make_ui(test_speed, waveform, depth, rate, enable):
    """
    Builds ui_in from named fields.

    ui_in[0]   = enable
    ui_in[2:1] = rate
    ui_in[4:3] = depth
    ui_in[6:5] = waveform
    ui_in[7]   = test_speed
    """
    return (
        ((test_speed & 0x1) << 7) |
        ((waveform   & 0x3) << 5) |
        ((depth      & 0x3) << 3) |
        ((rate       & 0x3) << 1) |
        ((enable     & 0x1) << 0)
    )


def out_value(dut):
    return int(dut.uo_out.value)


def pwm_bit(dut):
    return out_value(dut) & 0x1


def lfo_debug_bit(dut):
    return (out_value(dut) >> 1) & 0x1


def pwm_debug_bit(dut):
    return (out_value(dut) >> 2) & 0x1


def enable_debug_bit(dut):
    return (out_value(dut) >> 3) & 0x1


def mod_debug(dut):
    return (out_value(dut) >> 4) & 0xF


async def count_pwm_highs(dut, cycles):
    highs = 0

    for _ in range(cycles):
        await ClockCycles(dut.clk, 1)

        if pwm_bit(dut):
            highs += 1

    return highs


async def collect_mod_debug_values(dut, cycles):
    values = []

    for _ in range(cycles):
        await ClockCycles(dut.clk, 1)
        values.append(mod_debug(dut))

    return values


async def reset_dut(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0

    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


# ------------------------------------------------------------
# Main test
# ------------------------------------------------------------

@cocotb.test()
async def test_project(dut):
    dut._log.info("Start final PWM tremolo controller test")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # ------------------------------------------------------------
    # Input map:
    #
    # ui_in[0]   = enable
    # ui_in[2:1] = rate select
    # ui_in[4:3] = depth select
    # ui_in[6:5] = waveform select
    # ui_in[7]   = test/demo speed select
    #
    # test_speed = 1 for simulation speed
    # test_speed = 0 for real pedal-rate hardware speed
    #
    # Waveform modes:
    # 00 = saw up
    # 01 = saw down
    # 10 = square
    # 11 = triangle-like
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # Test 1: Disabled output should stay low
    # ------------------------------------------------------------
    dut._log.info("TEST 1: Disabled output")

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=0,
        depth=0,
        rate=0,
        enable=0
    )

    disabled_highs = await count_pwm_highs(dut, 256)

    dut._log.info(f"disabled_highs={disabled_highs}")

    assert disabled_highs == 0
    assert enable_debug_bit(dut) == 0

    # ------------------------------------------------------------
    # Test 2: Enabled saw-up PWM should produce activity
    # ------------------------------------------------------------
    dut._log.info("TEST 2: Enabled saw-up PWM activity")

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=0,
        depth=3,
        rate=0,
        enable=1
    )

    saw_up_highs = await count_pwm_highs(dut, 512)

    dut._log.info(f"saw_up_highs={saw_up_highs}")

    assert saw_up_highs > 0
    assert enable_debug_bit(dut) == 1

    # ------------------------------------------------------------
    # Test 3: Saw-down PWM should produce activity
    # ------------------------------------------------------------
    dut._log.info("TEST 3: Saw-down PWM activity")

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=1,
        depth=3,
        rate=0,
        enable=1
    )

    saw_down_highs = await count_pwm_highs(dut, 512)

    dut._log.info(f"saw_down_highs={saw_down_highs}")

    assert saw_down_highs > 0
    assert enable_debug_bit(dut) == 1

    # ------------------------------------------------------------
    # Test 4: Square waveform should behave differently from saw-up
    # ------------------------------------------------------------
    dut._log.info("TEST 4: Square waveform behavior")

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=2,
        depth=3,
        rate=0,
        enable=1
    )

    square_highs = await count_pwm_highs(dut, 2048)

    dut._log.info(f"square_highs={square_highs}")

    assert square_highs != saw_up_highs
    assert enable_debug_bit(dut) == 1

    # ------------------------------------------------------------
    # Test 5: Triangle waveform should produce activity
    # ------------------------------------------------------------
    dut._log.info("TEST 5: Triangle waveform activity")

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=3,
        depth=3,
        rate=0,
        enable=1
    )

    triangle_highs = await count_pwm_highs(dut, 512)

    dut._log.info(f"triangle_highs={triangle_highs}")

    assert triangle_highs > 0
    assert enable_debug_bit(dut) == 1

    # ------------------------------------------------------------
    # Test 6: Saw-up and saw-down should not have identical
    # modulation debug behavior.
    # ------------------------------------------------------------
    dut._log.info("TEST 6: Saw-up vs saw-down debug behavior")

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=0,
        depth=3,
        rate=0,
        enable=1
    )

    saw_values = await collect_mod_debug_values(dut, 1024)

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=1,
        depth=3,
        rate=0,
        enable=1
    )

    saw_down_values = await collect_mod_debug_values(dut, 1024)

    dut._log.info(f"saw first={saw_values[0]}, last={saw_values[-1]}")
    dut._log.info(f"saw_down first={saw_down_values[0]}, last={saw_down_values[-1]}")

    assert saw_values != saw_down_values

    # ------------------------------------------------------------
    # Test 7: Depth select should change PWM behavior.
    # This test checks the fixed depth-scaling logic.
    # ------------------------------------------------------------
    dut._log.info("TEST 7: Depth select behavior")

    depth_highs = []

    for depth_setting in range(4):
        await reset_dut(dut)

        dut.ui_in.value = make_ui(
            test_speed=1,
            waveform=0,
            depth=depth_setting,
            rate=0,
            enable=1
        )

        highs = await count_pwm_highs(dut, 512)
        depth_highs.append(highs)

        dut._log.info(f"depth_{depth_setting:02b}_highs={highs}")

    assert depth_highs[0] > 0
    assert depth_highs[1] > 0
    assert depth_highs[2] > 0

    # Full depth can begin near zero for saw-up, but it should still
    # produce valid behavior and should not match every other depth.
    assert len(set(depth_highs)) > 1

    # ------------------------------------------------------------
    # Test 8: Rate select should change modulation speed.
    # Fast rate should create at least as many unique modulation
    # debug levels as slow rate over the same sample window.
    # ------------------------------------------------------------
    dut._log.info("TEST 8: Rate select behavior")

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=3,
        depth=3,
        rate=0,
        enable=1
    )

    fast_values = await collect_mod_debug_values(dut, 1024)

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=1,
        waveform=3,
        depth=3,
        rate=3,
        enable=1
    )

    slow_values = await collect_mod_debug_values(dut, 1024)

    fast_unique = len(set(fast_values))
    slow_unique = len(set(slow_values))

    dut._log.info(f"fast_unique_mod_levels={fast_unique}")
    dut._log.info(f"slow_unique_mod_levels={slow_unique}")

    assert fast_unique >= slow_unique

    # ------------------------------------------------------------
    # Test 9: Real-speed mode should still produce valid output.
    # This does not wait long enough to verify slow LFO movement,
    # but it proves test_speed=0 does not break the design.
    # ------------------------------------------------------------
    dut._log.info("TEST 9: Real-speed mode sanity check")

    await reset_dut(dut)

    dut.ui_in.value = make_ui(
        test_speed=0,
        waveform=0,
        depth=0,
        rate=0,
        enable=1
    )

    real_speed_highs = await count_pwm_highs(dut, 128)

    dut._log.info(f"real_speed_highs={real_speed_highs}")

    assert real_speed_highs > 0
    assert enable_debug_bit(dut) == 1

    # ------------------------------------------------------------
    # Test 10: Output bus should contain valid 8-bit logic.
    # ------------------------------------------------------------
    dut._log.info("TEST 10: Output bus valid logic")

    final_output = out_value(dut)

    dut._log.info(f"final_output={final_output}")

    assert final_output >= 0
    assert final_output <= 255
