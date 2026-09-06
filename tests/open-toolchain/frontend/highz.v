/* Fixture: an undriven physical output must retain high impedance. */
module top(output wire floating);
 assign floating=1'bz;
endmodule
