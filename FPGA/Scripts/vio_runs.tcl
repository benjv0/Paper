# ============================================================================
# vio_runs.tcl  -  Paso 4: 5 corridas automaticas con el VIO
#
# Requisitos: Hardware Manager abierto, placa programada con sp701_top.bit
#             y su .ltx (el mismo diseno con VIO que ya mediste).
#
# Uso, en la Tcl Console de Vivado:
#     cd {C:/Users/Benjamin Oyarzun/Downloads}
#     set OUT_NAME vio_runs_N8.csv      ;# opcional (por defecto vio_runs.csv)
#     source vio_runs.tcl
#
# Sirve igual para el diseno de 1 nucleo y para el de N nucleos (mismo VIO).
#
# Que hace en cada corrida:
#   1) calentamiento: run = 1 durante WARM_MS, luego run = 0
#   2) lee los contadores (inicio)
#   3) run = 1 durante RUN_MS, midiendo el tiempo con el reloj del PC
#   4) run = 0, lee los contadores (fin)
# Escribe el CSV (OUT_NAME) en la carpeta actual. Tarda ~ N_RUNS x 64 s.
# El tiempo incluye la latencia JTAG de dos comandos (decenas de ms en 60 s,
# < 0.1 %). Los ciclos los cuenta la FPGA, asi que el throughput es exacto.
# ============================================================================
set N_RUNS  5
set RUN_MS  60000
set WARM_MS 3000
if {![info exists OUT_NAME]} { set OUT_NAME vio_runs.csv }
set OUT_CSV [file join [pwd] $OUT_NAME]

set vio [lindex [get_hw_vios -of_objects [current_hw_device]] 0]
if {$vio eq ""} { error "No encontre el VIO: programa la placa con el .bit y el .ltx" }

proc find_probe {pat} {
    global vio
    set p [get_hw_probes -of_objects $vio -filter "NAME =~ \"$pat\""]
    if {[llength $p] != 1} { error "Esperaba 1 probe para '$pat' y encontre: $p" }
    return $p
}
set p_run  [find_probe "*run*"]
set p_nist [find_probe "*nist_pass*"]
set p_msg  [find_probe "*msg_counter*"]
set p_cyc  [find_probe "*cycles*"]
set p_dig  [find_probe "*last_digest*"]
foreach p [list $p_msg $p_cyc $p_dig] { set_property INPUT_VALUE_RADIX HEX $p }

proc set_run {v} {
    global vio p_run
    set_property OUTPUT_VALUE $v $p_run
    commit_hw_vio $vio
}
proc snap {} {
    global vio p_msg p_cyc p_dig
    refresh_hw_vio $vio
    return [list [get_property INPUT_VALUE $p_msg] \
                 [get_property INPUT_VALUE $p_cyc] \
                 [get_property INPUT_VALUE $p_dig]]
}

set_run 0
after 300
refresh_hw_vio $vio
if {[get_property INPUT_VALUE $p_nist] ne "1"} { error "nist_pass no esta en 1: el autotest no paso" }

set f [open $OUT_CSV w]
puts $f "run,ms,msg_ini,cyc_ini,msg_fin,cyc_fin,dig_fin"

for {set i 1} {$i <= $N_RUNS} {incr i} {
    puts "Corrida $i de $N_RUNS: calentamiento..."
    set_run 1
    after $WARM_MS
    set_run 0
    after 300
    set s0 [snap]

    puts "Corrida $i de $N_RUNS: midiendo [expr {$RUN_MS / 1000}] s..."
    set t0 [clock milliseconds]
    set_run 1
    after $RUN_MS
    set_run 0
    set t1 [clock milliseconds]
    after 300
    set s1 [snap]

    puts $f "$i,[expr {$t1 - $t0}],[lindex $s0 0],[lindex $s0 1],[lindex $s1 0],[lindex $s1 1],[lindex $s1 2]"
    flush $f
}
close $f
puts "Listo: $OUT_CSV"
