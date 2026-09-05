/* Experimental cached-dictionary GIF LZW decoder. Only the bounded phrase
   stack is local; dictionary accesses use an external-memory cache. Cancel
   drains external memory before releasing ownership. No SC64 bus integration. */
module gif_lzw_cached (
    input logic clk, reset, start, cancel,
    input logic [3:0] minimum,
    input logic [31:0] output_limit,
    input logic in_valid, in_end,
    output logic in_ready,
    input logic [7:0] in_byte,
    output logic out_valid,
    input logic out_ready,
    output logic [7:0] out_byte,
    output logic busy, done, error,
    output logic memory_valid, memory_write,
    output logic [11:0] memory_key,
    output logic [19:0] memory_wdata,
    input logic memory_ack, memory_error,
    input logic [19:0] memory_rdata
);
    typedef enum logic [3:0] { IDLE, CODE, WALK, PUSH, DICT, EMIT, READ_REQ, READ_WAIT, WRITE_REQ, WRITE_WAIT, CLEAR_CACHE, CACHE_WAIT, CANCEL_WAIT } state_t;
    state_t state;
    logic [7:0] stack [0:4095];
    logic [23:0] reservoir;
    logic [4:0] available;
    logic [3:0] width, initial_width;
    logic [12:0] next_code, clear_code, stop_code, stack_size;
    logic [11:0] previous, current, walk_code, fetched_prefix;
    logic [7:0] first, previous_first, fetched_suffix;
    logic [7:0] stack_output;
    logic have_previous;
    logic [31:0] emitted, limit;
    wire [11:0] code = 12'(reservoir & ((24'd1 << width)-24'd1));
    assign busy = state != IDLE;
    assign in_ready = state == CODE && available < 5'(width);
    assign out_valid = state == EMIT;
    assign out_byte = stack_output;
    always_ff @(posedge clk) begin
        if (state == DICT || (state == EMIT && out_ready))
            stack_output <= stack[12'(stack_size - (state == EMIT ? 13'd2 : 13'd1))];
    end
    logic request_ready,response_valid,response_error,cache_cancelled;
    logic [19:0] response_data;
    cached_dictionary dictionary (
        .clk(clk),.reset(reset),.clear(state == CLEAR_CACHE),.cancel(cancel),
        .request_valid(state == READ_REQ || state == WRITE_REQ),
        .request_write(state == WRITE_REQ),.request_ready(request_ready),
        .request_key(state == WRITE_REQ ? next_code[11:0] : walk_code),
        .request_data({previous,first}),.response_valid(response_valid),
        .response_error(response_error),.response_ready(1'b1),.response_data(response_data),
        .memory_valid(memory_valid),.memory_write(memory_write),.memory_key(memory_key),
        .memory_wdata(memory_wdata),.memory_ack(memory_ack),.memory_error(memory_error),
        .memory_rdata(memory_rdata),.cancelled(cache_cancelled)
    );
    always_ff @(posedge clk) begin
        done <= 0;
        if (reset) begin
            state <= IDLE; error <= 0;
        end else if (cancel) begin
            state <= CANCEL_WAIT; error <= 0;
        end else if (start && state == IDLE) begin
            error <= minimum < 2 || minimum > 8;
            state <= minimum < 2 || minimum > 8 ? IDLE : CLEAR_CACHE;
            done <= minimum < 2 || minimum > 8;
            reservoir <= 0; available <= 0;
            clear_code <= 13'd1 << minimum;
            stop_code <= (13'd1 << minimum)+1;
            next_code <= (13'd1 << minimum)+2;
            width <= minimum+1; initial_width <= minimum+1;
            have_previous <= 0; emitted <= 0; limit <= output_limit;
            stack_size <= 0;
        end else case (state)
            CODE: begin
                if (available < 5'(width)) begin
                    if (in_valid) begin
                        reservoir <= reservoir | (24'(in_byte) << available);
                        available <= available+8;
                    end else if (in_end) begin
                        error <= 1; done <= 1; state <= IDLE;
                    end
                end else begin
                    reservoir <= reservoir >> width;
                    available <= available-width;
                    if (13'(code) == clear_code) begin
                        next_code <= clear_code+2; width <= initial_width;
                        have_previous <= 0; state <= CLEAR_CACHE;
                    end else if (13'(code) == stop_code) begin
                        error <= emitted != limit; done <= 1; state <= IDLE;
                    end else if (13'(code) > next_code ||
                                 (13'(code) == next_code && !have_previous)) begin
                        error <= 1; done <= 1; state <= IDLE;
                    end else begin
                        current <= code; state <= WALK;
                        if (13'(code) == next_code) begin
                            stack[0] <= previous_first; stack_size <= 1;
                            walk_code <= previous;
                        end else begin
                            stack_size <= 0; walk_code <= code;
                        end
                    end
                end
            end
            WALK: begin
                if (stack_size >= 4096) begin
                    error <= 1; done <= 1; state <= IDLE;
                end else if (13'(walk_code) < clear_code) begin
                    stack[stack_size[11:0]] <= walk_code[7:0];
                    stack_size <= stack_size+1; first <= walk_code[7:0];
                    state <= DICT;
                end else if (13'(walk_code) >= next_code ||
                             13'(walk_code) <= stop_code) begin
                    error <= 1; done <= 1; state <= IDLE;
                end else begin
                    state <= READ_REQ;
                end
            end
            PUSH: begin
                stack[stack_size[11:0]] <= fetched_suffix;
                stack_size <= stack_size+1; walk_code <= fetched_prefix;
                state <= WALK;
            end
            READ_REQ: if (request_ready) state <= READ_WAIT;
            READ_WAIT: if (response_valid) begin
                if (response_error) begin error <= 1; done <= 1; state <= IDLE; end
                else begin
                    fetched_prefix <= response_data[19:8]; fetched_suffix <= response_data[7:0];
                    state <= PUSH;
                end
            end
            DICT: begin
                if (32'(stack_size) > limit-emitted) begin
                    error <= 1; done <= 1; state <= IDLE;
                end else if (have_previous && next_code < 4096) state <= WRITE_REQ;
                else begin
                    previous <= current; previous_first <= first;
                    have_previous <= 1; state <= EMIT;
                end
            end
            WRITE_REQ: if (request_ready) state <= WRITE_WAIT;
            WRITE_WAIT: if (response_valid) begin
                if (response_error) begin error <= 1; done <= 1; state <= IDLE; end
                else begin
                    next_code <= next_code+1;
                    if (next_code+1 == (13'd1 << width) && width < 12) width <= width+1;
                    previous <= current; previous_first <= first;
                    have_previous <= 1; state <= EMIT;
                end
            end
            CLEAR_CACHE: state <= CACHE_WAIT;
            CACHE_WAIT: if (request_ready) state <= CODE;
            CANCEL_WAIT: if (cache_cancelled) state <= IDLE;
            EMIT: if (out_ready) begin
                emitted <= emitted+1; stack_size <= stack_size-1;
                if (stack_size == 1) state <= CODE;
            end
            default: state <= IDLE;
        endcase
    end
endmodule
