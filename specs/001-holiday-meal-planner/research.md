# Technical Research Findings

**Feature**: Holiday Meal Planner
**Date**: 2026-03-18
**Status**: In Progress

## Research Overview

This document consolidates research findings for critical technical decisions in the holiday meal planner implementation. All research was conducted to resolve technical unknowns and guide implementation planning.

## 1. Ingredient Consolidation Algorithms ✅ COMPLETE

**Decision**: Multi-tier conversion system with fuzzy matching for ingredient normalization

**Rationale**:
- Requires handling diverse unit systems (volume, weight, count) with ingredient-specific conversions
- Need robust name normalization for ingredient variants ("butter" vs "unsalted butter")
- Fractional quantity handling essential for recipe accuracy

**Key Implementation Approach**:
- **Unit Conversion**: Multi-tier system with volume/weight conversions and ingredient-specific densities
- **Name Normalization**: Fuzzy matching using difflib/fuzzywuzzy with synonym dictionaries
- **Quantity Aggregation**: Hierarchical strategy with context-aware unit preference
- **Ambiguity Resolution**: Portion size standardization and contextual analysis

**Recommended Libraries**:
- `pint`: Scientific unit conversions
- `ingredient-parser`: Parse ingredient strings into components
- `fuzzywuzzy`: Fuzzy string matching for names
- `recipe-scrapers`: Extract structured data from websites
- `spacy`: NLP for ingredient parsing

**System Architecture**:
```python
class RecipeConsolidator:
    def __init__(self):
        self.parser = IngredientParser()
        self.normalizer = IngredientNormalizer()
        self.converter = UnitConverter()
        self.aggregator = QuantityAggregator()
```

**Alternatives Considered**:
- Simple string matching (rejected - insufficient for real-world ingredient variations)
- Manual conversion tables (rejected - doesn't scale to diverse ingredient types)

---

## 2. PydanticAI Multi-Agent Architecture ✅ COMPLETE

**Decision**: Three-agent pipeline with async orchestrator and Pydantic model communication

**Rationale**:
- Clear separation of concerns across recipe processing, consolidation, and timeline generation
- Async/await patterns for optimal performance with web scraping and NLP tasks
- Robust error handling with graceful degradation

**Key Implementation Architecture**:
- **RecipeProcessorAgent**: Extracts ingredients from URLs and text descriptions
- **IngredientConsolidatorAgent**: Merges duplicates and optimizes quantities
- **TimelineGeneratorAgent**: Creates day-by-day preparation schedules
- **Pipeline Orchestrator**: Coordinates agents with state management

**Agent Communication**:
```python
class MenuItemData(BaseModel):
    id: str
    name: str
    source_url: Optional[str] = None
    ingredients: List[Ingredient] = []
    prep_time_hours: Optional[float] = None

class PipelineState(BaseModel):
    menu_items: List[MenuItemData] = []
    consolidated_ingredients: List[Ingredient] = []
    processing_errors: List[str] = []
```

**Alternatives Considered**:
- Single monolithic agent (rejected - violates separation of concerns)
- Message queue architecture (rejected - adds complexity without benefit for this scale)

---

## 3. Recipe Website Parsing Strategies ✅ COMPLETE

**Decision**: Cascade extraction strategy with security-first approach

**Rationale**:
- Most recipe sites use standardized JSON-LD markup for reliable extraction
- Multiple fallback strategies ensure robust parsing across varied sites
- Security constraints align with constitutional requirements for HTTPS-only access

**Cascade Strategy**:
1. **JSON-LD extraction** (primary) - Schema.org Recipe markup
2. **Microdata extraction** (secondary) - HTML microdata attributes
3. **HTML pattern matching** (fallback) - CSS selectors and regex patterns
4. **AI/LLM extraction** (last resort) - When structured data unavailable

**Security Implementation**:
- HTTPS-only URL validation with blocked internal addresses
- Rate limiting (1-2 seconds between requests) and response size limits (5MB)
- Content-type validation and SSL certificate verification
- Timeout controls (30 seconds) and graceful error handling

**Recommended Libraries**:
- `recipe-scrapers`: Supports 450+ recipe sites with built-in fallbacks
- `extruct`: Structured data extraction (JSON-LD, microdata)
- `BeautifulSoup`: HTML parsing with CSS selectors
- `requests`: HTTP with session management and security features

**Alternatives Considered**:
- Scrapy framework (rejected - overkill for single-user application)
- Direct HTML parsing only (rejected - too brittle for diverse sites)

---

## 4. CLI/API Framework Integration ✅ COMPLETE

**Decision**: Typer + FastAPI with service layer pattern

**Rationale**:
- Both frameworks from same author (Sebastian Ramirez) designed for integration
- Excellent type hint support and automatic validation via Pydantic
- Service layer ensures identical business logic across both interfaces

**Architecture Pattern**:
```
core/
├── models.py           # Pydantic models
├── meal_planner.py     # Main orchestrator
└── services/          # Business logic services
cli/
├── main.py            # Typer CLI entry
└── formatters.py      # Human-readable output
api/
├── main.py            # FastAPI entry
└── routers.py         # API endpoints
shared/
├── config.py          # Settings
├── exceptions.py      # Error types
└── validators.py      # Custom validation
```

**Consistency Strategy**:
- Shared Pydantic models for input validation across interfaces
- Service layer dependency injection for identical business logic
- Contract testing to ensure CLI and API produce identical results
- Unified error handling with interface-appropriate formatting

**Alternatives Considered**:
- Click + Flask (rejected - less modern type hint integration)
- argparse + FastAPI (rejected - inconsistent validation approaches)

---

## 5. NLP for Dish Description Parsing ✅ COMPLETE

**Decision**: spaCy with custom NER training plus rule-based patterns

**Rationale**:
- Production-ready NLP with excellent performance for ingredient extraction
- Custom NER training allows domain-specific food/ingredient recognition
- Rule-based patterns provide high-confidence extraction for common patterns

**Implementation Approach**:
```python
class IngredientExtractor:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.matcher = Matcher(self.nlp.vocab)
        self.confidence_threshold = 0.6

    def extract_with_confidence(self, text: str) -> List[Dict]:
        # 1. Pattern matching (high precision)
        # 2. NER extraction (comprehensive)
        # 3. Fuzzy matching for normalization
        # 4. Confidence scoring with fallbacks
```

**Confidence Thresholds**:
- **High confidence (>0.8)**: Auto-accept extraction
- **Medium confidence (0.6-0.8)**: Flag for user review
- **Low confidence (<0.6)**: Request user confirmation with suggestions

**Alternative Libraries**:
- `transformers`: BERT/GPT models for highest accuracy (secondary option)
- `NLTK`: Rule-based processing and text preprocessing (supporting role)
- `fuzzywuzzy`: Fuzzy string matching for ingredient synonyms

**Alternatives Considered**:
- Pure transformer approach (rejected - slower inference, overkill for this domain)
- Only rule-based patterns (rejected - insufficient coverage for varied descriptions)

---

## 6. Timeline Optimization Algorithms ✅ COMPLETE

**Decision**: Constraint programming with topological sorting and load balancing

**Rationale**:
- Multiple complex constraints (dependencies, food safety, workload limits) require sophisticated scheduling
- Topological sorting handles task dependencies efficiently
- Constraint programming provides optimal solutions for multi-objective optimization

**Algorithm Stack**:
1. **Topological Sorting** (Kahn's algorithm): Order tasks by dependencies
2. **Food Safety Constraints**: Time windows for perishable ingredients
3. **Load Balancing**: Distribute workload across days (max 4 hours/day)
4. **Multi-Objective Optimization**: Minimize daily variance, maximize make-ahead tasks

**Implementation Libraries**:
- `networkx`: Dependency graph management and critical path analysis
- `ortools`: Constraint programming solver for complex scheduling
- `pulp`: Linear programming for workload optimization
- Built-in algorithms: Topological sort, bin packing variants

**Key Constraints**:
```python
FOOD_SAFETY_RULES = [
    FoodSafetyConstraint("dairy", 12),      # 12 hours max advance
    FoodSafetyConstraint("seafood", 6),     # 6 hours max advance
    FoodSafetyConstraint("stock", 120),     # 5 days max advance
    FoodSafetyConstraint("marinade", 24, 2) # 2-24 hours advance
]
```

**Alternatives Considered**:
- Simple greedy scheduling (rejected - doesn't handle complex constraints)
- Manual priority-based sorting (rejected - suboptimal for multi-day planning)

---

## Constitutional Compliance Analysis

**Security Requirements**:
- HTTPS-only URL access with validation ✅ Addressed in web parsing research
- Input sanitization for web content ✅ Addressed in parsing strategies
- Rate limiting and response size controls ✅ Addressed in web access patterns

**Quality Requirements**:
- 90% test coverage minimum ✅ All recommended libraries have testing strategies
- Python 3.8+ with type hints ✅ All implementations will follow this standard
- PEP 8 compliance with 88-character limits ✅ Standard practice

**Performance Requirements**:
- Sub-60-second processing for 8-12 dish menus ✅ Algorithms designed for efficiency
- Memory-only operations ✅ No persistent storage in design

## Next Steps

1. Complete remaining research areas (5 agents in progress)
2. Consolidate all findings with final technical decisions
3. Proceed to Phase 1: Design & Contracts
4. Generate implementation plan with [SYNC]/[ASYNC] task classification
