# Lessons from the Magic Professor

Full run: 2 CPU cores, 3,000 games per data point per opponent, about 70 minutes, over 30 million simulated games.
Raw numbers are in `results/results.json`; the full log is `results_log.txt` (not committed).

## Cheat sheet

1. **Lands: about 37–40% of the deck.** Simulated best: 15 of 40, 22 of 60, 32 of 100 (40 life). Real Limited: 16–17, because real games have mana sinks and bombs.
2. **Lower lands for a low curve, raise for a high curve.** 2.0 avg MV won 57% on 14 lands; 4.7 avg MV needed 20 and still flooded 25% of games.
3. **Pick a lane.** Very low curve (57%) or high curve with answers (52%) beat the medium middle (48%).
4. **Removal is almost never wrong.** 0 → 12 removal: 43% → 51%.
5. **Draw and ramp need payoffs.** In a creature deck: 1 draw spell best (8 → 34%); every ramp spell hurt (8 → 26%).
6. **Synergy needs density.** Lords flat/negative in a creature deck; 1 lord helped control, 8 hurt (60% → 44%). Aristocrats with no sac outlets: 45% → 33%.
7. **Combos: 4 copies of each piece + 2 tutors** (60%). Redundancy added 15–17%; tutors at most 4%.
8. **Beating combo takes interaction:** 0 removal = 33%, 12 removal = 52%.
9. **Mono-color** won ~4% more than two colors (50% vs 45%).
10. Mulligan rule and play/draw barely mattered in this model.

## Land counts

| Format | Best | Plateau | Win at best |
|---|---|---|---|
| 40 cards | 15 | 14–16 | 49% |
| 60 cards | 22 | 21–24 | 49% |
| 100 cards, 40 life | 32 | 32–38 | 51% |

## Curve

| Avg MV | Lands | Win | Screw | Flood |
|---|---|---|---|---|
| 2.0 | 14 | 57% | 9% | 2% |
| 2.6 | 14 | 48% | 9% | 2% |
| 3.1 | 15 | 48% | 6% | 3% |
| 4.0 | 18 | 52% | 2% | 12% |
| 4.7 | 20 | 45% | 1% | 25% |

## Meta (starting archetypes vs the field)

| Archetype | Win | Main win condition |
|---|---|---|
| Ramp | 61% | big ground creatures |
| Control | 57% | removal, then finishers |
| Combo | 56% | combo (97% of wins) |
| Aggro | 47% | fast ground damage |
| Goodstuff | 47% | ground |
| Midrange | 46% | ground |
| Tribal | 43% | pumped team |
| Flyers | 43% | flyers (60% of wins) |

## Evolved champions (40 cards, vs original field)

| Archetype | Win | Lands | Deck |
|---|---|---|---|
| Combo | 75% | 18 | 20 combo pieces, 2 two-drops |
| Midrange | 68% | 15 | 7 two-drops, 7 big creatures, 6 draw, 4 removal, 1 ramp |
| Aggro | 64% | 10 | 12 one-drops, 10 two-drops, 5 flyers, 3 removal |
| Control | 62% | 16 | 16 removal, 4 finishers, 3 flyers, 1 draw |

Open evolution converged on combo at both 40 (18 lands, 75%) and 60 cards (28 lands, 74%).

## Honest limits

- No 4-copy limit: evolved combo ran 10 of each piece (illegal). With 4 each it is ~60%.
- No mana sinks/bombs: real decks want 1–2 more lands than simulated.
- No counterspells, instants, tokens or sac outlets: synergy payoffs look weaker than in real Magic.
- Same simple AI for both players: mulligan and play/draw effects are underestimated.

---

# Round 2: real-world advice, checked (engine2.py / learn2.py)

Engine v2 adds mana sinks (S3), bombs (B5), card-draw creatures (V3), counterspells (X2), board wipes (W4),
tokens (TK) + sac outlet (SO), Blood Artist-style aristocrats (AR), a commander (CM, +2 tax), free mulligan,
format life totals, 4-copy limit and singleton combo pieces. About 6 million games, 27 minutes on 2 cores.
Raw numbers: `results/results2.json`.

## Land counts vs expert advice

| Format | Expert advice | Sim best | Within ~2% |
|---|---|---|---|
| Draft, average | 17 | 17 | 16–17 |
| Draft, low curve | ≤16 | 14 | 14–15 |
| Draft, high curve | 18 | 18 | 17–20 |
| 60 aggro | 20–22 | 18 | 18–19 |
| 60 midrange | ~24 (Karsten 25.7) | 26 | 23–27 |
| 60 control | 26–28 (Karsten 25.9) | 24 | 22–25 |
| Standard Brawl 59+cmdr | 24–26 | 25 | 23–26 |
| Brawl 99+cmdr, 25 life | 36–38 | 42 | 36–44 |
| Commander 1v1, 40 life | 36–38 | 42 | 36–44 |

- Mana sinks + bombs push draft from 16 to 17 lands (48% → 53%).
- Ramp replaces lands: Brawl with no ramp wanted 44 lands.

## Brawl template (37 lands)

| Slot | Template | Sim best | Notes |
|---|---|---|---|
| Ramp | 8–12 | 8 | >10 hurts (16: 50%) |
| Draw | 10–12 | 10 | flat 52–55% |
| Removal | 8–10 | 16+ | 48% → 58% |
| Wipes | 2–3 | 6+ | 49% → 62% (1v1, wipe only when behind) |

## Other findings

- Draft two-drops: more helps up to 9 (44% → 58%). Creatures: ~16 of 23 spells. Each bomb ≈ +5–7%.
- Aristocrat payoffs help a built shell (26% → 34%), but the token/sac shell is weak in this model. Lords in token deck hurt.
- 60-card combo with 4-copy limit: 4 pieces + 2 tutors = 50% (balanced now).
- vs combo: removal 0 → 12 = 40% → 63%; counterspells 0 → 6 = 53% → 57%. vs whole field counterspells hurt (59% → 54%).
- Evolution (all cards allowed) in draft, 60 and Brawl converged on bombs + wipes + removal + card-draw creatures, 83–85% vs field.

## Sources
- Wizards Brawl rules: https://magic.wizards.com/en/formats/brawl
- Draftsim 40-card lands (Karsten): https://draftsim.com/mtg-40-card-deck-number-of-lands/
- Wizards mana curve: https://magic.wizards.com/en/news/feature/how-build-mana-curve-2017-05-18
- Draftsim 60-card lands: https://draftsim.com/how-many-lands-in-a-60-card-deck/
- ScrollVault Karsten formulas: https://scrollvault.net/guides/how-many-lands.html
- Draftsim Arena Brawl guide: https://draftsim.com/mtg-arena-brawl-guide/
- Nerd Leagues Commander ratios: https://www.nerdleagues.com/blog/deck-building-basics-ratios-curves-the-8x8-method
- Nerd Leagues Commander lands: https://www.nerdleagues.com/blog/how-many-lands-commander-edh
