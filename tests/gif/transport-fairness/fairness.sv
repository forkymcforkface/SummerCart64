/* Actual stock arbitration with a four-owner CFG mux or continuous stock CFG.
   All requests use fixed distinct SDRAM words. The external responder owns
   delay and ACK; flash and BRAM cannot acknowledge these addresses. */
module fairness (
    input logic clk, reset, mux_enable, cfg_enable, pi_active,
    input logic [6:0] requests,
    output logic [6:0] acknowledgements,
    output logic [111:0] readback,
    input logic memory_ack,
    input logic [15:0] memory_rdata,
    output logic memory_request,
    output logic [26:0] memory_address,
    output logic cfg_request
);
    mem_bus scratch(), source(), packet(), mcu(), multiplexed(), cfg();
    mem_bus usb(), sd(), n64(), sdram(), flash(), bram();
    n64_scb scb();
    assign scb.pi_sdram_active=pi_active;
    assign scb.pi_flash_active=0;
    assign scratch.request=requests[0];
    assign source.request=requests[1];
    assign packet.request=requests[2];
    assign mcu.request=requests[3];
    assign usb.request=requests[4];
    assign sd.request=requests[5];
    assign n64.request=requests[6];
    assign scratch.address=27'h100;
    assign source.address=27'h104;
    assign packet.address=27'h108;
    assign mcu.address=27'h10c;
    assign usb.address=27'h110;
    assign sd.address=27'h114;
    assign n64.address=27'h118;
    assign scratch.write=0; assign scratch.wmask=3; assign scratch.wdata=0;
    assign source.write=0; assign source.wmask=3; assign source.wdata=0;
    assign packet.write=0; assign packet.wmask=3; assign packet.wdata=0;
    assign mcu.write=0; assign mcu.wmask=3; assign mcu.wdata=0;
    assign usb.write=0; assign usb.wmask=3; assign usb.wdata=0;
    assign sd.write=0; assign sd.wmask=3; assign sd.wdata=0;
    assign n64.write=0; assign n64.wmask=3; assign n64.wdata=0;
    gif_transport_mcu_mux mux (.clk(clk),.reset(reset),.gif_admit(1'b1),
        .idle(),.gif_idle(),.scratch(scratch),.source(source),.packet(packet),.mcu(mcu),.memory(multiplexed));
    assign cfg.request=cfg_enable&&(mux_enable?multiplexed.request:1'b1);
    assign cfg.address=mux_enable?multiplexed.address:27'h10c;
    assign cfg.write=0; assign cfg.wmask=3; assign cfg.wdata=0;
    assign multiplexed.ack=mux_enable&&cfg.ack;
    assign multiplexed.rdata=cfg.rdata;
    assign acknowledgements={n64.ack,sd.ack,usb.ack,
        mux_enable?mcu.ack:cfg.ack,packet.ack,source.ack,scratch.ack};
    assign readback={n64.rdata,sd.rdata,usb.rdata,
        mux_enable?mcu.rdata:cfg.rdata,packet.rdata,source.rdata,scratch.rdata};
    assign cfg_request=cfg.request;
    assign sdram.ack=memory_ack;
    assign sdram.rdata=memory_rdata;
    assign memory_request=sdram.request;
    assign memory_address=sdram.address;
    assign flash.ack=0; assign flash.rdata=0;
    assign bram.ack=0; assign bram.rdata=0;
    memory_arbiter arbiter (.clk(clk),.reset(reset),.n64_scb(scb),
        .n64_bus(n64),.cfg_bus(cfg),.usb_dma_bus(usb),.sd_dma_bus(sd),
        .sdram_mem_bus(sdram),.flash_mem_bus(flash),.bram_mem_bus(bram));
endmodule
