#include "fpga.h"
#include "hw.h"


uint8_t fpga_id_get (void) {
    fpga_cmd_t cmd = CMD_IDENTIFY;
    uint8_t id;

    hw_spi_start();
    hw_spi_tx((uint8_t *) (&cmd), 1);
    hw_spi_rx(&id, 1);
    hw_spi_stop();

    return id;
}

uint32_t fpga_reg_get (fpga_reg_t reg) {
    uint8_t command[6] = { CMD_REG_READ, (uint8_t) reg, 0, 0, 0, 0 };
    uint8_t response[6];

    hw_spi_start();
    hw_spi_transfer(command, response, sizeof(command));
    hw_spi_stop();

    return (uint32_t) response[2] | ((uint32_t) response[3] << 8) |
        ((uint32_t) response[4] << 16) | ((uint32_t) response[5] << 24);
}

void fpga_reg_set (fpga_reg_t reg, uint32_t value) {
    uint8_t command[6] = {
        CMD_REG_WRITE, (uint8_t) reg,
        (uint8_t) value, (uint8_t) (value >> 8),
        (uint8_t) (value >> 16), (uint8_t) (value >> 24)
    };

    hw_spi_start();
    hw_spi_tx(command, sizeof(command));
    hw_spi_stop();
}

/* The existing FPGA register protocol advances after each little-endian word.
   Callers order trigger registers last; one CS frame contains the full group. */
void fpga_reg_set_words (fpga_reg_t reg, const uint32_t *values, size_t count) {
    uint8_t header[2] = { CMD_REG_WRITE, (uint8_t) reg };
    if (count == 0) {
        return;
    }
    hw_spi_start();
    hw_spi_tx(header, sizeof(header));
    hw_spi_tx((uint8_t *) values, count * sizeof(*values));
    hw_spi_stop();
}

void fpga_mem_read (uint32_t address, size_t length, uint8_t *buffer) {
    fpga_cmd_t cmd = CMD_MEM_READ;
    uint8_t buffer_address = 0;
    size_t dma_length = length;
    if ((dma_length % 2) != 0) {
        dma_length += 1;
    }

    fpga_reg_set(REG_MEM_ADDRESS, address);
    fpga_reg_set(REG_MEM_SCR, (dma_length << MEM_SCR_LENGTH_BIT) | MEM_SCR_START);
    while (fpga_reg_get(REG_MEM_SCR) & MEM_SCR_BUSY);

    hw_spi_start();
    hw_spi_tx((uint8_t *) (&cmd), 1);
    hw_spi_tx(&buffer_address, 1);
    hw_spi_rx(buffer, length);
    hw_spi_stop();
}

void fpga_mem_write (uint32_t address, size_t length, uint8_t *buffer) {
    fpga_cmd_t cmd = CMD_MEM_WRITE;
    uint8_t buffer_address = 0;
    size_t dma_length = length;
    if ((dma_length % 2) != 0) {
        dma_length += 1;
    }

    hw_spi_start();
    hw_spi_tx((uint8_t *) (&cmd), 1);
    hw_spi_tx(&buffer_address, 1);
    hw_spi_tx(buffer, length);
    hw_spi_stop();

    fpga_reg_set(REG_MEM_ADDRESS, address);
    fpga_reg_set(REG_MEM_SCR, (dma_length << MEM_SCR_LENGTH_BIT) | MEM_SCR_DIRECTION | MEM_SCR_START);
    while (fpga_reg_get(REG_MEM_SCR) & MEM_SCR_BUSY);
}

void fpga_mem_copy (uint32_t src, uint32_t dst, size_t length) {
    size_t dma_length = length;
    if ((dma_length % 2) != 0) {
        dma_length += 1;
    }

    fpga_reg_set(REG_MEM_ADDRESS, src);
    fpga_reg_set(REG_MEM_SCR, (dma_length << MEM_SCR_LENGTH_BIT) | MEM_SCR_START);
    while (fpga_reg_get(REG_MEM_SCR) & MEM_SCR_BUSY);

    fpga_reg_set(REG_MEM_ADDRESS, dst);
    fpga_reg_set(REG_MEM_SCR, (dma_length << MEM_SCR_LENGTH_BIT) | MEM_SCR_DIRECTION | MEM_SCR_START);
    while (fpga_reg_get(REG_MEM_SCR) & MEM_SCR_BUSY);
}

uint8_t fpga_usb_status_get (void) {
    fpga_cmd_t cmd = CMD_USB_STATUS;
    uint8_t status;

    hw_spi_start();
    hw_spi_tx((uint8_t *) (&cmd), 1);
    hw_spi_rx(&status, 1);
    hw_spi_stop();

    return status;
}

uint8_t fpga_usb_pop (void) {
    fpga_cmd_t cmd = CMD_USB_READ;
    uint8_t data;

    hw_spi_start();
    hw_spi_tx((uint8_t *) (&cmd), 1);
    hw_spi_rx(&data, 1);
    hw_spi_stop();

    return data;
}

void fpga_usb_push (uint8_t data) {
    fpga_cmd_t cmd = CMD_USB_WRITE;

    hw_spi_start();
    hw_spi_tx((uint8_t *) (&cmd), 1);
    hw_spi_tx(&data, 1);
    hw_spi_stop();
}
