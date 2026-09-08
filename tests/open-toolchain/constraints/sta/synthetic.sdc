# Synthetic fixture constraints; this is not an SC64 LPF translation.
create_clock -name root -period 10 [get_ports clk]
create_generated_clock -name phase270 -source [get_ports clk] \
    -edges {1 2 3} -edge_shift {7.5 7.5 7.5} [get_pins phase/Y]
set_input_delay -clock root -max 2.0 [get_ports d]
set_input_delay -clock root -min -0.5 [get_ports d]
set_output_delay -clock root -max 3.0 [get_ports q]
set_output_delay -clock root -min -1.0 [get_ports q]
