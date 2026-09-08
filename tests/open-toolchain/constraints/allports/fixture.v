/* Input, output, vector, bidirectional and internal logic distinguish ports. */
module allports(input a, input [1:0] v, output b, inout d);
    assign b = a ^ v[0];
    assign d = v[1] ? 1'bz : a;
endmodule
