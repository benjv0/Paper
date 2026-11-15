# ============================================================================
# sp701_sha256.xdc  -  Pines que YA comprobaste con el hola mundo
#   reloj LVDS AE8/AE7 (LVDS_25), LED D6 = GPIO_LED0 en J25 (LVCMOS33)
# ============================================================================
set_property PACKAGE_PIN AE8 [get_ports sysclk_p]
set_property PACKAGE_PIN AE7 [get_ports sysclk_n]
set_property IOSTANDARD LVDS_25 [get_ports sysclk_p]
set_property IOSTANDARD LVDS_25 [get_ports sysclk_n]

set_property PACKAGE_PIN J25 [get_ports led]
set_property IOSTANDARD LVCMOS33 [get_ports led]

# Periodo del reloj: AJUSTA segun lo que midas con tu hola mundo (cnt[25]):
#   LED cambia cada ~1 s    -> 33.33 MHz -> periodo 30.000 ns   (valor puesto abajo)
#   LED cambia cada ~0.17 s -> 200 MHz   -> periodo  5.000 ns
create_clock -period 30.000 -name sysclk [get_ports sysclk_p]
