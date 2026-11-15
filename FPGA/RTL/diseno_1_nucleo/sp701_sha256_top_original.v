`timescale 1ns / 1ps
module sp701_top (
    input  wire sysclk_p,
    input  wire sysclk_n,
    output wire led
);

    // 1. Reloj diferencial de 200 MHz (5.0 ns) desde pines AE8/AE7
    wire clk_200m;
    IBUFDS ibufds_i (.I(sysclk_p), .IB(sysclk_n), .O(clk_200m));

    // 2. Divisor síncrono a 100 MHz (10.0 ns) en red global BUFG
    reg clk_div = 1'b0;
    always @(posedge clk_200m) clk_div <= ~clk_div;

    wire clk;
    BUFG bufg_i (.I(clk_div), .O(clk));

    // 3. Reset de arranque: 16 ciclos
    reg [3:0] rst_cnt = 4'd0;
    wire      rst_n   = &rst_cnt;
    always @(posedge clk) if (!rst_n) rst_cnt <= rst_cnt + 4'd1;

    wire         run;
    wire         nist_pass;
    wire [63:0]  msg_counter;
    wire [63:0]  cycles;
    wire [255:0] last_digest;

    sha256_bench u_bench (
        .clk        (clk),
        .rst_n      (rst_n),
        .run        (run),
        .nist_pass  (nist_pass),
        .msg_counter(msg_counter),
        .cycles     (cycles),
        .last_digest(last_digest)
    );

    vio_0 u_vio (
        .clk       (clk),
        .probe_in0 (nist_pass),
        .probe_in1 (msg_counter),
        .probe_in2 (cycles),
        .probe_in3 (last_digest),
        .probe_out0(run)
    );

    assign led = nist_pass;

endmodule