/* Experimental 512-entry write-allocate GIF dictionary cache. External owner
   stores 4096 twenty-bit entries in bounded 32-bit slots. Cancel drains an
   accepted memory request and clears cache tags before reporting completion. */
module cached_dictionary (
    input logic clk, reset, clear, cancel,
    input logic request_valid, request_write,
    output logic request_ready,
    input logic [11:0] request_key,
    input logic [19:0] request_data,
    output logic response_valid, response_error,
    input logic response_ready,
    output logic [19:0] response_data,
    output logic memory_valid, memory_write,
    output logic [11:0] memory_key,
    output logic [19:0] memory_wdata,
    input logic memory_ack, memory_error,
    input logic [19:0] memory_rdata,
    output logic cancelled
);
    typedef enum logic [2:0] { CLEAR, IDLE, LOOKUP, MEMORY, RESPONSE } state_t;
    state_t state;
    logic [23:0] entries [0:511];
    logic [23:0] entry;
    logic [8:0] clear_index;
    logic [11:0] key;
    logic [19:0] data;
    logic write_request, cancel_pending;
    assign request_ready = state == IDLE && !clear && !cancel;
    assign response_valid = state == RESPONSE;
    assign memory_valid = state == MEMORY;
    assign memory_write = write_request;
    assign memory_key = key;
    assign memory_wdata = data;
    always_ff @(posedge clk) begin
        if (state == IDLE && request_valid && request_ready)
            entry <= entries[request_key[8:0]];
    end
    always_ff @(posedge clk) begin
        cancelled <= 0;
        if (reset) begin
            state <= CLEAR; clear_index <= 0; cancel_pending <= 0;
            response_error <= 0;
        end else if ((cancel || cancel_pending) && state != CLEAR) begin
            cancel_pending <= 1;
            if (state != MEMORY || memory_ack) begin
                state <= CLEAR; clear_index <= 0;
            end
        end else case (state)
            CLEAR: begin
                entries[clear_index] <= 0;
                if (cancel) cancel_pending <= 1;
                if (clear_index == 511) begin
                    state <= IDLE; cancelled <= cancel_pending || cancel;
                    cancel_pending <= 0;
                end else clear_index <= clear_index+1;
            end
            IDLE: begin
                if (clear) begin state <= CLEAR; clear_index <= 0; end
                else if (request_valid) begin
                    key <= request_key; data <= request_data;
                    write_request <= request_write; response_error <= 0;
                    state <= LOOKUP;
                end
            end
            LOOKUP: begin
                if (!write_request && entry[23] && entry[22:20] == key[11:9]) begin
                    response_data <= entry[19:0]; state <= RESPONSE;
                end else state <= MEMORY;
            end
            MEMORY: if (memory_ack) begin
                response_error <= memory_error;
                response_data <= memory_rdata;
                entries[key[8:0]] <= memory_error ? 24'd0 :
                    {1'b1,key[11:9],write_request ? data : memory_rdata};
                state <= RESPONSE;
            end
            RESPONSE: if (response_ready) state <= IDLE;
            default: state <= CLEAR;
        endcase
    end
endmodule
