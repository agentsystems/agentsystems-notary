# AgentSystems Notary

[![PyPI version](https://img.shields.io/pypi/v/agentsystems-notary.svg)](https://pypi.org/project/agentsystems-notary/)

> **Audit logging infrastructure for AI systems**

AgentSystems Notary provides tamper-evident audit trails for AI systems. It creates cryptographically verifiable logs of all LLM interactions with dual-write architecture: your storage bucket (raw logs) + hash storage (verification receipts).

## Features

- **Multi-Framework Support**: LangChain and CrewAI adapters
- **Dual-Write Architecture**: Your bucket (raw logs) + hash storage (receipts)
- **Flexible Hash Storage**: Custodied (AgentSystems API) and/or Arweave (decentralized)
- **Cryptographic Verification**: SHA-256 hashes with JCS canonicalization (RFC 8785)
- **Multi-Tenant Support**: Isolated audit trails for SaaS applications

## Installation

```bash
pip install agentsystems-notary
```

## Quick Start

Copy `.env.example` to `.env` and fill in your credentials.

### LangChain

```bash
pip install langchain-anthropic
```

```python
import os
from agentsystems_notary import (
    LangChainNotary,
    RawPayloadStorage,
    CustodiedHashStorage,
    AwsS3StorageConfig,
)
from langchain_anthropic import ChatAnthropic

notary = LangChainNotary(
    raw_payload_storage=RawPayloadStorage(
        storage=AwsS3StorageConfig(
            bucket_name=os.environ["ORG_AWS_S3_BUCKET_NAME"],
            aws_access_key_id=os.environ["ORG_AWS_S3_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["ORG_AWS_S3_SECRET_ACCESS_KEY"],
        ),
    ),
    hash_storage=[
        CustodiedHashStorage(
            api_key=os.environ["AGENTSYSTEMS_NOTARY_API_KEY"],
            slug="my_tenant",
        ),
    ],
)

model = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    callbacks=[notary],
)

response = model.invoke("What is 2 + 2?")
```

### CrewAI

```bash
pip install crewai
```

```python
import os
from agentsystems_notary import (
    CrewAINotary,
    RawPayloadStorage,
    CustodiedHashStorage,
    AwsS3StorageConfig,
)
from crewai import Agent, Task, Crew, LLM

notary = CrewAINotary(
    raw_payload_storage=RawPayloadStorage(
        storage=AwsS3StorageConfig(
            bucket_name=os.environ["ORG_AWS_S3_BUCKET_NAME"],
            aws_access_key_id=os.environ["ORG_AWS_S3_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["ORG_AWS_S3_SECRET_ACCESS_KEY"],
        ),
    ),
    hash_storage=[
        CustodiedHashStorage(
            api_key=os.environ["AGENTSYSTEMS_NOTARY_API_KEY"],
            slug="my_tenant",
        ),
    ],
)

llm = LLM(
    model="anthropic/claude-sonnet-4-5-20250929",
    api_key=os.environ["ANTHROPIC_API_KEY"],
)
agent = Agent(role="Analyst", goal="Answer questions", backstory="Expert analyst", llm=llm)
task = Task(description="What is 2 + 2?", expected_output="The answer", agent=agent)
crew = Crew(agents=[agent], tasks=[task])

result = crew.kickoff()
```

## How It Works

1. **Capture**: Intercepts LLM requests/responses via framework hooks
2. **Canonicalize**: Deterministic JSON serialization (JCS/RFC 8785)
3. **Hash**: SHA-256 of canonical bytes
4. **Dual-Write**:
   - Your bucket: Full canonical JSON payload
   - Hash storage: Hash receipt for verification

## Configuration

### Raw Payload Storage

Where full audit payloads are stored (your bucket):

```python
from agentsystems_notary import RawPayloadStorage, AwsS3StorageConfig

raw_payload_storage = RawPayloadStorage(
    storage=AwsS3StorageConfig(
        bucket_name="my-audit-logs",
        aws_access_key_id="...",
        aws_secret_access_key="...",
        aws_region="us-east-1",  # optional, defaults to us-east-1
    ),
)
```

### Hash Storage

Where hashes are stored for verification. You can use one or both.

**Custodied (AgentSystems API)** — Managed service, simpler setup.
```python
from agentsystems_notary import CustodiedHashStorage

CustodiedHashStorage(
    api_key="sk_asn_prod_...",  # From agentsystems.ai
    slug="my_tenant",
)
```

**Arweave (Decentralized)** — Public blockchain, immutable, no vendor dependency.
```python
from agentsystems_notary import ArweaveHashStorage, AwsKmsSignerConfig

ArweaveHashStorage(
    namespace="my_tenant",
    signer=AwsKmsSignerConfig(
        kms_key_arn="arn:aws:kms:...",
        aws_access_key_id="...",
        aws_secret_access_key="...",
    ),
    bundler_url="https://upload.ardrive.io/v1/tx/arweave",
)
```

**Using both:**
```python
hash_storage=[
    CustodiedHashStorage(api_key="...", slug="my_tenant"),
    ArweaveHashStorage(namespace="my_tenant", signer=..., bundler_url="..."),
]
```

### Debug Mode

```python
notary = LangChainNotary(
    raw_payload_storage=...,
    hash_storage=[...],
    debug=True,  # Prints canonical JSON and hashes
)
```

## S3 Bucket Structure

```
{env}/{tenant_id}/{YYYY}/{MM}/{DD}/{hash}.json
```

- `env`: `test`, `prod`, or `arweave`
- `tenant_id`: From API response (custodied) or namespace (Arweave)
- `hash`: SHA-256 hash of the canonical payload

## Verification

```python
import hashlib

# 1. Download payload from your bucket
with open("payload.json", "rb") as f:
    canonical_bytes = f.read()

# 2. Compute hash
computed_hash = hashlib.sha256(canonical_bytes).hexdigest()

# 3. Compare with stored hash (from custodied receipt or Arweave)
assert computed_hash == stored_hash
```

## Support

- **Documentation**: [docs.agentsystems.ai/notary](https://docs.agentsystems.ai/notary/)
- **Dashboard**: [notary.agentsystems.ai](https://notary.agentsystems.ai)
- **Issues**: [GitHub Issues](https://github.com/agentsystems/agentsystems-notary/issues)

## License

Licensed under the [Apache-2.0 license](./LICENSE).
