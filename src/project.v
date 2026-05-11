`default_nettype none

module tt_um_pschuetz_tremolo (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    // ============================================================
    // Input mapping
    // ============================================================
    // ui_in[0]   = enable
    // ui_in[2:1] = rate select
    // ui_in[4:3] = depth select
    // ui_in[6:5] = waveform select
    // ui_in[7]   = test/demo speed select
    //
    // test_speed = 0 -> real pedal-rate LFO speeds
    // test_speed = 1 -> fast simulation/demo speeds
    // ============================================================

    wire enable = ui_in[0];
    wire [1:0] rate     = ui_in[2:1];
    wire [1:0] depth    = ui_in[4:3];
    wire [1:0] waveform = ui_in[6:5];
    wire test_speed     = ui_in[7];

    // ============================================================
    // Counters
    // ============================================================
    // pwm_counter runs continuously and creates the PWM carrier.
    // lfo_counter changes more slowly and creates the tremolo motion.
    // rate_divider controls how quickly the LFO counter advances.
    // ============================================================

    reg [7:0]  lfo_counter;
    reg [7:0]  pwm_counter;
    reg [23:0] rate_divider;

    wire [23:0] rate_limit;

    assign rate_limit = test_speed ?
        (
            // Fast simulation/demo values
            (rate == 2'b00) ? 24'd4  :
            (rate == 2'b01) ? 24'd8  :
            (rate == 2'b10) ? 24'd16 :
                              24'd32
        ) :
        (
            // Real pedal-rate values assuming a 50 MHz clock.
            // These make the 8-bit LFO cycle at practical tremolo speeds.
            (rate == 2'b00) ? 24'd19530  :  // fastest
            (rate == 2'b01) ? 24'd39061  :
            (rate == 2'b10) ? 24'd78124  :
                              24'd156249    // slowest
        );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfo_counter  <= 8'd0;
            pwm_counter  <= 8'd0;
            rate_divider <= 24'd0;
        end else begin
            pwm_counter <= pwm_counter + 8'd1;

            if (rate_divider >= rate_limit) begin
                rate_divider <= 24'd0;
                lfo_counter  <= lfo_counter + 8'd1;
            end else begin
                rate_divider <= rate_divider + 24'd1;
            end
        end
    end

    // ============================================================
    // Waveform generator
    // ============================================================
    // waveform = 00 -> saw up
    // waveform = 01 -> saw down
    // waveform = 10 -> square
    // waveform = 11 -> triangle-like
    // ============================================================

    wire [7:0] saw_up;
    wire [7:0] saw_down;
    wire [7:0] square_wave;
    wire [7:0] triangle_wave;
    wire [7:0] waveform_value;

    assign saw_up      = lfo_counter;
    assign saw_down    = ~lfo_counter;
    assign square_wave = lfo_counter[7] ? 8'd255 : 8'd0;

    assign triangle_wave = lfo_counter[7] ?
                           {~lfo_counter[6:0], 1'b0} :
                           { lfo_counter[6:0], 1'b0};

    assign waveform_value =
        (waveform == 2'b00) ? saw_up :
        (waveform == 2'b01) ? saw_down :
        (waveform == 2'b10) ? square_wave :
                              triangle_wave;

    // ============================================================
    // Depth control
    // ============================================================
    // This version gives each depth setting a better tremolo range:
    //
    // depth = 00 -> light tremolo:  192 to 255
    // depth = 01 -> medium tremolo: 128 to 255
    // depth = 10 -> deep tremolo:    64 to 255-ish
    // depth = 11 -> full tremolo:     0 to 255
    //
    // This is better for a real pedal because the deepest setting
    // can use the full modulation range.
    // ============================================================

    wire [7:0] modulation_level;

    assign modulation_level =
        (depth == 2'b00) ? (8'd192 + {2'b00, waveform_value[7:2]}) :
        (depth == 2'b01) ? (8'd128 + {1'b0,  waveform_value[7:1]}) :
        (depth == 2'b10) ? (8'd64  + {1'b0,  waveform_value[7:1]} + {2'b00, waveform_value[7:2]}) :
                           waveform_value;

    // ============================================================
    // PWM output
    // ============================================================
    // The PWM duty cycle follows modulation_level.
    // This output should be externally low-pass filtered into a
    // control voltage before driving analog pedal circuitry.
    // ============================================================

    wire pwm_out;

    assign pwm_out = enable ? (pwm_counter < modulation_level) : 1'b0;

    // ============================================================
    // Output mapping
    // ============================================================
    // uo_out[0]   = main PWM tremolo control output
    // uo_out[1]   = LFO debug
    // uo_out[2]   = PWM carrier debug
    // uo_out[3]   = enable status
    // uo_out[7:4] = modulation level debug
    // ============================================================

    assign uo_out[0]   = pwm_out;
    assign uo_out[1]   = lfo_counter[7];
    assign uo_out[2]   = pwm_counter[7];
    assign uo_out[3]   = enable;
    assign uo_out[7:4] = modulation_level[7:4];

    // ============================================================
    // Bidirectional IOs unused
    // ============================================================

    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    // Mark intentionally unused inputs as used
    wire _unused = &{ena, uio_in, 1'b0};

endmodule
