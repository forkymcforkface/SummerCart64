/* Research harness for the existing SC64 stream DMA. FIFO read data follows
   the registered FIFO contract; memory timing belongs to the test driver. */
module dma_output (
    input logic clk, reset, start, stop,
    input logic [26:0] address, length,
    output logic busy,
    input logic rx_empty,
    input logic [7:0] rx_rdata,
    output logic rx_read,
    output logic request, write,
    output logic [26:0] mem_address,
    output logic [15:0] wdata,
    output logic [1:0] wmask,
    input logic ack
);
    mem_bus memory ();
    dma_scb control ();
    fifo_bus stream ();
    assign control.start = start;
    assign control.stop = stop;
    assign control.direction = 1;
    assign control.byte_swap = 0;
    assign control.starting_address = address;
    assign control.transfer_length = length;
    assign busy = control.busy;
    assign stream.rx_empty = rx_empty;
    assign stream.rx_rdata = rx_rdata;
    assign rx_read = stream.rx_read;
    assign stream.tx_full = 0;
    assign memory.ack = ack;
    assign memory.rdata = 0;
    assign request = memory.request;
    assign write = memory.write;
    assign mem_address = memory.address;
    assign wdata = memory.wdata;
    assign wmask = memory.wmask;
    memory_dma dma (.clk(clk), .reset(reset), .dma_scb(control),
                    .fifo_bus(stream), .mem_bus(memory));
endmodule
