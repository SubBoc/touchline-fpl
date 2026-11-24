# What I learned

I chose FPL because I follow football and wanted a concrete way to explore agent development. I scoped the project around historical player research, where the calculations and supporting records can be inspected.

The most useful lesson was to inspect the tool contract alongside the prompt. A well-formed tool call can still use the wrong period, and a complete CSV does not guarantee that the application exposes all of it. I learned to check the executed arguments and configuration before trusting the final answer.

The data model matters just as much. Multiple fixtures in a gameweek are valid observations. Removing them as duplicates loses information; the correct unit is the player-fixture record. I also learned to evaluate historical prices at the requested interval end rather than silently using later prices.

I used Codex to help develop the code, tests and automated checks. My contribution was choosing the problem and scope, directing iterations, reviewing behaviour and manually checking a remembered player result against the CSV. That spot check supports a particular answer; it does not establish general agent accuracy.

I would next add a separately authored evaluation set for task completion and unsupported claims, and make the model transport easier to replace. I would continue to build in small, verifiable steps.
