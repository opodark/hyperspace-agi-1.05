---
name: hyperspace-image-gate-diagnostic
description: Diagnose chat 503 responses saying the Mac is completing an image; inspect ComfyUI queue and the HyperSpace memory gate, and only close a specifically authorized stale claim when ComfyUI is unreachable.
---

# Diagnosi del gate immagini HyperSpace

When chat returns `Il Mac sta completando un'immagine; riprova fra poco`:

1. Run `python3 scripts/diagnostics/image_gate.py` from the repository root.
2. Compare `in_esecuzione`, active job IDs, `memory_gate.image_job`, its lease,
   `paused` / `auto_paused`, and whether ComfyUI responds.
3. A `running` queue item with an image gate owner can keep chat blocked even
   when there are no pending jobs. Check whether ComfyUI is actually rendering.
4. Keep the queue paused when automatic image work is supposed to be idle/night
   only. Do not restart the Control Plane to clear a stale lease: startup can
   restore a persisted running claim and start a fresh memory lease.
5. Close a job only after confirming it is stale and ComfyUI is unreachable:
   `python3 scripts/diagnostics/image_gate.py --close-stale JOB_ID`. The script
   fails that one claim and releases the memory gate; it does not requeue it.
6. Re-run the read-only diagnostic and confirm no active jobs and an empty gate.

Never print or paste `CHANNEL_CLIENTS` or its token. The diagnostic reads the
Comfy channel token from `.env` or `HYPERSPACE_CHANNEL_TOKEN` and suppresses it.
If ComfyUI responds at all, the cleanup flag refuses to run; inspect the render
instead. A skill is guidance only and does not authorize image creation or queue
changes without the explicit cleanup command.
