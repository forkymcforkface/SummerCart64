/* Compare mapped physical RAM with the original two-port source across all
 * write collision modes after initializing every address. Timing is untested. */
`timescale 1ns/1ps
module GSR_INST; reg GSRNET=0; initial #20 GSRNET=1; endmodule
module PUR_INST; reg PURNET=0; initial #20 PURNET=1; endmodule
module physical_tb;
reg clk=0, wa=0, wb=0;
reg [8:0] aa=0, ab=0;
reg [15:0] da=0, db=0;
wire [15:0] ga,gb,qa,qb;
integer i,mode;
reg checking=0;
gate dut(clk,wa,wb,aa,ab,da,db,qa,qb);
dual_old gold(clk,wa,wb,aa,ab,da,db,ga,gb);
task tick;
 begin
 #5 clk=1;
 #5;
 if(checking && ((qa !== ga) || (qb !== gb))) begin
 $display("FAIL i=%0d mode=%0d got=%h/%h expected=%h/%h",i,mode,qa,qb,ga,gb);
 $fatal(1);
 end
 clk=0;
 #5;
 end
endtask
initial begin
 #100;
 for(i=0;i<512;i=i+1) begin
 aa=i;ab=i;wa=1;wb=1;da=i;db=i^16'h5a5a;tick;
 end
 checking=1;
 for(i=0;i<6000;i=i+1) begin
 aa=$random;ab=$random;da=$random;db=$random;
 mode=i%8;wa=mode[0];wb=mode[1];
 if(mode[2])ab=aa;
 tick;
 end
 $display("PASS physical DP8KC collision comparison cycles=6000");
 $finish;
end
endmodule
