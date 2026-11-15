`timescale 1ns / 1ps
// ============================================================================
// tb_pwr_saif.v  -  Estimulo para generar el SAIF (paso 3)
//
// Solo genera el reloj diferencial de 200 MHz de la placa. El top arranca
// solo (reset interno), hace el autotest NIST y luego procesa mensajes sin
// parar (run = 1 fijo), igual que en la placa.
//
// Se usa con "Run Post-Implementation Functional Simulation" y los comandos
// open_saif / log_saif / close_saif (ver instrucciones).
// ============================================================================
module tb_pwr_saif;

    reg  sysclk_p = 1'b0;
    wire sysclk_n = ~sysclk_p;
    always #2.5 sysclk_p = ~sysclk_p;     // 200 MHz

    wire led;
    wire led_act;

    sp701_pwr_top dut (
        .sysclk_p(sysclk_p),
        .sysclk_n(sysclk_n),
        .led     (led),
        .led_act (led_act)
    );

endmodule
