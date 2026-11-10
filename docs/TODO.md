# TODO

## Next action
Start Milestone 2 (see the end of `IMPLEMENTATION_STATUS.md`).

## Needs a decision from the owner
- Remove `bun.lockb` (keep npm only)?
- Real credentials needed later: LLM key (M4), maps/routing key (M5), weather key (M6), Sarvam/Azure speech (M7), payment sandbox (M8). Until then the adapters will be explicit dev adapters.

## Deferred / not yet in scope
- Email verification and password reset.
- Redis-backed rate limiter (currently in-process).
- Verify Docker build and compose on a machine with a running daemon.
- Browser E2E (Playwright), Milestone 9.
- Code-split the 1 MB bundle (Milestone 2).
