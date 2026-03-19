# Holiday Meal Planner 🦃

AI-powered holiday meal planner that processes recipes and generates consolidated grocery lists with day-by-day preparation timelines.

## Overview

Holiday Meal Planner uses a multi-agent AI system to:

1. **Process Recipes**: Extract ingredients from recipe URLs or free-text descriptions
2. **Consolidate Shopping**: Merge ingredients with intelligent unit conversion and duplicate detection
3. **Plan Timeline**: Generate optimal preparation schedules with food safety constraints

Perfect for holiday cooking with multiple dishes, complex timing, and detailed organization needs.

## Features

- 🔗 **URL Processing**: Supports 450+ recipe websites via secure HTTPS extraction
- 📝 **Text Descriptions**: NLP processing for free-form dish descriptions
- 🛒 **Smart Consolidation**: Intelligent ingredient merging with unit conversion
- 📅 **Timeline Planning**: Day-by-day preparation schedules with workload balancing
- 🖥️ **Dual Interface**: Both CLI and REST API access with identical functionality
- 🔒 **Security First**: HTTPS-only, rate limiting, input validation throughout

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd holiday-meal-planner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e .

# Install development dependencies (optional)
pip install -e ".[dev]"

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Basic Usage

```bash
# Process a holiday menu with CLI
holiday-planner process \
  --url "https://allrecipes.com/recipe/turkey-stuffing" \
  --description "mashed potatoes for 10 people with butter and cream" \
  --meal-date "2024-11-28T14:00:00" \
  --max-prep-days 3

# Start API server
uvicorn interfaces.api.main:app --reload --port 8000

# View interactive API documentation
open http://localhost:8000/docs
```

### Example Output

**Grocery List:**
```
📋 Consolidated Grocery List (12 people)
─────────────────────────────────────────
🥩 Protein
  • Turkey (whole): 12.0 pounds

🥕 Vegetables
  • Potatoes (russet): 4.0 pounds
  • Onions (yellow): 2.0 whole
  • Celery: 1.0 bunch

🧈 Dairy
  • Butter (unsalted): 1.5 cups
  • Heavy cream: 0.75 cups
```

**Timeline:**
```
📅 Preparation Timeline
─────────────────────────────────────────
📆 3 Days Before (Nov 25)
  • Make turkey stock (2 hours)
  • Prepare bread cubes for stuffing (30 min)

📆 Day Before (Nov 27)
  • Prep vegetables (45 min)
  • Make cranberry sauce (20 min)

📆 Day of Meal (Nov 28)
  • Start turkey (6 hours)
  • Prepare stuffing (1 hour)
  • Mash potatoes (30 min)
```

## Architecture

### Multi-Agent Pipeline
- **RecipeProcessorAgent**: Secure web extraction and NLP parsing
- **IngredientConsolidatorAgent**: Fuzzy matching and unit conversion
- **TimelineGeneratorAgent**: Constraint programming and optimization

### Technology Stack
- **Framework**: PydanticAI for agent coordination
- **CLI**: Typer with rich formatting
- **API**: FastAPI with automatic OpenAPI docs
- **NLP**: spaCy with custom ingredient extraction
- **Optimization**: NetworkX + Google OR-Tools for scheduling
- **Security**: HTTPS-only, comprehensive input validation

## Development

### Project Structure

```
holiday_meal_planner/
├── core/                   # Business logic and agents
│   ├── models.py          # Pydantic data models
│   ├── meal_planner.py    # Main pipeline orchestrator
│   ├── agents/            # Specialized AI agents
│   └── services/          # Core processing services
├── interfaces/            # User interfaces
│   ├── cli/              # Typer CLI commands
│   └── api/              # FastAPI REST endpoints
├── shared/               # Utilities and configuration
└── tests/               # Comprehensive test suite
```

### Development Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Code formatting
black .
isort .

# Type checking
mypy .

# Linting
ruff check .

# Run tests
pytest

# Run tests with coverage
pytest --cov=core --cov=interfaces --cov=shared --cov-report=html
```

### Testing Strategy

- **Unit Tests**: Mock external dependencies (web requests, file I/O)
- **Integration Tests**: Full pipeline with controlled test data
- **Contract Tests**: Ensure CLI and API return identical results
- **Security Tests**: Validate HTTPS-only and input sanitization

## Configuration

### Environment Variables

```bash
# Optional: Configure rate limiting
export MEAL_PLANNER_REQUEST_DELAY=2.0  # seconds between web requests
export MEAL_PLANNER_MAX_ITEMS=20       # maximum menu items per request
export MEAL_PLANNER_TIMEOUT=30         # web request timeout

# Optional: Configure processing
export MEAL_PLANNER_CONFIDENCE_THRESHOLD=0.6  # minimum NLP confidence
export MEAL_PLANNER_MAX_PREP_DAYS=7           # maximum advance preparation
```

## Constitutional Requirements

- ✅ **Human Oversight**: All AI agent results require validation
- ✅ **Security by Default**: HTTPS-only, input validation, rate limiting
- ✅ **Test Coverage**: >90% coverage target with comprehensive mocking
- ✅ **Documentation**: Clear contracts and implementation guidance
- ✅ **Type Safety**: Full Python type hints with mypy validation

## Performance Targets

- **Processing Time**: <60 seconds for 8-12 dish holiday menus
- **Success Rate**: >90% ingredient extraction from common recipe sites
- **Consolidation**: >80% duplicate reduction vs manual compilation
- **Timeline Balance**: ≤4 hours active preparation per day

## API Documentation

Once the server is running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI schema**: http://localhost:8000/openapi.json

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes with comprehensive tests
4. Ensure all quality checks pass (`pytest`, `mypy`, `black`, `isort`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/holiday-meal-planner/issues)
- **Documentation**: [Read the Docs](https://holiday-meal-planner.readthedocs.io/)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/holiday-meal-planner/discussions)

---

**Ready to plan your perfect holiday meal!** 🎉