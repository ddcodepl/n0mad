---
page_id: 2450fc11-d335-8066-9794-c550c4d501b1
title: Add option to use OpenRouter with new model format
ticket_id: NOMAD-19
stage: pre-refined
generated_at: 2025-08-04 10:13:38
---

We should extend current functionality in the system which allows us to refine prompts with openai, we should add option to use open router as well 

Models are provided in property Model as status in format provider/model eg. openai/o3

we should split the text at / and check provider if provider is openai, we should ask directly openai, if model is different we should ask openrouter to process it in the same way

default model should be openai/o4-mini

open router api key is stored in .env as OPENROUTER_API_KEY
openai key is stored as OPENAI_API_KEY