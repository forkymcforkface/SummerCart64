"""Generate a bounded local-stack experiment without changing baseline RTL.

The full 4096-byte phrase capacity remains available through an explicit
external byte-memory port. Local indices below512 use inferred RAM.
"""
from pathlib import Path
import sys

from run import replace


def generate(source, output):
    core = (source / 'gif_lzw_cached.sv').read_text()
    core = replace(core, 'input logic [19:0] memory_rdata', '''input logic [19:0] memory_rdata,
    output logic stack_valid, stack_write,
    output logic [11:0] stack_address,
    output logic [7:0] stack_wdata,
    input logic stack_ack, stack_error,
    input logic [7:0] stack_rdata''')
    core = replace(core, 'logic [3:0] {', 'logic [4:0] {')
    core = replace(core, 'CACHE_WAIT, CANCEL_WAIT }', 'CACHE_WAIT, CANCEL_WAIT, SPILL_PUSH, SPILL_LITERAL, SPILL_READ, SPILL_READ_WAIT, CANCEL_SPILL }')
    core = replace(core, 'stack [0:4095]', 'stack [0:511]')
    core = replace(core, 'logic [7:0] stack [', '(* ram_style = "block" *) logic [7:0] stack [')
    core = replace(core, 'logic [7:0] stack_output;', 'logic [7:0] stack_output, spill_output;')
    core = replace(core, 'assign out_byte = stack_output;', 'assign out_byte = stack_size > 512 ? spill_output : stack_output;')
    core = replace(core, 'logic have_previous;', 'logic have_previous, spill_pending, cache_cancel_seen;\n    assign stack_valid = spill_pending;')
    core = replace(core, '''        if (state == DICT || (state == EMIT && out_ready))
            stack_output <= stack[12'(stack_size - (state == EMIT ? 13'd2 : 13'd1))];''', '''        if ((state == DICT || (state == EMIT && out_ready)) &&
            (stack_size - (state == EMIT ? 13'd2 : 13'd1)) < 512)
            stack_output <= stack[9'(stack_size - (state == EMIT ? 13'd2 : 13'd1))];
        if (state == SPILL_READ_WAIT && stack_ack && !stack_error)
            spill_output <= stack_rdata;''')
    core = replace(core, '        done <= 0;', '''        done <= 0;
        if (spill_pending && stack_ack) spill_pending <= 0;
        if (cache_cancelled) cache_cancel_seen <= 1;''')
    core = replace(core, 'state <= IDLE; error <= 0;', 'state <= IDLE; error <= 0; spill_pending <= 0; cache_cancel_seen <= 0;')
    core = replace(core, 'state <= CANCEL_WAIT; error <= 0;', 'state <= spill_pending && !stack_ack ? CANCEL_SPILL : CANCEL_WAIT; error <= 0;')
    core = replace(core, '            stack_size <= 0;', '            stack_size <= 0; cache_cancel_seen <= 0;', 2)
    core = replace(core, '''                    stack[stack_size[11:0]] <= walk_code[7:0];
                    stack_size <= stack_size+1; first <= walk_code[7:0];
                    state <= DICT;''', '''                    if (stack_size < 512) begin
                        stack[stack_size[8:0]] <= walk_code[7:0];
                        stack_size <= stack_size+1; first <= walk_code[7:0];
                        state <= DICT;
                    end else begin
                        spill_pending <= 1; stack_write <= 1;
                        stack_address <= stack_size[11:0]; stack_wdata <= walk_code[7:0];
                        state <= SPILL_LITERAL;
                    end''')
    core = replace(core, '''                stack[stack_size[11:0]] <= fetched_suffix;
                stack_size <= stack_size+1; walk_code <= fetched_prefix;
                state <= WALK;''', '''                if (stack_size < 512) begin
                    stack[stack_size[8:0]] <= fetched_suffix;
                    stack_size <= stack_size+1; walk_code <= fetched_prefix;
                    state <= WALK;
                end else begin
                    spill_pending <= 1; stack_write <= 1;
                    stack_address <= stack_size[11:0]; stack_wdata <= fetched_suffix;
                    state <= SPILL_PUSH;
                end''')
    core = replace(core, 'have_previous <= 1; state <= EMIT;', 'have_previous <= 1; state <= stack_size > 512 ? SPILL_READ : EMIT;', 2)
    core = replace(core, 'CANCEL_WAIT: if (cache_cancelled) state <= IDLE;', '''CANCEL_WAIT: if (cache_cancelled || cache_cancel_seen) state <= IDLE;
            CANCEL_SPILL: if (stack_ack) state <= CANCEL_WAIT;
            SPILL_PUSH, SPILL_LITERAL: if (stack_ack) begin
                if (stack_error) begin error <= 1; done <= 1; state <= IDLE; end
                else begin
                    stack_size <= stack_size+1;
                    if (state == SPILL_PUSH) begin walk_code <= fetched_prefix; state <= WALK; end
                    else begin first <= walk_code[7:0]; state <= DICT; end
                end
            end
            SPILL_READ: begin
                spill_pending <= 1; stack_write <= 0; stack_wdata <= 0;
                stack_address <= 12'(stack_size-1); state <= SPILL_READ_WAIT;
            end
            SPILL_READ_WAIT: if (stack_ack) begin
                if (stack_error) begin error <= 1; done <= 1; state <= IDLE; end
                else state <= EMIT;
            end''')
    core = replace(core, 'if (stack_size == 1) state <= CODE;', 'if (stack_size == 1) state <= CODE;\n                else if (stack_size > 513) state <= SPILL_READ;')
    (output / 'gif_lzw_cached.sv').write_text(core)
    (output / 'cached_dictionary.sv').write_text((source / 'cached_dictionary.sv').read_text())


if __name__ == '__main__':
    generate(Path(sys.argv[1]), Path(sys.argv[2]))
