/* The failing SC64 pattern: two old-data read ports and port-B write priority. */
module dual_old #(parameter WIDTH=16, ABITS=9)(
 input clk,wa,wb,input [ABITS-1:0] aa,ab,
 input [WIDTH-1:0] da,db,output reg [WIDTH-1:0] qa,qb
);
 reg [WIDTH-1:0] mem[0:(1<<ABITS)-1];
 always @(posedge clk) begin
  if(wa)mem[aa]<=da;
  if(wb)mem[ab]<=db;
  qa<=mem[aa];qb<=mem[ab];
 end
endmodule
