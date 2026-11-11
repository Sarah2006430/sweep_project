# Expected results for the synthetic demo clip

`floor.mp4` is a synthetic 70-second clip made by `tools/make_demo_clip.py` (960x540, 15 fps). It is not real footage.
`reference.jpg` is its first frame, an empty floor. Settings: `backend/config.json` as shipped (diff detector, `confirm_s` 3, `ticket_after_s` 15, `clean_after_s` 5).

## What happens in the clip

| Footage time | Event in the scene |
|---|---|
| 0 to 10 s | Empty floor. Both zones score 100. |
| 4 to 14 s | Two passers-by cross the frame. Expected: no ticket, no score change. |
| 14 to 26 s | A visitor drops four items: bottle (Entrance), wrapper (Entrance), can (Seating area), paper ball (Seating area). |
| 30 to 40 s | Two more passers-by cross while the litter is on the floor. Expected: no extra tickets. |
| 46 to 63 s | A cleaner picks the items up in turn: paper, can, wrapper, bottle. |
| 63 to 70 s | Empty floor again. Scores return to about 100. |

## Expected tickets

Measured on this clip, in footage seconds. Allow about 3 seconds either way, since timing depends on frame stride and detector noise.

| Ticket | Item | Zone | Opens at | Closes at |
|---|---|---|---|---|
| 1 | Bottle | Entrance | 30.7 s | 61.6 s |
| 2 | Wrapper | Entrance | 33.9 s | 58.9 s |
| 3 | Can | Seating area | 38.0 s | 56.0 s |
| 4 | Paper ball | Seating area | 42.4 s | 52.8 s |

Exactly four tickets open and four close. All are type Litter, priority Low, and close automatically once the item has been gone for 5 seconds.

## Expected zone scores

Lowest scores seen during the clip: Entrance 60, Seating area 66. Both are back at 100 (or within a few points) by the end.

## How this was checked

`python tests/test_demo_clip.py` regenerates the clip and asserts four opens and four cleans. `python tests/test_logic.py` covers the rules on their own.

## Limits

This clip has a fixed camera, even lighting and cartoon-style figures, so it is easier than real footage. These numbers show the workflow works. They are not an accuracy measurement, and real footage will need threshold tuning.
