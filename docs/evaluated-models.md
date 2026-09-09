# Evaluated models and pricing

This catalog mirrors the technical comparison published on the UniAIBench
website. It identifies the **14 model--mode configurations** in the matched
60-item panel and separates two different price concepts:

- **latest verified API rate:** the standard first-party rate manually checked
  on **31 August 2026**;
- **benchmark rate:** the frozen rate used to estimate the study costs on
  **14 August 2026**.

Prices are in USD per one million tokens and show input before output. They are
not live prices. Cached input, batch, regional, tax, tool, and priority-processing
charges are omitted unless the exception materially changes the comparison.

## Identity and benchmark setup

| Model | Provider | Exact API identifier / configuration | Public release | Open weights | Benchmark reasoning mode |
|---|---|---|---|:---:|---|
| [GPT-5.6 Sol](https://openai.com/index/gpt-5-6/) | OpenAI | [`gpt-5.6-sol`](https://developers.openai.com/api/docs/models/gpt-5.6-sol) | 9 Jul 2026; GA, preview 26 Jun 2026 | No | Configurable effort; `xhigh` |
| [OpenAI o3](https://openai.com/index/introducing-o3-and-o4-mini/) | OpenAI | [`o3-2025-04-16`](https://developers.openai.com/api/docs/models/o3) | 16 Apr 2025; dated snapshot | No | Native reasoning; `high` |
| [OpenAI GPT-4.1](https://openai.com/index/gpt-4-1/) | OpenAI | [`gpt-4.1-2025-04-14`](https://developers.openai.com/api/docs/models/gpt-4.1) | 14 Apr 2025; dated snapshot | No | No native reasoning; `none` |
| [Claude Fable 5](https://www.anthropic.com/news/claude-fable-5-mythos-5) | Anthropic | [`claude-fable-5`](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5) | 9 Jun 2026; GA, restored 1 Jul 2026 | No | Adaptive thinking; effort `high` |
| [Claude Sonnet 4.5](https://www.anthropic.com/news/claude-sonnet-4-5) | Anthropic | [`claude-sonnet-4-5-20250929`](https://platform.claude.com/docs/en/about-claude/models/overview) | 29 Sep 2025; dated snapshot | No | Optional extended thinking; provider default |
| [Claude Haiku 4.5](https://www.anthropic.com/news/claude-haiku-4-5) | Anthropic | [`claude-haiku-4-5-20251001`](https://platform.claude.com/docs/en/about-claude/models/overview) | 15 Oct 2025; API snapshot 1 Oct 2025 | No | Extended thinking available; not requested |
| [Gemini 3.5 Flash](https://deepmind.google/models/model-cards/gemini-3-5-flash/) | Google | [`gemini-3.5-flash`](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash) | 19 May 2026; GA | No | Native thinking; `high` |
| [Gemini 3.1 Pro Preview](https://deepmind.google/models/gemini/pro/) | Google | [`gemini-3.1-pro-preview`](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview) | 19 Feb 2026; public preview | No | Native thinking; `high` |
| [Gemma 4 31B IT](https://ai.google.dev/gemma/docs/core/model_card_4) | Google | [`gemma-4-31b-it`](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api) | 31 Mar 2026; API 2 Apr 2026 | Yes | Thinking available; disabled |
| [DeepSeek V4 Flash](https://api-docs.deepseek.com/news/news260424/) | DeepSeek | [`deepseek-v4-flash`, thinking](https://api-docs.deepseek.com/api/create-chat-completion) | 24 Apr 2026; V4 preview | Yes | Thinking enabled; `high` |
| [DeepSeek V4 Flash (no thinking)](https://api-docs.deepseek.com/news/news260424/) | DeepSeek | [`deepseek-v4-flash`, no thinking](https://api-docs.deepseek.com/guides/thinking_mode) | 24 Apr 2026; same weights | Yes | Thinking disabled |
| [DeepSeek V4 Pro](https://api-docs.deepseek.com/news/news260424/) | DeepSeek | [`deepseek-v4-pro`](https://api-docs.deepseek.com/api/create-chat-completion) | 24 Apr 2026; V4 preview | Yes | Thinking enabled; `high` |
| [Grok 4.5](https://x.ai/news/grok-4-5) | xAI | [`grok-4.5`](https://docs.x.ai/developers/models/grok-4.5) | 16 Jul 2026; public launch | No | Configurable reasoning; `high` |
| [Grok 4.3](https://x.ai/news/grok-amazon-bedrock) | xAI | [`grok-4.3`](https://docs.x.ai/developers/models/grok-4.3) | By 6 May 2026; earliest dated official use identified | No | Configurable reasoning; `high` |

The two DeepSeek V4 Flash rows are distinct benchmark configurations of the
same model weights.

## Technical specifications

| Model | Parameters | Architecture / model class | Context | Maximum output | Knowledge / training cutoff |
|---|---|---|---:|---:|---|
| GPT-5.6 Sol | Not disclosed | Closed frontier flagship; architecture undisclosed | 1,050,000 | 128,000 | 16 Feb 2026 knowledge |
| OpenAI o3 | Not disclosed | Closed o-series reasoning model; architecture undisclosed | 200,000 | 100,000 | 1 Jun 2024 knowledge |
| OpenAI GPT-4.1 | Not disclosed | Closed general-purpose non-reasoning model | 1,047,576 | 32,768 | 1 Jun 2024 knowledge |
| Claude Fable 5 | Not disclosed | Closed Mythos-class safeguarded model | 1,000,000 | 128,000 | Jan 2026 reliable/training |
| Claude Sonnet 4.5 | Not disclosed | Closed Sonnet-tier hybrid reasoning model | 200,000 | 64,000 | Not disclosed |
| Claude Haiku 4.5 | Not disclosed | Closed small and low-latency tier | 200,000 | 64,000 | Feb/Jul 2025 reliable/training |
| Gemini 3.5 Flash | Not disclosed | Closed multimodal Flash-tier model | 1,048,576 | 65,536 | Jan 2025 knowledge |
| Gemini 3.1 Pro Preview | Not disclosed | Closed multimodal Pro-tier model | 1,048,576 | 65,536 | Jan 2025 knowledge |
| Gemma 4 31B IT | 30.7B total; dense; 60 layers; about 550M vision encoder | Dense decoder-only transformer; hybrid local/global attention | 256,000 | Not specified | Jan 2025 training |
| DeepSeek V4 Flash | 284B total; 13B active per token | Mixture-of-Experts; DeepSeek Sparse Attention | 1,000,000 | 384,000 | Not disclosed |
| DeepSeek V4 Flash (no thinking) | 284B total; 13B active per token | Mixture-of-Experts; DeepSeek Sparse Attention | 1,000,000 | 384,000 | Not disclosed |
| DeepSeek V4 Pro | 1.6T total; 49B active per token | Mixture-of-Experts; DeepSeek Sparse Attention | 1,000,000 | 384,000 | Not disclosed |
| Grok 4.5 | Not disclosed | Closed frontier model; architecture undisclosed | 500,000 | Not specified | 1 Feb 2026 knowledge |
| Grok 4.3 | Not disclosed | Closed general-purpose model; architecture undisclosed | 1,000,000 | Not specified | Not disclosed |

## Pricing

| Model | Latest verified standard API rate | Benchmark rate | Official pricing source |
|---|---|---|---|
| GPT-5.6 Sol | Input $4; cached input $0.40; output $20; promotional rate, higher long-context rates apply | Input $5; output $30 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |
| OpenAI o3 | Input $2; cached input $0.50; output $8 | Input $2; output $8 | [OpenAI](https://developers.openai.com/api/docs/models/o3) |
| OpenAI GPT-4.1 | Input $2; cached input $0.50; output $8 | Input $2; output $8 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-4.1) |
| Claude Fable 5 | Input $10; output $50 | Input $10; output $50 | [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude Sonnet 4.5 | Input $3; output $15 | Input $3; output $15 | [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing) |
| Claude Haiku 4.5 | Input $1; output $5 | Input $1; output $5 | [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing) |
| Gemini 3.5 Flash | Input $1.50; cached input $0.15; output $9 | Input $1.50; output $9 | [Google](https://ai.google.dev/gemini-api/docs/pricing) |
| Gemini 3.1 Pro Preview | Input $2; output $12; over 200k: $4 / $18 | Input $2; output $12 | [Google](https://ai.google.dev/gemini-api/docs/pricing) |
| Gemma 4 31B IT | Free tier $0; paid tier unavailable | Input $0; output $0 | [Google](https://ai.google.dev/gemini-api/docs/pricing) |
| DeepSeek V4 Flash | Off-peak $0.22 / $0.66; peak $0.44 / $1.32 | Input $0.14; output $0.28 | [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) |
| DeepSeek V4 Flash (no thinking) | Off-peak $0.22 / $0.66; peak $0.44 / $1.32 | Input $0.14; output $0.28 | [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) |
| DeepSeek V4 Pro | Off-peak $0.66 / $1.98; peak $1.32 / $3.96 | Input $0.435; output $0.87 | [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) |
| Grok 4.5 | Input $2; cached input $0.30; output $6; over 200k: $4 / $12 | Input $2; output $6 | [xAI](https://docs.x.ai/developers/models/grok-4.5) |
| Grok 4.3 | Input $1.25; cached input $0.20; output $2.50; over 200k: $2.50 / $5 | Input $1.25; output $2.50 | [xAI](https://docs.x.ai/developers/models/grok-4.3) |

For DeepSeek, the current-rate pairs are cache-miss input / output and vary by
time of day. Gemma's zero benchmark rate was explicitly configured for the
campaign and is not a universal market price. Benchmark requests to Gemini 3.1
Pro Preview used the standard context tier.

The frozen rates used by the analysis are also available in
[`analysis/tables/tariffe_token_costi.csv`](../analysis/tables/tariffe_token_costi.csv),
while per-model observed token and cost summaries are in
[`analysis/tables/token_costi_modelli_14x60.csv`](../analysis/tables/token_costi_modelli_14x60.csv).
