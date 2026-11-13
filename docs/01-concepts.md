# 01 — Concepts

## The problem

A 12-year-old's 22:00 for 5 km and a 55-year-old's 22:00 for 5 km are not the
same achievement. Neither is a 40:00 10 km and a 3:00 marathon. Age grading
answers two questions with one number:

1. **How good was this performance, given the athlete's age and sex?**
2. **How do two performances compare when age, sex or distance differ?**

The answer is a percentage where **100% means "as good as the world-standard
performance for that exact age"**. 80% means "took 25% longer than that
standard" (because 100/80 = 1.25). Everything else is arithmetic.

## The four quantities

Age grading needs exactly one table per (sex, distance): a list of **factors**,
one per age from 5 to 100. From a factor and the distance's open standard,
everything else follows.

### 1. Open standard — `S_open`

The world-standard time for the distance, in seconds, with **no age
adjustment** — the "open class" mark. In the 2025 road tables these are the
world records at 5 km, 10 km, half marathon and marathon; at the other
distances they are records adjusted slightly by eye so that pace varies
smoothly with distance ([04-methodology.md](04-methodology.md)).

```
5 km   M 12:49  F 13:54
10 km  M 26:24  F 28:46
Half   M 57:31  F 1:02:52
Mara   M 2:00:35  F 2:09:56
```

### 2. Age factor — `f(age, distance)`

A dimensionless multiplier in `(0, 1]` that converts a performance at a given
age into its open-class equivalent.

* `f = 1` across a plateau of "prime" ages where the world standard is set.
  The plateau is **not** the same for every distance or sex, and it shrinks as
  distances get longer for women:

  | | male | female |
  | --- | --- | --- |
  | 1 mile | 19–29 | 19–34 |
  | 5 km | 19–29 | 19–26 |
  | 10 km, 20 km | 21–30 | 21–27 |
  | half marathon | 20–31 | 22–27 |
  | marathon … 200 km | 22–35 | **26–27** |

* `f < 1` for children, teenagers and masters — the older or younger you are,
  the smaller the factor, because your time has to be *reduced* more before it
  can be compared with an adult record.
* `f` is **never above 1**: by construction the standard is at least as fast as
  any age best, so the factor can only pull a time down.

### 3. Age standard — `S_age`

The time that scores 100% for that age and distance — i.e. the world standard
translated to that age:

```
S_age = S_open / f
```

A 75-year-old man's marathon age standard is `7235 s / 0.6857 = 10551 s`
≈ **2:55:51**.

### 4. Age grade — `P`

The percentage. Two definitions, mathematically identical:

```
P = 100 × S_age / T          where T is the performance time
P = 100 × S_open / (T × f)
```

And the **age-graded time**:

```
T_graded = T × f
```

so that `P = 100 × S_open / T_graded`. The age-graded time is the time the same
effort would have produced at open-class age.

```
Male, age 40, 10 km, 40:00
  S_open  = 1584 s        (26:24)
  f       = 0.9636
  S_age   = 1643.8 s      (27:23.8)
  T_graded= 2312.6 s      (38:32.6)
  P       = 100 × 1643.8 / 2400 = 68.49 %
```

## Percentages above 100

`P > 100` means the athlete beat the age standard — a genuine outlier, a record,
or a course/measurement problem. It is arithmetic, not an error, and it happens:

| Male, 10 km | 32:00 run |
| --- | --- |
| age 25 | 82.50% |
| age 45 | 89.08% |
| age 65 | **106.30%** |
| age 75 | **119.08%** |

A grading system is *too soft* at an age if ordinary good performances score
above 100 there; that is precisely the failure mode that forced the 2010
revision of the women's long-distance tables ([09-history.md](09-history.md)).

## What the percentage is not

* **Not a rank.** It compares a performance to a standard, not to other
  entrants. A 65% can win a small race.
* **Not a prediction of an absolute time at another distance.** It says the
  *effort* is equivalent, not that the athlete could physically run the other
  distance at the implied pace.
* **Not sex-neutral.** Male and female tables are separate and are not
  comparable across the divide — a 75% female mark and a 75% male mark are both
  "75% of their own standard", nothing more.
* **Not stable over time.** It is a function of one f-t curve per distance per
  sex; when the tables are revised, historical percentages move slightly.

## Same thing, different names

Age grading has been through several governing bodies, so the vocabulary moves.
A translation table is in [glossary.md](glossary.md). The short version:

| Concept | Names in the wild |
| --- | --- |
| `P` | age grade, age-graded percentage, age percentage, PLP, wma% |
| `T_graded` | age-graded time, age-adjusted time, equivalent open time |
| `S_age` | age standard, age record, age-graded standard |

## Why the tables are needed at all

The factor for each (age, distance) is not derivable from a formula you can
look up — it is a **fitted curve over observed single-age bests**, refitted
periodically as records fall ([04-methodology.md](04-methodology.md)). That is
why implementations ship the tables as data and never try to recompute them
from first principles at runtime.
