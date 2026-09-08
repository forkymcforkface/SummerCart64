# Stock EFB regeneration through installed vendor front-end tools

The actual SC64 generator command runs without changing licensing in official
SC64 environment v1.10 (Diamond 3.13). Its emitted Verilog matches the stock
wrapper's 1,146 lexical tokens, including synthesis attributes and string
literals. Dates, ordinary comments and formatting differ. This is exact HDL
regeneration, not a configuration or bitstream equivalence proof.

```sh
python3 -B tests/open-toolchain/efb/scuba/test_tokens.py
python3 -B tests/open-toolchain/efb/scuba/run.py /path/to/sc64 /out/fresh-efb
```

The runner generates Verilog and EDIF in a new output directory, then invokes
`edif2ngd -l MachXO2 -d LCMXO2-7000HC` and
`ngdbuild -a MachXO2 -d LCMXO2-7000HC`. Both conversions pass; NGD DRC reports
zero errors and warnings. Original source bytes must remain unchanged. The
generated vendor netlists and logs remain outside the repository's tests tree.
The tests ensure comparison does not erase synthesis attributes, literal
whitespace, identifier boundaries or operator boundaries.

Parent evidence is ignored under `build/sc64-efb-compiler/reproduced-final/`,
with the earlier direct probes alongside it. The runner works against the
detached official v2.20.2 checkout, not just the experimental fork. Source SHA:
`758815c0620715ee4551237a9c33a61219ec1803a4397738b70a6cdee3174879`.

The installed help's `LATTICE-XO2C` example spelling is rejected as a library;
`MachXO2` is the working library name. SCUBA's generic help does not describe
EFB options, so the exact command comes from the checked-in generated wrapper.
No undocumented option is used to alter a license check.

The next ordinary stage, `map -p LCMXO2-7000HC -s 6 -t TQFP144`, reaches the
correct part selection and fails its LSC_BASE checkout. Separately, `ngd2ltm`
advertises NGD/NGO timing extraction, but the direct EFB probe fails because
its expected MACO cell model is absent. Neither is counted as a successful
mapped design or timing extraction. The runner intentionally stops at NGD.

These results establish more usable front-end tooling, while leaving the
[configuration question](../inactive/configuration-research.md) unresolved:
generated UFM attributes do not by themselves identify static configuration
bits or prove that varying them changes only discarded UFM initialization.
No vendor file is redistributed, production RTL changed, or FPGA image flashed.
