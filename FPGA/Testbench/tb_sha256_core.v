`timescale 1ns / 1ps
// ============================================================================
// tb_sha256_core.v  -  Testbench autoverificable del nucleo SHA-256
//
// Que hace:
//   1) Prueba 4 vectores contra el resultado correcto (generado con hashlib):
//        - cadena vacia                (1 bloque)
//        - "abc"                       (1 bloque)
//        - 56 bytes del NIST           (2 bloques, prueba el encadenamiento)
//        - 64 bytes 00..3F             (2 bloques, ES TU CASO C = 64 B)
//   2) Mide los ciclos de reloj por bloque y por mensaje de 64 B.
//   3) (Opcional) 1 000 000 de 'a'    (15 626 bloques encadenados).
//
// Usa el MISMO handshake que sp701_sha256_top.v (peticion registrada,
// espera de digest_valid), asi los ciclos medidos son los del top.
//
// Como correrlo en Vivado:
//   Sources -> "+" -> Add or create simulation sources -> agregar este archivo
//   Flow Navigator -> Run Simulation -> Run Behavioral Simulation
//   En la Tcl Console escribir:   run all
// ============================================================================
module tb_sha256_core;

    parameter RUN_MILLION_A = 1;   // 0 para saltarse la prueba larga

    reg          clk        = 1'b0;
    reg          rst_n      = 1'b0;
    reg          init_msg   = 1'b0;
    reg          next_block = 1'b0;
    reg  [511:0] block_in   = 512'd0;
    wire         ready;
    wire         digest_valid;
    wire [255:0] digest_out;

    sha256_core dut (
        .clk         (clk),
        .rst_n       (rst_n),
        .init_msg    (init_msg),
        .next_block  (next_block),
        .block_in    (block_in),
        .ready       (ready),
        .digest_valid(digest_valid),
        .digest_out  (digest_out)
    );

    always #5 clk = ~clk;          // 100 MHz

    // Contador de flancos de reloj
    reg [63:0] cyc = 64'd0;
    always @(posedge clk) cyc <= cyc + 64'd1;

    // ------------------------------------------------------------------
    // Vectores (generados con Python/hashlib)
    // ------------------------------------------------------------------
    localparam [511:0] ABC_B1   = 512'h61626380000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000018;
    localparam [255:0] ABC_EXP  = 256'hba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad;

    localparam [511:0] EMP_B1   = 512'h80000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000;
    localparam [255:0] EMP_EXP  = 256'he3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855;

    localparam [511:0] N56_B1   = 512'h6162636462636465636465666465666765666768666768696768696a68696a6b696a6b6c6a6b6c6d6b6c6d6e6c6d6e6f6d6e6f706e6f70718000000000000000;
    localparam [511:0] N56_B2   = 512'h000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001c0;
    localparam [255:0] N56_EXP  = 256'h248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1;

    localparam [511:0] C64_B1   = 512'h000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f;
    localparam [511:0] C64_B2   = 512'h80000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000200;
    localparam [255:0] C64_EXP  = 256'hfdeab9acf3710362bd2658cdc9a29e8f9c757fcf9811603a8c447cd1d9151108;

    localparam [511:0] A64_BLK  = 512'h61616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161;
    localparam [511:0] A1M_PAD  = {8'h80, 440'd0, 64'd8000000};
    localparam [255:0] A1M_EXP  = 256'hcdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0;

    // ------------------------------------------------------------------
    // Tarea: envia un bloque como lo hace el top y espera digest_valid
    //   first = 1 -> pulso init_msg   (bloque 1, parte de H0)
    //   first = 0 -> pulso next_block (bloque 2+, encadena el digest)
    // ------------------------------------------------------------------
    reg [63:0] t_req;
    reg [63:0] lat_last;

    task send_block;
        input [511:0] blk;
        input         first;
        begin
            @(posedge clk);
            while (!ready) @(posedge clk);
            block_in   <= blk;
            init_msg   <= first;
            next_block <= ~first;
            t_req = cyc;
            @(posedge clk);
            init_msg   <= 1'b0;
            next_block <= 1'b0;
            while (!digest_valid) @(posedge clk);
            lat_last = cyc - t_req;
        end
    endtask

    integer errors = 0;

    task check;
        input [255:0] expected;
        begin
            if (digest_out === expected)
                $display("    -> PASS   digest = %h", digest_out);
            else begin
                $display("    -> FAIL   obtenido = %h", digest_out);
                $display("              esperado = %h", expected);
                errors = errors + 1;
            end
        end
    endtask

    integer    k;
    reg [63:0] t_first, t_last;

    initial begin
        $display("=== Testbench sha256_core  (reloj 100 MHz) ===");
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;
        repeat (2) @(posedge clk);

        $display("[1] Cadena vacia");
        send_block(EMP_B1, 1'b1);
        $display("    latencia peticion->digest_valid = %0d ciclos", lat_last);
        check(EMP_EXP);

        $display("[2] \"abc\" (1 bloque)");
        send_block(ABC_B1, 1'b1);
        $display("    latencia peticion->digest_valid = %0d ciclos", lat_last);
        check(ABC_EXP);

        $display("[3] 56 bytes del NIST (2 bloques)");
        send_block(N56_B1, 1'b1);
        send_block(N56_B2, 1'b0);
        check(N56_EXP);

        $display("[4] 64 bytes 00..3F (C = 64 B, B = 2)");
        send_block(C64_B1, 1'b1);
        send_block(C64_B2, 1'b0);
        check(C64_EXP);

        // Regimen permanente: 101 mensajes de 64 B seguidos, igual que el top
        for (k = 0; k <= 100; k = k + 1) begin
            send_block(C64_B1, 1'b1);
            if (k == 0)   t_first = t_req;
            if (k == 100) t_last  = t_req;
            send_block(C64_B2, 1'b0);
        end
        $display("[5] Ciclos por mensaje de 64 B en regimen permanente = %0d",
                 (t_last - t_first) / 100);
        check(C64_EXP);

        if (RUN_MILLION_A) begin
            $display("[6] 1 000 000 de 'a' (15 626 bloques encadenados)...");
            send_block(A64_BLK, 1'b1);
            for (k = 1; k < 15625; k = k + 1)
                send_block(A64_BLK, 1'b0);
            send_block(A1M_PAD, 1'b0);
            check(A1M_EXP);
        end

        $display("--------------------------------------------");
        if (errors == 0) $display("*** TODAS LAS PRUEBAS PASARON ***");
        else             $display("*** HAY %0d PRUEBA(S) CON ERROR ***", errors);
        $finish;
    end

    // Watchdog: si algo se cuelga, termina
    initial begin
        #100_000_000;
        $display("*** TIMEOUT: la simulacion se colgo ***");
        $finish;
    end

endmodule
