# Holiday Meal Planner - Architecture Documentation

## Overview

The Holiday Meal Planner is an AI-powered application that helps users plan complex holiday meals by processing recipes, consolidating ingredients into a unified grocery list, and generating optimized preparation timelines. The system is built using a multi-agent architecture with clear separation of concerns and dual user interfaces (CLI and REST API).

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interfaces                          │
├─────────────────────┬───────────────────────────────────────┤
│      CLI Interface  │           REST API Interface          │
│   (Typer + Rich)    │          (FastAPI + OpenAPI)          │
├─────────────────────┴───────────────────────────────────────┤
│                 Pipeline Orchestrator                       │
├─────────────────────────────────────────────────────────────┤
│              MealPlannerOrchestrator                        │
│         (Coordinates Multi-Agent Pipeline)                  │
├─────────────────────┬───────────────────┬───────────────────┤
│  Recipe Processing  │ Ingredient        │  Timeline         │
│      Agent          │ Consolidation     │ Generation Agent  │
│                     │      Agent        │                   │
├─────────────────────┼───────────────────┼───────────────────┤
│                        Services Layer                       │
├─────────────────────┬───────────────────┬───────────────────┤
│  Web Extractor      │  NLP Processor    │   Scheduler       │
│  Consolidator       │                   │                   │
├─────────────────────┴───────────────────┴───────────────────┤
│                   Shared Utilities                          │
├─────────────────────────────────────────────────────────────┤
│  Config | Logging | Exceptions | Validators | i18n          │
└─────────────────────────────────────────────────────────────┘
```

## Architecture Principles

### 1. Multi-Agent System
- **Agent-Based Design**: Uses PydanticAI framework for coordinated AI agents
- **Specialized Responsibilities**: Each agent handles a specific domain
- **Async Coordination**: Agents work together through async message passing

### 2. Hexagonal Architecture
- **Port-Adapter Pattern**: Clear separation between business logic and external interfaces
- **Interface Isolation**: CLI and API interfaces are completely separate but functionally identical
- **Dependency Inversion**: Core business logic doesn't depend on external frameworks

### 3. Type Safety First
- **Pydantic Models**: All data structures are strongly typed with validation
- **Full Type Hints**: Complete mypy coverage across the codebase
- **Runtime Validation**: Input validation at all system boundaries

### 4. Security by Design
- **HTTPS Only**: All external communications use secure protocols
- **Input Sanitization**: Comprehensive validation of all user inputs
- **Rate Limiting**: Built-in protection against abuse

## Core Components

### 1. Pipeline Orchestrator

#### MealPlannerOrchestrator
**Location**: `core/meal_planner.py`
**Role**: Central coordinator for the entire meal planning pipeline

**Key Responsibilities**:
- **Pipeline State Management**: Tracks processing state across all phases
- **Agent Coordination**: Orchestrates sequential execution of specialized agents
- **Phase Validation**: Validates pipeline state between each processing phase
- **Error Handling**: Manages failures and provides comprehensive error reporting
- **Metrics Collection**: Calculates processing metrics and performance data
- **Result Assembly**: Consolidates outputs from all agents into final results

**Pipeline Phases**:
1. **Recipe Processing Phase**: Coordinates recipe extraction and parsing
2. **Ingredient Consolidation Phase**: Manages ingredient merging and categorization
3. **Timeline Generation Phase**: Optional timeline creation and optimization
4. **Result Assembly Phase**: Final result packaging and validation

**Public Interface**:
- `plan_meal(request)`: Complete meal planning pipeline
- `plan_simple_meal(items, serving_size)`: Grocery list only
- `process_single_recipe(url, description, serving_size)`: Single recipe processing

**Agent Management**:
- Contains instances of all three specialized agents
- Manages agent dependencies and shared context
- Handles lazy loading of optional components (timeline generator)
- Provides unified error handling across agent boundaries

### 2. Multi-Agent Pipeline

#### Recipe Processor Agent
**Location**: `core/agents/recipe_processor.py`
**Responsibilities**:
- Extract recipes from URLs using recipe-scrapers library
- Parse free-text recipe descriptions using NLP
- Validate and structure ingredient data
- Handle 450+ supported recipe websites

**Dependencies**:
- Web Extractor Service
- NLP Processor Service
- Recipe Scrapers library

#### Ingredient Consolidator Agent
**Location**: `core/agents/ingredient_consolidator.py`
**Responsibilities**:
- Merge duplicate ingredients using fuzzy matching
- Convert between different units of measurement
- Categorize ingredients for organized grocery lists
- Scale quantities based on serving size

**Dependencies**:
- Consolidator Service
- Pint library for unit conversion
- FuzzyWuzzy for similarity matching

#### Timeline Generator Agent
**Location**: `core/agents/timeline_generator.py`
**Responsibilities**:
- Generate optimal preparation schedules
- Balance daily workload constraints
- Optimize for food safety and quality
- Create day-by-day preparation tasks

**Dependencies**:
- Scheduler Service
- NetworkX for graph algorithms
- OR-Tools for constraint optimization

### 2. Services Layer

#### Web Extractor Service
**Location**: `core/services/web_extractor.py`
**Responsibilities**:
- Secure HTTPS-only web scraping
- Recipe metadata extraction
- Rate limiting and timeout handling
- BeautifulSoup and Extruct integration

#### NLP Processor Service
**Location**: `core/services/nlp_processor.py`
**Responsibilities**:
- Parse free-text recipe descriptions
- Extract ingredients, quantities, and units
- Named entity recognition for food items
- spaCy integration with custom models

#### Consolidator Service
**Location**: `core/services/consolidator.py`
**Responsibilities**:
- Intelligent ingredient merging
- Unit standardization and conversion
- Duplicate detection algorithms
- Category-based organization

#### Scheduler Service
**Location**: `core/services/scheduler.py`
**Responsibilities**:
- Timeline optimization algorithms
- Constraint programming for food safety
- Workload balancing across days
- Task dependency management

### 3. Data Models

#### Core Models
**Location**: `core/models.py`

Key data structures:
- **MenuItemInput**: User input for recipes/descriptions
- **ProcessedMenuItem**: Validated recipe with structured ingredients
- **ConsolidatedGroceryList**: Optimized shopping list
- **Timeline**: Day-by-day preparation schedule
- **ProcessingResult**: Complete pipeline output

#### Enumerations
- **UnitEnum**: Standardized measurement units
- **IngredientCategory**: Grocery list organization
- **TaskType**: Preparation task classifications

### 4. User Interfaces

#### CLI Interface
**Location**: `interfaces/cli/`
**Components**:
- **main.py**: Typer CLI application setup
- **commands.py**: Command implementations
- **formatters.py**: Rich formatting for output

**Features**:
- Interactive command-line interface
- Rich formatting with colors and tables
- Progress bars for long-running operations
- Comprehensive help system

#### REST API Interface
**Location**: `interfaces/api/`
**Components**:
- **main.py**: FastAPI application setup
- **routers/**: Endpoint implementations
- **dependencies.py**: Dependency injection
- **responses.py**: Response formatting

**Features**:
- OpenAPI/Swagger documentation
- Async request handling
- Structured JSON responses
- Health check endpoints

### 5. Shared Utilities

#### Configuration Management
**Location**: `shared/config.py`
- Environment-based configuration
- Pydantic Settings validation
- Feature toggles and limits

#### Logging System
**Location**: `shared/logging.py`
- Structured JSON logging
- Request tracing and correlation IDs
- Performance metrics collection

#### Exception Hierarchy
**Location**: `shared/exceptions.py`
- Custom exception classes
- Error categorization and handling
- User-friendly error messages

#### Input Validation
**Location**: `shared/validators.py`
- Custom Pydantic validators
- Security-focused input sanitization
- Business rule validation

#### Internationalization
**Location**: `shared/i18n.py`
- Multi-language support infrastructure
- Localized error messages
- Cultural adaptation for units/formats

## Data Flow

### Primary Processing Pipeline

```
1. User Input → CLI/API Interface
2. Input Validation → Shared Validators
3. Menu Items → MealPlannerOrchestrator
4. Orchestrator → Recipe Processor Agent
5. Orchestrator → Ingredient Consolidator Agent
6. Orchestrator → Timeline Generator Agent (optional)
7. Orchestrator → Result Assembly & Validation
8. Complete Results → Response Formatting
9. Formatted Output → User Interface
```

### Orchestrator-Driven Flow

```
┌─────────────────┐    ┌─────────────────────────────────┐
│   CLI/API       │───▶│     MealPlannerOrchestrator     │
│   Interface     │    │                                 │
└─────────────────┘    │ ┌─────────────────────────────┐ │
                       │ │    Pipeline State Manager   │ │
                       │ └─────────────────────────────┘ │
                       │              │                  │
                       │              ▼                  │
                       │ ┌─────────────────────────────┐ │
                       │ │   Agent Coordinator         │ │
                       │ └─────────────────────────────┘ │
                       └─────────────────────────────────┘
                                       │
                                       ▼
           ┌─────────────────┬─────────────────┬
           │                 │                 │                 
           ▼                 ▼                 ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │   Recipe    │  │ Ingredient  │  │  Timeline   │
   │ Processor   │  │Consolidator │  │ Generator   │
   │   Agent     │  │   Agent     │  │   Agent     │
   └─────────────┘  └─────────────┘  └─────────────┘
```

### Agent Coordination

```
                    ┌───────────────────────────┐
                    │   MealPlannerOrchestrator │
                    │   ┌─────────────────┐     │
                    │   │ Pipeline State  │     │
                    │   │   Management    │     │
                    │   └─────────────────┘     │
                    │   ┌─────────────────┐     │
                    │   │ Phase Validation│     │
                    │   └─────────────────┘     │
                    │   ┌─────────────────┐     │
                    │   │ Error Handling  │     │
                    │   └─────────────────┘     │
                    └───────────────────────────┘
                              │
        ┌─────────────────────┼────────────────────┐
        │                     │                    │
        ▼                     ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Recipe          │  │ Ingredient      │  │ Timeline        │
│ Processor       │  │ Consolidator    │  │ Generator       │
│ Agent           │  │ Agent           │  │ Agent           │
└─────────────────┘  └─────────────────┘  └─────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Web Extractor   │  │ Consolidator    │  │ Scheduler       │
│ NLP Processor   │  │ Service         │  │ Service         │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Interface Integration Pattern

Both CLI and API interfaces follow the same orchestrator integration pattern:

```python
# CLI Interface (interfaces/cli/commands.py)
from core.meal_planner import MealPlannerOrchestrator, plan_holiday_meal

# API Interface (interfaces/api/routers/process.py)
from core.meal_planner import MealPlannerOrchestrator, MealPlanningRequest
```

**Key Integration Points**:
- **Unified Entry Point**: Both interfaces use the same orchestrator methods
- **Consistent Error Handling**: Common exception handling across interfaces
- **Identical Results**: Contract tests ensure CLI and API return identical data
- **Shared Configuration**: Common settings and validation logic

### Convenience Functions

The orchestrator provides high-level convenience functions for external usage:

**Location**: `core/meal_planner.py` (module-level functions)

```python
# Complete meal planning with optional timeline
async def plan_holiday_meal(
    menu_items: List[MenuItemInput],
    serving_size: int = 8,
    confidence_threshold: float = 0.6,
    similarity_threshold: float = 85.0,
    include_timeline: bool = False
) -> MealPlanningResponse

# Simplified grocery list generation
async def generate_grocery_list(
    menu_items: List[MenuItemInput],
    serving_size: int = 8
) -> ConsolidatedGroceryList

# Single recipe processing
async def process_recipe_url(
    url: str,
    serving_size: int = 8
) -> ConsolidatedGroceryList
```

These functions create orchestrator instances internally and provide simplified APIs for common use cases.

## Technology Stack

### Core Technologies
- **Language**: Python 3.9+
- **AI Framework**: PydanticAI for agent coordination
- **Type System**: Pydantic v2 with full type hints
- **Async Runtime**: asyncio for concurrent processing

### User Interface Technologies
- **CLI**: Typer with Rich formatting
- **API**: FastAPI with automatic OpenAPI generation
- **HTTP Client**: HTTPX for testing and client integrations

### AI & NLP Technologies
- **NLP Engine**: spaCy with en_core_web_sm model
- **Web Scraping**: recipe-scrapers + BeautifulSoup4
- **Fuzzy Matching**: FuzzyWuzzy with C speedup
- **Unit Conversion**: Pint library

### Optimization Technologies
- **Graph Algorithms**: NetworkX for dependency modeling
- **Constraint Programming**: Google OR-Tools for scheduling
- **Date/Time Handling**: python-dateutil

### Development & Quality
- **Build System**: Hatchling (PEP 517)
- **Dependency Management**: uv for fast package resolution
- **Code Formatting**: Black + isort
- **Type Checking**: mypy with strict configuration
- **Linting**: Ruff for fast Python linting
- **Testing**: pytest with asyncio and coverage

## Security Architecture

### Input Security
- **Validation**: Pydantic models validate all inputs
- **Sanitization**: Custom validators prevent injection attacks
- **Rate Limiting**: Configurable limits on requests and processing

### Network Security
- **HTTPS Only**: All external requests use secure protocols
- **URL Validation**: Recipe URLs are validated before processing
- **Timeout Protection**: Network requests have configurable timeouts

### Data Security
- **No Persistent Storage**: Application is stateless by design
- **Memory Management**: Automatic cleanup of processing data
- **Error Handling**: No sensitive data in error messages

## Performance Characteristics

### Processing Targets
- **Small Menus** (1-4 dishes): < 10 seconds
- **Medium Menus** (5-8 dishes): < 30 seconds
- **Large Menus** (9-12 dishes): < 60 seconds

### Scalability Features
- **Async Processing**: Concurrent recipe processing
- **Memory Efficient**: Streaming processing where possible
- **Resource Limits**: Configurable limits on processing complexity

### Optimization Strategies
- **Caching**: Recipe metadata caching during processing
- **Batching**: Efficient bulk operations for similar ingredients
- **Early Termination**: Stop processing on confidence thresholds

## Testing Strategy

### Test Architecture

```
tests/
├── unit/              # Isolated component testing
├── integration/       # Full pipeline testing
├── contract/          # CLI-API consistency testing
└── performance/       # Load and timing testing
```

### Testing Approaches

#### Unit Tests
- **Mocking**: External dependencies (web, NLP models)
- **Fixtures**: Controlled test data
- **Coverage**: >90% code coverage target

#### Integration Tests
- **End-to-End**: Complete pipeline with real data
- **Error Scenarios**: Failure case handling
- **Performance**: Timing and resource usage

#### Contract Tests
- **Interface Consistency**: CLI and API return identical results
- **Data Validation**: All inputs/outputs match schemas
- **Error Compatibility**: Consistent error handling

## Configuration Management

### Environment Variables

```bash
# Rate Limiting
MEAL_PLANNER_REQUEST_DELAY=2.0      # seconds between requests
MEAL_PLANNER_MAX_ITEMS=20           # maximum menu items
MEAL_PLANNER_TIMEOUT=30             # web request timeout

# Processing Thresholds
MEAL_PLANNER_CONFIDENCE_THRESHOLD=0.6  # minimum NLP confidence
MEAL_PLANNER_SIMILARITY_THRESHOLD=85   # ingredient matching threshold
MEAL_PLANNER_MAX_PREP_DAYS=7          # maximum advance preparation

# Resource Limits
MEAL_PLANNER_MAX_WORKERS=4            # parallel processing workers
MEAL_PLANNER_MEMORY_LIMIT=1024        # MB memory limit per process
```

### Configuration Validation
- **Pydantic Settings**: Type-safe configuration loading
- **Environment Detection**: Automatic dev/test/prod configuration
- **Validation**: Startup validation of all configuration values

## Deployment Architecture

### Development Environment
- **Local Development**: Direct Python execution
- **Virtual Environment**: Isolated dependency management
- **Live Reload**: Automatic restart on code changes

### Production Deployment
- **Container Ready**: Docker-compatible application structure
- **Process Management**: WSGI/ASGI server compatibility
- **Health Checks**: Built-in health and readiness endpoints

### Monitoring Integration
- **Structured Logging**: JSON logs for centralized collection
- **Metrics**: Processing time and success rate tracking
- **Tracing**: Request correlation across agent pipeline

## Future Architecture Considerations

### Scalability Enhancements
- **Microservices**: Potential agent separation for horizontal scaling
- **Message Queues**: Async processing for large batch operations
- **Caching Layer**: Recipe and ingredient caching for performance

### AI/ML Enhancements
- **Custom Models**: Domain-specific ingredient recognition training
- **Learning Pipeline**: User feedback integration for improved accuracy
- **A/B Testing**: Algorithm optimization based on user outcomes

### Integration Capabilities
- **Calendar Integration**: Timeline export to calendar applications
- **Shopping Apps**: Direct grocery list export to shopping services
- **Recipe Platforms**: Enhanced recipe source integrations

---

*This architecture documentation is maintained as a living document and should be updated as the system evolves.*