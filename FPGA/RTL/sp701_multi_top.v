`timescale 1ns / 1ps
// ============================================================================
// sp701_multi_top.v  -  Top para la placa: N nucleos + VIO (medicion)
//
// Igual que sp701_top.v (mismo reloj, reset, LED y VIO vio_0 sin cambios),
// pero con sha256_multi en lugar de un solo banco.
//
// >>> Para cambiar el numero de nucleos, edita SOLO el valor de N_CORES <<<
// ============================================================================
module sp701_multi_top #(
    parameter integer N_CORES = 24
) (
    input  wire sysclk_p,
    input  wire sysclk_n,
    output wire led                 // D6 = autotest NIST paso en todos los nucleos
);

    // Reloj diferencial 200 MHz -> divisor -> 100 MHz en BUFG
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

    wire         run;
    wire         nist_pass;
    wire [63:0]  msg_counter;
    wire [63:0]  cycles;
    wire [255:0] last_digest;

    sha256_multi #(.N_CORES(N_CORES)) u_multi (
        .clk        (clk),
        .rst_n      (rst_n),
        .run        (run),
        .nist_pass  (nist_pass),
        .msg_counter(msg_counter),
        .cycles     (cycles),
        .last_digest(last_digest)
    );

    // Mismo VIO que el diseno de 1 nucleo (4 entradas: 1/64/64/256, 1 salida)
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
