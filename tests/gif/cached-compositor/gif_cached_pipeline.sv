/* Simulation integration of the original-GIF LZW core and external-canvas
   compositor. Framing, global palette and the memory owner remain explicit
   host responsibilities; this is not an SC64 top-level bitstream. */
module gif_cached_pipeline (
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
    input logic mem_ack, mem_error,
    input logic [7:0] mem_rdata,
    output logic busy, initialized, frame_done, packet_done, cancelled, error,
    output logic dict_valid, dict_write,
    output logic [11:0] dict_key,
    output logic [19:0] dict_wdata,
    input logic dict_ack, dict_error,
    input logic [19:0] dict_rdata,
    output logic decode_busy, decode_done, decode_error
);
    logic compressed_ready, pixel_valid, pixel_ready, compose_ready, compose_error;
    logic [7:0] pixel_byte;
    gif_lzw_cached decoder (
        .clk(clk), .reset(reset), .start(frame_start && !bypass_lzw), .cancel(cancel),
        .minimum(minimum), .output_limit(32'd76800),
        .in_valid(in_valid && !bypass_lzw), .in_end(in_end),
        .in_ready(compressed_ready), .in_byte(in_byte),
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
        .out_valid(out_valid), .out_last(out_last), .out_ready(out_ready), .out_byte(out_byte),
        .mem_valid(mem_valid), .mem_write(mem_write), .mem_address(mem_address),
        .mem_wdata(mem_wdata), .mem_ack(mem_ack), .mem_error(mem_error), .mem_rdata(mem_rdata),
        .busy(busy), .initialized(initialized), .frame_done(frame_done),
        .packet_done(packet_done), .cancelled(cancelled), .error(compose_error)
    );
endmodule
