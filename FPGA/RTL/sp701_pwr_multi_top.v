`timescale 1ns / 1ps
// ============================================================================
// sp701_pwr_multi_top.v  -  Top SOLO para potencia (SAIF) con N nucleos
//
// Igual que sp701_multi_top.v pero sin VIO y con run fijo en 1.
// Tiene una sola salida (led), como el diseno medido, asi la potencia
// estatica de I/O no cambia. El LED se actualiza solo cada 2^24 ciclos con
// el XOR de todas las salidas: obliga a Vivado a conservar toda la logica
// sin anadir potencia de conmutacion de I/O.
// Usa el mismo sp701.xdc que el diseno con VIO.
//
// >>> Usa el MISMO N_CORES que en sp701_multi_top.v <<<
// ============================================================================
module sp701_pwr_multi_top #(
    parameter integer N_CORES = 4
) (
    input  wire sysclk_p,
    input  wire sysclk_n,
    output wire led
);

    wire clk_200m;
    IBUFDS ibufds_i (.I(sysclk_p), .IB(sysclk_n), .O(clk_200m));

    reg clk_div = 1'b0;
    always @(posedge clk_200m) clk_div <= ~clk_div;

    wire clk;
    BUFG bufg_i (.I(clk_div), .O(clk));

    reg [3:0] rst_cnt = 4'd0;
    wire      rst_n   = &rst_cnt;
    always @(posedge clk) if (!rst_n) rst_cnt <= rst_cnt + 4'd1;

    wire         nist_pass;
    wire [63:0]  msg_counter;
    wire [63:0]  cycles;
    wire [255:0] last_digest;

    sha256_multi #(.N_CORES(N_CORES)) u_multi (
        .clk        (clk),
        .rst_n      (rst_n),
        .run        (1'b1),
        .nist_pass  (nist_pass),
        .msg_counter(msg_counter),
        .cycles     (cycles),
        .last_digest(last_digest)
    );

    reg led_r = 1'b0;
    always @(posedge clk)
        if (cycles[23:0] == 24'd0)
            led_r <= ^{nist_pass, msg_counter, cycles, last_digest};

    assign led = led_r;

endmodule
