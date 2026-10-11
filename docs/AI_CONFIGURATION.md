# AI mentor configuration

The core product is offline-first. All built-in mission descriptions, three-step hints, validators, notebook and progress tracking work without an API key. The AI adapter is optional and uses an OpenAI-compatible `/chat/completions` endpoint.

## Configure it

Open **Settings & Lab → AI mentor**, enter:

- Provider profile name (just a label)
- Base URL, such as a provider's HTTPS `/v1` endpoint or a local compatible model service at `http://127.0.0.1:PORT/v1`
- Model identifier expected by that endpoint
- Optional API key
- Request timeout between 3 and 120 seconds

Save settings and use **Test connection**. The key is stored outside the project at `~/.config/redpanda-labs/ai.json`, with intended mode `0600`. Read/write failures or broad permissions should surface a warning. File permissions are not encryption. Do not store keys in a frontend, browser storage, Git, challenge pack, or SQLite export.

Remote providers must use HTTPS. Plain HTTP is only accepted for local endpoints. Redirects are blocked so a configured endpoint cannot redirect an authorization-bearing request elsewhere. Connection failures, bad credentials, rate limits and timeouts are intended to return user-safe errors.

## Privacy

Mentor requests include challenge learning context and the user's question. Selected terminal output is only sent after the UI explains that content is going to the selected endpoint and the user confirms. Do not share credentials, tokens, personal files, environment variables, or unrelated history. The app does not automatically send a whole shell transcript.

## Offline fallback

Use the hint ladder in the challenge workspace or read the mission's learning material. AI output is never run as a shell command and cannot mark a challenge complete; the backend validator is the authority for completion.
