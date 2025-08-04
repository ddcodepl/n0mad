---
page_id: 2450fc11-d335-8066-9794-c550c4d501b1
title: Add option to use OpenRouter with new model format
ticket_id: NOMAD-19
stage: refined
generated_at: 2025-08-04 10:13:49
---

# NOMAD-19 Add option to use OpenRouter with new model format

## Overview
Extend the prompt refinement feature to support routing requests to either OpenAI or OpenRouter based on the configured model identifier (`provider/model`). This enables use of alternative model providers without altering existing workflows.

## Acceptance Criteria
- [ ] **AC1:** Codebase Recon completed; relevant modules/files/services, integration points, and impacted dependencies identified and documented.
- [ ] **AC2:** Feature behavior implemented and verified within existing architecture with regression-safe tests.
- [ ] **AC3:** Performance/quality requirement measured with agreed thresholds and documented.

## Technical Requirements

### Core Functionality
- **Codebase Recon:** Analyze the existing codebase to identify the prompt refinement module (e.g., services or utilities handling OpenAI calls), configuration loaders for environment variables, and test suites.
- Parse the model string in the format `provider/model` by splitting on `/`.
- If `provider` equals `openai`, invoke the existing OpenAI request flow using the extracted `model`.
- If `provider` is not `openai`, route the request to OpenRouter, passing the `model` segment as target model.
- Default to `openai/o4-mini` when no model is specified.
- Validation: Ensure `provider` and `model` strings are non-empty and conform to expected patterns.
- Error handling: Surface clear errors when keys are missing, provider unknown, or external API responds with an error.

### Integration Points
- Modify the existing prompt refinement service/module that currently handles OpenAI integration.
- Enhance the configuration loader to read `OPENROUTER_API_KEY` in addition to `OPENAI_API_KEY` from environment.
- Update internal interfaces to accept a `model` parameter in the form `provider/model`.
- Ensure dependency versions for HTTP client (if any) are compatible with both OpenAI and OpenRouter endpoints.

### Data Requirements
- No schema changes required.
- No data migration necessary.
- Validate incoming model strings at the service boundary to prevent malformed requests.

## Implementation Approach

### Architecture & Design
- Introduce a routing layer within the prompt refinement service:
  1. Extract `provider` and `modelName` from the full model identifier.
  2. Switch on `provider`:
     - `openai` → call existing `callOpenAI(modelName, prompt)`.
     - others → call new `callOpenRouter(modelName, prompt)`.
- Encapsulate OpenRouter HTTP logic in a new helper function/class aligned with the existing code’s structure.
- Follow existing error handling and retry/backoff patterns used for OpenAI requests.
- Reuse existing configuration module to fetch API keys and timeouts.

## Performance & Scalability
- Expected request rate remains unchanged; additional routing logic introduces minimal overhead.
- Measure latency before and after change; ensure end-to-end response time increase is within acceptable threshold (e.g., <5%).
- Leverage existing connection pooling or HTTP client reuse for OpenRouter as done for OpenAI.

## Security Considerations
- Ensure `OPENROUTER_API_KEY` is never logged or exposed.
- Validate both provider and model inputs to guard against injection attacks.
- Use secure transport for API calls (HTTPS).
- Confirm compliance with data handling policies for both providers.

## Complexity Estimate
**Medium** - Requires careful integration into existing prompt service, validation of inputs, and addition of a parallel request flow with error handling matching current standards.

## Additional Notes
- Information Needed:
  - Exact file paths or module names for the current prompt refinement implementation.
  - Details on existing configuration loader to integrate new environment variable.
  - Preferred test framework and conventions to add regression tests.
- Dependencies:
  - None beyond existing HTTP/request client.
- Risks & Mitigations:
  - Misrouting requests due to malformed model strings – mitigate with strict validation and fallback default.
  - API key misconfiguration – validate presence at startup.
- Future Enhancements:
  - Support provider-specific options (e.g., custom headers or endpoint overrides).
  - Metrics collection per provider for usage tracking.