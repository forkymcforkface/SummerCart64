/* Old-data dual-port memory with independent read enables and B write priority. */
module dual_enabled(input clk, wa, wb, ea, eb,
 input [1:0] aa, ab, input [2:0] da, db,
 output reg [2:0] qa, qb);
 reg [2:0] mem[0:3];
 always @(posedge clk) begin
  if (wa) mem[aa] <= da;
  if (wb) mem[ab] <= db;
  if (ea) qa <= mem[aa];
  if (eb) qb <= mem[ab];
 end
endmodule
