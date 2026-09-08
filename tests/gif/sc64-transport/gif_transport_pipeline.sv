/* Simulation integration of the original-GIF LZW core and external-canvas
   compositor. Framing, global palette and the memory owner remain explicit
   host responsibilities; this is not an SC64 top-level bitstream. */
module gif_transport_pipeline (
    input logic clk, reset, session_start, frame_start, emit_packet,
    input logic packet_ack, cancel, bypass_lzw,
    input logic [31:0] generation, initial_reference, frame_id,
    input logic [31:0] ack_generation, ack_frame,
    input logic [15:0] frame_width, frame_height, frame_left, frame_top,
    input logic [2:0] disposal,
    input logic interlaced, local_palette, transparent,
    input logic [7:0] transparent_index, background_index,
    input logic [3:0] minimum,
    input logic in_valid, in_end,
    output logic in_ready,
    input logic [7:0] in_byte,
    output logic out_valid, out_last,
    input logic out_ready,
    output logic [7:0] out_byte,
    output logic mem_valid, mem_write,
    output logic [16:0] mem_address,
    output logic [7:0] mem_wdata,
    output logic mem_ack, mem_error,
    output logic [7:0] mem_rdata,
    output logic busy, initialized, frame_done, packet_done, cancelled, error,
    output logic dict_valid, dict_write,
    output logic [11:0] dict_key,
    output logic [19:0] dict_wdata,
    output logic dict_ack, dict_error,
    output logic [19:0] dict_rdata,
    input logic [26:0] source_length,
    input logic verify_start, verify_ready,
    output logic verify_valid,
    output logic [7:0] verify_byte,
    output logic source_busy, output_busy, stream_output_ready,
    output logic [26:0] source_consumed, output_length,
    input logic configure, pi_active,
    output logic configured, config_error,
    input logic chip_drive,
    input logic [15:0] chip_data,
    output logic [15:0] chip_dq,
    output logic [3:0] chip_command,
    output logic [1:0] chip_bank, chip_mask,
    output logic [12:0] chip_address,
    output logic arb_request, arb_ack, cfg_request,
    output logic [26:0] arb_address,
    input logic n64_request, n64_write,
    input logic [26:0] n64_address,
    input logic [15:0] n64_wdata,
    output logic n64_ack,
    output logic [15:0] n64_rdata,
    input logic usb_request, usb_write,
    input logic [26:0] usb_address,
    input logic [15:0] usb_wdata,
    output logic usb_ack,
    output logic [15:0] usb_rdata,
    input logic sd_request, sd_write,
    input logic [26:0] sd_address,
    input logic [15:0] sd_wdata,
    output logic sd_ack,
    output logic [15:0] sd_rdata,
    output logic decode_busy, decode_done, decode_error
);
    logic input_valid, input_end;
    logic [7:0] input_byte;
    logic output_ready;
    logic compressed_ready, pixel_valid, pixel_ready, compose_ready, compose_error;
    logic [7:0] pixel_byte;
    gif_lzw_cached decoder (
        .clk(clk), .reset(reset), .start(frame_start && !bypass_lzw), .cancel(cancel),
        .minimum(minimum), .output_limit(32'd76800),
        .in_valid(input_valid && !bypass_lzw), .in_end(input_end),
        .in_ready(compressed_ready), .in_byte(input_byte),
        .out_valid(pixel_valid), .out_ready(pixel_ready), .out_byte(pixel_byte),
        .busy(decode_busy), .done(decode_done), .error(decode_error),
        .memory_valid(dict_valid), .memory_write(dict_write), .memory_key(dict_key),
        .memory_wdata(dict_wdata), .memory_ack(dict_ack), .memory_error(dict_error),
        .memory_rdata(dict_rdata)
    );
    assign in_ready = bypass_lzw ? compose_ready : compressed_ready;
    assign pixel_ready = compose_ready && !bypass_lzw;
    assign error = compose_error || (!bypass_lzw && decode_error);
    gif_ci8_compose compositor (
        .clk(clk), .reset(reset), .session_start(session_start), .frame_start(frame_start),
        .emit_packet(emit_packet), .packet_ack(packet_ack),
        .cancel(cancel || (!bypass_lzw && decode_done && decode_error)),
        .generation(generation), .initial_reference(initial_reference), .frame_id(frame_id),
        .ack_generation(ack_generation), .ack_frame(ack_frame),
        .frame_width(frame_width), .frame_height(frame_height), .frame_left(frame_left),
        .frame_top(frame_top), .disposal(disposal), .interlaced(interlaced),
        .local_palette(local_palette), .transparent(transparent),
        .transparent_index(transparent_index), .background_index(background_index),
        .in_valid(bypass_lzw ? in_valid : pixel_valid), .in_ready(compose_ready),
        .in_byte(bypass_lzw ? in_byte : pixel_byte),
        .out_valid(out_valid), .out_last(out_last), .out_ready(output_ready), .out_byte(out_byte),
        .mem_valid(mem_valid), .mem_write(mem_write), .mem_address(mem_address),
        .mem_wdata(mem_wdata), .mem_ack(mem_ack), .mem_error(mem_error), .mem_rdata(mem_rdata),
        .busy(busy), .initialized(initialized), .frame_done(frame_done),
        .packet_done(packet_done), .cancelled(cancelled), .error(compose_error)
    );
    mem_bus scratch_bus(), source_bus(), output_bus();
    mem_bus n64_bus(), cfg_bus(), usb_bus(), sd_bus(), sdram_bus(), flash_bus(), bram_bus();
    n64_scb scb();
    assign scb.pi_sdram_active=pi_active;
    assign scb.pi_flash_active=1'b0;
    assign flash_bus.ack=1'b0;
    assign flash_bus.rdata=16'd0;
    assign bram_bus.ack=1'b0;
    assign bram_bus.rdata=16'd0;
    assign cfg_request=cfg_bus.request;
    assign arb_request=sdram_bus.request;
    assign arb_ack=sdram_bus.ack;
    assign arb_address=sdram_bus.address;
    assign n64_bus.request=n64_request;
    assign n64_bus.write=n64_write;
    assign n64_bus.address=n64_address;
    assign n64_bus.wdata=n64_wdata;
    assign n64_bus.wmask=2'b11;
    assign n64_ack=n64_bus.ack;
    assign n64_rdata=n64_bus.rdata;
    assign usb_bus.request=usb_request;
    assign usb_bus.write=usb_write;
    assign usb_bus.address=usb_address;
    assign usb_bus.wdata=usb_wdata;
    assign usb_bus.wmask=2'b11;
    assign usb_ack=usb_bus.ack;
    assign usb_rdata=usb_bus.rdata;
    assign sd_bus.request=sd_request;
    assign sd_bus.write=sd_write;
    assign sd_bus.address=sd_address;
    assign sd_bus.wdata=sd_wdata;
    assign sd_bus.wmask=2'b11;
    assign sd_ack=sd_bus.ack;
    assign sd_rdata=sd_bus.rdata;
    gif_sc64_bus adapter (
        .clk(clk),.reset(reset),.configure(configure),.cancel(cancel),
        .arena_begin(27'd0),.arena_end(27'h30000),
        .dictionary_base(27'd0),.canvas_base(27'h10000),
        .configured(configured),.config_error(config_error),.busy(),.cancelled(),
        .dict_valid(dict_valid),.dict_write(dict_write),.dict_key(dict_key),
        .dict_wdata(dict_wdata),.dict_ack(dict_ack),.dict_error(dict_error),.dict_rdata(dict_rdata),
        .canvas_valid(mem_valid),.canvas_write(mem_write),.canvas_address(mem_address),
        .canvas_wdata(mem_wdata),.canvas_ack(mem_ack),.canvas_error(mem_error),.canvas_rdata(mem_rdata),
        .bus(scratch_bus)
    );
    memory_arbiter arbiter (.clk(clk),.reset(reset),.n64_scb(scb),
        .n64_bus(n64_bus),.cfg_bus(cfg_bus),.usb_dma_bus(usb_bus),.sd_dma_bus(sd_bus),
        .sdram_mem_bus(sdram_bus),.flash_mem_bus(flash_bus),.bram_mem_bus(bram_bus));
    wire [15:0] dq;
    assign dq=chip_drive?chip_data:16'hzzzz;
    assign chip_dq=dq;
    memory_sdram controller (.clk(clk),.reset(reset),.mem_bus(sdram_bus),
        .sdram_cs(chip_command[3]),.sdram_ras(chip_command[2]),
        .sdram_cas(chip_command[1]),.sdram_we(chip_command[0]),
        .sdram_ba(chip_bank),.sdram_a(chip_address),.sdram_dqm(chip_mask),.sdram_dq(dq));
    dma_scb source_control(), output_control();
    fifo_bus source_stream(), output_stream();
    logic verification, output_start;
    logic [7:0] source_fifo[0:63], output_fifo[0:63];
    logic [5:0] source_head, source_tail, output_head, output_tail;
    logic [6:0] source_count, output_count;
    logic [26:0] source_limit, emitted;
    logic [31:0] header_payload;
    wire source_push=source_stream.tx_write;
    wire source_pop=(verification?verify_ready:compressed_ready)&&source_count!=0;
    wire output_push=out_valid&&output_ready;
    wire output_pop=output_stream.rx_read;
    assign source_control.start=frame_start||verify_start;
    assign source_control.stop=cancel;
    assign source_control.direction=1'b0;
    assign source_control.byte_swap=1'b0;
    assign source_control.starting_address=verification?27'h40000:27'h30000;
    assign source_control.transfer_length=source_limit;
    assign source_busy=source_control.busy;
    assign source_stream.rx_empty=1'b1;
    assign source_stream.rx_rdata=8'd0;
    assign source_stream.tx_full=source_count>=7'd60;
    assign input_valid=!verification&&source_count!=0;
    assign input_byte=source_fifo[source_head];
    assign input_end=source_consumed==source_limit;
    assign verify_valid=verification&&source_count!=0;
    assign verify_byte=source_fifo[source_head];
    assign output_ready=output_count<7'd60;
    assign stream_output_ready=output_ready;
    assign output_control.start=output_start;
    assign output_control.stop=cancel;
    assign output_control.direction=1'b1;
    assign output_control.byte_swap=1'b0;
    assign output_control.starting_address=27'h40000;
    assign output_control.transfer_length=output_length;
    assign output_busy=output_control.busy||output_count!=0||output_bus.request;
    assign output_stream.rx_empty=output_count==0;
    assign output_stream.tx_full=1'b0;
    memory_dma source_dma (.clk(clk),.reset(reset),.dma_scb(source_control),
        .fifo_bus(source_stream),.mem_bus(source_bus));
    memory_dma output_dma (.clk(clk),.reset(reset),.dma_scb(output_control),
        .fifo_bus(output_stream),.mem_bus(output_bus));
    always_ff @(posedge clk) begin
        output_start<=1'b0;
        if(reset) begin
            source_count<=0;source_head<=0;source_tail<=0;source_consumed<=0;
            source_limit<=0;verification<=0;output_count<=0;output_head<=0;
            output_tail<=0;emitted<=0;output_length<=0;header_payload<=0;
            output_stream.rx_rdata<=0;
        end else begin
            if(source_count>64||output_count>64)$fatal(1,"transport FIFO count out of bounds");
            if(source_push&&source_count==64&&!source_pop)$fatal(1,"source FIFO overflow");
            if(output_pop&&output_count==0)$fatal(1,"output FIFO underflow");
            if((frame_start||verify_start)&&(source_control.busy||source_count!=0))$fatal(1,"source reused before retirement");
            if(emit_packet&&output_busy)$fatal(1,"output reused before retirement");
            if(frame_start||verify_start) begin
                source_count<=0;source_head<=0;source_tail<=0;source_consumed<=0;
                verification<=verify_start;
                source_limit<=verify_start?output_length:source_length;
            end else begin
                case({source_push,source_pop})
                    2'b10:source_count<=source_count+1'b1;
                    2'b01:source_count<=source_count-1'b1;
                    default:begin end
                endcase
                if(source_push) begin
                    source_fifo[source_tail]<=source_stream.tx_wdata;source_tail<=source_tail+1'b1;
                end
                if(source_pop) begin source_head<=source_head+1'b1;source_consumed<=source_consumed+1'b1;end
            end
            if(emit_packet) begin
                output_count<=0;output_head<=0;output_tail<=0;emitted<=0;header_payload<=0;
            end else begin
                case({output_push,output_pop})
                    2'b10:output_count<=output_count+1'b1;
                    2'b01:output_count<=output_count-1'b1;
                    default:begin end
                endcase
                if(output_push) begin
                    output_fifo[output_tail]<=out_byte;output_tail<=output_tail+1'b1;
                    emitted<=emitted+1'b1;
                    if(emitted>=28&&emitted<=31)header_payload<={header_payload[23:0],out_byte};
                    if(emitted==31) begin
                        if({header_payload[23:0],out_byte}>32'd76800||out_byte[5:0]!=0)
                            $fatal(1,"GPD1 payload outside bounded output window");
                        output_length<=27'd192+{header_payload[18:0],out_byte};output_start<=1'b1;
                    end
                end
                if(output_pop) begin output_stream.rx_rdata<=output_fifo[output_head];output_head<=output_head+1'b1;end
            end
        end
    end
    gif_transport_mux mux (.clk(clk),.reset(reset),.scratch(scratch_bus),
        .source(source_bus),.packet(output_bus),.memory(cfg_bus));
endmodule
