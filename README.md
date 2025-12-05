# AgentSystems Notary

[![PyPI version](https://img.shields.io/pypi/v/agentsystems-notary.svg)](https://pypi.org/project/agentsystems-notary/)

> **Audit logging infrastructure for AI systems**

AgentSystems Notary provides tamper-evident audit trails for AI systems. It creates cryptographically verifiable logs of all LLM interactions with dual-write architecture: your S3 bucket (raw logs) + Notary ledger (hash receipts).

## Features

- **Multi-Framework Support**: LangChain and CrewAI adapters (extensible to other frameworks)
- **Dual-Write Architecture**: Organization S3 (raw logs) + Notary API (hash receipts)
- **Cryptographic Verification**: SHA-256 hashes with JCS canonicalization (RFC 8785)
- **Tenant Isolation**: Multi-tenant support for SaaS applications
- **Audit Trail Architecture**: Designed with verifiability and auditability in mind

## Disclaimer

This SDK provides technical infrastructure for audit logging. It does not guarantee regulatory compliance, which depends on your specific jurisdiction, industry, policies, and operational practices. This SDK does not constitute legal, compliance, or regulatory advice. Consult with qualified legal and compliance professionals for your specific requirements.

## Installation

```bash
# Install with LangChain support
pip install agentsystems-notary[langchain]

# Install with CrewAI support
pip install agentsystems-notary[crewai]

# Install with both
pip install agentsystems-notary[all]
```

## Quick Start

### LangChain

```python
from agentsystems_notary import LangChainNotary
from langchain_anthropic import ChatAnthropic

# 1. Create notary callback
notary = LangChainNotary(
    api_key="sk_asn_prod_...",        # From notary.agentsystems.ai
    slug="tnt_acme_corp",             # Your tenant slug
    org_bucket_name="acme-llm-logs"   # Your S3 bucket
)

# 2. Add to any LangChain model
model = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    callbacks=[notary]
)

# 3. Use normally - logs are automatic
response = model.invoke("What is AIUC-1 compliance?")
```

### CrewAI

```python
from agentsystems_notary import CrewAINotary
from crewai import Agent, Task, Crew

# 1. Initialize notary (registers hooks automatically)
notary = CrewAINotary(
    api_key="sk_asn_prod_...",
    slug="tnt_acme_corp",
    org_bucket_name="acme-llm-logs"
)

# 2. Create crew normally
agent = Agent(role="Research Analyst", goal="...", backstory="...")
task = Task(description="Research AIUC-1 compliance", agent=agent)
crew = Crew(agents=[agent], tasks=[task])

# 3. All LLM calls are logged automatically
crew.kickoff()
```

## How It Works

1. **Capture**: Intercepts LLM requests/responses via LangChain callbacks
2. **Canonicalize**: Deterministic JSON serialization (JCS/RFC 8785)
3. **Hash**: SHA-256 of canonical bytes
4. **Dual-Write**:
   - Your S3 bucket: Full canonical JSON (verifiable by re-hashing)
   - Notary API: Hash receipt (immutable ledger)

## Configuration

### Environment Variables

```bash
# AWS credentials (for organization S3 bucket)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

### Debug Mode

```python
notary = LangChainNotary(
    api_key="sk_asn_prod_...",
    slug="tnt_acme_corp",
    org_bucket_name="acme-llm-logs",
    debug=True  # Prints canonical JSON and hashes
)
```

## Multi-Tenant Setup

For SaaS applications serving multiple end-customers:

```python
# Each end-customer gets their own tenant
notary_bank_a = LangChainNotary(
    api_key="sk_asn_prod_...",
    slug="tnt_bank_a",              # Bank A's logs
    org_bucket_name="your-logs"
)

notary_bank_b = LangChainNotary(
    api_key="sk_asn_prod_...",
    slug="tnt_bank_b",              # Bank B's logs (isolated)
    org_bucket_name="your-logs"
)
```

## API Keys

Generate API keys at [notary.agentsystems.ai](https://notary.agentsystems.ai).

## S3 Bucket Structure

Organization bucket (your S3):
```
logs/
  {slug}/
    {session_id}/
      1.json
      2.json
      3.json
```

Each file contains canonical JSON that can be re-hashed to verify the hash receipt.

## Verification

To verify a log entry:

```python
import hashlib
import jcs

# 1. Download from your S3 bucket
log_data = s3.get_object(Bucket="your-bucket", Key="logs/tnt_acme/session-123/1.json")

# 2. Re-hash
canonical_bytes = log_data["Body"].read()
computed_hash = hashlib.sha256(canonical_bytes).hexdigest()

# 3. Compare with Notary receipt
assert computed_hash == notary_receipt_hash  # Proof of integrity
```

## Support

- **Documentation**: [docs.agentsystems.ai/notary](https://docs.agentsystems.ai/notary/)
- **Dashboard**: [notary.agentsystems.ai](https://notary.agentsystems.ai)
- **Issues**: [GitHub Issues](https://github.com/agentsystems/agentsystems-notary/issues)

## License

Licensed under the [Apache-2.0 license](./LICENSE).
