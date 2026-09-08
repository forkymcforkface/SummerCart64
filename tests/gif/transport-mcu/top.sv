/* Test boundary around unchanged stock MCU memory mechanics and four clients.
 * Memory is an ACK-delayed host model, not the SDRAM chip or SPI protocol. */
module top(input logic clk,reset,gif_admit,
input logic [2:0] requests,writes,
input logic [26:0] a0,a1,a2,input logic [15:0] d0,d1,d2,
output logic [2:0] acks,output logic [15:0] r0,r1,r2,
input logic mem_start,mem_stop,mem_direction,input logic [8:0] mem_length,
input logic [31:0] mem_address,input logic mem_read,mem_write,
input logic [7:0] address,input logic mem_word_select,input logic [15:0] mem_wdata,
output logic [15:0] mem_rdata,output logic mem_busy,mcu_ack,
output logic idle,gif_idle,request,write,output logic [26:0] bus_address,
output logic [15:0] wdata,output logic [1:0] wmask,
input logic ack,input logic [15:0] rdata);
mem_bus scratch();mem_bus source();mem_bus packet();mem_bus mcu();mem_bus memory();
assign scratch.request=requests[0];assign source.request=requests[1];assign packet.request=requests[2];
assign scratch.write=writes[0];assign source.write=writes[1];assign packet.write=writes[2];
assign scratch.address=a0;assign source.address=a1;assign packet.address=a2;
assign scratch.wdata=d0;assign source.wdata=d1;assign packet.wdata=d2;
assign scratch.wmask=2'b11;assign source.wmask=2'b11;assign packet.wmask=2'b11;
assign acks={packet.ack,source.ack,scratch.ack};
assign r0=scratch.rdata;assign r1=source.rdata;assign r2=packet.rdata;
assign request=memory.request;assign write=memory.write;assign bus_address=memory.address;
assign wdata=memory.wdata;assign wmask=memory.wmask;
assign memory.ack=ack;assign memory.rdata=rdata;assign mcu_ack=mcu.ack;
gif_transport_mcu_mux mux(.clk(clk),.reset(reset),.gif_admit(gif_admit),.idle(idle),
.gif_idle(gif_idle),
.scratch(scratch),.source(source),.packet(packet),.mcu(mcu),.memory(memory));
stock_memory_slice stock(.clk(clk),.reset(reset),.mem_start(mem_start),.mem_stop(mem_stop),
.mem_direction(mem_direction),.mem_length(mem_length),.mem_address(mem_address),
.mem_read(mem_read),.mem_write(mem_write),.address(address),.mem_word_select(mem_word_select),
.mem_wdata(mem_wdata),.mem_rdata(mem_rdata),.mem_busy(mem_busy),.mem_bus(mcu));
endmodule
