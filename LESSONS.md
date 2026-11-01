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
