/* Experimental scratch-memory adapter. One upstream operation owns mem_bus
 * until completion. Cancellation drains an issued beat; scratch writes are
 * not atomic. Reset requires the downstream bus owner to reset together. */
module gif_sc64_bus (
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
    mem_bus.controller bus
);
    typedef enum logic [2:0] { IDLE, FIRST, GAP, SECOND, RESPONSE,
                               CANCEL_RESPONSE } state_t;
    state_t state;
    logic [26:0] dict_base, ci8_base;
    logic source_dict, prefer_canvas, odd_byte, abort_pending;
    logic [3:0] high_data;
    wire [27:0] dict_end = {1'b0, dictionary_base} + 28'd16384;
    wire [27:0] ci8_end = {1'b0, canvas_base} + 28'd76800;
    wire valid_config = arena_begin < arena_end && arena_end <= 27'h4000000 &&
        dictionary_base[1:0] == 0 && canvas_base[0] == 0 &&
        dictionary_base >= arena_begin && canvas_base >= arena_begin &&
        dict_end <= {1'b0, arena_end} && ci8_end <= {1'b0, arena_end} &&
        (dict_end <= {1'b0, canvas_base} || ci8_end <= {1'b0, dictionary_base});
    wire choose_dict = dict_valid && (!canvas_valid || !prefer_canvas);
    assign busy = state != IDLE;

    always_ff @(posedge clk) begin
        dict_ack <= 0;
        canvas_ack <= 0;
        dict_error <= 0;
        canvas_error <= 0;
        config_error <= 0;
        cancelled <= 0;
        if (reset) begin
            state <= IDLE;
            configured <= 0;
            bus.request <= 0;
            bus.write <= 0;
            bus.wmask <= 0;
            bus.address <= 0;
            bus.wdata <= 0;
            dict_rdata <= 0;
            canvas_rdata <= 0;
            dict_base <= 0;
            ci8_base <= 0;
            source_dict <= 0;
            prefer_canvas <= 0;
            odd_byte <= 0;
            abort_pending <= 0;
            high_data <= 0;
        end else begin
            if (configure && state != IDLE) config_error <= 1;
            if (cancel) begin
                abort_pending <= 1;
                configured <= 0;
            end
            case (state)
                IDLE: begin
                    if (cancel || abort_pending) state <= CANCEL_RESPONSE;
                    else if (configure) begin
                        configured <= valid_config;
                        config_error <= !valid_config;
                        dict_base <= dictionary_base;
                        ci8_base <= canvas_base;
                    end else if ((dict_valid || canvas_valid) && !bus.ack) begin
                        source_dict <= choose_dict;
                        prefer_canvas <= choose_dict;
                        if (!configured || (!choose_dict && canvas_address >= 17'd76800)) begin
                            dict_ack <= choose_dict;
                            dict_error <= choose_dict;
                            canvas_ack <= !choose_dict;
                            canvas_error <= !choose_dict;
                            state <= RESPONSE;
                        end else begin
                            bus.request <= 1;
                            state <= FIRST;
                            if (choose_dict) begin
                                bus.address <= dict_base + {13'b0, dict_key, 2'b0};
                                bus.write <= dict_write;
                                bus.wmask <= 2'b11;
                                bus.wdata <= dict_wdata[15:0];
                                high_data <= dict_wdata[19:16];
                            end else begin
                                bus.address <= ci8_base + {10'b0, canvas_address[16:1], 1'b0};
                                bus.write <= canvas_write;
                                bus.wmask <= canvas_address[0] ? 2'b01 : 2'b10;
                                bus.wdata <= canvas_address[0] ? {8'b0, canvas_wdata} : {canvas_wdata, 8'b0};
                                odd_byte <= canvas_address[0];
                            end
                        end
                    end
                end
                FIRST: if (bus.ack) begin
                    bus.request <= 0;
                    if (abort_pending || cancel) state <= CANCEL_RESPONSE;
                    else if (source_dict) begin
                        dict_rdata[15:0] <= bus.rdata;
                        state <= GAP;
                    end else begin
                        canvas_rdata <= odd_byte ? bus.rdata[7:0] : bus.rdata[15:8];
                        canvas_ack <= 1;
                        state <= RESPONSE;
                    end
                end
                GAP: begin
                    if (abort_pending || cancel) state <= CANCEL_RESPONSE;
                    else if (!bus.ack) begin
                        bus.address <= bus.address + 27'd2;
                        bus.wdata <= {12'b0, high_data};
                        bus.request <= 1;
                        state <= SECOND;
                    end
                end
                SECOND: if (bus.ack) begin
                    bus.request <= 0;
                    if (abort_pending || cancel) state <= CANCEL_RESPONSE;
                    else begin
                        dict_rdata[19:16] <= bus.rdata[3:0];
                        dict_ack <= 1;
                        state <= RESPONSE;
                    end
                end
                RESPONSE: begin
                    if (abort_pending || cancel) state <= CANCEL_RESPONSE;
                    else if (!bus.ack) state <= IDLE;
                end
                CANCEL_RESPONSE: if (!bus.ack) begin
                    dict_ack <= dict_valid;
                    dict_error <= dict_valid;
                    canvas_ack <= canvas_valid;
                    canvas_error <= canvas_valid;
                    configured <= 0;
                    abort_pending <= 0;
                    cancelled <= 1;
                    state <= RESPONSE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
