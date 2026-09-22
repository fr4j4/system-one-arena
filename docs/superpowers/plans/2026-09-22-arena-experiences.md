# Arena experiences implementation plan

Approved design: separate turn-based games, continuous worlds and dataset processing. Keep model adapters neutral. Hide technical scheduling knobs from normal use. Add substantial, transparently synthetic ticket/email/phishing datasets, reproducible sampling, readable paginated results and matched-case comparisons.

1. Execution policy: scenario execution metadata, technical timeout for turns/batches, realtime deadlines only for continuous worlds; stop semantics preserved. Tests for slow turns and batch failure progression.
2. Data: versioned synthetic scenario families with explicit provenance, reference rationales and difficulty; contextual variations identified as such, not independent real-world observations. Random/balanced sampling without replacement, requested size capped by availability. Preserve source IDs and sample manifest. CSV/JSONL import.
3. Results: per-case timing, status, labels, route and probability; paginated/filterable/sortable tables, details and exports. No accuracy for unlabeled cases. Side-by-side provider decisions aligned by sampled IDs.
4. Controls: automatic/manual turns; play/evaluate speed for realtime; sample controls for datasets. Technical knobs only in advanced realtime settings. Pause/stop/restart visible.
5. Verification: protocol/runtime/data unit and integration tests, production build, browser checks for each experience, live Jev smoke, docs and push. Restart local server with final code.

Completed: all five implementation steps; 80 backend tests, 9 browser tests, production build/lint, visual inspection, and isolated Jev smoke across the three expanded corpora. The other business domains remain explicitly labeled starter sets, with full import/sampling/table support.
