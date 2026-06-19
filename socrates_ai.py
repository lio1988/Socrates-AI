#!/usr/bin/env python3
"""
Σωκρατικός Διάλογος Pro - Socratic Dialog with Multiple LLM Models
Convert HTML/JavaScript version to pure Python CLI application
"""

import json
import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import anthropic
import requests


class DialogMode(Enum):
    """Dialog modes available"""
    SOCRATIC = "socratic"
    DEBATE = "debate"
    CONSENSUS = "consensus"


class DialogSpeed(Enum):
    """Speed levels for dialog delays"""
    VERY_SLOW = ("Πολύ Αργή", 2.2)
    SLOW = ("Αργή", 1.1)
    NORMAL = ("Κανονική", 0.45)
    FAST = ("Γρήγορη", 0.1)
    VERY_FAST = ("Πολύ Γρήγορη", 0.0)

    def __init__(self, label: str, delay: float):
        self.label = label
        self.delay = delay


class SummaryMode(Enum):
    """Round summary modes"""
    NONE = "none"
    EVERY = "every"
    HALF = "half"


@dataclass
class DialogTurn:
    """Single turn in the dialog"""
    round: int
    model_id: str
    content: str
    is_socratic: bool = False
    is_injection: bool = False
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class DialogConfig:
    """Configuration for a dialog session"""
    topic: str
    rounds: int = 8
    mode: DialogMode = DialogMode.SOCRATIC
    speed: DialogSpeed = DialogSpeed.NORMAL
    summary_mode: SummaryMode = SummaryMode.EVERY


class ModelConfig:
    """Model configurations and personalities"""

    MODELS = {
        "claude": {
            "name": "Claude",
            "icon": "🟠",
            "color": "#c17f3a",
            "personality": "αναλυτικός, ηθικά προσεκτικός, αναγνωρίζεις αβεβαιότητα",
        },
        "grok": {
            "name": "Grok",
            "icon": "🔵",
            "color": "#3ab8d4",
            "personality": "προκλητικός, anti-establishment, τολμηρός, δεν φοβάσαι να αμφισβητήσεις",
        },
        "gemini": {
            "name": "Gemini",
            "icon": "💠",
            "color": "#6a9fd8",
            "personality": "ολιστικός, σύνθεση, ζυγοσταθμισμένος, αναζητάς αρμονία",
        },
        "chatgpt": {
            "name": "ChatGPT",
            "icon": "🟢",
            "color": "#4fbb7c",
            "personality": "λογικός, δομημένος, χρήσιμος, ευέλικτος",
        },
    }

    MODE_INSTRUCTIONS = {
        "socratic": "Ακολουθείς τη σωκρατική ελεγκτική και μαιευτική μέθοδο.",
        "debate": "Ο διάλογος είναι σε format αντιδικίας. Υπερασπίζεσαι τη θέση σου με λογική.",
        "consensus": "Στόχος: βρες κοινό έδαφος και δημιούργησε σύνθεση των απόψεων.",
    }


class DialogManager:
    """Manages the Socratic dialog session"""

    def __init__(self, config: DialogConfig, api_keys: Dict[str, str]):
        self.config = config
        self.api_keys = api_keys
        self.history: List[DialogTurn] = []
        self.scores: Dict[str, int] = {mid: 0 for mid in api_keys.keys()}
        self.available_models = list(api_keys.keys())
        self._validate_setup()

    def _validate_setup(self):
        """Validate that we have enough models and API keys"""
        if len(self.available_models) < 2:
            raise ValueError(
                f"Need at least 2 models. Got {len(self.available_models)}"
            )
        for model_id in self.available_models:
            if not self.api_keys[model_id]:
                raise ValueError(f"Missing API key for {model_id}")

    async def run_dialog(self) -> str:
        """Execute the complete Socratic dialog"""
        print(f"\n🏛️  Έναρξη Κυκλικού Σωκρατικού Ελέγχου")
        print(f"📖 Θέμα: {self.config.topic}")
        print(f"🔄 Γύροι: {self.config.rounds}")
        print(f"⚙️  Mode: {self.config.mode.value}")
        print(f"⏱️  Ταχύτητα: {self.config.speed.label}")
        print("=" * 80)

        for round_num in range(1, self.config.rounds + 1):
            if not await self._run_round(round_num):
                break

            # Add round summary if configured
            if self._should_summarize(round_num):
                await self._generate_summary(round_num)

        # Generate final philosophical synthesis
        await self._generate_synthesis()

        return self._format_output()

    async def _run_round(self, round_num: int) -> bool:
        """Execute a single dialog round"""
        print(f"\n🔄 Γύρος {round_num}")
        print("-" * 80)

        # Determine Socrates for this round (rotate through models)
        socrates_id = self.available_models[(round_num - 1) % len(self.available_models)]
        model_name = ModelConfig.MODELS[socrates_id]["name"]
        icon = ModelConfig.MODELS[socrates_id]["icon"]

        print(f"{icon} {model_name} ως Σωκράτης: ")

        # Socrates asks/examines
        socratic_response = await self._call_model(
            socrates_id,
            self._build_socratic_prompt(socrates_id, round_num),
        )

        if socratic_response:
            self.history.append(
                DialogTurn(
                    round=round_num,
                    model_id=socrates_id,
                    content=socratic_response,
                    is_socratic=True,
                )
            )
            print(f"  {socratic_response[:150]}...\n")
            self._add_score(socrates_id, 1)
            await self._delay()
        else:
            return False

        # Other models respond
        for respondent_id in self.available_models:
            if respondent_id == socrates_id:
                continue

            respondent_name = ModelConfig.MODELS[respondent_id]["name"]
            respondent_icon = ModelConfig.MODELS[respondent_id]["icon"]
            print(f"{respondent_icon} {respondent_name}: ")

            response = await self._call_model(
                respondent_id,
                self._build_participant_prompt(respondent_id, round_num),
            )

            if response:
                self.history.append(
                    DialogTurn(
                        round=round_num,
                        model_id=respondent_id,
                        content=response,
                        is_socratic=False,
                    )
                )
                print(f"  {response[:150]}...\n")

                # Smart scoring for progress
                if self._detect_progress(response):
                    self._add_score(respondent_id, 3)
                else:
                    self._add_score(respondent_id, 1)
                await self._delay()
            else:
                return False

        self._display_scores()
        return True

    async def _call_model(
        self, model_id: str, prompt: str
    ) -> Optional[str]:
        """Call the appropriate LLM model"""
        try:
            if model_id == "claude":
                return await self._call_claude(prompt)
            elif model_id == "grok":
                return await self._call_grok(prompt)
            elif model_id == "gemini":
                return await self._call_gemini(prompt)
            elif model_id == "chatgpt":
                return await self._call_openai(prompt)
        except Exception as e:
            print(f"❌ Error calling {model_id}: {str(e)}")
            return None

    async def _call_claude(self, prompt: str) -> Optional[str]:
        """Call Claude API"""
        try:
            client = anthropic.Anthropic(api_key=self.api_keys["claude"])
            message = client.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    async def _call_grok(self, prompt: str) -> Optional[str]:
        """Call Grok (xAI) API"""
        try:
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_keys['grok']}",
                },
                json={
                    "model": os.getenv("GROK_MODEL", "grok-2-latest"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise Exception(f"Grok API error: {str(e)}")

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """Call Google Gemini API"""
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')}:generateContent",
                headers={"Content-Type": "application/json"},
                params={"key": self.api_keys["gemini"]},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI (ChatGPT) API"""
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_keys['chatgpt']}",
                },
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def _build_socratic_prompt(self, model_id: str, round_num: int) -> str:
        """Build prompt for Socratic questioning"""
        model_name = ModelConfig.MODELS[model_id]["name"]
        personality = ModelConfig.MODELS[model_id]["personality"]
        mode_instruction = ModelConfig.MODE_INSTRUCTIONS[self.config.mode.value]

        messages_context = self._format_history_for_prompt(model_id)

        return f"""Είσαι {model_name} ({personality}). Ο ρόλος σου είναι ο Μαιευτικός Σωκράτης.
{mode_instruction}

Αποστολή:
1. Ελεγκτική: Εντόπισε μία λογική ασάφεια ή αντίφαση στις προηγούμενες απαντήσεις
2. Μαιευτική: Με στοχευμένες ερωτήσεις, οδήγησε τους συνομιλητές να ανακαλύψουν σφάλματα
3. Προγωγή: Υπόδειξε νέες διαστάσεις του θέματος «{self.config.topic}»

Θέμα: {self.config.topic}
Γύρος: {round_num}/{self.config.rounds}

Προηγούμενος διάλογος:
{messages_context}

Σας ρωτάς με σοφία και μέθοδο. Απάντησε σε ελληνικά."""

    def _build_participant_prompt(self, model_id: str, round_num: int) -> str:
        """Build prompt for participant response"""
        model_name = ModelConfig.MODELS[model_id]["name"]
        personality = ModelConfig.MODELS[model_id]["personality"]
        mode_instruction = ModelConfig.MODE_INSTRUCTIONS[self.config.mode.value]

        messages_context = self._format_history_for_prompt(model_id)

        return f"""Είσαι {model_name} ({personality}). Συμμετέχεις σε διαλεκτικό έλεγχο.
{mode_instruction}

ΧΡΥΣΟΣ ΚΑΝΟΝΑΣ: Αν ο Σωκράτης έχει δίκιο, το παραδέχεσαι και διορθώνεις. Αν όχι, υπερασπίζεσαι λογικά.

Θέμα: {self.config.topic}
Γύρος: {round_num}/{self.config.rounds}

Προηγούμενος διάλογος:
{messages_context}

Απάντησε σε ελληνικά. Δείξε εσωτερική αναθεώρηση αν χρειάζεται."""

    def _format_history_for_prompt(self, exclude_model: Optional[str] = None) -> str:
        """Format dialog history for context in prompts"""
        if not self.history:
            return f"Αρχή διαλόγου για θέμα: {self.config.topic}"

        lines = []
        for turn in self.history[-10:]:  # Last 10 turns for context
            model_name = ModelConfig.MODELS[turn.model_id]["name"]
            role = "(Σωκράτης)" if turn.is_socratic else ""
            lines.append(f"[{model_name} {role}]: {turn.content[:200]}...")

        return "\n".join(lines)

    async def _generate_summary(self, round_num: int) -> None:
        """Generate summary of the round"""
        print(f"\n📝 Σύνοψη Γύρου {round_num}:")
        # Use first available model for summary
        model_id = self.available_models[0]

        summary_prompt = f"""Αναλυτής φιλοσοφικών διαλόγων. Σε 2-3 προτάσεις Ελληνικά, τι αποκαλύφθηκε σε αυτόν τον γύρο για: {self.config.topic}

Διάλογος:
{self._format_history_for_prompt()}"""

        summary = await self._call_model(model_id, summary_prompt)
        if summary:
            print(f"  {summary}\n")

    async def _generate_synthesis(self) -> None:
        """Generate final philosophical synthesis"""
        print("\n✨ Φιλοσοφική Σύνθεση:")
        print("=" * 80)

        model_id = self.available_models[0]
        synthesis_prompt = f"""Ουδέτερος φιλόσοφος. Εξήγαγε μια τελική Φιλοσοφική Σύνθεση:
(α) κεντρικές θέσεις που εμφανίστηκαν
(β) αντιφάσεις που εξετάστηκαν
(γ) πιθανή αλήθεια ή νέα ερώτηση

Θέμα: {self.config.topic}

Συνολικός διάλογος:
{self._format_history_for_prompt()}"""

        synthesis = await self._call_model(model_id, synthesis_prompt)
        if synthesis:
            print(synthesis)
            print("\n" + "=" * 80)

    def _should_summarize(self, round_num: int) -> bool:
        """Determine if we should generate a summary this round"""
        if self.config.summary_mode == SummaryMode.NONE:
            return False
        elif self.config.summary_mode == SummaryMode.EVERY:
            return True
        elif self.config.summary_mode == SummaryMode.HALF:
            return round_num % 2 == 0
        return False

    def _detect_progress(self, response: str) -> bool:
        """Detect if model is showing intellectual progress"""
        progress_indicators = [
            "αναθεωρ",
            "έχεις δίκιο",
            "οπτική",
            "παραδέχομαι",
            "επαναπροσδιορ",
            "συμφωνώ",
            "εύστοχ",
        ]
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in progress_indicators)

    def _add_score(self, model_id: str, points: int) -> None:
        """Add points to a model's score"""
        self.scores[model_id] = self.scores.get(model_id, 0) + points

    def _display_scores(self) -> None:
        """Display current scores"""
        print("\n📊 Σκοροί:")
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        for model_id, score in sorted_scores:
            model_name = ModelConfig.MODELS[model_id]["name"]
            icon = ModelConfig.MODELS[model_id]["icon"]
            print(f"  {icon} {model_name}: {score}")

    def display_final_scores(self) -> None:
        """Display final scores"""
        print("\n" + "=" * 80)
        print("📊 ΤΕΛΙΚΟΙ ΣΚΟΡΟΙ")
        print("=" * 80)
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        for model_id, score in sorted_scores:
            model_name = ModelConfig.MODELS[model_id]["name"]
            icon = ModelConfig.MODELS[model_id]["icon"]
            print(f"  {icon} {model_name}: {score} πόντοι")
        print("=" * 80)

    async def _delay(self) -> None:
        """Add delay based on configured speed"""
        if self.config.speed.delay > 0:
            await asyncio.sleep(self.config.speed.delay)

    def _format_output(self) -> str:
        """Format the dialog for export"""
        output = []
        output.append("=" * 80)
        output.append(f"Σωκρατικός Διάλογος: {self.config.topic}")
        output.append(f"Ημερομηνία: {datetime.now().isoformat()}")
        output.append(f"Mode: {self.config.mode.value}")
        output.append("=" * 80)
        output.append("")

        for turn in self.history:
            model_name = ModelConfig.MODELS[turn.model_id]["name"]
            role = "(Σωκράτης)" if turn.is_socratic else ""
            output.append(f"[{model_name} {role}]:")
            output.append(turn.content)
            output.append("")

        output.append("\nΤελικοί Σκοροί:")
        for model_id, score in sorted(
            self.scores.items(), key=lambda x: x[1], reverse=True
        ):
            model_name = ModelConfig.MODELS[model_id]["name"]
            output.append(f"  {model_name}: {score}")

        return "\n".join(output)

    def export_json(self, filename: str) -> None:
        """Export dialog to JSON"""
        data = {
            "topic": self.config.topic,
            "mode": self.config.mode.value,
            "rounds": self.config.rounds,
            "timestamp": datetime.now().isoformat(),
            "history": [asdict(turn) for turn in self.history],
            "scores": self.scores,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Exported to {filename}")

    def export_markdown(self, filename: str) -> None:
        """Export dialog to Markdown"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# Σωκρατικός Διάλογος\n\n")
            f.write(f"**Θέμα:** {self.config.topic}\n\n")
            f.write(f"**Mode:** {self.config.mode.value}\n\n")
            f.write(f"**Ημερομηνία:** {datetime.now().isoformat()}\n\n")
            f.write("---\n\n")

            for turn in self.history:
                model_name = ModelConfig.MODELS[turn.model_id]["name"]
                role = "(Σωκράτης)" if turn.is_socratic else ""
                f.write(f"### {model_name} {role}\n\n")
                f.write(f"{turn.content}\n\n")

            f.write("---\n\n## Τελικοί Σκοροί\n\n")
            for model_id, score in sorted(
                self.scores.items(), key=lambda x: x[1], reverse=True
            ):
                model_name = ModelConfig.MODELS[model_id]["name"]
                f.write(f"- {model_name}: {score}\n")

        print(f"✅ Exported to {filename}")


async def main():
    """Main entry point"""
    print("🏛️  Σωκρατικός Διάλογος Pro")
    print("Philosophical Dialogues with Multiple LLMs")
    print()

    # Get API keys
    api_keys = {
        "claude": os.getenv("ANTHROPIC_API_KEY", ""),
        "grok": os.getenv("XAI_API_KEY", ""),
        "gemini": os.getenv("GOOGLE_API_KEY", ""),
        "chatgpt": os.getenv("OPENAI_API_KEY", ""),
    }

    # Filter to only configured keys
    api_keys = {k: v for k, v in api_keys.items() if v}

    if not api_keys:
        print(
            "❌ No API keys found. Set environment variables:"
        )
        print("   ANTHROPIC_API_KEY, XAI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY")
        sys.exit(1)

    print(f"✅ Found {len(api_keys)} configured models: {', '.join(api_keys.keys())}")
    print()

    # Get dialog configuration from user
    topic = input(
        "📖 Enter dialog topic (or press Enter for AI Ethics): "
    ).strip()
    if not topic:
        topic = "Ηθική της Τεχνητής Νοημοσύνης"

    rounds = input("🔄 Enter number of rounds (default 8): ").strip()
    rounds = int(rounds) if rounds.isdigit() else 8

    mode_choice = (
        input("⚙️  Select mode (socratic/debate/consensus, default socratic): ")
        .strip()
        .lower()
    )
    mode = (
        DialogMode.SOCRATIC
        if mode_choice not in ["debate", "consensus"]
        else DialogMode(mode_choice)
    )

    speed_choice = input(
        "⏱️  Select speed (0-4, default 2): "
    ).strip()
    speed_idx = int(speed_choice) if speed_choice.isdigit() and 0 <= int(speed_choice) <= 4 else 2
    speed = list(DialogSpeed)[speed_idx]

    # Create config and manager
    config = DialogConfig(topic=topic, rounds=rounds, mode=mode, speed=speed)
    manager = DialogManager(config, api_keys)

    # Run dialog
    try:
        await manager.run_dialog()
        manager.display_final_scores()

        # Export options
        export = input("\n💾 Export dialog? (json/markdown/both/no): ").strip().lower()
        if export in ["json", "both"]:
            manager.export_json("dialog.json")
        if export in ["markdown", "both"]:
            manager.export_markdown("dialog.md")

    except KeyboardInterrupt:
        print("\n\n🛑 Dialog interrupted by user")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
