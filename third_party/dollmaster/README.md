# Dollmaster (original source, not shipped)

Don's copy of **Dollmaster** by VAMDeluxe (2019), received 22.11.2026 (`dollmaster_old.zip`,
`Custom/Scripts/VAMDeluxe/Dollmaster/`). Upstream: [vamdeluxe/DeluxePlugin](https://github.com/vamdeluxe/DeluxePlugin)
(folder `Dollmaster`, commit e606e780e79af214b2b4be0a53b1e7b45ecf59b7), MIT license (`LICENSE`, copied from upstream).

Kept unchanged here as the reference of the port: `src/AIBody/Dm*.cs` is this code with the types prefixed `Dm`, the
namespace `AIBody` and changes only where the project rules need them (every change is marked `AIBody port:`).
`tools/port_dollmaster.py` does the mechanical part; `companion/tests/test_dollmaster_port.py` checks that every
difference to this source carries such a mark. The assets (personas, sound effects, expressions, VAMasutra) are in
`assets/dollmaster/` and ship in the .var below `Custom/Scripts/d0n/AIBody/Dollmaster/`.

`config.original.json` is the original `config.json`, renamed because the token scan forbids any file named
`config.json` (the shipped copy is `assets/dollmaster/dollmaster_config.json`, content unchanged).
