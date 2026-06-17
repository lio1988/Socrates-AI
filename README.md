# Σωκρατικός Διάλογος Pro - Python Edition

**Philosophical Dialogues with Multiple LLM Models**

This is a Python conversion of the original HTML/JavaScript Socratic Dialog application. It enables multi-model philosophical discussions where different AI models engage in Socratic questioning and dialectical reasoning.

## Features

✨ **Multi-Model Dialogues**: Engage Claude, Grok, Gemini, and ChatGPT in philosophical discussions

🏛️ **Socratic Method**: True Socratic questioning with maieutic dialogue

⚔️ **Multiple Dialog Modes**:
- **Socratic**: Pure Socratic method with examination and questioning
- **Debate**: Adversarial format with logical argumentation
- **Consensus**: Seeks common ground and synthesis

📊 **Intelligent Scoring**: Tracks contributions and detects intellectual progress

💾 **Export Formats**: Save dialogs as JSON or Markdown

🌐 **Greek Language**: Full support for Greek philosophical terminology

⏱️ **Speed Control**: 5 speed levels from very slow to instant

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Set environment variables for your LLM providers:

```bash
export ANTHROPIC_API_KEY="your-claude-key"
export XAI_API_KEY="your-grok-key"
export GOOGLE_API_KEY="your-gemini-key"
export OPENAI_API_KEY="your-openai-key"
```

Or create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
XAI_API_KEY=xai-...
GOOGLE_API_KEY=AIza...
OPENAI_API_KEY=sk-...
```

### 3. Run the Application

```bash
python socrates_ai.py
```

## Usage

The application will guide you through an interactive setup:

```
🏛️  Σωκρατικός Διάλογος Pro
Philosophical Dialogues with Multiple LLMs

✅ Found 4 configured models: claude, grok, gemini, chatgpt

📖 Enter dialog topic (or press Enter for AI Ethics): Τι είναι η συνείδηση;
🔄 Enter number of rounds (default 8): 6
⚙️  Select mode (socratic/debate/consensus, default socratic): socratic
⏱️  Select speed (0-4, default 2): 2
```

## Dialog Modes

### 🏛️ Socratic Mode
The classic Socratic method where one model acts as Socrates, asking probing questions to expose contradictions and guide discovery of truth. Other models respond and are examined.

### ⚔️ Debate Mode
Adversarial format where models defend positions with logical argumentation. Emphasis on rhetoric and persuasion.

### 🤝 Consensus Mode
Cooperative format seeking synthesis and common ground. Models build on each other's insights.

## Architecture

### Core Classes

**DialogConfig**: Stores configuration (topic, rounds, mode, speed, summary)

**DialogManager**: Orchestrates the dialog session
- Manages turn rotation
- Calls LLM APIs
- Tracks scores and progress
- Generates summaries and synthesis

**DialogTurn**: Individual turn data (round, model, content, metadata)

**ModelConfig**: Model personalities, colors, and instructions

### Key Methods

- `run_dialog()`: Main event loop
- `_run_round()`: Execute single round with all models
- `_call_model()`: Route to correct API
- `_build_socratic_prompt()`: Socratic questioning prompt
- `_build_participant_prompt()`: Response prompt
- `_detect_progress()`: Smart scoring for intellectual progress
- `export_json()` / `export_markdown()`: Save dialogs

## Scoring System

Models earn points for:
- **Participation**: 1 point per turn
- **Progress**: 3 points for showing intellectual growth (detecting changes in perspective, acknowledging stronger arguments, etc.)

The scoring system uses keyword detection to identify when models demonstrate genuine progress or dialectical reasoning.

## API Support

### Claude (Anthropic)
- Model: `claude-3-5-sonnet-20241022`
- 1024 token max output

### Grok (xAI)
- Model: `grok-2-latest`
- 1024 token max output

### Gemini (Google)
- Model: `gemini-pro`
- 1024 token max output

### ChatGPT (OpenAI)
- Model: `gpt-4o-mini`
- 1024 token max output

## Output Examples

### Console Output
```
🏛️  Έναρξη Κυκλικού Σωκρατικού Ελέγχου
📖 Θέμα: Ηθική της Τεχνητής Νοημοσύνης
🔄 Γύροι: 6
⚙️  Mode: socratic
⏱️  Ταχύτητα: Κανονική
================================================================================

🔄 Γύρος 1
────────────────────────────────────────────────────────────────────────────────
🟠 Claude ως Σωκράτης: 
  Αν η ηθική της ΑΙ είναι το ερώτημα, ποια θεωρούμε ως τις θεμελιώδεις αρχές...

🔵 Grok: 
  Η ηθική δεν είναι κάτι που ορίζεται εκ των άνω. Είναι κάτι που δημιουργείται...

💠 Gemini: 
  Συμφωνώ εν μέρει, αλλά υπάρχει μια σημαντική διαφορά...

🟢 ChatGPT: 
  Η πρόσεγγιση σας είναι ενδιαφέρουσα, αλλά αν θεωρήσουμε...
```

### JSON Export
```json
{
  "topic": "Ηθική της Τεχνητής Νοημοσύνης",
  "mode": "socratic",
  "rounds": 6,
  "timestamp": "2024-06-17T10:30:00",
  "history": [
    {
      "round": 1,
      "model_id": "claude",
      "content": "...",
      "is_socratic": true
    }
  ],
  "scores": {
    "claude": 12,
    "grok": 9,
    "gemini": 8,
    "chatgpt": 10
  }
}
```

## Configuration Options

### Rounds
- 4, 6, 8, 10, 12, 16, 20
- Default: 8

### Speed
- 0: Πολύ Γρήγορη (0s delay)
- 1: Γρήγορη (0.1s delay)
- 2: Κανονική (0.45s delay)
- 3: Αργή (1.1s delay)
- 4: Πολύ Αργή (2.2s delay)

### Summary Mode
- None: No summaries
- Every: Summary after each round
- Half: Summary every 2 rounds

## Error Handling

The application gracefully handles:
- Missing API keys (with helpful error message)
- API failures (logs error and continues)
- Invalid inputs (with defaults)
- Interrupted sessions (Ctrl+C)

## Development

To extend the application:

1. **Add a new model**: Add config to `ModelConfig.MODELS` and create `_call_[model]()` method
2. **Add a new mode**: Add to `DialogMode` enum and `MODE_INSTRUCTIONS`
3. **Customize prompts**: Edit `_build_socratic_prompt()` and `_build_participant_prompt()`
4. **Add features**: Extend `DialogManager` class

## License

MIT License - See LICENSE file

## Original Project

Based on the HTML/JavaScript version: https://github.com/lio1988/Socrates-AI

## Contributing

Contributions welcome! Please submit issues and pull requests.
