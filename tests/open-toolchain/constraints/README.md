# Fail-closed SC64 constraint inventory

This guard reads the original LPF without stripping or translating statements.
It understands the narrow SC64 grammar, including adjacent quoted tokens,
enumerates exact physical ports from `module top`, checks sites/groups/clock
references, and reports the pinned backend's missing semantics for each
statement. It does not apply constraints or certify a bitstream.

From the SC64 checkout:

```sh
python3 -B tests/open-toolchain/constraints/test_audit.py
python3 -B tests/open-toolchain/constraints/audit.py fw/project/lcmxo2/sc64.lpf fw/rtl/top.sv
```

The audit writes JSON to stdout; redirect it only to an ignored build directory.
Exit **2** means invalid/incomplete inventory or input. Exit **3** means valid
inventory but unresolved backend qualification. The original SC64 project must
currently return 3, with `qualified: false`. There is deliberately no override
to turn unsupported timing into a pass. Unit-test exit 0 qualifies the guard's
behavior only. No hardware, external toolchain or network is used.

Port directions, sites, electrical attributes, voltage declarations, aliases,
clock frequencies, groups, every tokenized statement and source SHA-256s are
included. LOCATE validation checks declared ports, unique TG144 sites and full
coverage; it does not establish package bank mapping, post-route placement or
electrical configuration bits. The source parser fails closed on unsupported
ANSI declarations rather than guessing bus widths. Synthesized net names and
ports still require a separate netlist/post-route comparison.

`backend_status` describes the pinned nextpnr version in the parent directory's
README. Parser acceptance is distinguished from configuration/timing evidence.
Updating a backend requires updating and verifying these classifications;
this inventory never treats parser acceptance as semantic implementation.
