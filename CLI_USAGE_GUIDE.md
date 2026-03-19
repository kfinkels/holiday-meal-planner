# CLI Usage Guide - Hebrew Support / מדריך שימוש בעברית

## ✅ **Ready to Use Commands:**

### **1. Basic Syntax:**

```bash
uv run python -m interfaces.cli.main process [OPTIONS]
```

### **2. Hebrew Output Examples:**

```bash
# Simple Hebrew recipe
uv run python -m interfaces.cli.main process -l he -d "עוף צלוי עם תפוחי אדמה" -s 6

# Multiple Hebrew recipes
uv run python -m interfaces.cli.main process -l he \
  -d "עוף צלוי עם תפוחי אדמה" \
  -d "אורז עם ירקות" \
  -d "סלט ירוק עם עגבניות" \
  -s 8

# Hebrew with timeline
uv run python -m interfaces.cli.main process -l he \
  -d "עוף צלוי עם תפוחי אדמה" \
  --timeline \
  --meal-date "2026-03-21 18:00" \
  -s 6

# Mix URLs and Hebrew descriptions
uv run python -m interfaces.cli.main process -l he \
  --url "https://example.com/recipe" \
  -d "עוף צלוי עם תפוחי אדמה" \
  -s 10
```

### **3. English Output Examples:**

```bash
# English recipe
uv run python -m interfaces.cli.main process -l en -d "roasted chicken with potatoes" -s 6

# Default (English) - no need to specify language
uv run python -m interfaces.cli.main process -d "roasted chicken with potatoes" -s 6
```

### **4. All Available Options:**

```bash
uv run python -m interfaces.cli.main process \
  --language he \                    # -l he (Language: he/en)
  --description "עוף צלוי" \           # -d (Recipe description)
  --url "https://..." \              # -u (Recipe URL)
  --serving-size 8 \                 # -s (Number of people)
  --confidence 0.8 \                 # -c (Confidence threshold)
  --similarity 90 \                  # Similarity for consolidation
  --timeline \                       # -t Generate timeline
  --meal-date "2026-03-21 18:00" \   # -m Meal date
  --max-prep-days 5 \               # Maximum prep days
  --max-daily-hours 4 \             # Max hours per day
  --table \                         # Table format output
  --details \                       # Show detailed info
  --output grocery_list.txt         # -o Save to file
```

### **5. Quick Test Commands:**

```bash
# Test Hebrew support (simple)
uv run python demo_cli_simple.py

# Test Hebrew vs English comparison
uv run python demo_hebrew.py

# Test simple Hebrew CLI functionality
uv run python test_cli_hebrew.py
```

## 🔧 **Command Structure:**

### **Main Command:**
```bash
uv run python -m interfaces.cli.main [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]
```

### **Available Commands:**
- `process` - Main meal planning command
- `quick` - Quick single recipe processing
- `interactive` - Interactive meal planner
- `validate` - Validate recipes
- `timeline` - Generate timelines
- `config` - Show configuration
- `version` - Show version

### **Language Options:**
- `--language en` or `-l en` - English output
- `--language he` or `-l he` - Hebrew output
- `--language hebrew` or `-l hebrew` - Hebrew output
- `--language עברית` or `-l עברית` - Hebrew output

## 📝 **Expected Output:**

### **Hebrew Output Example:**
```
🛒 רשימת קניות עבור 6 אנשים • 5 פריטים
=====================================

🥩 חלבונים
─────────
  □ 2 פאונד עוף

🥕 ירקות
───────
  □ 4 פאונד תפוחי אדמה
  □ 1 שלם בצל

📅 נוצר: 2026-03-19 14:30
```

### **English Output Example:**
```
🛒 Grocery List for 6 people • 5 items
=====================================

🥩 Protein
─────────
  □ 2 pound chicken

🥕 Vegetables
────────────
  □ 4 pound potatoes
  □ 1 whole onion

📅 Generated: 2026-03-19 14:30
```

## ⚠️ **Important Notes:**

1. **Dependencies**: For full AI functionality, you'll need:
   - OpenAI API key: `export OPENAI_API_KEY="your-key"`
   - Recipe scraping libraries
   - NLP models

2. **Language Detection**: The system will automatically detect Hebrew input, but you still need to specify the output language with `-l he`

3. **Fallback**: Missing translations automatically fall back to English

4. **File Output**: When using `--output`, the file will be saved in the specified language

## 🎯 **Quick Start:**

1. **Test Hebrew formatting** (no AI needed):
   ```bash
   uv run python demo_hebrew.py
   ```

2. **Try CLI with sample data** (no AI needed):
   ```bash
   uv run python demo_cli_simple.py
   ```

3. **Use CLI with Hebrew** (requires AI setup):
   ```bash
   uv run python -m interfaces.cli.main process -l he -d "עוף צלוי" -s 6
   ```

## 🔍 **Troubleshooting:**

- If `--language` option doesn't appear: Make sure you're using the updated code
- If Hebrew text looks broken: Check your terminal supports Unicode/UTF-8
- If AI processing fails: Check API keys and dependencies
- For help: `uv run python -m interfaces.cli.main process --help`