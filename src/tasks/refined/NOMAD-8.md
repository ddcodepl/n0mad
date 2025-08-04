---
page_id: 2450fc11-d335-804d-8b56-edb5cc07ea03
title: Add option to use openrouter awith default open router
ticket_id: NOMAD-8
stage: refined
generated_at: 2025-08-04 07:48:33
---

# NOMAD-8 Add option to use OpenRouter for prompt refinement

## Overview
Extend the existing prompt refinement service to support routing requests to OpenRouter in addition to OpenAI, enabling multi-provider flexibility and a configurable default model.

## Acceptance Criteria
- [ ] **AC1:** If `model` property prefix is `openai`, route request to OpenAI API; otherwise route to OpenRouter API.
- [ ] **AC2:** Default model is `openai/o4-mini` when no model is specified.
- [ ] **AC3:** End-to-end prompt refinement latency remains under 1 second for 90th percentile.

## Technical Requirements

### Core Functionality
- Parse incoming model identifier string in format `<provider>/<model>`.
- If `provider === "openai"`, invoke OpenAI completion endpoint:  
  • Endpoint: `https://api.openai.com/v1/chat/completions`  
  • Input: `{ model: string, messages: Message[] }`  
  • Output: `{ choices: [{ message: Message }] }`  
- If `provider !== "openai"`, invoke OpenRouter completion endpoint:  
  • Endpoint: `https://openrouter.ai/api/v1/chat/completions`  
  • Input: `{ model: string, messages: Message[] }`  
  • Output: `{ choices: [{ message: Message }] }`  
- Validate that `provider` and `model` are non-empty strings matching `/^[a-z0-9_-]+$/i`.

### Integration Points
- OpenAI API using existing OpenAI SDK (version ^4.0.0).
- OpenRouter API via HTTP client (e.g., axios v1.x or openrouter-node-client v2.x).
- Environment variables:  
  • `OPENAI_API_KEY` for OpenAI  
  • `OPENROUTER_API_KEY` for OpenRouter  
- No additional internal services impacted.

### Data Requirements
- No persistent database schema changes.
- Ensure in-memory request context carries `model` string unchanged.
- Validate and reject requests with malformed `model` identifiers (400 Bad Request).

## Implementation Approach

### Architecture & Design
- Introduce a `PromptRefinementProvider` interface with `refine(messages, model)` method.
- Implement two strategies: `OpenAIRefinementProvider` and `OpenRouterRefinementProvider`.
- Use a Factory or Strategy selector based on parsed provider prefix.
- Integrate into existing prompt refinement service pipeline.

### Technology Stack
- Node.js 16+ with TypeScript 4.x.
- Existing OpenAI SDK (`openai` v4.x).
- HTTP client: `axios` v1.x or `openrouter-node-client` v2.x.
- Environment management: `dotenv` v10.x.
- Testing: Jest v28.x for unit and integration tests.
- Reuse existing logging and error-handling modules.

## Performance & Scalability
- Target 90th percentile response time <1s under 100 RPS.
- Use HTTP keep-alive and connection pooling for outbound API calls.
- Consider circuit breaker (e.g., `opossum` v6.x) for OpenRouter calls.
- Cache recent prompt responses if identical inputs appear within 5 minutes (optional extension).

## Security Considerations
- Retrieve API keys exclusively from `.env`; never log secrets.
- Enforce HTTPS for outbound API calls.
- Validate all inputs to prevent injection.
- Ensure compliance with data residency and privacy policies.
- Rate-limit outbound requests per API provider.

## Complexity Estimate
**Medium** – Introduces new strategy pattern, external HTTP integration, configuration management, and requires thorough testing.

## Additional Notes
- Depends on completion of NOMAD-5 (refactor of prompt refinement service).
- Risk: OpenRouter API downtime; mitigate with circuit breaker and fallback logging.
- Future: Add support for additional providers (e.g., Anthropic, Azure OpenAI).