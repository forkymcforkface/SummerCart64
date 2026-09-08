/* Exact runtime payload reuse pilot. Two caller-owned external scratch banks
 * hold previous committed and current bytes. A commit means both decoding and
 * composition succeeded. No payload RAM or hash-based equality exists here. */
module gif_payload_reuse (
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
 mem_bus.controller bus
);
 typedef enum logic [3:0] {IDLE, INPUT_BYTE, WRITE_WAIT, WRITE_GAP,
  COMPARE_WAIT, NEXT_BYTE, RESULT, REPLAY_READ, REPLAY_WAIT, REPLAY_OUTPUT,
  COMMIT, DRAIN, CANCEL_DONE} state_t;
 state_t state;
 logic [26:0] base;
 logic prior_bank, current_bank, prior_valid, equal_bytes, abort_pending;
 logic [15:0] prior_length, current_length, position;
 logic [191:0] prior_metadata, current_metadata;
 logic [31:0] prior_epoch, current_epoch;
 logic current_eligible, prior_eligible;
 logic [7:0] byte_latch;
 wire [27:0] banks_end={1'b0,buffer_base}+28'd51496;
 wire [26:0] current_address=base+(current_bank?27'd25748:27'd0)+{11'b0,position};
 wire [26:0] prior_address=base+(prior_bank?27'd25748:27'd0)+{11'b0,position};
 assign busy=state!=IDLE;
 assign in_ready=state==INPUT_BYTE&&!cancel;
 assign out_valid=state==REPLAY_OUTPUT&&!cancel;
 assign out_last=position==current_length-16'd1;
 assign result_valid=state==RESULT;
 assign result_hit=equal_bytes;
 always_ff @(posedge clk) begin
  error<=0;cancelled<=0;
  if(reset) begin
   state<=IDLE;configured<=0;prior_valid<=0;prior_bank<=0;current_bank<=1;
   abort_pending<=0;bus.request<=0;bus.write<=0;bus.wmask<=0;
   bus.address<=0;bus.wdata<=0;base<=0;position<=0;byte_latch<=0;out_byte<=0;
   prior_length<=0;current_length<=0;prior_metadata<=0;current_metadata<=0;
   prior_epoch<=0;current_epoch<=0;current_eligible<=0;prior_eligible<=0;equal_bytes<=0;
  end else begin
   if(cancel) begin abort_pending<=1;prior_valid<=0;configured<=0;end
   if((configure||start)&&state!=IDLE)error<=1;
   if((cancel||abort_pending)&&state!=DRAIN&&state!=CANCEL_DONE) begin
    if(bus.request&&!bus.ack)state<=DRAIN;
    else begin bus.request<=0;state<=CANCEL_DONE;end
   end else case(state)
    IDLE: if(configure) begin
     prior_valid<=0;base<=buffer_base;
     configured<=buffer_base[0]==0 && arena_begin<=buffer_base &&
      arena_begin<arena_end && arena_end<=27'h4000000 && banks_end<={1'b0,arena_end};
     error<=!(buffer_base[0]==0 && arena_begin<=buffer_base &&
      arena_begin<arena_end && arena_end<=27'h4000000 && banks_end<={1'b0,arena_end});
    end else if(start) begin
     if(!configured||length==0||length>16'd25747)begin error<=1;prior_valid<=0;end
     else begin
      current_bank<=!prior_bank;current_length<=length;position<=0;
      current_metadata<=metadata;current_epoch<=epoch;current_eligible<=disposal<=1;
      equal_bytes<=prior_valid&&prior_eligible&&disposal<=1&&prior_length==length&&
       prior_metadata==metadata&&prior_epoch==epoch;
      state<=INPUT_BYTE;
     end
    end
    INPUT_BYTE: if(in_valid)begin
     byte_latch<=in_byte;bus.address<={current_address[26:1],1'b0};
     bus.wdata<=position[0]?{8'b0,in_byte}:{in_byte,8'b0};
     bus.wmask<=position[0]?2'b01:2'b10;bus.write<=1;bus.request<=1;state<=WRITE_WAIT;
    end
    WRITE_WAIT: if(bus.ack)begin bus.request<=0;state<=WRITE_GAP;end
    WRITE_GAP: if(!bus.ack)begin
     if(equal_bytes)begin
      bus.address<={prior_address[26:1],1'b0};bus.write<=0;bus.wmask<=2'b11;
      bus.request<=1;state<=COMPARE_WAIT;
     end else state<=NEXT_BYTE;
    end
    COMPARE_WAIT: if(bus.ack)begin
     if((position[0]?bus.rdata[7:0]:bus.rdata[15:8])!=byte_latch)equal_bytes<=0;
     bus.request<=0;state<=NEXT_BYTE;
    end
    NEXT_BYTE: if(!bus.ack)begin
     if(position+16'd1==current_length)state<=RESULT;
     else begin position<=position+16'd1;state<=INPUT_BYTE;end
    end
    RESULT: begin
     if(equal_bytes&&commit_valid)begin
      prior_valid<=commit_success;prior_bank<=current_bank;prior_length<=current_length;
      prior_metadata<=current_metadata;prior_epoch<=current_epoch;prior_eligible<=current_eligible;
      state<=IDLE;
     end else if(!equal_bytes&&replay_start)begin position<=0;state<=REPLAY_READ;end
    end
    REPLAY_READ: if(!bus.ack)begin
     bus.address<={current_address[26:1],1'b0};bus.write<=0;bus.wmask<=2'b11;
     bus.request<=1;state<=REPLAY_WAIT;
    end
    REPLAY_WAIT: if(bus.ack)begin
     out_byte<=position[0]?bus.rdata[7:0]:bus.rdata[15:8];bus.request<=0;state<=REPLAY_OUTPUT;
    end
    REPLAY_OUTPUT: if(out_ready)begin
     if(position+16'd1==current_length)state<=COMMIT;
     else begin position<=position+16'd1;state<=REPLAY_READ;end
    end
    COMMIT: if(commit_valid)begin
     prior_valid<=commit_success;prior_bank<=current_bank;prior_length<=current_length;
     prior_metadata<=current_metadata;prior_epoch<=current_epoch;prior_eligible<=current_eligible;
     state<=IDLE;
    end
    DRAIN: if(bus.ack)begin bus.request<=0;state<=CANCEL_DONE;end
    CANCEL_DONE: if(!bus.ack)begin abort_pending<=0;cancelled<=1;state<=IDLE;end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
