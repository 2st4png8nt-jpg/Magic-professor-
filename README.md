# Magic Professor

A machine-learning agent that teaches itself Magic: The Gathering deckbuilding by
playing hundreds of thousands of simulated games, then reports what it learned.

## What's here
- `engine.py` — a simplified two-player Magic engine: lands, two-color mana, the curve,
  creatures and combat, removal, card draw, ramp, flyers, London mulligans, play/draw.
  Cards are generic ("3-mana 3/3") so the lessons transfer to any format.
- `learn.py` — the learning agent, using every CPU core:
  1. **Controlled experiments** — change one thing about a deck and measure its win rate
     against a field of six archetypes (aggro, midrange, control, flyers, ramp, goodstuff).
  2. **Evolution** — a genetic algorithm breeds 40- and 60-card decks; the best decks join a
     hall of fame the next generation must beat.
- `results/results.json` — everything the agent measured.
- `LESSONS.md` — what it learned, written as lessons.

## Run it
```
python3 learn.py          # full run (~30-60 min on 2 cores)
python3 learn.py --quick  # smoke test (~30 s)
```

## Honest limits
The engine leaves out card text (abilities, tricks, trample, lifelink, bombs) and uses a
simple rules-based pilot. Treat the numbers as *direction and size of effect*, not exact
real-world values.
