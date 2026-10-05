# 04: Use and transfer authoritative items

**What to build:** A player can take, use, and consume only items carried in inventory or available in the current surroundings, with every quantity change persisted as replayable state.

**Blocked by:** 03: Reject unavailable action targets before DM resolution.

**Status:** ready-for-agent

- [ ] Taking a portable nearby item transfers its declared quantity from the current Location into inventory.
- [ ] Using an item validates its stable ID and availability before the DM narrates an outcome.
- [ ] Consumable use deducts quantity deterministically and removes zero-quantity stacks without permitting underflow.
- [ ] Non-portable, unavailable, remote, and exhausted items return a Tool error and cannot mutate state.
- [ ] Turn output and subsequent intent validation immediately reflect inventory and surroundings changes.
- [ ] Inventory and surroundings rebuild identically from the Event log.
- [ ] Automated tests cover take, use, consume, invalid use, quantity boundaries, streaming state changes, and replay.
