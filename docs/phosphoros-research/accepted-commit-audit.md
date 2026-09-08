# Final accepted-commit audit

Read-only audit completed 2026-09-08. Root main was `3e97cd23d44799be46a1f187b2a4de9c6b1a5b6b` (72 commits ahead of origin/main), and vendor SC64 HEAD was `bed672b2240abf09a9a60385a69aa96b72b16cec`. No merges, resets, source edits, hardware actions, or pushes were performed by this audit.

## Finding

No accepted optimization from the software boot and frame-time rounds was found missing from current main or the tested vendor HEAD. Earlier isolated positives superseded by combined-stack rejections are not accepted wins. Pending hardware candidates remain pending until the parent's final verdict; this audit does not promote them.

## Retained root performance commits

All 21 commits below pass `git merge-base --is-ancestor <commit> HEAD`. Their dispositions are supported by the maintained vendor `boot-testing.md` and `ui-testing.md` ledgers, read chronologically so later integrated results supersede preliminary observations.

| Commit | Retained change |
|---|---|
| aef1f60c | Defer USB polling during active PI transfers |
| 0b2d3e5b | Retain pending root scan during boot |
| 19fd308f | Use LZ4 compression for the SC64 menu |
| d3a404b1 | Avoid redundant cache directory transfers at boot |
| 68845a42 | Overlap RTC detection with FAT mounting |
| 2349ab0b | Read language/theme caches in larger blocks |
| 38b9fa55 | Package menus with a 16 KiB LZ4 window |
| 2410b611 | Process CRC eight bytes per loop iteration |
| e4493948 | Hydrate cached theme strings in one owned arena |
| 8b598a27 | Index configuration lookups while preserving ownership |
| 078e6a77 | Read native sprite slices without stdio buffering |
| 44b60c96 | Avoid full RGB maps for indexed font atlases |
| 2ac737a6 | Flush decompressed menu output through the whole cache |
| 57ce0a31 | Negotiate atomic SC64 native SD reads |
| 841682c7 | Construct bounded configuration keys without formatting |
| ff917700 | Consolidate startup heap diagnostics |
| 66ed588d | Avoid buffered virtual wav64 guard reads |
| e6b69f79 | Defer disposable browser construction at boot |
| 89bacff4 | Specialize complete-input PDSB GIF decoding |
| a8dd082f | Defer speculative song prefetch during navigation |
| e0e120e8 | Reuse recorded page indicator draws |

The historical accepted USB commit `6a39cafd` has the same commit explanation and byte-identical affected source as main ancestor `aef1f60c`; the old hash is not a missing optimization. Current root's vendor gitlink is exactly `bed672b2240abf09a9a60385a69aa96b72b16cec`.

## Retained vendor changes

- `1c8f6f9`: original five optimizations consolidated: cursor reuse, c1 bootloader compression, bounded menu extents, SPI byte batching, and adjacent register grouping. Its entire `sw/` and `fw/` trees compare byte-identical to the old remote boot branch `6199a540c91eb8198cac846b81cfed6d30969bd0`; those historical implementations are represented despite rewritten ancestry.
- `701e31d`: omit diagnostic logo while retaining plain diagnostics.
- `a57d302`: full-duplex register reads.
- `faacf01`: smaller diagnostic formatter.
- `19c7387`: negotiated native READ_AT command.

Their regression gates, provenance, and research ledgers are reachable from tested vendor HEAD. New software argument-pair, speculative scheduling, or FPGA experiments are not implicitly retained.

## Older agent branch reconciliation

Enumerated all local branch heads and compared commits not reachable from main. The archived `old_main` lineage is a rewritten historical tree, not a queue to reapply wholesale. Isolated active-agent commits were then identified with `git log <branch> --not HEAD old_main` and matched against integrated main commit subjects. For the 35 matching commits, compared stable patch IDs over `src/`, `mk/`, `tools/`, `configs/`, and `docs/` (excluding generated staged ROMs). Twenty-eight match exactly. Seven underwent explicit `git range-diff` review: differences are adjacent lint/documentation context, additional gate registrations, staged ROM updates, or one explanatory image-cache comment; no optimization implementation was dropped.

| Old branch commit | Integrated main commit |
|---|---|
| 138f94d2 | f9c96823 |
| 463167b7 | 0b4b32ab |
| 03c531a9 | 9803d13a |
| bfad58d3 | 62ab4d3b |
| 582a8552 | 71d411f0 |
| d564b6cc | d3bd2212 |
| e39ecdcc | 0a03a33a |
| c237e2c2 | 2aa772ff |
| b56c5f48 | be335fcf |
| 1fd254bd | bb576c2f |
| f13e9349 | 530e584b |
| f39ac93e | bb89c563 |
| 832f26cd | 14063206 |
| 27783903 | d355a698 |
| f094bd02 | f9c0560e |
| 499da156 | b5073b7b |
| f4c859df | 388c95ab |
| 663e60b1 | 481af6b7 |
| b51d4ee2 | 1a72ea95 |
| 4a63cf88 | 02bcd270 |
| bef734bf | cdfb8c34 |
| 4a148421 | eaf7467d |
| 0fc67ec3 | 4013ceda |
| 6fca3ac0 | b20bb45f |
| 2a026737 | 94184a47 |
| 041a2699 | 80894423 |
| 8f8af883 | fc221b73 |
| f8fb13b9 | 7093e588 |
| 966993b0 | 316cdb9c |
| d3b6ed9e | 7d89ba81 |
| 5f1b6fab | c8f66c16 |
| c6e93954 | 1a4a1999 |
| c1fa405f | 8097d8d2 |
| 33a8d5ae | 66779fa5 |
| 3935594b | 6b6de3fb |

This does not authorize restoring abandoned module-system work, archived experiments, or the independent theme-builder project. It is a bounded reconciliation of accepted performance work and the relevant old agent branches, not a claim that every archived historical commit should be retained.

## Exclusions and remaining verdicts

Later ledger decisions reject or leave unaccepted heap-only O2, text O2, filename copying, systems buffering/copies, MCU argument-pair experiments, and alternate CRC work. Earlier standalone benefits do not override their final dispositions. At this audit snapshot, current-main mixed-atlas text, wide-LZ4, and tap tests remain parent-owned pending final verdict. The inline-length decoder experiment is explicitly parked and excluded; no hardware result or acceptance is claimed.

## Remote reachability before publishing

Read-only `git ls-remote` confirmed vendor origin/main at `a1e7996d2cbece686820a5c785029c68514f17b0`, and origin/phosphoros-boot at `6199a540c91eb8198cac846b81cfed6d30969bd0`. Tested HEAD diverges from main by 39 local / 25 upstream commits, and from the old boot branch by 39 / 33 because of the authorized squash.

The 25 remote-main commits include real FatFs/GPT, FlashRAM, CIC/SERV, bootloader and tooling changes absent from this tested firmware baseline. A read-only three-way merge preview reports conflicts in `sw/bootloader/src/fatfs/ffconf.h` and `sw/bootloader/src/menu.c`; ten paths overlap. An ours merge would preserve ancestry while discarding upstream file changes, so it is not recommended.

Publish the exact tested vendor HEAD (or its documentation-only descendant) on a new named remote branch first, then publish root main with the matching gitlink. This preserves the tested firmware and all existing remote branches without force, upstream merge, or unvalidated firmware changes. Confirm the published vendor SHA is remotely reachable before root publication. No push has been performed by this audit.

## Closure addendum

The final hardware round retains PDSB lookahead in root main e07e5c25, with its
actual-owner test extension in a06cb2ce. These join the 21 earlier retained
optimizations above. Mixed-atlas, raw-rectangle and tap experiments are rejected;
the wider decoder's standalone positive is superseded by its final-stack
rejection. Full results and the verified final SD hash are in ui-testing.md.
Publication targets root main and the exact tested vendor tree on the new
phosphoros-verified-20260908 branch. The older remote vendor branches are preserved.
