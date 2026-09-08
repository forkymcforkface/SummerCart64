# Experimental GIF scratch-memory adapter

`gif_sc64_bus.sv` connects the cached dictionary and CI8 compositor request
interfaces to SC64's unchanged `mem_bus.controller`. It is research RTL only;
no production source list, address map, firmware or bitstream changes.

```sh
sh tests/gif/sc64-bus/run.sh /path/to/build/adapter
```

Use Python 3, Verilator, g++ and make. The standalone runner requires no GIF
because it checks the memory transport independently. The separate integration
harness feeds the original Final Fight GIF through the decoder and compositor.
Generated outputs must remain outside `tests/gif/`.

## Contract

Configure while idle with a half-open caller-owned SDRAM arena. The adapter
checks both complete windows, non-overlap, alignment and the 64 MiB SDRAM limit
using widened arithmetic. It cannot establish exclusive ownership of that
arena: the future job owner must reserve and retire it. Configuration during
an operation reports `config_error` and preserves the active addresses.

Dictionary entries use 4096 four-byte slots: low16 bits at base+key*4 and
zero-padded high4 bits at base+key*4+2. This internal word order is not a GIF or
N64 asset format. The canvas occupies 76800 bytes. Even byte offsets select the
upper 16-bit word lane, odd offsets select the lower lane, matching SC64 memory
byte order. Every issued bus address is even. Reads ignore the unused upper
12 dictionary bits. The client supplies a 12-bit key and 20-bit entry.

Requests hold valid until ACK. Both channels can request simultaneously;
round-robin selection grants one complete operation at a time. A dictionary
operation holds ownership across two bus beats. Every beat remains stable
until downstream ACK, and a request-low/ACK-low gap separates beats. SC64
`mem_bus` has no error response; adapter errors mean invalid configuration,
invalid canvas offset or cancellation, not a fabricated SDRAM fault.

Pulse cancel and cancel both clients together. The adapter drains any issued
beat, suppresses an unissued second dictionary beat, invalidates configuration,
and error-ACKs both held client requests, including the unselected channel.
`cancelled` accompanies those error ACKs; a response bubble allows consumers
to observe them. Retirement must wait for adapter `busy` to fall **and** both
client owners to finish their cancellation. Do not restart until a fresh
configuration. An issued write can already have changed scratch memory; there
is no rollback or two-word atomicity. Reset assumes the downstream bus owner
resets together and is not a substitute for live cancellation.

## Verification and limits

The standalone regression passes all 4096 dictionary round trips, canvas
lane/edge checks and surrounding guards, seven invalid configuration classes,
unconfigured access, invalid canvas offsets, simultaneous-channel fairness,
busy reconfiguration, 65 cancellation offsets with both channels requesting,
and explicit cancellation during first beat, between beats and during second
beat. The latter asserts exactly one/one/two committed beats respectively.
The delayed memory responder stalls ACK and holds ACK high for extra cycles;
it checks request stability and bounds. Every run has a global watchdog.

The recorded run passes in 217508 simulated cycles with 16580 completed bus
beats. These are test workload counts, not playback performance. This test
uses a synthetic mem_bus responder, not the actual arbiter, SDRAM controller,
chip timing, refresh or PI traffic. Those belong to the separate integration
harness. FPGA synthesis, place-and-route, timing closure and board validation
remain required before production use.
