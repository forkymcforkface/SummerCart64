# Frontend boot follow-up

Reviewed 2026-09-07. This is a source and existing-capture review only; it
does not change PhosphorOS, cart firmware, FPGA state, or hardware.

## Current profile and boundary

The current 4 MiB Final Fight profile is 425 ms to the ready log. Its material
synchronous phases are configuration 36 ms, language cache 31 ms, modules
28.8 ms, theme 204 ms (INI 36, assets 118, sound 34, views 14), and root
scan settlement 62.3 ms. The root list must be complete before the first
themed frame. The boot destination path may then enter one system and settle
that list; autoplay and fast reboot remain before the ordinary frame loop.

This review excludes the previously rejected asynchronous SD-to-cart work.
It also does not count bootloader or MCU improvements as frontend work.

## Highest-value candidate: coalesce abandoned root scan arms

The eager root browser currently starts the same cold root scan three times
before it completes it once. This is visible in the prior Final Fight captures:
`build/boot-stages/repeat.log` and `build/boot-final/repeat.log` each contain
three `browser 'sd:/roms' n=0 root=1` records followed by the single
`n=12 root=1` record. The old detailed profile attributes the final settle to
67--81 ms. The current profile measures it at 62.3 ms.

The source establishes the ownership chain:

1. `games_view_init()` registers a non-transient container, so
   `view_container_register()` immediately calls `games_build()`.
2. `phos_theme_engage()` calls `view_refresh_all()`. A container refresh drops
   and builds every non-transient view, so it calls `games_build()` again.
3. `view_set_root("systems_view")` calls `games_activate()`, which calls
   `rebuild()` a third time.

Each `rebuild()` reaches `get_items()`, which unconditionally cancels the
previous listing, resets it, and calls `games_listing_scan_arm()` when no table
exists. Thus the first two arms have no published rows and are discarded by
the next arm. `games_view.c` records that a cold `fs_dir_open` can itself cost
93 ms, so removing even one abandoned open is a credible boot-size win. The
exact saving must be measured; the 62.3 ms final scan is required work and is
not a saving estimate.

The narrowest first candidate is to leave the theme-refresh build as the
single arm and make `games_activate()` retain a pending foreground root scan
that already belongs to the current root. It must not retain a prefetch scan,
a scan for another directory, or an already completed listing. It still calls
`games_view_scan_settle()` after `view_set_root`, so frame one receives the
same complete root rows. This removes only the activation-time cancelled open.

Do not make the root container transient just to avoid its pre-theme build.
The architecture deliberately makes the root eager, and the theme funnel
needs its release/refresh/heal lifecycle for the first live atlas and widgets.
A larger boot-only arm suppression can be considered only after the narrow
case passes: it must retain registration, release, refresh and heal behavior,
then issue exactly one post-theme foreground root arm.

Required guard and measurement:

- Add a focused actual-source lifecycle test that records arm/cancel/path/root/
  prefetch state across registration, `phos_theme_engage`, `view_set_root` and
  `games_view_scan_settle`. It must require one surviving root arm and one
  completed root table, not merely fewer log lines.
- Negative cases: an armed prefetch must not suppress a foreground rebuild;
  a theme heal's second refresh must be safe; an empty root must still publish
  its completed-empty latch; changing root or a boot-to-system path must not
  reuse the wrong cursor.
- On N64, interleave baseline/candidate/baseline with the same card, theme,
  cache state and root contents. Record ready time and the individual root
  open/scan/store timings, then check the first root screenshot and direct
  boot-to-system, autoplay, fast-reboot, theme switch and root-return flows.

## Second target: identify module command cost before deferring anything

`modules_init()` is 28.8 ms in the current profile, but it is one aggregate
timer. The SC64 production set is `rtc emulators viz memview patcher resident
sc64 cpak cheats dd64`. Most initializers only register views, rows, USB
commands or scoped settings. Deferring the aggregate would violate the
documented rule that modules register before views consume their rows.

There is, however, concrete hardware-command work inside the aggregate:
`sc64_available()` probes a cart setting while building the active registry;
`sc64_init()` repeats the firmware version request already made by
`rgbpiui.c`, then writes LED and button configuration through two cart
commands. `resident_init()` reads the return/capture marker and may harvest a
pending screenshot. These operations have different boot obligations and
cannot be safely hidden behind a generic module delay.

First add per-module elapsed timing and cart-command counts to an isolated
profiling ROM. If the repeated SC64 version query is material, pass the
already-read boot version to the SC64 module through its existing narrow cart
or module contract, preserving its displayed value. If configuration sets
dominate, test only an idempotent-set elision after proving the persisted cart
state is already equal; never assume it from `config.ini`. Screenshot harvest
is an IGR-return contract and stays synchronous when its marker is present.
No implementation is justified until the attribution identifies a multi-ms
operation.

## Areas deliberately not proposed

| Area | Reason |
| --- | --- |
| Language parsing | The active `translations.cache` is already in use. Historical `build/boot-language/report.txt` improved uncached parsing from 240 ms to 166 ms; the current cached phase is 31 ms. |
| Recents, messages, transition | Existing owner-held deferrals already preserve first-root behavior. `build/boot-deferred/report.txt` records the accepted recents result, and theme resources pump messages/transition after ready. |
| Theme parse/font maps | `theme.cache` already validates and restores parsed theme settings and maps. |
| Required theme assets | The 118 ms asset phase loads the font sheets and background required by frame one in memory-safe order. Moving it after ready would change first-frame behavior and can break 4 MiB allocation order. |
| Theme sound inventory | `sound_reload_theme()` must preserve the OS4 refresh order and immediate playlist policy. Its directory work has already been consolidated into two directory scans, avoiding repeated missing-file probes. |
| Favorites and collections | Favorite membership is required by root-row policy; collection entries are attached while their roots are enumerated. Deferral would change initial pins/counts unless a separately owned, parity-proven snapshot is introduced. |
| Generic read-buffer/cache tuning | Historical `boot-cache`, `boot-read`, `boot-prefix` and `boot-bulk` captures vary with card state and do not isolate a repeatable frontend semantic win. Do not revive them without a new trace tied to one owner. |

The root-arm coalescing candidate is the only source-supported change here
with a plausible tens-of-milliseconds ceiling and a narrow ownership boundary.
The module breakdown is the next diagnostic gate, not a claimed optimization.
