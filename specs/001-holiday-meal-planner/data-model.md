# Data Model

**Feature**: Holiday Meal Planner
**Date**: 2026-03-18
**Version**: 1.0

## Core Entities

### MenuItemInput
Represents user input for a single dish in the holiday menu.

**Fields**:
- `id`: Unique identifier (auto-generated UUID)
- `source_url`: Optional recipe URL for web extraction
- `description`: Optional free-text description of the dish
- `serving_size`: Number of people this dish serves (default: 8)

**Validation Rules**:
- Must have either `source_url` OR `description` (not both empty)
- If `source_url` provided, must be valid HTTPS URL
- `serving_size` must be positive integer ≤ 100

**State Transitions**:
- Input → Processing → Processed/Failed

---

### Ingredient
Represents a single ingredient with standardized quantity and unit.

**Fields**:
- `name`: Canonical ingredient name (normalized)
- `quantity`: Numeric amount required
- `unit`: Standardized unit of measurement (enum)
- `category`: Food category for organization (optional)
- `confidence`: Extraction confidence score (0.0-1.0)
- `original_text`: Original extracted text for reference

**Validation Rules**:
- `quantity` must be positive decimal
- `unit` must be from supported unit enumeration
- `name` must be non-empty after normalization
- `confidence` between 0.0 and 1.0

**Unit Enumeration**:
```
VOLUME: cup, tablespoon, teaspoon, fluid_ounce, pint, quart, gallon, liter, milliliter
WEIGHT: pound, ounce, gram, kilogram
COUNT: whole, piece, clove, bunch, package
SPECIAL: to_taste, pinch, dash
```

---

### ConsolidatedGroceryList
Represents the final consolidated shopping list with optimized quantities.

**Fields**:
- `ingredients`: List of consolidated Ingredient objects
- `total_items`: Count of unique ingredients
- `consolidation_notes`: List of merging decisions made
- `generated_at`: Timestamp of list generation
- `serving_size`: Total serving size for entire menu

**Validation Rules**:
- `ingredients` list cannot be empty
- All ingredients must have positive quantities
- `total_items` must match length of ingredients list

---

### PrepTask
Represents a single preparation task with timing and dependency information.

**Fields**:
- `id`: Unique task identifier
- `dish_name`: Name of associated dish
- `task_description`: What needs to be done
- `estimated_duration`: Time in minutes
- `dependencies`: List of task IDs that must complete first
- `timing_type`: Category of timing constraint (enum)
- `optimal_timing`: When task should ideally be performed relative to meal
- `confidence`: AI confidence in task details

**Timing Type Enumeration**:
```
MAKE_AHEAD: Can be done days in advance
DAY_BEFORE: Should be done 12-24 hours prior
DAY_OF_EARLY: Morning of meal day
DAY_OF_LATE: Within 4 hours of meal
IMMEDIATE: Must be done just before serving
```

**Validation Rules**:
- `estimated_duration` must be positive integer
- Dependencies cannot create circular references
- `optimal_timing` must align with food safety rules

---

### DayPlan
Represents preparation tasks scheduled for a specific day.

**Fields**:
- `day_offset`: Days before meal (0 = day of meal)
- `date`: Actual calendar date
- `tasks`: List of PrepTask objects scheduled for this day
- `total_duration`: Sum of all task durations in minutes
- `workload_level`: Subjective difficulty rating (1-5 scale)
- `notes`: Additional guidance for the day

**Validation Rules**:
- `day_offset` must be non-negative integer ≤ 7
- `total_duration` should not exceed 240 minutes (4 hours) without warning
- `tasks` cannot have conflicting dependencies

---

### Timeline
Represents the complete day-by-day preparation schedule.

**Fields**:
- `meal_date`: Target date and time for the meal
- `days`: List of DayPlan objects ordered by day_offset
- `critical_path`: List of tasks on the critical path
- `total_prep_time`: Sum of all preparation time across all days
- `complexity_score`: Overall difficulty rating (1-10 scale)
- `optimization_notes`: Explanation of scheduling decisions

**Validation Rules**:
- `meal_date` must be in the future
- `days` must be ordered by day_offset (descending)
- Critical path tasks must form valid dependency chain

---

### ProcessingResult
Represents the complete output of the meal planning pipeline.

**Fields**:
- `grocery_list`: ConsolidatedGroceryList object
- `prep_timeline`: Timeline object
- `processed_items`: List of successfully processed MenuItemInput
- `failed_items`: List of items that failed processing with error messages
- `processing_metadata`: Statistics and performance information
- `generated_at`: Timestamp of result generation

**Validation Rules**:
- Must have at least one successfully processed item
- `grocery_list` and `prep_timeline` must be consistent with processed items
- All timestamps must be in ISO format

---

## Entity Relationships

```
MenuItemInput (1:N) → Ingredient
    ↓ (processing)
ConsolidatedGroceryList (1:N) → Ingredient

MenuItemInput (1:N) → PrepTask
    ↓ (scheduling)
Timeline (1:N) → DayPlan (1:N) → PrepTask

ProcessingResult → ConsolidatedGroceryList
ProcessingResult → Timeline
ProcessingResult (1:N) → MenuItemInput
```

## Data Flow

1. **Input Phase**: User provides MenuItemInput objects (URLs + descriptions)
2. **Processing Phase**: Extract ingredients and prep requirements per item
3. **Consolidation Phase**: Merge ingredients → ConsolidatedGroceryList
4. **Scheduling Phase**: Generate PrepTasks → Timeline with DayPlan objects
5. **Output Phase**: Combine all results → ProcessingResult

## Constitutional Compliance

- **Type Safety**: All entities use Pydantic models with strict validation
- **Input Sanitization**: URL validation and text cleaning at ingestion
- **Error Handling**: Failed items tracked separately from successful processing
- **Auditability**: Confidence scores and original text preserved for traceability
- **Performance**: Memory-only processing with no persistent storage requirements