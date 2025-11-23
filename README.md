# AgentSystems Witness

[![PyPI version](https://img.shields.io/pypi/v/agentsystems-witness.svg)](https://pypi.org/project/agentsystems-witness/)

> **Audit logging infrastructure for AI systems in regulated industries**

AgentSystems Witness provides tamper-evident audit trails for AI systems in banking, legal, healthcare, and other regulated industries. It creates cryptographically verifiable logs of all LLM interactions with dual-write architecture: your S3 bucket (raw logs) + Witness ledger (hash receipts).

## Features

- **LangChain Integration**: Drop-in callback handler for any LangChain model
- **Dual-Write Architecture**: Vendor S3 (raw logs) + Witness API (hash receipts)
- **Cryptographic Verification**: SHA-256 hashes with JCS canonicalization (RFC 8785)
- **Tenant Isolation**: Multi-tenant support with blast radius controls
- **Compliance Support**: Audit trail architecture aligned with AIUC-1 E015 requirements

## Disclaimer

This SDK provides technical infrastructure for audit logging. It does not guarantee regulatory compliance, which depends on your specific jurisdiction, industry, policies, and operational practices. This SDK does not constitute legal, compliance, or regulatory advice. Consult with qualified legal and compliance professionals for your specific requirements.

## Installation

```bash
pip install agentsystems-witness
```

## Quick Start

```python
from agentsystems_witness import WitnessCallback
from langchain_anthropic import ChatAnthropic

# 1. Create callback handler
callback = WitnessCallback(
    api_key="sk_live_...",           # From witness.agentsystems.ai
    tenant_id="tnt_acme_corp",       # Your tenant identifier
    vendor_bucket_name="acme-llm-logs"  # Your S3 bucket
)

# 2. Add to any LangChain model
model = ChatAnthropic(
    model="claude-sonnet-4",
    callbacks=[callback]
)

# 3. Use normally - logs are automatic
response = model.invoke("What is AIUC-1 compliance?")
```

## How It Works

1. **Capture**: Intercepts LLM requests/responses via LangChain callbacks
2. **Canonicalize**: Deterministic JSON serialization (JCS/RFC 8785)
3. **Hash**: SHA-256 of canonical bytes
4. **Dual-Write**:
   - Your S3 bucket: Full canonical JSON (verifiable by re-hashing)
   - Witness API: Hash receipt (immutable ledger)

## Configuration

### Environment Variables

```bash
# AWS credentials (for vendor S3 bucket)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

### Debug Mode

```python
callback = WitnessCallback(
    api_key="sk_live_...",
    tenant_id="tnt_acme_corp",
    vendor_bucket_name="acme-llm-logs",
    debug=True  # Prints canonical JSON and hashes
)
```

## Multi-Tenant Setup

For SaaS applications serving multiple end-customers:

```python
# Each end-customer gets their own tenant
callback_bank_a = WitnessCallback(
    api_key="sk_live_...",           # Your master or scoped key
    tenant_id="tnt_bank_a",          # Bank A's logs
    vendor_bucket_name="your-logs"
)

callback_bank_b = WitnessCallback(
    api_key="sk_live_...",           # Same or different key
    tenant_id="tnt_bank_b",          # Bank B's logs (isolated)
    vendor_bucket_name="your-logs"
)
```

## API Keys

Generate API keys at [witness.agentsystems.ai](https://witness.agentsystems.ai):

- **Tenant-Scoped Keys**: Limited to specific tenant (recommended)
- **Master Keys**: Access all tenants (use only for internal systems)

## S3 Bucket Structure

Vendor bucket (your S3):
```
logs/
  {tenant_id}/
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

# 3. Compare with Witness receipt
assert computed_hash == witness_receipt_hash  # Proof of integrity
```

## Support

- **Documentation**: [docs.agentsystems.ai/witness](https://docs.agentsystems.ai/witness/)
- **Dashboard**: [witness.agentsystems.ai](https://witness.agentsystems.ai)
- **Issues**: [GitHub Issues](https://github.com/agentsystems/agentsystems-witness/issues)

## License

Licensed under the [Apache-2.0 license](./LICENSE).
