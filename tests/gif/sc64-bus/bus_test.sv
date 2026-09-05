/* Flat simulation boundary around the real mem_bus interface. */
module bus_test (
 input logic clk, reset, configure, cancel,
 input logic [26:0] arena_begin, arena_end, dictionary_base, canvas_base,
 output logic configured, config_error, busy, cancelled,
 input logic dict_valid, dict_write,
 input logic [11:0] dict_key,
 input logic [19:0] dict_wdata,
 output logic dict_ack, dict_error,
 output logic [19:0] dict_rdata,
 input logic canvas_valid, canvas_write,
 input logic [16:0] canvas_address,
 input logic [7:0] canvas_wdata,
 output logic canvas_ack, canvas_error,
 output logic [7:0] canvas_rdata,
 output logic request, write,
 output logic [1:0] wmask,
 output logic [26:0] address,
 output logic [15:0] wdata,
 input logic ack,
 input logic [15:0] rdata
);
 mem_bus bus ();
 assign request=bus.request;
 assign write=bus.write;
 assign wmask=bus.wmask;
 assign address=bus.address;
 assign wdata=bus.wdata;
 assign bus.ack=ack;
 assign bus.rdata=rdata;
 gif_sc64_bus adapter (.*);
endmodule
