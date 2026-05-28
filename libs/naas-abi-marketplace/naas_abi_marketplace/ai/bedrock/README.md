# Bedrock Module

## Overview

The Bedrock module provides integration with **Amazon Bedrock**, AWS's fully managed
service for accessing leading foundation models through a single API. It lets ABI agents
invoke models from Anthropic (Claude), Meta (Llama), Amazon (Nova/Titan), Mistral, AI21,
Cohere, and others without managing infrastructure.

## Provider: Amazon Web Services (AWS)

**Service**: Amazon Bedrock
**Launched**: 2023
**Focus**: Managed, serverless inference for foundation models with enterprise security,
data isolation, and IAM-based access control.

## Why Bedrock?

- **Unified API** across multiple model providers.
- **No data retention** by AWS for inference requests.
- **VPC / PrivateLink** support for enterprise networking.
- **IAM-based access control** and CloudTrail audit logging.
- **Regional availability** lets you keep data in a specific geography.

## Configuration

Add the module to your config file:

```yaml
modules:
  - module: naas_abi_marketplace.ai.bedrock
    enabled: true
    config:
      aws_access_key_id: "{{ secret.AWS_ACCESS_KEY_ID }}"
      aws_secret_access_key: "{{ secret.AWS_SECRET_ACCESS_KEY }}"
      aws_session_token: "{{ secret.AWS_SESSION_TOKEN }}"  # optional
      region_name: "us-east-1"
      validate_on_load: true                               # optional, default true
      validation_model_id: null                            # optional, e.g. "anthropic.claude-3-5-haiku-20241022-v1:0"
```

If `aws_access_key_id` / `aws_secret_access_key` are omitted, the underlying boto3 client
falls back to the standard AWS credential resolution chain (environment variables,
shared credentials file, ECS/EKS container credentials, EC2 IMDS, etc.).

## Startup validation

When `validate_on_load` is `true` (the default), the module verifies on load that:

1. `boto3` can resolve AWS credentials from any source in the chain,
2. `sts:GetCallerIdentity` succeeds (credentials are usable),
3. `bedrock:ListFoundationModels` succeeds in `region_name` (Bedrock is reachable
   and the principal has Bedrock permissions),
4. *(Optional)* if `validation_model_id` is set, a 1-token `Converse` call is made
   against that model to prove model-level access has been granted in the Bedrock
   console.

On failure, the module raises `BedrockValidationError` and the application will not
start — surfacing IAM / IMDS / region issues at deploy time instead of mid-conversation.

To disable (e.g. for offline development), set `validate_on_load: false` in config,
or export `BEDROCK_SKIP_VALIDATION=1` in the environment.

Validation is also auto-skipped when `PYTEST_CURRENT_TEST` is set, so unit tests that
import the module do not require live AWS access.

## Installation

This module depends on `langchain-aws`. Install the optional extra:

```bash
uv pip install "naas-abi-marketplace[ai-bedrock]"
```

## Available Models

| File | Bedrock Model ID |
| --- | --- |
| `models/claude_sonnet_4_bedrock.py` | `anthropic.claude-sonnet-4-20250514-v1:0` |
| `models/claude_haiku_3_5_bedrock.py` | `anthropic.claude-3-5-haiku-20241022-v1:0` |
| `models/llama_3_3_70b_bedrock.py` | `meta.llama3-3-70b-instruct-v1:0` |
| `models/nova_pro_bedrock.py` | `amazon.nova-pro-v1:0` |
| `models/gemini_2_5_pro_bedrock.py` | `us.google.gemini-2-5-pro-v1:0` |
| `models/gemma_3_27b_it_bedrock.py` | `google.gemma-3-27b-it-v1:0` |
| `models/gpt_oss_120b_bedrock.py` | `openai.gpt-oss-120b-1:0` |

## Embedding Models

| File | Bedrock Model ID |
| --- | --- |
| `models/titan_embed_text_v2_bedrock.py` | `amazon.titan-embed-text-v2:0` |

Each model is exposed as a `naas_abi_core.models.Model.ChatModel` and wraps
`langchain_aws.ChatBedrockConverse` so it can be dropped into any LangChain / LangGraph
pipeline.

## Agent

`agents/BedrockAgent.py` exposes a `create_agent()` factory returning an `IntentAgent`
that defaults to Gemma 3 27B Instruct on Bedrock. Swap the imported model to use another
foundation model.

## Requirements

- AWS account with **Bedrock access enabled** in the chosen region.
- Each foundation model must be **explicitly granted access** in the AWS console
  (Bedrock → Model access).
- IAM principal with `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`
  permissions.
