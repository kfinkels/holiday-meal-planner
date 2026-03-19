# Tasks: Holiday Meal Planner

**Input**: Design documents from `/specs/001-holiday-meal-planner/`
**Prerequisites**: spec.md (user stories), research.md (technical decisions), data-model.md (entities), quickstart.md (implementation plan)

**Tests**: Tests are optional for this implementation - focus on getting core functionality working first

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [SYNC/ASYNC] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[SYNC]**: Requires human review (complex logic, security-critical, architectural decisions)
- **[ASYNC]**: Can be delegated to async agents (well-defined CRUD, repetitive tasks, clear specifications)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on quickstart.md project structure:
- Core business logic: `core/`
- CLI interface: `interfaces/cli/`
- API interface: `interfaces/api/`
- Shared utilities: `shared/`
- Tests: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 [ASYNC] Create project directory structure per quickstart.md implementation plan
- [X] T002 [ASYNC] Initialize Python project with pyproject.toml and dependencies (pydantic-ai, typer, fastapi, recipe-scrapers, spacy, networkx, ortools, pint, fuzzywuzzy)
- [X] T003 [P] [ASYNC] Configure development tools (black, isort, mypy, pytest) in pyproject.toml
- [X] T004 [P] [ASYNC] Create .gitignore file with Python and IDE exclusions
- [X] T005 [P] [ASYNC] Setup basic README.md with project overview and quickstart instructions

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure and models that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 [SYNC] Create Pydantic data models in core/models.py (MenuItemInput, Ingredient, ConsolidatedGroceryList, PrepTask, DayPlan, Timeline, ProcessingResult)
- [X] T007 [P] [ASYNC] Create custom exception types in shared/exceptions.py (MealPlannerException, RecipeParsingError, IngredientConsolidationError, TimelineGenerationError)
- [X] T008 [P] [ASYNC] Implement configuration management in shared/config.py (Settings class with environment variables, security constraints, processing limits)
- [X] T009 [P] [ASYNC] Create input validation utilities in shared/validators.py (URL validation, security checks, input sanitization)
- [X] T010 [SYNC] Setup logging infrastructure with correlation IDs for debugging multi-agent pipeline operations
- [X] T011 [P] [ASYNC] Create basic test fixtures and utilities in tests/conftest.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Recipe Processing and Grocery List Generation (Priority: P1) 🎯 MVP

**Goal**: Users can provide recipe URLs and dish descriptions to receive a consolidated grocery list with all ingredients and quantities

**Independent Test**: Process 3-4 dishes (mix of URLs and descriptions) and verify consolidated ingredient list with correct quantities and no obvious duplicates

### Core Services for User Story 1

- [X] T012 [P] [SYNC] [US1] Implement secure web extraction service in core/services/web_extractor.py (recipe-scrapers integration with HTTPS-only, rate limiting, security validation)
- [X] T013 [P] [SYNC] [US1] Implement NLP ingredient processor in core/services/nlp_processor.py (spaCy integration with custom NER training, confidence scoring)
- [X] T014 [P] [SYNC] [US1] Implement ingredient consolidator in core/services/consolidator.py (fuzzy matching, unit conversion with pint, quantity aggregation)

### Multi-Agent Pipeline for User Story 1

- [X] T015 [SYNC] [US1] Create RecipeProcessorAgent in core/agents/recipe_processor.py (orchestrates web extraction and NLP processing with error handling)
- [X] T016 [SYNC] [US1] Create IngredientConsolidatorAgent in core/agents/ingredient_consolidator.py (manages ingredient deduplication and unit normalization)
- [X] T017 [SYNC] [US1] Implement main meal planner orchestrator in core/meal_planner.py (PydanticAI pipeline coordination, state management, async processing)

### Basic CLI Interface for User Story 1

- [X] T018 [P] [ASYNC] [US1] Create CLI output formatters in interfaces/cli/formatters.py (human-readable grocery list display, error message formatting)
- [X] T019 [SYNC] [US1] Implement basic CLI commands in interfaces/cli/commands.py (process command with URL and description inputs)
- [X] T020 [ASYNC] [US1] Create CLI entry point in interfaces/cli/main.py (Typer application setup, command registration)

**Checkpoint**: At this point, User Story 1 should be fully functional - users can process recipes and get consolidated grocery lists via CLI

---

## Phase 4: User Story 2 - Preparation Timeline Planning (Priority: P2)

**Goal**: Users receive day-by-day preparation plans showing optimal task scheduling and workload distribution

**Independent Test**: Process a holiday menu and verify timeline includes logical task sequencing with make-ahead items scheduled appropriately

### Timeline Services for User Story 2

- [X] T021 [P] [SYNC] [US2] Implement task dependency analyzer in core/services/scheduler.py (topological sorting with NetworkX, food safety constraints, critical path analysis)
- [X] T022 [SYNC] [US2] Create TimelineGeneratorAgent in core/agents/timeline_generator.py (constraint programming with OR-Tools, workload balancing, day-by-day scheduling)

### CLI Integration for User Story 2

- [X] T023 [P] [ASYNC] [US2] Extend CLI formatters in interfaces/cli/formatters.py (timeline display, day-by-day task formatting, workload summaries)
- [X] T024 [SYNC] [US2] Update CLI commands in interfaces/cli/commands.py (add timeline generation options, meal datetime input, prep day limits)
- [X] T025 [SYNC] [US2] Update meal planner orchestrator in core/meal_planner.py (integrate timeline generation into pipeline, ensure processing result consistency)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - users get both grocery lists and preparation timelines

---

## Phase 5: User Story 3 - Multiple Interface Access (Priority: P3)

**Goal**: Users can access meal planning functionality through both CLI and REST API with identical results

**Independent Test**: Process the same menu through both CLI and API calls, verify identical results in appropriate formats

### API Implementation for User Story 3

- [X] T026 [P] [ASYNC] [US3] Create API response models in interfaces/api/responses.py (FastAPI response schemas matching OpenAPI spec)
- [X] T027 [P] [SYNC] [US3] Implement API routers in interfaces/api/routers/ (process endpoint, async job handling, utility endpoints per api-spec.yml)
- [X] T028 [P] [ASYNC] [US3] Create shared dependencies in interfaces/api/dependencies.py (rate limiting, input validation, error handling)
- [X] T029 [SYNC] [US3] Create FastAPI application in interfaces/api/main.py (app setup, router registration, CORS configuration, OpenAPI documentation)

### Interface Consistency for User Story 3

- [X] T030 [SYNC] [US3] Implement shared service layer pattern (ensure identical business logic between CLI and API, unified error handling)
- [X] T031 [P] [ASYNC] [US3] Create contract tests in tests/contract/ (verify CLI and API return identical results for same inputs)

**Checkpoint**: All user stories should now be independently functional through both CLI and API interfaces

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality improvements that enhance all user stories

- [ ] T032 [P] [ASYNC] Create comprehensive unit tests in tests/unit/ (mock external dependencies, test individual components)
- [ ] T033 [P] [ASYNC] Create integration tests in tests/integration/ (end-to-end pipeline testing with controlled test data)
- [ ] T034 [P] [ASYNC] Add performance monitoring and metrics (processing time tracking, success rate monitoring, confidence score analysis)
- [ ] T035 [SYNC] Security hardening review (input validation audit, rate limiting verification, HTTPS-only enforcement)
- [ ] T036 [P] [ASYNC] Documentation updates (API documentation generation, CLI help text, error message clarity)
- [ ] T037 [ASYNC] Run quickstart.md validation scenarios (verify implementation matches quickstart guidance)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational - Integrates with US1 but independently testable
- **User Story 3 (P3)**: Can start after Foundational - Uses US1+US2 logic but provides different interfaces

### Within Each User Story

- Services before agents (agents orchestrate services)
- Core implementation before interface integration
- CLI formatting before API responses
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational completes, all user stories can start in parallel (if team capacity allows)
- Services within each story marked [P] can run in parallel
- Interface implementations marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch core services for User Story 1 together:
Task T012: "Implement secure web extraction service in core/services/web_extractor.py"
Task T013: "Implement NLP ingredient processor in core/services/nlp_processor.py"
Task T014: "Implement ingredient consolidator in core/services/consolidator.py"

# Launch interface components together:
Task T018: "Create CLI output formatters in interfaces/cli/formatters.py"
Task T020: "Create CLI entry point in interfaces/cli/main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test recipe processing and grocery list generation independently
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (adds timeline planning)
4. Add User Story 3 → Test independently → Deploy/Demo (adds API interface)
5. Each story adds value without breaking previous functionality

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (core recipe processing)
   - Developer B: User Story 2 (timeline generation)
   - Developer C: User Story 3 (API interface)
3. Stories integrate but remain independently testable

---

## Task Classification Summary

**[SYNC] Tasks (25 total)**: Complex business logic, multi-agent coordination, security-critical components, architectural decisions
**[ASYNC] Tasks (12 total)**: Well-defined infrastructure, formatting, configuration, repetitive implementations

**SYNC/ASYNC Rationale**:
- **Multi-agent orchestration** → SYNC (requires understanding of PydanticAI patterns and error handling)
- **Web scraping security** → SYNC (constitutional requirement for security-first approach)
- **NLP confidence scoring** → SYNC (requires domain expertise for ingredient extraction)
- **Timeline optimization** → SYNC (complex constraint programming and algorithm selection)
- **Project setup and formatting** → ASYNC (well-defined, standard patterns)

---

## Notes

- [P] tasks = different files, no dependencies
- [SYNC]/[ASYNC] classification drives execution strategy
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Constitutional compliance: HTTPS-only, 90% test coverage target, security by default
- Focus on MVP delivery: get User Story 1 working first, then expand functionality