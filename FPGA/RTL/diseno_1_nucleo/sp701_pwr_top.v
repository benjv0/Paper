`timescale 1ns / 1ps
// ============================================================================
// sp701_pwr_top.v  -  Top SOLO para medir potencia (paso 3, SAIF)
//
// Igual que sp701_top.v pero:
//   - SIN VIO ni dbg_hub (la potencia que reporta Vivado queda solo del diseno)
//   - run fijo en 1: el banco procesa mensajes sin parar desde el arranque
//   - led_act = XOR de contadores y digest, para que Vivado NO pode nada
//     (sin VIO, msg_counter/cycles/last_digest no saldrian del chip)
//
// La jerarquia se llama igual (u_bench/u_core) que en el diseno medido,
// asi la potencia de u_core es comparable con la del reporte anterior.
// ============================================================================
module sp701_pwr_top (
    input  wire sysclk_p,
    input  wire sysclk_n,
    output wire led,        // D6  = autotest NIST
    output wire led_act     // D7  = actividad (solo para que no se pode logica)
);

    // Reloj diferencial 200 MHz -> divisor -> 100 MHz en BUFG (igual que sp701_top)
    wire clk_200m;
    IBUFDS ibufds_i (.I(sysclk_p), .IB(sysclk_n), .O(clk_200m));

    reg clk_div = 1'b0;
    always @(posedge clk_200m) clk_div <= ~clk_div;

    wire clk;
    BUFG bufg_i (.I(clk_div), .O(clk));

    // Reset de arranque: 16 ciclos
    reg [3:0] rst_cnt = 4'd0;
    wire      rst_n   = &rst_cnt;
    always @(posedge clk) if (!rst_n) rst_cnt <= rst_cnt + 4'd1;

    wire         nist_pass;
    wire [63:0]  msg_counter;
    wire [63:0]  cycles;
    wire [255:0] last_digest;

    sha256_bench u_bench (
        .clk        (clk),
        .rst_n      (rst_n),
        .run        (1'b1),
        .nist_pass  (nist_pass),
        .msg_counter(msg_counter),
        .cycles     (cycles),
        .last_digest(last_digest)
    );

    reg act = 1'b0;
    always @(posedge clk) act <= ^{msg_counter, cycles, last_digest};

    assign led     = nist_pass;
    assign led_act = act;

endmodule
