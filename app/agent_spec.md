# Agent contract

Touchline researches historical midfielder and forward performance in a saved season.
The model selects tools and explains results. Python owns the calculations.

- The controller accepts only `describe_snapshot`, `lookup_players`, `find_players` and `compare_players` JSON actions.
- A comparison ID must have appeared in a tool observation. Invalid actions are returned to the model for correction.
- Statistics use inclusive start/end gameweeks or a trailing window. Common explicit period phrases are protected by a deterministic guard.
- Shortlists require a position and budget. Missing or unsupported scope should trigger clarification.
- Prices and club context come from the latest recorded fixture at or before the interval end.
- Distinct fixtures in double gameweeks are summed. Only fully identical source rows are removed; conflicting player-fixture keys are rejected.
- Missing measurements stay unavailable. Per-match rates use total contributions divided by total minutes, rather than averaging row-level rates.
- The controller bounds requests and subprocess time, disables Copilot built-in tools and MCP servers, and saves prompts, model events, actions, observations and errors locally.

The [dictionary](../fpl_data_taxonomy.json) defines units and formulas.
The [configuration](config.json) pins the source fingerprint and defaults.
The recorded demo replays the [public example](../results/example.json) and accepts only that example question.

The period guard is not a complete language parser. A valid tool action does not guarantee that the model's final answer fulfils the whole request. This is a local prototype; the HTTP server binds to loopback and is not intended for public hosting.
