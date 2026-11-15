`timescale 1ns / 1ps
// ============================================================================
// tb_sha256_multi.v  -  Testbench del banco de N nucleos (N = 4, sin VIO)
//
//  [1] el autotest NIST pasa en los 4 nucleos
//  [2] run=1 hasta ~20 mensajes por nucleo, run=0:
//        ciclos == 136 x mensajes y XOR de digests correcto
//  [3] con run=0 los contadores NO cambian
//  [4] run=1 otra vez (+5 mensajes): ciclos y XOR de digests correctos
//
// Los XOR esperados salen de 4 cadenas hashlib (una por CORE_ID). El modelo
// ciclo a ciclo de este diseno predice N = 21 en [2] y N = 27 en [4], igual
// que el banco de 1 nucleo; la tabla cubre 19..29 por si acaso.
//
// Correr: clic derecho en tb_sha256_multi -> Set as Top,
//         Run Behavioral Simulation y en la Tcl Console:  run all
// ============================================================================
module tb_sha256_multi;

    localparam integer N = 4;

    reg          clk   = 1'b0;
    reg          rst_n = 1'b0;
    reg          run   = 1'b0;
    wire         nist_pass;
    wire [63:0]  msg_counter;
    wire [63:0]  cycles;
    wire [255:0] last_digest;

    sha256_multi #(.N_CORES(N)) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .run        (run),
        .nist_pass  (nist_pass),
        .msg_counter(msg_counter),
        .cycles     (cycles),
        .last_digest(last_digest)
    );

    always #5 clk = ~clk;          // 100 MHz

    integer    errors = 0;
    reg [63:0] n_stop;
    reg [63:0] c_stop;

    function [255:0] expected_xor;
        input [63:0] n;
        begin
            case (n)
                64'd19:  expected_xor = 256'h3e955bb76b463c0ec74d03d9da44798974d311a949669889604bfb9d57881500;
                64'd20:  expected_xor = 256'h0ecd4cffc743896c74dc11dff654ac6e913696f3f692ed72a50d5ea29799877f;
                64'd21:  expected_xor = 256'h3e22357d4ad8c0737502046d284e6f7ec502bc624be06d760ac788ebd24133a6;
                64'd22:  expected_xor = 256'h3c491c4b43e01435bdcc02b2414e1266ffd6802a264e41ebbfbb9e3f005e6e9f;
                64'd23:  expected_xor = 256'ha08fb33b6afb0dbabe5ff51cb83b48c0d08bf3b7b361e9155b8622b50edb512a;
                64'd24:  expected_xor = 256'h41b6f82da502b2066afb7dc3e5ae643e5997d6d7378d8d00f274e206bd43cd47;
                64'd25:  expected_xor = 256'h7cd3ab36e6c361f2a066f9440bf7506a5e290d7cab20bc3bd9b54008cb4db456;
                64'd26:  expected_xor = 256'h83a95a28e7101f4cb09b7c6286534edb7093e7c3f8e8da4c8a56752b5e918348;
                64'd27:  expected_xor = 256'h0715d81f2c22f7173e5398e93ee97e44d23e8da3cc9532c3ebd4d03507d8fb5f;
                64'd28:  expected_xor = 256'h0a1a3750197d4382dccc3af8784d7a977108ec8bb2a03fe743a1982b03810c3c;
                64'd29:  expected_xor = 256'h10345a1827649cfee590bb71b5362bb7007ebfa31c4aa00938ea5519a80ca073;
                default: expected_xor = 256'd0;
            endcase
        end
    endfunction

    task check_point;
        input [63:0] n;
        input [63:0] c;
        input [255:0] d;
        begin
            if (c === n * 64'd136)
                $display("    -> PASS   ciclos = 136 x mensajes");
            else begin
                $display("    -> FAIL   se esperaban %0d ciclos", n * 64'd136);
                errors = errors + 1;
            end
            if (expected_xor(n) === 256'd0)
                $display("    (N=%0d no esta en la tabla) XOR = %h", n, d);
            else if (d === expected_xor(n))
                $display("    -> PASS   XOR de %0d digests = %h", N, d);
            else begin
                $display("    -> FAIL   XOR obtenido = %h", d);
                $display("              XOR esperado = %h", expected_xor(n));
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        $display("=== Testbench sha256_multi (N = %0d, reloj 100 MHz) ===", N);
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;

        // [1] Autotest NIST en todos los nucleos
        while (!nist_pass) @(posedge clk);
        $display("[1] Autotest NIST 'abc' en los %0d nucleos: PASS", N);

        // [2] Correr hasta 20 mensajes por nucleo y parar
        run <= 1'b1;
        while (msg_counter < 20) @(posedge clk);
        run <= 1'b0;
        repeat (400) @(posedge clk);
        n_stop = msg_counter;
        c_stop = cycles;
        $display("[2] Mensajes por nucleo = %0d (total %0d), ciclos = %0d", n_stop, n_stop * N, c_stop);
        check_point(n_stop, c_stop, last_digest);

        // [3] Con run=0 todo debe quedarse quieto
        repeat (400) @(posedge clk);
        if (msg_counter === n_stop && cycles === c_stop)
            $display("[3] Con run=0 el banco queda parado: PASS");
        else begin
            $display("[3] FAIL: los contadores cambiaron estando parado");
            errors = errors + 1;
        end

        // [4] Reanudar 5 mensajes mas
        run <= 1'b1;
        while (msg_counter < n_stop + 5) @(posedge clk);
        run <= 1'b0;
        repeat (400) @(posedge clk);
        $display("[4] Tras reanudar: mensajes por nucleo = %0d, ciclos = %0d", msg_counter, cycles);
        check_point(msg_counter, cycles, last_digest);

        $display("--------------------------------------------");
        if (errors == 0) $display("*** TODAS LAS PRUEBAS PASARON ***");
        else             $display("*** HAY %0d PRUEBA(S) CON ERROR ***", errors);
        $finish;
    end

    // Watchdog: 5 ms de simulacion
    initial begin
        #5_000_000;
        $display("*** TIMEOUT: la simulacion se colgo ***");
        $finish;
    end

endmodule
