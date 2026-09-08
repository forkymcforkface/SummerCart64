/* Exercise the exact generated SC64 FIFO against the separately installed
 * vendor model. No substitute FIFO implementation is provided by this test. */
`timescale 1ns/1ps
module model_test;
    reg wrclk=0,rdclk=0;
    always #5 wrclk=~wrclk;
    always #7 rdclk=~rdclk;
    reg [7:0] data=0;
    reg we=0,re=0,rst=1,rprst=0;
    wire [7:0] q;
    wire empty,full,ae,af;
    GSR GSR_INST(.GSR(1'b1));
    PUR PUR_INST(.PUR(1'b1));
    fifo_8kb_lattice_generated dut(.Data(data),.WrClock(wrclk),.RdClock(rdclk),
        .WrEn(we),.RdEn(re),.Reset(rst),.RPReset(rprst),.Q(q),
        .Empty(empty),.Full(full),.AlmostEmpty(ae),.AlmostFull(af));
    task push(input [7:0] value);
        begin @(negedge wrclk);data=value;we=1;@(posedge wrclk);#1;end
    endtask
    task pop(input [7:0] expected);
        begin
            @(negedge rdclk);re=1;@(posedge rdclk);#1;
            if(q!==expected)$fatal(1,"FIFO order expected=%h got=%h",expected,q);
        end
    endtask
    task settle;
        begin repeat(8)@(posedge wrclk);repeat(8)@(posedge rdclk);#1;end
    endtask
    integer i;
    initial begin
        #100;@(negedge wrclk);rst=0;settle();
        if(empty!==1||ae!==1||full!==0||af!==0)$fatal(1,"reset flags");
        for(i=0;i<1023;i=i+1)push(8'(i));
        @(negedge wrclk);we=0;settle();
        if(full!==0||af!==1)$fatal(1,"almost-full threshold");
        push(8'hff);@(negedge wrclk);we=0;settle();
        if(full!==1||af!==1||empty!==0)$fatal(1,"full threshold");
        for(i=0;i<1024;i=i+1)pop(8'(i));
        @(negedge rdclk);re=0;settle();
        if(empty!==1||ae!==1||full!==0)$fatal(1,"drain flags");
        @(negedge wrclk);rst=1;settle();rst=0;settle();
        for(i=0;i<32;i=i+1)push(8'(i+17));
        @(negedge wrclk);we=0;settle();
        for(i=0;i<8;i=i+1)pop(8'(i+17));
        @(negedge rdclk);re=0;settle();rprst=1;settle();rprst=0;settle();
        for(i=0;i<32;i=i+1)pop(8'(i+17));
        @(negedge rdclk);re=0;settle();
        if(empty!==1)$fatal(1,"read-pointer reset/replay");
        $display("PASS exact SC64 FIFO model: independent clocks,1024-byte fill/drain,flags,globalreset,read-pointer replay");
        $finish;
    end
    initial begin #1000000;$fatal(1,"FIFO model watchdog");end
endmodule
