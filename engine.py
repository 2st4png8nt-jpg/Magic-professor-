"""
Magic Professor — a simplified two-player Magic: The Gathering engine.

It keeps the parts of Magic that decide whether a DECK is good:
lands and mana, the curve, creatures and combat, removal, card draw,
ramp, evasion, mulligans, and who goes first. Everything is generic
("a 3-mana 3/3") so the lessons transfer to any format.

Card codes (a deck is just a count of each code):
  L    land
  C1..C6  vanilla creature, mana value = N  (stats below)
  F3   3-mana 2/2 flyer (can only be blocked by flyers)
  R2   2-mana removal: destroy a creature with toughness <= 3
  R4   4-mana removal: destroy any creature
  D3   3-mana: draw two cards
  M2   2-mana ramp: put a land from your library onto the battlefield

Colors: decks are two colors by default (cards and lands split evenly).
A spell needs 1 land of its color, or 2 if its mana value is 4+.
"""
import random

CARDS = ["L", "C1", "C2", "C3", "C4", "C5", "C6", "F3", "R2", "R4", "D3", "M2"]
# Stats follow real Limited rates: cheap cards are more mana-efficient,
# expensive cards are bigger in absolute size (one card is still one card).
STATS = {"C1": (2, 1), "C2": (3, 2), "C3": (3, 3), "C4": (4, 3),
         "C5": (4, 5), "C6": (5, 5), "F3": (2, 2)}
COST = {"L": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5, "C6": 6,
        "F3": 3, "R2": 2, "R4": 4, "D3": 3, "M2": 2}
MAX_TURNS = 30


class Creature:
    __slots__ = ("code", "power", "tough", "flying", "sick")

    def __init__(self, code):
        self.code = code
        self.power, self.tough = STATS[code]
        self.flying = code == "F3"
        self.sick = True

    def value(self):
        return self.power + self.tough + (2 if self.flying else 0)


def pips(code):
    """Colored mana needed: 1 for cheap spells, 2 for mana value 4+."""
    return 2 if COST[code] >= 4 else 1


class Player:
    """Cards are strings: base code + color letter, e.g. 'C3a', 'Lb'.
    colors=1 -> mono-color deck, colors=2 -> even two-color split."""

    def __init__(self, deck_counts, rng, mulligan=True, life=20, colors=2):
        letters = "ab"[:colors]
        self.library = []
        for c, n in deck_counts.items():
            for i in range(n):
                self.library.append(c + letters[i % colors])
        rng.shuffle(self.library)
        self.rng = rng
        self.hand, self.board = [], []
        self.lands = {"a": 0, "b": 0}
        self.life = life
        self.land_drop = False
        self.decked = False
        self.stats = {"mulls": 0, "screw": False, "flood": False, "stuck": 0}
        self._opening_hand(mulligan)

    @property
    def n_lands(self):
        return self.lands["a"] + self.lands["b"]

    def hand_lands(self):
        return [c for c in self.hand if c[0] == "L"]

    def _opening_hand(self, mulligan):
        """London mulligan: draw 7, keep 2-5 lands, bottom 1 card per mulligan."""
        n_mull = 0
        while True:
            self.library += self.hand
            self.hand = []
            self.rng.shuffle(self.library)
            self.draw(7)
            lands = len(self.hand_lands())
            if not mulligan or 2 <= lands <= 5 or n_mull >= 2:
                break
            n_mull += 1
        for _ in range(n_mull):  # bottom the least useful cards
            hl = self.hand_lands()
            spells = [c for c in self.hand if c[0] != "L"]
            if len(hl) > 3 or not spells:
                pick = hl[0]
            else:
                pick = max(spells, key=lambda c: COST[c[:-1]])
            self.hand.remove(pick)
            self.library.insert(0, pick)
        self.stats["mulls"] = n_mull

    def draw(self, n=1):
        for _ in range(n):
            if not self.library:
                self.decked = True
                return
            self.hand.append(self.library.pop())

    def can_cast(self, card, mana):
        code, col = card[:-1], card[-1]
        return COST[code] <= mana and self.lands[col] >= pips(code)

    def want_color(self):
        """The color our hand is most short of."""
        need = {"a": 0, "b": 0}
        for c in self.hand:
            if c[0] != "L":
                need[c[-1]] += 1
        return max("ab", key=lambda k: need[k] / (self.lands[k] + 1))

    def fetch_land(self):
        """Ramp: take a land of the color we want most from the library."""
        want = self.want_color()
        lands = [c for c in self.library if c[0] == "L"]
        if not lands:
            return False
        pick = next((c for c in lands if c[-1] == want), lands[0])
        self.library.remove(pick)
        self.lands[pick[-1]] += 1
        self.rng.shuffle(self.library)
        return True


def _best_target(board, max_tough):
    cands = [c for c in board if c.tough <= max_tough]
    return max(cands, key=Creature.value) if cands else None


def _use_removal(me, opp, mana, order, picky):
    for code, cap in order:
        while True:
            cards = [c for c in me.hand if c[:-1] == code and me.can_cast(c, mana)]
            if not cards:
                break
            tgt = _best_target(opp.board, cap)
            # don't waste premium removal on small stuff while cheap removal is in hand
            if tgt is None or (picky and code == "R4" and tgt.value() < 6
                               and any(c[:-1] == "R2" for c in me.hand)):
                break
            opp.board.remove(tgt)
            me.hand.remove(cards[0])
            mana -= COST[code]
    return mana


def main_phase(me, opp):
    """Greedy but sensible: land (of the color we need), removal on the biggest
    threat, ramp early, then spend as much mana as possible."""
    hl = me.hand_lands()
    if hl and not me.land_drop:
        want = me.want_color()
        land = next((c for c in hl if c[-1] == want), hl[0])
        me.hand.remove(land)
        me.lands[land[-1]] += 1
        me.land_drop = True
    mana = me.n_lands

    mana = _use_removal(me, opp, mana, (("R4", 99), ("R2", 3)), picky=True)

    while True:
        castable = [c for c in me.hand if c[0] != "L" and c[0] != "R"
                    and me.can_cast(c, mana)]
        if not castable:
            break
        # ramp first while short on lands, then board presence, then card draw
        castable.sort(key=lambda c: (c[0] == "M" and me.n_lands <= 5,
                                     c[:-1] in STATS, COST[c[:-1]]), reverse=True)
        card = castable[0]
        code = card[:-1]
        me.hand.remove(card)
        mana -= COST[code]
        if code in STATS:
            me.board.append(Creature(code))
        elif code == "D3":
            me.draw(2)
        elif code == "M2":
            me.fetch_land()

    _use_removal(me, opp, mana, (("R2", 3), ("R4", 99)), picky=False)
    # "stuck": spells in hand we can't cast purely because of color
    if any(c[0] != "L" and COST[c[:-1]] <= me.n_lands and not me.can_cast(c, 99)
           for c in me.hand):
        me.stats["stuck"] += 1


def combat(att, dfn):
    ready = [c for c in att.board if not c.sick]
    if not ready:
        return
    blockers = list(dfn.board)
    total_power = sum(c.power for c in ready)
    alpha = total_power >= dfn.life or len(ready) > len(blockers) + 2
    attackers = []
    for c in ready:
        can_block = [b for b in blockers if c.flying <= b.flying]
        bad = any(b.power >= c.tough and b.tough > c.power for b in can_block)
        if alpha or not bad:
            attackers.append(c)
    if not attackers:
        return

    incoming = sum(a.power for a in attackers)
    attackers.sort(key=lambda a: a.power, reverse=True)
    unblocked = []
    for a in attackers:
        legal = [b for b in blockers if a.flying <= b.flying]
        eat = [b for b in legal if b.tough > a.power and b.power >= a.tough]
        trade = [b for b in legal if b.power >= a.tough and b.value() <= a.value()]
        wall = [b for b in legal if b.tough > a.power]
        choice = None
        if eat:
            choice = min(eat, key=Creature.value)
        elif trade:
            choice = min(trade, key=Creature.value)
        elif wall:
            choice = min(wall, key=Creature.value)
        elif incoming >= dfn.life and legal:
            choice = min(legal, key=Creature.value)  # chump to survive
        if choice is None:
            unblocked.append(a)
            continue
        blockers.remove(choice)
        incoming -= a.power
        if choice.power >= a.tough:
            att.board.remove(a)
        if a.power >= choice.tough:
            dfn.board.remove(choice)
    dfn.life -= sum(a.power for a in unblocked)


def play_game(deck_a, deck_b, rng, a_first=True, mulligan=True, life=20, colors=2):
    """Returns (winner_index 0/1, turns, statsA, statsB)."""
    p = [Player(deck_a, rng, mulligan, life, colors), Player(deck_b, rng, mulligan, life, 2)]
    order = [0, 1] if a_first else [1, 0]
    lands_by_t4 = [None, None]
    for turn in range(1, MAX_TURNS + 1):
        for i in order:
            me, opp = p[i], p[1 - i]
            if not (turn == 1 and i == order[0]):
                me.draw()
            if me.decked:
                return 1 - i, turn, p[0].stats, p[1].stats
            me.land_drop = False
            for c in me.board:
                c.sick = False
            combat(me, opp)
            if opp.life <= 0:
                return i, turn, p[0].stats, p[1].stats
            main_phase(me, opp)
            if turn == 4 and lands_by_t4[i] is None:
                lands_by_t4[i] = me.n_lands
                me.stats["screw"] = me.n_lands <= 2
                me.stats["flood"] = len(me.hand_lands()) >= 3
    # timeout: higher life wins, coin flip on tie
    if p[0].life != p[1].life:
        return (0 if p[0].life > p[1].life else 1), MAX_TURNS, p[0].stats, p[1].stats
    return rng.randint(0, 1), MAX_TURNS, p[0].stats, p[1].stats


def match(deck_a, deck_b, games, seed, mulligan=True, life=20, a_first=None, colors=2):
    """Play `games` games alternating who goes first. Returns A's win rate and extras."""
    rng = random.Random(seed)
    wins = turns = screw = flood = stuck = 0
    for g in range(games):
        first = (g % 2 == 0) if a_first is None else a_first
        w, t, sa, _ = play_game(deck_a, deck_b, rng, a_first=first, mulligan=mulligan, life=life, colors=colors)
        wins += (w == 0)
        turns += t
        screw += sa["screw"]
        flood += sa["flood"]
        stuck += sa["stuck"] > 0
    return {"win": wins / games, "turns": turns / games,
            "screw": screw / games, "flood": flood / games, "color_stuck": stuck / games}
