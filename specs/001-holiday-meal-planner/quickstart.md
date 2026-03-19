# Holiday Meal Planner - Implementation Quickstart

**Feature**: Holiday Meal Planner
**Date**: 2026-03-18
**Implementation Ready**: ✅ Ready to begin

## Technology Stack

Based on comprehensive research, this implementation uses:

- **Framework**: PydanticAI for multi-agent pipeline
- **CLI**: Typer with human-readable output formatting
- **API**: FastAPI with automatic OpenAPI documentation
- **Web Parsing**: recipe-scrapers + BeautifulSoup with security-first cascade strategy
- **NLP**: spaCy with custom NER training for ingredient extraction
- **Scheduling**: NetworkX + Google OR-Tools for timeline optimization
- **Validation**: Pydantic models throughout for type safety

## Key Implementation Decisions

### Multi-Agent Architecture
```python
# Three specialized agents with async coordination
agents = {
    'recipe_processor': RecipeProcessorAgent(),      # URL extraction + NLP parsing
    'ingredient_consolidator': IngredientConsolidatorAgent(),  # Deduplication + unit conversion
    'timeline_generator': TimelineGeneratorAgent()   # Dependency scheduling + load balancing
}
```

### Security & Performance
- **HTTPS-only** URL access with comprehensive validation (constitutional requirement)
- **1-2 second delays** between web requests for respectful scraping
- **5MB response limits** and 30-second timeouts for security
- **90% test coverage** target with mocked web responses

### Confidence-Based Processing
- **High confidence (>0.8)**: Auto-accept ingredient extraction
- **Medium confidence (0.6-0.8)**: Flag for user review
- **Low confidence (<0.6)**: Request user confirmation with suggestions

## Project Structure

```
holiday_meal_planner/
├── core/
│   ├── models.py           # Pydantic data models (see data-model.md)
│   ├── meal_planner.py     # Main pipeline orchestrator
│   ├── agents/
│   │   ├── recipe_processor.py     # Web scraping + NLP extraction
│   │   ├── ingredient_consolidator.py  # Deduplication + unit conversion
│   │   └── timeline_generator.py   # Task scheduling + optimization
│   └── services/
│       ├── web_extractor.py        # Secure recipe website parsing
│       ├── nlp_processor.py        # spaCy ingredient extraction
│       ├── consolidator.py         # Fuzzy matching + unit conversion
│       └── scheduler.py            # Constraint programming + topological sort
├── interfaces/
│   ├── cli/
│   │   ├── main.py         # Typer CLI entry point
│   │   ├── commands.py     # CLI command definitions
│   │   └── formatters.py   # Human-readable output
│   └── api/
│       ├── main.py         # FastAPI application
│       ├── routers/        # API endpoints (see contracts/api-spec.yml)
│       └── dependencies.py # Shared FastAPI dependencies
├── shared/
│   ├── config.py          # Settings management
│   ├── exceptions.py      # Custom exception types
│   └── validators.py      # Input validation utilities
└── tests/
    ├── unit/              # Unit tests for components
    ├── integration/       # End-to-end pipeline tests
    └── contract/          # CLI vs API consistency tests
```

## Implementation Phases

### Phase 1: Core Data Pipeline (Priority: P1)
**Scope**: Implement basic ingredient extraction and consolidation
**Deliverables**:
- Pydantic models from `data-model.md`
- Basic web scraping with security controls
- Ingredient consolidation with unit conversion
- Simple CLI interface for testing

**Key Files**:
- `core/models.py` - All Pydantic models
- `core/services/web_extractor.py` - recipe-scrapers integration
- `core/services/consolidator.py` - ingredient merging logic
- `interfaces/cli/main.py` - Basic Typer CLI

### Phase 2: Timeline Generation (Priority: P2)
**Scope**: Add preparation timeline planning
**Deliverables**:
- Task dependency analysis with topological sorting
- Food safety constraint implementation
- Daily workload balancing
- Timeline optimization with OR-Tools

**Key Files**:
- `core/agents/timeline_generator.py` - Timeline agent
- `core/services/scheduler.py` - Constraint programming
- Updated CLI with timeline display

### Phase 3: API & Polish (Priority: P3)
**Scope**: FastAPI implementation and advanced features
**Deliverables**:
- FastAPI implementation matching `contracts/api-spec.yml`
- NLP enhancement with spaCy custom training
- Async processing for large menus
- Complete test suite with >90% coverage

**Key Files**:
- `interfaces/api/main.py` - FastAPI application
- `core/services/nlp_processor.py` - Enhanced NLP
- Comprehensive test suite

## Quick Start Commands

### Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install pydantic-ai typer[all] fastapi[all] recipe-scrapers spacy
pip install beautifulsoup4 pint fuzzywuzzy networkx ortools
python -m spacy download en_core_web_sm

# Install development dependencies
pip install pytest pytest-asyncio httpx responses black isort mypy
```

### Basic Implementation Test
```bash
# Test basic functionality (implement after Phase 1)
python -m interfaces.cli process \
  --url "https://allrecipes.com/recipe/example" \
  --description "mashed potatoes for 8 people" \
  --meal-date "2026-11-28T14:00:00"
```

### Run API Server
```bash
# Start FastAPI server (implement after Phase 3)
uvicorn interfaces.api.main:app --reload --port 8000

# View interactive docs
open http://localhost:8000/docs
```

## Constitutional Compliance Checklist

- ✅ **Human Oversight**: All AI agents require validation of results
- ✅ **Security by Default**: HTTPS-only, input validation, rate limiting
- ✅ **Tests Drive Confidence**: >90% coverage target with mocked web responses
- ✅ **Documentation**: Clear API contracts and implementation guidance
- ✅ **Safe File I/O**: Memory-only processing, no persistent storage
- ✅ **Secure URL Access**: Comprehensive validation and error handling
- ✅ **Python Standards**: 3.8+, type hints, PEP 8 (88-char lines)

## Performance Targets

- **Processing Time**: <60 seconds for 8-12 dish menus
- **Success Rate**: >90% ingredient extraction from common recipe sites
- **Consolidation**: >80% duplicate reduction vs manual compilation
- **Workload Balance**: ≤4 hours active cooking per day for typical menus

## Error Handling Strategy

```python
# Graceful degradation pattern used throughout
try:
    primary_result = extract_with_recipe_scrapers(url)
except WebScrapingError:
    try:
        fallback_result = extract_with_html_patterns(url)
    except Exception:
        # Continue processing other menu items
        add_to_failed_items(url, error_message)
        continue
```

## Testing Strategy

- **Unit Tests**: Mock all external dependencies (web requests, file I/O)
- **Integration Tests**: Full pipeline with controlled test data
- **Contract Tests**: Ensure CLI and API return identical results
- **Security Tests**: Validate URL filtering and input sanitization
- **Performance Tests**: Verify <60 second processing requirement

---

**Ready to implement!** This quickstart provides all the technical guidance needed to build the holiday meal planner according to research findings and constitutional requirements.