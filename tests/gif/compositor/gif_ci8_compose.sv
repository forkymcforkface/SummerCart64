/* Original-GIF CI8 composition research pilot. The 320x240 canvas belongs
   to an external byte-addressed memory owner; only the 1200-bit dirty map is
   local. Full-canvas global-palette retain frames are supported. GPD1 output
   is immutable until acknowledged; cancellation drains a pending memory
   transaction before releasing the session. */
module gif_ci8_compose (
    input logic clk, reset,
    input logic session_start, frame_start, emit_packet, packet_ack, cancel,
    input logic [31:0] generation, initial_reference, frame_id,
    input logic [31:0] ack_generation, ack_frame,
    input logic [15:0] frame_width, frame_height, frame_left, frame_top,
    input logic [2:0] disposal,
    input logic interlaced, local_palette, transparent,
    input logic [7:0] transparent_index, background_index,
    input logic in_valid,
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
    output logic busy, initialized, frame_done, packet_done, cancelled, error
);
    typedef enum logic [4:0] {
        IDLE, CLEAR, INPUT_PIXEL, READ_PIXEL, WRITE_PIXEL,
        HEADER, SELECT_TILE, READ_TILE, SEND_TILE, WAIT_ACK,
        CLEAR_DIRTY, MARK_READ, MARK_WRITE, MASK_READ, MASK_SEND, TEST_TILE
    } state_t;
    state_t state;
    logic [7:0] dirty [0:149];
    logic [7:0] dirty_address, dirty_data, dirty_wdata, dirty_clear_position;
    logic dirty_write, dirty_initialize;
    logic [10:0] dirty_count, tile, tiles_left;
    logic [16:0] position;
    logic [8:0] x;
    logic [7:0] y, pixel, clear_index, trans_index, header_pos, tile_byte;
    logic [5:0] tile_pixel;
    logic [5:0] tile_x;
    logic [4:0] tile_y;
    logic use_transparency, cancel_pending;
    logic [31:0] session_generation, reference_frame, current_frame, header_word;
    wire [10:0] pixel_tile = 11'(y >> 3) * 11'd40 + 11'(x >> 3);
    wire memory_state = state == CLEAR || state == READ_PIXEL ||
                        state == WRITE_PIXEL || state == READ_TILE;
    assign busy = state != IDLE;
    assign in_ready = state == INPUT_PIXEL && !cancel && !cancel_pending;
    assign mem_valid = memory_state;
    assign mem_write = state == CLEAR || state == WRITE_PIXEL;
    assign mem_address = state == READ_TILE ?
        17'(tile_y) * 17'd2560 + (17'(tile_x) << 3) +
        17'(tile_pixel[5:3]) * 17'd320 + 17'(tile_pixel[2:0]) : position;
    assign mem_wdata = state == CLEAR ? clear_index : pixel;
    assign out_valid = state == HEADER || state == MASK_SEND || state == SEND_TILE;
    assign out_last = (state == HEADER && header_pos == 191 && dirty_count == 0) ||
                      (state == SEND_TILE && tile_pixel == 63 && tiles_left == 1);
    always_comb begin
        case (header_pos[4:2])
            0: header_word = 32'h47504431;
            1: header_word = session_generation;
            2: header_word = current_frame;
            3: header_word = reference_frame;
            4: header_word = 32'h014000f0;
            5: header_word = 1;
            6: header_word = {21'd0, dirty_count};
            default: header_word = {15'd0, dirty_count, 6'd0};
        endcase
        out_byte = 0;
        if (state == SEND_TILE) out_byte = tile_byte;
        else if (header_pos < 32)
            out_byte = 8'(header_word >> ((3 - int'(header_pos[1:0])) * 8));
        else if (state == MASK_SEND) out_byte = dirty_data;
    end
    always_comb begin
        dirty_address = 0; dirty_wdata = 0; dirty_write = 0;
        if (state == CLEAR_DIRTY) begin
            dirty_address = dirty_clear_position;
            dirty_wdata = dirty_initialize ? 8'hff : 8'h00;
            dirty_write = !reset && !cancel && !cancel_pending;
        end else if (state == MARK_READ || state == MARK_WRITE) begin
            dirty_address = pixel_tile[10:3];
            dirty_wdata = dirty_data | (8'd1 << pixel_tile[2:0]);
            dirty_write = state == MARK_WRITE && !reset && !cancel && !cancel_pending;
        end else if (state == MASK_READ || state == MASK_SEND)
            dirty_address = header_pos - 8'd32;
        else if ((state == SELECT_TILE || state == TEST_TILE) && tile < 1200)
            dirty_address = tile[10:3];
    end
    always_ff @(posedge clk) begin
        if (dirty_write) dirty[dirty_address] <= dirty_wdata;
        dirty_data <= dirty[dirty_address];
    end
    task automatic advance_tile;
        tile <= tile + 1;
        if (tile_x == 39) begin tile_x <= 0; tile_y <= tile_y + 1; end
        else tile_x <= tile_x + 1;
    endtask
    task automatic advance_pixel;
        if (position == 76799) begin
            state <= IDLE;
            frame_done <= 1;
        end else begin
            position <= position + 1;
            if (x == 319) begin x <= 0; y <= y + 1; end
            else x <= x + 1;
            state <= INPUT_PIXEL;
        end
    endtask
    always_ff @(posedge clk) begin
        frame_done <= 0; packet_done <= 0; cancelled <= 0;
        if (reset) begin
            state <= IDLE; initialized <= 0; error <= 0;
            cancel_pending <= 0; dirty_count <= 0;
            dirty_clear_position <= 0; dirty_initialize <= 0;
            position <= 0; x <= 0; y <= 0; pixel <= 0;
            tile <= 0; tile_pixel <= 0; tile_byte <= 0; tile_x <= 0; tile_y <= 0;
            header_pos <= 0; tiles_left <= 0;
            session_generation <= 0; reference_frame <= 0; current_frame <= 0;
            clear_index <= 0; trans_index <= 0; use_transparency <= 0;
        end else if ((cancel || cancel_pending) && (!memory_state || mem_ack)) begin
            state <= IDLE; initialized <= 0; cancel_pending <= 0;
            dirty_count <= 0; cancelled <= 1;
        end else if (cancel || cancel_pending) begin
            cancel_pending <= 1;
        end else if (memory_state && mem_ack && mem_error) begin
            state <= IDLE; initialized <= 0; error <= 1;
        end else begin
            case (state)
                IDLE: begin
                    if (session_start) begin
                        session_generation <= generation;
                        reference_frame <= initial_reference;
                        current_frame <= initial_reference;
                        clear_index <= background_index;
                        dirty_count <= 1200;
                        dirty_clear_position <= 0; dirty_initialize <= 1;
                        position <= 0; initialized <= 0; error <= 0;
                        state <= CLEAR_DIRTY;
                    end else if (frame_start) begin
                        error <= 0;
                        if (!initialized || frame_width != 320 || frame_height != 240 ||
                            frame_left != 0 || frame_top != 0 || disposal > 1 ||
                            interlaced || local_palette) begin
                            error <= 1; frame_done <= 1;
                        end else begin
                            current_frame <= frame_id;
                            use_transparency <= transparent; trans_index <= transparent_index;
                            position <= 0; x <= 0; y <= 0; state <= INPUT_PIXEL;
                        end
                    end else if (emit_packet && initialized) begin
                        header_pos <= 0; tile <= 0; tile_pixel <= 0; tile_x <= 0; tile_y <= 0;
                        tiles_left <= dirty_count; state <= HEADER;
                    end
                end
                CLEAR: if (mem_ack) begin
                    if (position == 76799) begin state <= IDLE; initialized <= 1; end
                    else position <= position + 1;
                end
                CLEAR_DIRTY: begin
                    if (dirty_clear_position == 149)
                        state <= dirty_initialize ? CLEAR : IDLE;
                    else dirty_clear_position <= dirty_clear_position + 1;
                end
                INPUT_PIXEL: if (in_valid) begin
                    pixel <= in_byte;
                    if (use_transparency && in_byte == trans_index) advance_pixel();
                    else state <= READ_PIXEL;
                end
                READ_PIXEL: if (mem_ack) begin
                    if (mem_rdata == pixel) advance_pixel();
                    else state <= WRITE_PIXEL;
                end
                WRITE_PIXEL: if (mem_ack) begin
                    state <= MARK_READ;
                end
                MARK_READ: state <= MARK_WRITE;
                MARK_WRITE: begin
                    if (!dirty_data[pixel_tile[2:0]]) begin
                        dirty_count <= dirty_count + 1;
                    end
                    advance_pixel();
                end
                HEADER: if (out_ready) begin
                    if (header_pos == 191) begin
                        if (dirty_count == 0) begin state <= WAIT_ACK; packet_done <= 1; end
                        else state <= SELECT_TILE;
                    end else begin
                        header_pos <= header_pos + 1;
                        if (header_pos == 31) state <= MASK_READ;
                    end
                end
                MASK_READ: state <= MASK_SEND;
                MASK_SEND: if (out_ready) begin
                    header_pos <= header_pos + 1;
                    state <= header_pos == 181 ? HEADER : MASK_READ;
                end
                SELECT_TILE: begin
                    if (tile >= 1200) begin state <= IDLE; initialized <= 0; error <= 1; end
                    else state <= TEST_TILE;
                end
                TEST_TILE: begin
                    if (dirty_data[tile[2:0]]) begin tile_pixel <= 0; state <= READ_TILE; end
                    else begin advance_tile(); state <= SELECT_TILE; end
                end
                READ_TILE: if (mem_ack) begin tile_byte <= mem_rdata; state <= SEND_TILE; end
                SEND_TILE: if (out_ready) begin
                    if (tile_pixel == 63) begin
                        if (tiles_left == 1) begin state <= WAIT_ACK; packet_done <= 1; end
                        else begin tiles_left <= tiles_left - 1; advance_tile(); state <= SELECT_TILE; end
                    end else begin tile_pixel <= tile_pixel + 1; state <= READ_TILE; end
                end
                WAIT_ACK: if (packet_ack) begin
                    if (ack_generation == session_generation && ack_frame == current_frame) begin
                        dirty_count <= 0; dirty_clear_position <= 0; dirty_initialize <= 0;
                        reference_frame <= current_frame; state <= CLEAR_DIRTY;
                    end else error <= 1;
                end
                default: begin state <= IDLE; initialized <= 0; error <= 1; end
            endcase
        end
    end
endmodule
