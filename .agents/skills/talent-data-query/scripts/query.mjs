#!/usr/bin/env node
// Repository-installed Skill entrypoint; outputs always remain in the caller's workspace.
import { runCli } from '../../../../scripts/talent-data-query.mjs'
await runCli()
