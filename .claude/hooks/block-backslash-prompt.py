#!/usr/bin/env python3
r"""UserPromptSubmit hook: reject prompts that start with a backslash.

Catches the common typo of reaching for `\` instead of `/` when invoking a
slash command. The prompt is blocked (never sent to the model) and the user
gets a short reminder.
"""

import json
import sys

payload = json.load(sys.stdin)
prompt = payload.get("prompt", "")

if prompt.lstrip().startswith("\\"):
    print(json.dumps({
        "decision": "block",
        "reason": (
            "Message starts with `\\`. Claude Code commands are invoked with `/` "
            "(e.g. `/help`, `/config`, `/code-review`). "
            "Type the command with `/`, or if this was really plain text, "
            "remove the leading `\\`."
        ),
    }))

sys.exit(0)
