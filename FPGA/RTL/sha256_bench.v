`timescale 1ns / 1ps
// ============================================================================
// sha256_bench.v  -  Banco de prueba DENTRO del chip para tu sha256_core
//
// Replica la maquina de estados del modelo verify_model.py (clase Top):
//   1) Autotest NIST "abc": si el digest sale bien -> nist_pass = 1
//   2) Bucle de mensajes de 64 B (2 bloques c/u), encadenados:
//        bloque 1 = {contador(64), digest_previo(256), ~contador(64), digest_previo[127:0]}
//        bloque 2 = relleno fijo de 64 B
//      El digest de cada mensaje alimenta al siguiente, asi todo hash cuenta
//      y Python puede repetir la cadena para verificar el resultado final.
//
// Control:  run = 1 -> procesa mensajes
//           run = 0 -> termina el mensaje en curso y se PARA (valores estables)
//
// Contadores (para leer con el VIO):
//   msg_counter : mensajes de 64 B completados
//   cycles      : ciclos de reloj gastados procesando mensajes (parado no cuenta)
//   last_digest : digest del ultimo mensaje completado
//
// Debe salir  cycles = 136 x msg_counter  (el modelo y el testbench lo predicen).
// Requiere tu sha256_core.v con los puertos que usa tb_sha256_core.v.
//
// CORE_ID (version multinucleo): cada copia del banco recibe un CORE_ID
// distinto, que se mezcla en el tercer campo del bloque 1:
//     {contador, digest_previo, ~contador ^ {CORE_ID, 56'd0}, digest_previo[127:0]}
// Asi cada nucleo procesa una cadena distinta (Vivado no puede fusionarlos) y
// con CORE_ID = 0 la cadena es identica a la del banco de un nucleo ya medido.
// ============================================================================
module sha256_bench #(
    parameter [7:0] CORE_ID = 8'd0
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         run,
    output reg          nist_pass,
    output reg  [63:0]  msg_counter,
    output reg  [63:0]  cycles,
    output reg  [255:0] last_digest
);

    localparam [511:0] NIST_ABC_BLK  = {24'h616263, 8'h80, 416'd0, 64'd24};
    localparam [255:0] NIST_ABC_EXP  = 256'hba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad;
    localparam [511:0] PAD_BLOCK_64B = {8'h80, 440'd0, 64'd512};

    localparam [2:0] B_NIST_START = 3'd0,
                     B_NIST_WAIT  = 3'd1,
                     B_MSG_BLK1   = 3'd2,
                     B_WAIT_BLK1  = 3'd3,
                     B_MSG_BLK2   = 3'd4,
                     B_WAIT_BLK2  = 3'd5;

    reg  [2:0]   b_state;
    reg          init_msg;
    reg          next_block;
    reg  [511:0] block_in;
    reg          run_s;

    wire         ready;
    wire         digest_valid;
    wire [255:0] digest_out;

    sha256_core u_core (
        .clk         (clk),
        .rst_n       (rst_n),
        .init_msg    (init_msg),
        .next_block  (next_block),
        .block_in    (block_in),
        .ready       (ready),
        .digest_valid(digest_valid),
        .digest_out  (digest_out)
    );

    // El contador de ciclos NO cuenta durante el autotest ni cuando esta parado
    wire counting = (b_state != B_NIST_START) &&
                    (b_state != B_NIST_WAIT)  &&
                    !((b_state == B_MSG_BLK1) && !run_s);

    always @(posedge clk) begin
        if (!rst_n) begin
            b_state     <= B_NIST_START;
            init_msg    <= 1'b0;
            next_block  <= 1'b0;
            block_in    <= 512'd0;
            run_s       <= 1'b0;
            nist_pass   <= 1'b0;
            msg_counter <= 64'd0;
            cycles      <= 64'd0;
            last_digest <= 256'd0;
        end else begin
            run_s      <= run;
            init_msg   <= 1'b0;
            next_block <= 1'b0;

            if (counting) cycles <= cycles + 64'd1;

            case (b_state)
                B_NIST_START: begin
                    if (ready) begin
                        block_in <= NIST_ABC_BLK;
                        init_msg <= 1'b1;
                        b_state  <= B_NIST_WAIT;
                    end
                end

                B_NIST_WAIT: begin
                    if (digest_valid) begin
                        if (digest_out == NIST_ABC_EXP) nist_pass <= 1'b1;
                        b_state <= B_MSG_BLK1;
                    end
                end

                B_MSG_BLK1: begin
                    if (run_s && ready) begin
                        block_in <= {msg_counter, last_digest,
                                     (~msg_counter) ^ {CORE_ID, 56'd0},
                                     last_digest[127:0]};
                        init_msg <= 1'b1;
                        b_state  <= B_WAIT_BLK1;
                    end
                end

                B_WAIT_BLK1: begin
                    if (digest_valid) b_state <= B_MSG_BLK2;
                end

                B_MSG_BLK2: begin
                    if (ready) begin
                        block_in   <= PAD_BLOCK_64B;
                        next_block <= 1'b1;
                        b_state    <= B_WAIT_BLK2;
                    end
                end

                B_WAIT_BLK2: begin
                    if (digest_valid) begin
                        last_digest <= digest_out;
                        msg_counter <= msg_counter + 64'd1;
                        b_state     <= B_MSG_BLK1;
                    end
                end

                default: b_state <= B_NIST_START;
            endcase
        end
    end

endmodule
