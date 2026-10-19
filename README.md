# Hearth

An embeddable context engine that keeps an AI agent's prompt cache warm and proves it with measurements.

```python
import hearth

# Drop-in wrapper around model clients
client = hearth.wrap(client, mode="safe")
```

See [docs/BUILD_HANDBOOK.md](docs/BUILD_HANDBOOK.md) for specifications.
