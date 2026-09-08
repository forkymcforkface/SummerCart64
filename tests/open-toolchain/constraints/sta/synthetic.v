/* Artificial phase/hold test topology; CLOCK_BUFFER is not a PLL model. */
module top(input clk, input d, output q);
  wire shifted;
  CLOCK_BUFFER phase(.A(clk), .Y(shifted));
  REG capture(.CLK(shifted), .D(d), .Q(q));
endmodule
