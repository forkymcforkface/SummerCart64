/* Bounded research GIF LZW decoder. Owns dictionary and reverse phrase stack;
   ready/valid stalls preserve output, cancel discards all in-flight state.
   No cart memory or production protocol connection exists in this pilot. */
module gif_lzw (
    input logic clk, reset, start, cancel,
    input logic [3:0] minimum,
    input logic [31:0] output_limit,
    input logic in_valid, in_end,
    output logic in_ready,
    input logic [7:0] in_byte,
    output logic out_valid,
    input logic out_ready,
    output logic [7:0] out_byte,
    output logic busy, done, error
);
    typedef enum logic [3:0] { IDLE, CODE, WALK, PUSH, DICT, EMIT } state_t;
    state_t state;
    logic [11:0] prefix [0:4095];
    logic [7:0] suffix [0:4095];
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
    always_ff @(posedge clk) begin
        done <= 0;
        if (reset || cancel) begin
            state <= IDLE; error <= 0;
        end else if (start && state == IDLE) begin
            error <= minimum < 2 || minimum > 8;
            state <= minimum < 2 || minimum > 8 ? IDLE : CODE;
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
                        have_previous <= 0;
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
                    fetched_prefix <= prefix[walk_code];
                    fetched_suffix <= suffix[walk_code]; state <= PUSH;
                end
            end
            PUSH: begin
                stack[stack_size[11:0]] <= fetched_suffix;
                stack_size <= stack_size+1; walk_code <= fetched_prefix;
                state <= WALK;
            end
            DICT: begin
                if (have_previous && next_code < 4096) begin
                    prefix[next_code[11:0]] <= previous; suffix[next_code[11:0]] <= first;
                    next_code <= next_code+1;
                    if (next_code+1 == (13'd1 << width) && width < 12)
                        width <= width+1;
                end
                previous <= current; previous_first <= first;
                have_previous <= 1;
                if (32'(stack_size) > limit-emitted) begin
                    error <= 1; done <= 1; state <= IDLE;
                end else state <= EMIT;
            end
            EMIT: if (out_ready) begin
                emitted <= emitted+1; stack_size <= stack_size-1;
                if (stack_size == 1) state <= CODE;
            end
            default: state <= IDLE;
        endcase
    end
endmodule
