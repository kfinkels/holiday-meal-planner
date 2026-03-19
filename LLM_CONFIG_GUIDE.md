# LLM Configuration Guide

The system now uses three environment variables for LLM configuration:

## Environment Variables

### Required Environment Variables

```bash
# Base URL for your LLM API endpoint
export LLM_BASE_URL="https://api.openai.com/v1"

# Authentication token (API key)
export LLM_AUTH_TOKEN="your-api-key-here"

# Model name to use
export LLM_MODEL="gpt-3.5-turbo"
```

## Configuration Examples

### OpenAI GPT Models

```bash
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_AUTH_TOKEN="sk-your-openai-api-key"
export LLM_MODEL="gpt-3.5-turbo"
# or
export LLM_MODEL="gpt-4"
export LLM_MODEL="gpt-4-turbo"
```

### Anthropic Claude Models

```bash
export LLM_BASE_URL="https://api.anthropic.com/v1"
export LLM_AUTH_TOKEN="sk-ant-your-anthropic-key"
export LLM_MODEL="claude-3-sonnet-20240229"
# or
export LLM_MODEL="claude-3-haiku-20240307"
export LLM_MODEL="claude-3-opus-20240229"
```

### Local/Custom LLM Endpoints

```bash
# For local Ollama instance
export LLM_BASE_URL="http://localhost:11434/v1"
export LLM_AUTH_TOKEN="ollama"  # or whatever your local setup requires
export LLM_MODEL="llama3.1"

# For Azure OpenAI
export LLM_BASE_URL="https://your-resource.openai.azure.com/openai/deployments/your-deployment"
export LLM_AUTH_TOKEN="your-azure-api-key"
export LLM_MODEL="gpt-35-turbo"

# For other custom endpoints
export LLM_BASE_URL="https://your-custom-api.com/v1"
export LLM_AUTH_TOKEN="your-custom-api-key"
export LLM_MODEL="your-model-name"
```

### Test Mode (No API Required)

```bash
# For testing without actual AI
export LLM_MODEL="test"
# LLM_BASE_URL and LLM_AUTH_TOKEN not needed for test mode
```

## Using with CLI

### Set environment variables and run:

```bash
# Example with OpenAI
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_AUTH_TOKEN="sk-your-openai-key"
export LLM_MODEL="gpt-3.5-turbo"

# Run Hebrew CLI
uv run python -m interfaces.cli.main process \
  --language he \
  --description "עוף צלוי עם תפוחי אדמה" \
  --serving-size 6
```

### Or use a .env file:

Create a `.env` file in the project root:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_AUTH_TOKEN=sk-your-openai-key
LLM_MODEL=gpt-3.5-turbo
```

Then run:

```bash
uv run python -m interfaces.cli.main process -l he -d "עוף צלוי עם תפוחי אדמה" -s 6
```

## Environment Variable Priority

The system uses the following priority:

1. `LLM_*` environment variables (recommended)
2. Legacy `OPENAI_API_KEY` (deprecated but still supported)
3. Configuration defaults (test mode)

## Troubleshooting

### "Unknown model" Error
- Make sure `LLM_MODEL` is set correctly
- Check that your model name matches what your API provider expects

### Authentication Errors
- Verify your `LLM_AUTH_TOKEN` is correct
- Check that your API key has proper permissions

### Connection Errors
- Verify your `LLM_BASE_URL` is correct and accessible
- Check firewall/network settings

### Test Mode
If you want to test the Hebrew language support without setting up an API:

```bash
export LLM_MODEL="test"
uv run python demo_hebrew.py  # This works without API
```

## Configuration Verification

To check if your configuration is working:

```bash
# Test with a simple command
uv run python -c "
from shared.config import get_settings
settings = get_settings()
print(f'Model config: {settings.get_llm_model_config()}')
print(f'Base URL: {settings.llm_base_url}')
print(f'Model: {settings.llm_model}')
"
```