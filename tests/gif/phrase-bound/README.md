# Phrase bound for the 320 by 240 accelerator

The existing experimental compositor accepts a 320 by 240 canvas; its LZW
pipeline limits decoded output to 76,800 indices. Within that scope a 512-byte
phrase stack is sufficient without external spill. This is a bound on image
output, not compressed file size, frame count or the alphabet size.

## Argument and assumptions

Let M be the longest phrase already emitted since a fresh dictionary, and E
the number of emitted indices. Every dictionary addition in the existing
decoder is the previously emitted phrase plus one byte. The special next-code
case also adds exactly one byte to the previous phrase. Consequently the next
valid phrase length L is at most M+1. Literal codes have length one. Clearing
the dictionary restarts this argument; keeping E across a clear only weakens
the lower bound. A full dictionary cannot introduce longer entries.

Inductively E is at least T(M)=M(M+1)/2. For L<=M, output only increases E.
For L=M+1, the minimum new total is T(M)+(M+1)=T(M+1). Therefore an accepted
76,800-byte image has M<=391: T(391)=76,636 but T(392)=77,028.

The decoder can construct a phrase before checking the remaining output
space. Its next walk can therefore reach length 392 before reporting an
output overrun. It still cannot reach 512 with a valid dictionary in this
bounded job. A local-stack limit check must nevertheless precede every write
to contain malformed or corrupted dictionary chains. The start operation must
reject output limits above the advertised scope; this is not a reason to
truncate or silently accept a larger GIF. Larger images need another decoder
or an explicitly expanded implementation.

This argument applies to the inspected [cached decoder](../cached/README.md),
whose dictionary resets on every job and clear. It is not a theorem about
arbitrary pre-populated dictionaries or a substitute for RTL, memory-interface
or timing verification. The [GIF89a specification](https://www.w3.org/Graphics/GIF/spec-gif89a.txt)
Appendix F and deferred-clear clarification describe the applicable GIF LZW
code/clear rules; the triangular bound is derived here, not quoted from it.

## Executable check

```sh
python3 -B tests/gif/phrase-bound/check.py
```

The gate enumerates every abstract growth transition through the 4,096-entry
domain and checks the lower-bound induction step. An impossible two-level
jump must violate it. Independent-reference vectors for all seven legal
minimum code sizes reach the tight 391-byte phrase, pad exactly to 76,800
indices, and reject a 392-byte phrase that would exceed the image limit.
These checks support the mathematical argument; the bounded RTL and actual
SC64 transport still need their own differential tests.
