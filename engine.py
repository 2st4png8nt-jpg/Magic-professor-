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
  P3   3-mana 2/2 "lord": your OTHER creatures get +1/+1      (synergy)
  AR   2-mana 1/2 "aristocrat": whenever another creature you
       control dies, the opponent loses 1 life                (synergy)
  K1,K2 3-mana 1/3 combo pieces: start your turn with both = you win (combo)
  T2   2-mana tutor: search your deck for the card you need   (consistency)

Colors: decks are two colors by default (cards and lands split evenly).
A spell needs 1 land of its color, or 2 if its mana value is 4+.
"""
import random

CARDS = ["L", "C1", "C2", "C3", "C4", "C5", "C6", "F3", "R2", "R4", "D3", "M2",
         "P3", "AR", "K1", "K2", "T2"]
# Stats follow real Limited rates: cheap cards are more mana-efficient,
# expensive cards are bigger in absolute size (one card is still one card).
STATS = {"C1": (2, 1), "C2": (3, 2), "C3": (3, 3), "C4": (4, 3),
         "C5": (4, 5), "C6": (5, 5), "F3": (2, 2),
         "P3": (2, 2), "AR": (1, 2), "K1": (1, 3), "K2": (1, 3)}
COST = {"L": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5, "C6": 6,
        "F3": 3, "R2": 2, "R4": 4, "D3": 3, "M2": 2,
        "P3": 3, "AR": 2, "K1": 3, "K2": 3, "T2": 2}
MAX_TURNS = 30


class Creature:
    __slots__ = ("code", "base_p", "base_t", "power", "tough", "flying", "sick")

    def __init__(self, code):
        self.code = code
        self.base_p, self.base_t = STATS[code]
        self.power, self.tough = self.base_p, self.base_t
        self.flying = code == "F3"
        self.sick = True

    def value(self):
        """How badly the opponent wants this dead (drives removal and blocks)."""
        v = self.power + self.tough + (2 if self.flying else 0)
        if self.code in ("K1", "K2"):
            v += 8          # a live combo piece is the scariest thing on the table
        elif self.code in ("P3", "AR"):
            v += 3          # engines are worth more than their stats
        return v


def refresh(board):
    """Apply lord bonuses."""
    lords = sum(c.code == "P3" for c in board)
    for c in board:
        b = lords - (c.code == "P3")
        c.power, c.tough = c.base_p + b, c.base_t + b


def kill(owner, creature, enemy):
    """Remove a creature and fire the owner's aristocrat triggers."""
    owner.board.remove(creature)
    drains = sum(c.code == "AR" for c in owner.board)
    if drains:
        enemy.life -= drains
        owner.dealt["drain"] += drains
    refresh(owner.board)


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
        self.dealt = {"ground": 0, "flyers": 0, "drain": 0}
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

    def has(self, code):
        return any(c.code == code for c in self.board)

    def tutor(self):
        """Find the missing combo piece; otherwise a lord; otherwise the best creature."""
        wants = []
        for a, b in (("K1", "K2"), ("K2", "K1")):
            here = self.has(a) or any(c[:-1] == a for c in self.hand)
            if here:
                wants.append(b)
        wants += ["K1", "P3", "C6", "C5", "C4", "F3", "C3"]
        for w in wants:
            if (self.has(w) or any(c[:-1] == w for c in self.hand)) and w in ("K1", "K2"):
                continue
            pick = next((c for c in self.library if c[:-1] == w), None)
            if pick:
                self.library.remove(pick)
                self.hand.append(pick)
                self.rng.shuffle(self.library)
                return


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
            kill(opp, tgt, me)
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
        def prio(c):
            code = c[:-1]
            other = {"K1": "K2", "K2": "K1"}.get(code)
            combo_now = other and (me.has(other) or (any(h[:-1] == other for h in me.hand)
                                                     and mana >= 6))
            need_piece = code == "T2" and not (me.has("K1") and me.has("K2"))
            return (bool(combo_now), code == "M2" and me.n_lands <= 5, need_piece,
                    code == "P3", code in STATS and code not in ("K1", "K2"), COST[code])
        # combo if we can, ramp while short on lands, tutor, lords, other creatures,
        # then card draw; lone combo pieces wait for their partner
        castable.sort(key=prio, reverse=True)
        card = castable[0]
        code = card[:-1]
        me.hand.remove(card)
        mana -= COST[code]
        if code in STATS:
            me.board.append(Creature(code))
            refresh(me.board)
        elif code == "T2":
            me.tutor()
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
    ready = [c for c in att.board if not c.sick and c.code not in ("K1", "K2")]
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
        a_dies, b_dies = choice.power >= a.tough, a.power >= choice.tough
        if a_dies:
            kill(att, a, dfn)
        if b_dies:
            kill(dfn, choice, att)
    for a in unblocked:
        dfn.life -= a.power
        att.dealt["flyers" if a.flying else "ground"] += a.power


def _reason(p):
    d = p.dealt
    return max(d, key=d.get) if any(d.values()) else "ground"


def play_game(deck_a, deck_b, rng, a_first=True, mulligan=True, life=20, colors=2):
    """Returns (winner_index 0/1, turns, statsA, statsB, how_it_was_won)."""
    p = [Player(deck_a, rng, mulligan, life, colors), Player(deck_b, rng, mulligan, life, 2)]
    order = [0, 1] if a_first else [1, 0]
    for turn in range(1, MAX_TURNS + 1):
        for i in order:
            me, opp = p[i], p[1 - i]
            if not (turn == 1 and i == order[0]):
                me.draw()
            if me.decked:
                return 1 - i, turn, p[0].stats, p[1].stats, "decking"
            me.land_drop = False
            # combo pieces must survive a full turn cycle (the opponent's window to answer)
            if me.has("K1") and me.has("K2"):
                return i, turn, p[0].stats, p[1].stats, "combo"
            for c in me.board:
                c.sick = False
            combat(me, opp)
            if opp.life <= 0:
                return i, turn, p[0].stats, p[1].stats, _reason(me)
            main_phase(me, opp)
            if opp.life <= 0:
                return i, turn, p[0].stats, p[1].stats, "drain"
            if me.life <= 0:
                return 1 - i, turn, p[0].stats, p[1].stats, _reason(opp)
            if turn == 4:
                me.stats["screw"] = me.n_lands <= 2
                me.stats["flood"] = len(me.hand_lands()) >= 3
    # timeout: higher life wins, coin flip on tie
    w = (0 if p[0].life > p[1].life else 1) if p[0].life != p[1].life else rng.randint(0, 1)
    return w, MAX_TURNS, p[0].stats, p[1].stats, "timeout"


def match(deck_a, deck_b, games, seed, mulligan=True, life=20, a_first=None, colors=2):
    """Play `games` games alternating who goes first. Returns A's win rate and extras,
    including how A's wins and losses happened."""
    rng = random.Random(seed)
    wins = turns = screw = flood = stuck = 0
    won, lost = {}, {}
    for g in range(games):
        first = (g % 2 == 0) if a_first is None else a_first
        w, t, sa, _, how = play_game(deck_a, deck_b, rng, a_first=first,
                                     mulligan=mulligan, life=life, colors=colors)
        wins += (w == 0)
        bucket = won if w == 0 else lost
        bucket[how] = bucket.get(how, 0) + 1
        turns += t
        screw += sa["screw"]
        flood += sa["flood"]
        stuck += sa["stuck"] > 0
    return {"win": wins / games, "turns": turns / games,
            "screw": screw / games, "flood": flood / games, "color_stuck": stuck / games,
            "won_by": {k: v / games for k, v in won.items()},
            "lost_to": {k: v / games for k, v in lost.items()}}
