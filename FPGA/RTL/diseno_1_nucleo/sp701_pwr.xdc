## sp701_pwr.xdc - Restricciones del top de potencia (sp701_pwr_top)

set_property PACKAGE_PIN AE8 [get_ports sysclk_p]
set_property PACKAGE_PIN AE7 [get_ports sysclk_n]
set_property IOSTANDARD LVDS_25 [get_ports sysclk_p]
set_property IOSTANDARD LVDS_25 [get_ports sysclk_n]

# GPIO LED 0 (D6): autotest NIST
set_property PACKAGE_PIN J25 [get_ports led]
set_property IOSTANDARD LVCMOS33 [get_ports led]

# GPIO LED 1 (D7): actividad (solo evita que Vivado pode logica)
set_property PACKAGE_PIN M24 [get_ports led_act]
set_property IOSTANDARD LVCMOS33 [get_ports led_act]

# Reloj de entrada 200 MHz y reloj derivado de 100 MHz (igual que sp701.xdc)
create_clock -period 5.000 -name sysclk [get_ports sysclk_p]
create_generated_clock -name clk_100m -source [get_ports sysclk_p] -divide_by 2 [get_pins clk_div_reg/Q]
