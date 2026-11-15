`timescale 1ns / 1ps
// ============================================================================
// tb_sha256_bench.v  -  Testbench del banco sha256_bench (sin VIO, solo simulacion)
//
//  [1] el autotest NIST "abc" del banco da PASS
//  [2] run=1 hasta ~20 mensajes, run=0: ciclos == 136 x mensajes y digest correcto
//  [3] con run=0 los contadores NO cambian (el banco queda parado)
//  [4] run=1 otra vez: reanuda y sigue cumpliendo ciclos == 136 x mensajes
//
// Los digests esperados (N = 20, 21, 22) salen de la cadena calculada con hashlib.
// Como run=0 llega un ciclo despues de que el tb ve msg_counter=20, normalmente
// se completa 1 mensaje mas (N=21); por eso la tabla trae 20, 21 y 22.
//
// Como correrlo: agregar como simulation source, poner este modulo como top de
// simulacion (clic derecho -> Set as Top), Run Behavioral Simulation, y en la
// Tcl Console:  run all
// ============================================================================
module tb_sha256_bench;

    reg          clk   = 1'b0;
    reg          rst_n = 1'b0;
    reg          run   = 1'b0;
    wire         nist_pass;
    wire [63:0]  msg_counter;
    wire [63:0]  cycles;
    wire [255:0] last_digest;

    sha256_bench dut (
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

    function [255:0] expected_digest;
        input [63:0] n;
        begin
            case (n)
                64'd20:  expected_digest = 256'h4f25d4cf363de6ca8db154c35fb54807a3e242ee60238b263102179a5778a644;
                64'd21:  expected_digest = 256'h58280e00f6d9ade14ee59aa47e4e43aca8cd01be532cf60af186b111dc2080f7;
                64'd22:  expected_digest = 256'hfbb7b0935d2cc02fa66d1c9d6b8ae440fa7780baabab5c828366c59d9afb95a7;
                default: expected_digest = 256'd0;
            endcase
        end
    endfunction

    initial begin
        $display("=== Testbench sha256_bench (reloj 100 MHz) ===");
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;

        // [1] Autotest NIST dentro del banco
        while (!nist_pass) @(posedge clk);
        $display("[1] Autotest NIST 'abc' dentro del banco: PASS");

        // [2] Correr hasta 20 mensajes y parar
        run <= 1'b1;
        while (msg_counter < 20) @(posedge clk);
        run <= 1'b0;
        repeat (400) @(posedge clk);          // deja terminar el mensaje en curso
        n_stop = msg_counter;
        c_stop = cycles;
        $display("[2] Mensajes completados = %0d, ciclos = %0d", n_stop, c_stop);
        if (c_stop === n_stop * 64'd136)
            $display("    -> PASS   ciclos = 136 x mensajes");
        else begin
            $display("    -> FAIL   se esperaban %0d ciclos", n_stop * 64'd136);
            errors = errors + 1;
        end
        if (expected_digest(n_stop) === 256'd0)
            $display("    (N=%0d no esta en la tabla; compara con check_run.py) digest = %h", n_stop, last_digest);
        else if (last_digest === expected_digest(n_stop))
            $display("    -> PASS   digest = %h", last_digest);
        else begin
            $display("    -> FAIL   obtenido = %h", last_digest);
            $display("              esperado = %h", expected_digest(n_stop));
            errors = errors + 1;
        end

        // [3] Con run=0 todo debe quedarse quieto
        repeat (400) @(posedge clk);
        if (msg_counter === n_stop && cycles === c_stop)
            $display("[3] Con run=0 el banco queda parado: PASS");
        else begin
            $display("[3] FAIL: los contadores cambiaron estando parado");
            errors = errors + 1;
        end

        // [4] Reanudar
        run <= 1'b1;
        while (msg_counter < n_stop + 5) @(posedge clk);
        run <= 1'b0;
        repeat (400) @(posedge clk);
        $display("[4] Tras reanudar: mensajes = %0d, ciclos = %0d", msg_counter, cycles);
        if (cycles === msg_counter * 64'd136)
            $display("    -> PASS   ciclos = 136 x mensajes");
        else begin
            $display("    -> FAIL   se esperaban %0d ciclos", msg_counter * 64'd136);
            errors = errors + 1;
        end

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
