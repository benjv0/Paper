`timescale 1ns / 1ps
// ============================================================================
// sp701_top.v  -  Top para la SP701: reloj LVDS + banco SHA-256 + VIO
//
// Puertos (los mismos del XDC del hola mundo):  sysclk_p, sysclk_n, led
//   led = 1 si el autotest NIST "abc" dio bien EN LA PLACA.
//
// El VIO (IP "vio_0", ver instrucciones) permite desde Vivado:
//   probe_out0 : run  (1 = corre, 0 = para)
//   probe_in0  : nist_pass      (1 bit)
//   probe_in1  : msg_counter    (64 bits)
//   probe_in2  : cycles         (64 bits)
//   probe_in3  : last_digest    (256 bits)
// ============================================================================
module sp701_top (
    input  wire sysclk_p,
    input  wire sysclk_n,
    output wire led
);

    wire clk;
    IBUFDS ibufds_i (.I(sysclk_p), .IB(sysclk_n), .O(clk));

    // Reset de arranque: 16 ciclos
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
