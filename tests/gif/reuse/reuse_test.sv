/* Exact runtime payload reuse pilot. Two caller-owned external scratch banks
 * hold previous committed and current bytes. A commit means both decoding and
 * composition succeeded. No payload RAM or hash-based equality exists here. */
module reuse_test (
 input logic clk, reset, configure, start, cancel,
 input logic [26:0] arena_begin, arena_end, buffer_base,
 input logic [15:0] length,
 input logic [191:0] metadata,
 input logic [31:0] epoch,
 input logic [2:0] disposal,
 input logic in_valid,
 output logic in_ready,
 input logic [7:0] in_byte,
 output logic result_valid, result_hit,
 input logic replay_start,
 output logic out_valid, out_last,
 input logic out_ready,
 output logic [7:0] out_byte,
 input logic commit_valid, commit_success,
 output logic busy, cancelled, error, configured,
 output logic request, write,
 output logic [1:0] wmask,
 output logic [26:0] address,
 output logic [15:0] wdata,
 input logic ack,
 input logic [15:0] rdata
);
 mem_bus bus();
 assign request=bus.request;
 assign write=bus.write;
 assign wmask=bus.wmask;
 assign address=bus.address;
 assign wdata=bus.wdata;
 assign bus.ack=ack;
 assign bus.rdata=rdata;
 gif_payload_reuse reuse (.*);
endmodule