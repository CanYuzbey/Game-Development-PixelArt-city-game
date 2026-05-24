# Mapping System Index

This folder groups the existing procedural mapping structure.

Source of truth:

- `map_builder/`: production generator, phases, state, constants, tile registry.
- `Info_memory/mapping.txt`: older technical reference and history.
- `docs/MASTER_MIND.md`: current high-level project brain.
- `docs/PERFECTION_REPORT.md`: prior convergence report and quality targets.
- `tests/full_suite.py`: primary quality gate.
- `tests/diag.py`: diagnostic quality report.

The existing system remains the procedural city generator. New work for turning
generated mapping data into existing-city-inspired design output lives in
`existing_city_mapping/`.
