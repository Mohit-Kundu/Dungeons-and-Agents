# 07: Refresh Recaps only on restore or command

**What to build:** Recap generation no longer runs after every Turn. Loading a previously played Session or explicitly requesting a Recap incrementally refreshes it, while normal Turns finish without Recap latency.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Successful and aborted Turns do not invoke Recap generation or emit an updating-Recap progress phase.
- [x] A locked refresh operation summarizes only successful Turns after the persisted Recap watermark and advances that watermark atomically with the Recap Event.
- [x] Loading a previously played Session refreshes before displaying its Recap and latest exchange; a new Session with no Turns does not call the model.
- [x] `dnd recap` refreshes and displays the Session Recap.
- [x] In-play `/recap` uses the same operation without invoking the DM or recording a Turn.
- [x] Refresh failure preserves and displays the last good Recap without preventing Session load.
- [x] Automated tests cover incremental refresh, repeated no-op refresh, command behavior, restore behavior, model failure, concurrency, Event replay, API, and CLI output.
