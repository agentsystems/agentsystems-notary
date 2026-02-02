# AgentSystems Notary

[![PyPI version](https://img.shields.io/pypi/v/agentsystems-notary.svg)](https://pypi.org/project/agentsystems-notary/)

> **Audit logging infrastructure for AI systems**

AgentSystems Notary provides tamper-evident audit trails for AI systems. It creates cryptographically verifiable logs of all LLM interactions with dual-write architecture: your storage bucket (raw logs) + hash storage (verification receipts).

## Features

- **Multi-Framework Support**: LangChain and CrewAI adapters
- **Dual-Write Architecture**: Your bucket (raw logs) + hash storage (receipts)
- **Flexible Hash Storage**: Arweave (decentralized) and/or Custodied (AgentSystems API)
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
from dotenv import load_dotenv
from agentsystems_notary import (
    LangChainNotary,
    RawPayloadStorage,
    ArweaveHashStorage,
    LocalKeySignerConfig,
    AwsS3StorageConfig,
)
from langchain_anthropic import ChatAnthropic

load_dotenv()

# Where full audit payloads are stored (your S3 bucket)
raw_payload_storage = RawPayloadStorage(
    storage=AwsS3StorageConfig(
        bucket_name=os.environ["ORG_AWS_S3_BUCKET_NAME"],
        aws_access_key_id=os.environ["ORG_AWS_S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["ORG_AWS_S3_SECRET_ACCESS_KEY"],
        aws_region=os.environ["ORG_AWS_S3_REGION"],
    ),
)

# Where hashes are stored — Arweave for independent verification
hash_storage = [
    ArweaveHashStorage(
        namespace="my_namespace",
        signer=LocalKeySignerConfig(
            private_key_path=os.environ["ARWEAVE_PRIVATE_KEY_PATH"],
        ),
        bundler_url=os.environ["ARWEAVE_BUNDLER_URL"],
    ),
]

# Initialize notary
notary = LangChainNotary(
    raw_payload_storage=raw_payload_storage,
    hash_storage=hash_storage,
    debug=True,
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
from dotenv import load_dotenv
from agentsystems_notary import (
    CrewAINotary,
    RawPayloadStorage,
    ArweaveHashStorage,
    LocalKeySignerConfig,
    AwsS3StorageConfig,
)
from crewai import Agent, Task, Crew, LLM

load_dotenv()

# Where full audit payloads are stored (your S3 bucket)
raw_payload_storage = RawPayloadStorage(
    storage=AwsS3StorageConfig(
        bucket_name=os.environ["ORG_AWS_S3_BUCKET_NAME"],
        aws_access_key_id=os.environ["ORG_AWS_S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["ORG_AWS_S3_SECRET_ACCESS_KEY"],
        aws_region=os.environ["ORG_AWS_S3_REGION"],
    ),
)

# Where hashes are stored — Arweave for independent verification
hash_storage = [
    ArweaveHashStorage(
        namespace="my_namespace",
        signer=LocalKeySignerConfig(
            private_key_path=os.environ["ARWEAVE_PRIVATE_KEY_PATH"],
        ),
        bundler_url=os.environ["ARWEAVE_BUNDLER_URL"],
    ),
]

# Initialize notary (hooks register automatically)
notary = CrewAINotary(
    raw_payload_storage=raw_payload_storage,
    hash_storage=hash_storage,
    debug=True,
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
        aws_region="us-east-1",
    ),
)
```

### Hash Storage

Where hashes are stored for verification. You can use one or both.

**Arweave (Decentralized)** — Public blockchain, permanent storage, no vendor dependency. Verify independently with open-source CLI.
```python
from agentsystems_notary import ArweaveHashStorage, LocalKeySignerConfig

ArweaveHashStorage(
    namespace="my_namespace",
    signer=LocalKeySignerConfig(
        private_key_path="path/to/rsa-4096-private.pem",
    ),
    bundler_url="https://node2.bundlr.network",
)
```

**Custodied (AgentSystems API)** — Managed service if you prefer AgentSystems to handle the complexity.
```python
from agentsystems_notary import CustodiedHashStorage

CustodiedHashStorage(
    api_key="sk_asn_prod_...",  # From agentsystems.ai
    slug="my_tenant",
)
```

**Using both:**
```python
hash_storage=[
    ArweaveHashStorage(namespace="my_namespace", signer=..., bundler_url="..."),
    CustodiedHashStorage(api_key="...", slug="my_tenant"),
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
{env}/{namespace}/{YYYY}/{MM}/{DD}/{hash}.json
```

- `env`: `arweave`, `prod`, or `test`
- `namespace`: Your namespace (Arweave) or tenant ID from API response (custodied)
- `hash`: SHA-256 hash of the canonical payload

## Verification

For Arweave-notarized logs, use the open-source CLI — no account required:

```bash
npm install -g agentsystems-verify
agentsystems-verify --logs logs.zip
```

Manual verification:

```python
import hashlib

# 1. Download payload from your bucket
with open("payload.json", "rb") as f:
    canonical_bytes = f.read()

# 2. Compute hash
computed_hash = hashlib.sha256(canonical_bytes).hexdigest()

# 3. Compare with stored hash (from Arweave or custodied receipt)
assert computed_hash == stored_hash
```

## Support

- **Documentation**: [docs.agentsystems.ai/notary](https://docs.agentsystems.ai/notary/)
- **Dashboard**: [notary.agentsystems.ai](https://notary.agentsystems.ai)
- **Issues**: [GitHub Issues](https://github.com/agentsystems/agentsystems-notary/issues)

## License

Licensed under the [Apache-2.0 license](./LICENSE).
