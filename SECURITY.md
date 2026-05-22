# Security Policy

## Supported Versions

Security fixes target the latest public version of Agent Primer.

## Report A Vulnerability

Open a private security advisory on GitHub if available. If advisories are not available, open an issue with minimal reproduction details and avoid posting secrets, API keys, private repo paths, or generated context from private codebases.

## Security Model

Agent Primer is local-first:

- The GUI binds to `127.0.0.1`.
- Target project dependencies are never installed.
- Target application code is never modified by setup or verification modes.
- OpenRouter keys are stored in the local user config file with `0600` permissions.
- API keys are never written to target repositories.
- Existing context files are preserved unless overwrite is explicitly enabled.

## Out Of Scope

- Vulnerabilities in target repositories scanned by Agent Primer.
- Browser vulnerabilities in the system browser used to open the local GUI.
- Model-provider behavior outside Agent Primer's request payload and response validation.
