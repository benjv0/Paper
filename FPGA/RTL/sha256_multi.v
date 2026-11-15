`timescale 1ns / 1ps
// ============================================================================
// sha256_multi.v  -  N copias de sha256_bench en paralelo
//
// Todas las copias reciben el mismo reloj, reset y run. Como la maquina de
// estados es determinista, avanzan sincronizadas: completan el mismo numero
// de mensajes y se detienen en el mismo ciclo (comprobado con el modelo).
// Cada copia tiene un CORE_ID distinto, asi procesa una cadena distinta.
//
// Salidas (mismos nombres que el banco de 1 nucleo, para reusar el VIO):
//   nist_pass   : 1 si el autotest NIST "abc" paso en TODOS los nucleos
//   msg_counter : mensajes completados POR NUCLEO (todos llevan el mismo)
//   cycles      : ciclos de reloj procesando (parado no cuenta)
//   last_digest : XOR de los ultimos digests de los N nucleos
//
// Mensajes totales = N_CORES x msg_counter.  Debe cumplirse cycles = 136 x msg_counter.
// nist_pass y last_digest estan registrados (1 ciclo de retraso, irrelevante
// porque se leen con el banco parado).
// ============================================================================
module sha256_multi #(
    parameter integer N_CORES = 4          // 1..256
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         run,
    output reg          nist_pass,
    output wire [63:0]  msg_counter,
    output wire [63:0]  cycles,
    output reg  [255:0] last_digest
);

    wire [N_CORES-1:0]     nist_v;
    wire [64*N_CORES-1:0]  msg_v;
    wire [64*N_CORES-1:0]  cyc_v;
    wire [256*N_CORES-1:0] dig_v;

    // keep_hierarchy: la maquina de control es identica en todos los nucleos
    // (no depende de los datos). Sin este atributo Vivado podria fusionar esos
    // registros entre nucleos; con el, cada nucleo queda completo e igual al
    // banco de 1 nucleo ya medido, y el reporte por jerarquia es comparable.
    genvar k;
    generate
        for (k = 0; k < N_CORES; k = k + 1) begin : g_core
            (* keep_hierarchy = "yes" *)
            sha256_bench #(.CORE_ID(k)) u_bench (
                .clk        (clk),
                .rst_n      (rst_n),
                .run        (run),
                .nist_pass  (nist_v[k]),
                .msg_counter(msg_v[64*k +: 64]),
                .cycles     (cyc_v[64*k +: 64]),
                .last_digest(dig_v[256*k +: 256])
            );
        end
    endgenerate

    // Contadores del nucleo 0 (los demas llevan el mismo valor)
    assign msg_counter = msg_v[63:0];
    assign cycles      = cyc_v[63:0];

    // XOR de todos los digests
    reg [255:0] dig_xor;
    integer i;
    always @(*) begin
        dig_xor = 256'd0;
        for (i = 0; i < N_CORES; i = i + 1)
            dig_xor = dig_xor ^ dig_v[256*i +: 256];
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            nist_pass   <= 1'b0;
            last_digest <= 256'd0;
        end else begin
            nist_pass   <= &nist_v;
            last_digest <= dig_xor;
        end
    end

endmodule
