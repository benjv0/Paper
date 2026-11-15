`timescale 1ns / 1ps
// ============================================================================
// tb_pwr_multi.v  -  Estimulo para el SAIF del diseno de N nucleos
// Solo genera el reloj diferencial de 200 MHz; el diseno arranca solo
// (reset interno, autotest NIST y luego run = 1 fijo).
// ============================================================================
module tb_pwr_multi;

    reg  sysclk_p = 1'b0;
    wire sysclk_n = ~sysclk_p;
    always #2.5 sysclk_p = ~sysclk_p;     // 200 MHz

    wire led;

    sp701_pwr_multi_top dut (
        .sysclk_p(sysclk_p),
        .sysclk_n(sysclk_n),
        .led     (led)
    );

endmodule
