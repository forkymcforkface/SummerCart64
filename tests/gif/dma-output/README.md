# Reuse the existing SC64 DMA for GIF output

This research harness instantiates the unchanged production
[`memory_dma.sv`](../../../fw/rtl/memory/memory_dma.sv), `mem_bus`, `dma_scb`
and `fifo_bus`. It proves that its FIFO-to-memory path can write the byte stream
emitted by the GIF prototype. There is no new production DMA implementation.

```sh
sh tests/gif/dma-output/run.sh /path/to/build/dma-output /path/to/original-*.gpd
```

Use Python 3, Verilator, g++ and make, as in the other GIF research tests.
Generated output must remain outside `tests/gif/`. Source packets come from
the [compositor runner](../compositor/README.md), which validates them against
the original GIF. This harness treats them as an opaque stream and checks
exact destination bytes and surrounding guards.

The parent run passes **16 original-GIF RTL packets and 64 cases**. Cases cover
even/odd starting addresses, zero/odd/even lengths, delayed registered FIFO data,
FIFO starvation, delayed memory acknowledgements, stable outstanding requests,
stop at twelve positions around active transfers, no writes after retirement,
and restart after draining and flushing the test FIFO.

The test memory is a delayed `mem_bus` responder, not the physical SDRAM device
or the real arbiter. These results establish DMA mechanics only. A production
integration still needs a bounded FIFO between the packet emitter and DMA,
exclusive DMA ownership or another instance, output slot allocation, completion
publication, PI-consumer retirement and cancellation of the whole decoder job.
Two output buffers can reuse this same transfer mechanism; their ownership is
not implemented by this harness. No bitstream is built or flashed.
