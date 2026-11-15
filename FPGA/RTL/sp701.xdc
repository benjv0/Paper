set_property PACKAGE_PIN AE8 [get_ports sysclk_p]
set_property PACKAGE_PIN AE7 [get_ports sysclk_n]
set_property IOSTANDARD LVDS_25 [get_ports sysclk_p]
set_property IOSTANDARD LVDS_25 [get_ports sysclk_n]

set_property PACKAGE_PIN J25 [get_ports led]
set_property IOSTANDARD LVCMOS33 [get_ports led]

# Reloj físico de entrada (200 MHz -> 5.000 ns) y reloj derivado de 100 MHz (10.000 ns)
create_clock -period 5.000 -name sysclk [get_ports sysclk_p]
create_generated_clock -name clk_100m -source [get_ports sysclk_p] -divide_by 2 [get_pins clk_div_reg/Q]