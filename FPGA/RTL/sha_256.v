`timescale 1ns / 1ps

module sha256_core (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         init_msg,    // Pulso: procesa el Bloque 1 (inicializa con H0)
    input  wire         next_block,  // Pulso: procesa el Bloque 2+ (encadena digest previo)
    input  wire [511:0] block_in,    // Bloque de entrada de 512 bits (64 bytes)
    output reg          ready,       // 1 = núcleo libre para recibir bloque
    output reg          digest_valid,// Pulso de 1 ciclo al terminar las 64 rondas
    output wire [255:0] digest_out   // Digest SHA-256 resultante (256 bits)
);

    // Constantes iniciales H^(0) (FIPS 180-4)
    localparam [31:0] H0_INIT = 32'h6a09e667, H1_INIT = 32'hbb67ae85,
                      H2_INIT = 32'h3c6ef372, H3_INIT = 32'ha54ff53a,
                      H4_INIT = 32'h510e527f, H5_INIT = 32'h9b05688c,
                      H6_INIT = 32'h1f83d9ab, H7_INIT = 32'h5be0cd19;

    // Tabla de constantes de ronda K[0..63] (implementada en LUTROM)
    function [31:0] K_rom(input [5:0] r);
        case (r)
            6'd00: K_rom = 32'h428a2f98; 6'd01: K_rom = 32'h71374491;
            6'd02: K_rom = 32'hb5c0fbcf; 6'd03: K_rom = 32'he9b5dba5;
            6'd04: K_rom = 32'h3956c25b; 6'd05: K_rom = 32'h59f111f1;
            6'd06: K_rom = 32'h923f82a4; 6'd07: K_rom = 32'hab1c5ed5;
            6'd08: K_rom = 32'hd807aa98; 6'd09: K_rom = 32'h12835b01;
            6'd10: K_rom = 32'h243185be; 6'd11: K_rom = 32'h550c7dc3;
            6'd12: K_rom = 32'h72be5d74; 6'd13: K_rom = 32'h80deb1fe;
            6'd14: K_rom = 32'h9bdc06a7; 6'd15: K_rom = 32'hc19bf174;
            6'd16: K_rom = 32'he49b69c1; 6'd17: K_rom = 32'hefbe4786;
            6'd18: K_rom = 32'h0fc19dc6; 6'd19: K_rom = 32'h240ca1cc;
            6'd20: K_rom = 32'h2de92c6f; 6'd21: K_rom = 32'h4a7484aa;
            6'd22: K_rom = 32'h5cb0a9dc; 6'd23: K_rom = 32'h76f988da;
            6'd24: K_rom = 32'h983e5152; 6'd25: K_rom = 32'ha831c66d;
            6'd26: K_rom = 32'hb00327c8; 6'd27: K_rom = 32'hbf597fc7;
            6'd28: K_rom = 32'hc6e00bf3; 6'd29: K_rom = 32'hd5a79147;
            6'd30: K_rom = 32'h06ca6351; 6'd31: K_rom = 32'h14292967;
            6'd32: K_rom = 32'h27b70a85; 6'd33: K_rom = 32'h2e1b2138;
            6'd34: K_rom = 32'h4d2c6dfc; 6'd35: K_rom = 32'h53380d13;
            6'd36: K_rom = 32'h650a7354; 6'd37: K_rom = 32'h766a0abb;
            6'd38: K_rom = 32'h81c2c92e; 6'd39: K_rom = 32'h92722c85;
            6'd40: K_rom = 32'ha2bfe8a1; 6'd41: K_rom = 32'ha81a664b;
            6'd42: K_rom = 32'hc24b8b70; 6'd43: K_rom = 32'hc76c51a3;
            6'd44: K_rom = 32'hd192e819; 6'd45: K_rom = 32'hd6990624;
            6'd46: K_rom = 32'hf40e3585; 6'd47: K_rom = 32'h106aa070;
            6'd48: K_rom = 32'h19a4c116; 6'd49: K_rom = 32'h1e376c08;
            6'd50: K_rom = 32'h2748774c; 6'd51: K_rom = 32'h34b0bcb5;
            6'd52: K_rom = 32'h391c0cb3; 6'd53: K_rom = 32'h4ed8aa4a;
            6'd54: K_rom = 32'h5b9cca4f; 6'd55: K_rom = 32'h682e6ff3;
            6'd56: K_rom = 32'h748f82ee; 6'd57: K_rom = 32'h78a5636f;
            6'd58: K_rom = 32'h84c87814; 6'd59: K_rom = 32'h8cc70208;
            6'd60: K_rom = 32'h90befffa; 6'd61: K_rom = 32'ha4506ceb;
            6'd62: K_rom = 32'hbef9a3f7; 6'd63: K_rom = 32'hc67178f2;
        endcase
    endfunction

    // Ventana circular de expansión de mensajes W[0..15] (512 bits)
    reg [31:0] W [0:15];

    // Registros de trabajo (a..h) y estado encadenado (H0..H7)
    reg [31:0] a, b, c, d, e, f, g, h;
    reg [31:0] H0, H1, H2, H3, H4, H5, H6, H7;

    // Máquina de estados finitos (FSM)
    localparam [1:0] S_IDLE   = 2'd0,
                     S_ROUNDS = 2'd1,
                     S_UPDATE = 2'd2;

    reg [1:0] state;
    reg [5:0] round_cnt;

    // Operadores criptográficos libres de retardo de ruteo (rotaciones cableadas)
    wire [31:0] Sigma0 = {a[1:0],   a[31:2]}  ^ {a[12:0],  a[31:13]} ^ {a[21:0],  a[31:22]};
    wire [31:0] Sigma1 = {e[5:0],   e[31:6]}  ^ {e[10:0],  e[31:11]} ^ {e[24:0],  e[31:25]};
    wire [31:0] Ch     = (e & f) ^ (~e & g);
    wire [31:0] Maj    = (a & b) ^ (a & c) ^ (b & c);

    // Expansión dinámica en ventana deslizante W[16]
    wire [31:0] s0_w1  = {W[1][6:0],   W[1][31:7]}   ^ {W[1][17:0],  W[1][31:18]}  ^ (W[1]  >> 3);
    wire [31:0] s1_w14 = {W[14][16:0], W[14][31:17]} ^ {W[14][18:0], W[14][31:19]} ^ (W[14] >> 10);
    wire [31:0] W_new  = s1_w14 + W[9] + s0_w1 + W[0];

    // Ruta crítica mapeada en primitivas CARRY4
    wire [31:0] T1 = h + Sigma1 + Ch + K_rom(round_cnt) + W[0];
    wire [31:0] T2 = Sigma0 + Maj;

    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            state        <= S_IDLE;
            ready        <= 1'b1;
            digest_valid <= 1'b0;
            round_cnt    <= 6'd0;
            H0 <= H0_INIT; H1 <= H1_INIT; H2 <= H2_INIT; H3 <= H3_INIT;
            H4 <= H4_INIT; H5 <= H5_INIT; H6 <= H6_INIT; H7 <= H7_INIT;
            a  <= 32'd0;   b  <= 32'd0;   c  <= 32'd0;   d  <= 32'd0;
            e  <= 32'd0;   f  <= 32'd0;   g  <= 32'd0;   h  <= 32'd0;
            for (i = 0; i < 16; i = i + 1) W[i] <= 32'd0;
        end else begin
            digest_valid <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (init_msg || next_block) begin
                        ready     <= 1'b0;
                        round_cnt <= 6'd0;
                        state     <= S_ROUNDS;

                        // Carga de los 16 words iniciales del bloque de 512 bits
                        W[0]  <= block_in[511:480]; W[1]  <= block_in[479:448];
                        W[2]  <= block_in[447:416]; W[3]  <= block_in[415:384];
                        W[4]  <= block_in[383:352]; W[5]  <= block_in[351:320];
                        W[6]  <= block_in[319:288]; W[7]  <= block_in[287:256];
                        W[8]  <= block_in[255:224]; W[9]  <= block_in[223:192];
                        W[10] <= block_in[191:160]; W[11] <= block_in[159:128];
                        W[12] <= block_in[127:96];  W[13] <= block_in[95:64];
                        W[14] <= block_in[63:32];   W[15] <= block_in[31:0];

                        if (init_msg) begin
                            H0 <= H0_INIT; H1 <= H1_INIT; H2 <= H2_INIT; H3 <= H3_INIT;
                            H4 <= H4_INIT; H5 <= H5_INIT; H6 <= H6_INIT; H7 <= H7_INIT;
                            a  <= H0_INIT; b  <= H1_INIT; c  <= H2_INIT; d  <= H3_INIT;
                            e  <= H4_INIT; f  <= H5_INIT; g  <= H6_INIT; h  <= H7_INIT;
                        end else begin
                            a <= H0; b <= H1; c <= H2; d <= H3;
                            e <= H4; f <= H5; g <= H6; h <= H7;
                        end
                    end else begin
                        ready <= 1'b1;
                    end
                end

                S_ROUNDS: begin
                    // Actualización de registros de estado de trabajo
                    a <= T1 + T2;
                    b <= a;
                    c <= b;
                    d <= c;
                    e <= d + T1;
                    f <= e;
                    g <= f;
                    h <= g;

                    // Desplazamiento de la ventana circular W[0..15]
                    for (i = 0; i < 15; i = i + 1) begin
                        W[i] <= W[i+1];
                    end
                    W[15] <= W_new;

                    if (round_cnt == 6'd63) begin
                        state <= S_UPDATE;
                    end else begin
                        round_cnt <= round_cnt + 6'd1;
                    end
                end

                S_UPDATE: begin
                    // Acumulación de estado intermedio H^(i) = H^(i-1) + {a..h}
                    H0 <= H0 + a; H1 <= H1 + b; H2 <= H2 + c; H3 <= H3 + d;
                    H4 <= H4 + e; H5 <= H5 + f; H6 <= H6 + g; H7 <= H7 + h;
                    digest_valid <= 1'b1;
                    ready        <= 1'b1;
                    state        <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

    assign digest_out = {H0, H1, H2, H3, H4, H5, H6, H7};

endmodule