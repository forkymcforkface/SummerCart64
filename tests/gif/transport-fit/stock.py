"""Expose the existing arbiter and SDRAM controller at their bus boundary.

This is a separately mapped reuse reference, not a subtraction proof: combined
optimization and research observation ports can move logic across names.
"""


def wrapper():
    ports = ['input logic clk, reset, pi_active, chip_drive', 'input logic [15:0] chip_data',
             'output wire [15:0] chip_dq', 'output wire [3:0] chip_command',
             'output wire [1:0] chip_bank, chip_mask', 'output wire [12:0] chip_address']
    body = ['mem_bus sdram_bus(), flash_bus(), bram_bus();', 'n64_scb scb();',
            "assign scb.pi_sdram_active=pi_active; assign scb.pi_flash_active=1'b0;",
            "assign flash_bus.ack=0; assign flash_bus.rdata=0; assign bram_bus.ack=0; assign bram_bus.rdata=0;"]
    for name in ['n64','cfg','usb','sd']:
        ports += [f'input logic {name}_request, {name}_write',f'input logic [26:0] {name}_address',
                  f'input logic [15:0] {name}_wdata', f'input logic [1:0] {name}_wmask',
                  f'output wire {name}_ack',f'output wire [15:0] {name}_rdata']
        body += [f'mem_bus {name}_bus();']
        body += [f'assign {name}_bus.{field}={name}_{field};' for field in ['request','write','address','wdata','wmask']]
        body += [f'assign {name}_{field}={name}_bus.{field};' for field in ['ack','rdata']]
    body += ['''memory_arbiter arbiter (.clk(clk),.reset(reset),.n64_scb(scb),
        .n64_bus(n64_bus),.cfg_bus(cfg_bus),.usb_dma_bus(usb_bus),.sd_dma_bus(sd_bus),
        .sdram_mem_bus(sdram_bus),.flash_mem_bus(flash_bus),.bram_mem_bus(bram_bus));
    wire [15:0] dq;
    assign dq=chip_drive?chip_data:16'hzzzz;
    assign chip_dq=dq;
    memory_sdram controller (.clk(clk),.reset(reset),.mem_bus(sdram_bus),
        .sdram_cs(chip_command[3]),.sdram_ras(chip_command[2]),
        .sdram_cas(chip_command[1]),.sdram_we(chip_command[0]),
        .sdram_ba(chip_bank),.sdram_a(chip_address),.sdram_dqm(chip_mask),.sdram_dq(dq));''']
    return 'module gif_transport_abort_pipeline(\n'+',\n'.join(ports)+');\n'+'\n'.join(body)+'\nendmodule\n'
