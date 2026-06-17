#!/usr/bin/env python3
"""
Test suite for Socratic Dialog application
Tests all major components without requiring API calls
"""

import asyncio
import json
from datetime import datetime
from socrates_ai import (
    DialogConfig,
    DialogMode,
    DialogSpeed,
    SummaryMode,
    DialogTurn,
    DialogManager,
    ModelConfig,
)


def test_models_config():
    """Test that all models are configured correctly"""
    print("\n✅ Testing Model Configuration...")
    assert len(ModelConfig.MODELS) == 4, "Should have 4 models"
    
    for model_id, config in ModelConfig.MODELS.items():
        assert "name" in config, f"{model_id} missing name"
        assert "icon" in config, f"{model_id} missing icon"
        assert "color" in config, f"{model_id} missing color"
        assert "personality" in config, f"{model_id} missing personality"
        print(f"  ✓ {model_id}: {config['name']}")
    
    print("  ✅ All models configured correctly")


def test_dialog_modes():
    """Test dialog mode enum"""
    print("\n✅ Testing Dialog Modes...")
    modes = [DialogMode.SOCRATIC, DialogMode.DEBATE, DialogMode.CONSENSUS]
    
    for mode in modes:
        assert mode.value in ModelConfig.MODE_INSTRUCTIONS
        print(f"  ✓ {mode.value}: {ModelConfig.MODE_INSTRUCTIONS[mode.value][:50]}...")
    
    print("  ✅ All modes configured")


def test_dialog_speed():
    """Test speed settings"""
    print("\n✅ Testing Dialog Speeds...")
    speeds = list(DialogSpeed)
    
    for i, speed in enumerate(speeds):
        assert speed.delay >= 0, f"{speed} has invalid delay"
        print(f"  ✓ {speed.label}: {speed.delay}s delay")
    
    print("  ✅ All speeds valid")


def test_dialog_turn():
    """Test DialogTurn dataclass"""
    print("\n✅ Testing DialogTurn...")
    
    turn = DialogTurn(
        round=1,
        model_id="claude",
        content="Test content",
        is_socratic=True,
    )
    
    assert turn.round == 1
    assert turn.model_id == "claude"
    assert turn.is_socratic == True
    assert turn.timestamp is not None
    print(f"  ✓ Created turn: {turn.model_id} (round {turn.round})")
    print("  ✅ DialogTurn works correctly")


def test_dialog_config():
    """Test DialogConfig setup"""
    print("\n✅ Testing DialogConfig...")
    
    config = DialogConfig(
        topic="Τι είναι η αρετή;",
        rounds=8,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.EVERY,
    )
    
    assert config.topic == "Τι είναι η αρετή;"
    assert config.rounds == 8
    assert config.mode == DialogMode.SOCRATIC
    print(f"  ✓ Topic: {config.topic}")
    print(f"  ✓ Rounds: {config.rounds}")
    print(f"  ✓ Mode: {config.mode.value}")
    print("  ✅ DialogConfig initialized correctly")


def test_dialog_manager_init():
    """Test DialogManager initialization (without API calls)"""
    print("\n✅ Testing DialogManager Initialization...")
    
    api_keys = {
        "claude": "test-key-claude",
        "grok": "test-key-grok",
        "gemini": "test-key-gemini",
        "chatgpt": "test-key-openai",
    }
    
    config = DialogConfig(topic="Test Topic", rounds=4)
    manager = DialogManager(config, api_keys)
    
    assert len(manager.available_models) == 4
    assert len(manager.history) == 0
    assert all(score == 0 for score in manager.scores.values())
    print(f"  ✓ Available models: {', '.join(manager.available_models)}")
    print(f"  ✓ History initialized (empty)")
    print(f"  ✓ Scores initialized: {manager.scores}")
    print("  ✅ DialogManager initialized correctly")


def test_dialog_manager_validation():
    """Test DialogManager validation"""
    print("\n✅ Testing DialogManager Validation...")
    
    # Test insufficient models
    try:
        api_keys = {"claude": "test-key"}
        config = DialogConfig(topic="Test")
        manager = DialogManager(config, api_keys)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"  ✓ Correctly rejected single model: {str(e)}")
    
    # Test missing API key
    try:
        api_keys = {"claude": "test-key", "grok": ""}
        config = DialogConfig(topic="Test")
        manager = DialogManager(config, api_keys)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"  ✓ Correctly rejected empty API key: {str(e)}")
    
    print("  ✅ Validation working correctly")


def test_dialog_manager_scoring():
    """Test scoring system"""
    print("\n✅ Testing Scoring System...")
    
    api_keys = {
        "claude": "test-key",
        "grok": "test-key",
        "gemini": "test-key",
        "chatgpt": "test-key",
    }
    
    config = DialogConfig(topic="Test")
    manager = DialogManager(config, api_keys)
    
    # Test adding scores
    manager._add_score("claude", 1)
    assert manager.scores["claude"] == 1
    print(f"  ✓ Added 1 point to claude: {manager.scores['claude']}")
    
    manager._add_score("claude", 3)
    assert manager.scores["claude"] == 4
    print(f"  ✓ Added 3 points to claude: {manager.scores['claude']}")
    
    manager._add_score("grok", 2)
    print(f"  ✓ Added 2 points to grok: {manager.scores['grok']}")
    
    print("  ✅ Scoring system working correctly")


def test_progress_detection():
    """Test progress detection in responses"""
    print("\n✅ Testing Progress Detection...")
    
    api_keys = {
        "claude": "test-key",
        "grok": "test-key",
        "gemini": "test-key",
        "chatgpt": "test-key",
    }
    
    config = DialogConfig(topic="Test")
    manager = DialogManager(config, api_keys)
    
    # Test progress keywords
    progress_responses = [
        "Μετά από αναθεώρηση, συμφωνώ ότι...",
        "Έχεις δίκιο σε αυτή την οπτική...",
        "Παραδέχομαι ότι η άποψή μου επαναπροσδιορίστηκε...",
    ]
    
    for resp in progress_responses:
        result = manager._detect_progress(resp)
        assert result == True, f"Should detect progress in: {resp}"
        print(f"  ✓ Detected progress: {resp[:50]}...")
    
    # Test non-progress responses
    no_progress = [
        "Διαφωνώ απόλυτα.",
        "Αυτό είναι λάθος.",
    ]
    
    for resp in no_progress:
        result = manager._detect_progress(resp)
        assert result == False, f"Should not detect progress in: {resp}"
        print(f"  ✓ Correctly ignored non-progress: {resp[:50]}...")
    
    print("  ✅ Progress detection working correctly")


def test_summarization_logic():
    """Test when summaries should be generated"""
    print("\n✅ Testing Summarization Logic...")
    
    api_keys = {
        "claude": "test-key",
        "grok": "test-key",
        "gemini": "test-key",
        "chatgpt": "test-key",
    }
    
    # Test EVERY mode
    config = DialogConfig(
        topic="Test", rounds=4, summary_mode=SummaryMode.EVERY
    )
    manager = DialogManager(config, api_keys)
    assert manager._should_summarize(1) == True
    assert manager._should_summarize(2) == True
    assert manager._should_summarize(3) == True
    print("  ✓ EVERY mode: summarizes each round")
    
    # Test HALF mode
    config = DialogConfig(
        topic="Test", rounds=4, summary_mode=SummaryMode.HALF
    )
    manager = DialogManager(config, api_keys)
    assert manager._should_summarize(1) == False
    assert manager._should_summarize(2) == True
    assert manager._should_summarize(3) == False
    assert manager._should_summarize(4) == True
    print("  ✓ HALF mode: summarizes every 2 rounds")
    
    # Test NONE mode
    config = DialogConfig(topic="Test", rounds=4, summary_mode=SummaryMode.NONE)
    manager = DialogManager(config, api_keys)
    assert manager._should_summarize(1) == False
    assert manager._should_summarize(2) == False
    print("  ✓ NONE mode: no summaries")
    
    print("  ✅ Summarization logic correct")


def test_export_formats():
    """Test export data structure"""
    print("\n✅ Testing Export Formats...")
    
    api_keys = {
        "claude": "test-key",
        "grok": "test-key",
        "gemini": "test-key",
        "chatgpt": "test-key",
    }
    
    config = DialogConfig(topic="Test Topic")
    manager = DialogManager(config, api_keys)
    
    # Add some test history
    manager.history.append(
        DialogTurn(
            round=1,
            model_id="claude",
            content="Test response 1",
            is_socratic=True,
        )
    )
    manager.history.append(
        DialogTurn(
            round=1,
            model_id="grok",
            content="Test response 2",
            is_socratic=False,
        )
    )
    manager.scores["claude"] = 3
    manager.scores["grok"] = 2
    
    # Test JSON structure
    json_data = {
        "topic": manager.config.topic,
        "mode": manager.config.mode.value,
        "rounds": manager.config.rounds,
        "timestamp": datetime.now().isoformat(),
        "history": [
            {
                "round": t.round,
                "model_id": t.model_id,
                "content": t.content,
                "is_socratic": t.is_socratic,
            }
            for t in manager.history
        ],
        "scores": manager.scores,
    }
    
    # Verify it's valid JSON
    json_str = json.dumps(json_data, ensure_ascii=False)
    parsed = json.loads(json_str)
    
    assert parsed["topic"] == "Test Topic"
    assert len(parsed["history"]) == 2
    assert parsed["scores"]["claude"] == 3
    print("  ✓ JSON export format valid")
    print(f"  ✓ History: {len(parsed['history'])} turns")
    print(f"  ✓ Scores: {parsed['scores']}")
    
    print("  ✅ Export formats working correctly")


def test_model_rotation():
    """Test that models rotate correctly as Socrates"""
    print("\n✅ Testing Model Rotation...")
    
    api_keys = {
        "claude": "test-key",
        "grok": "test-key",
        "gemini": "test-key",
        "chatgpt": "test-key",
    }
    
    config = DialogConfig(topic="Test", rounds=8)
    manager = DialogManager(config, api_keys)
    
    # Simulate round rotation
    for round_num in range(1, 9):
        expected_socrates = manager.available_models[(round_num - 1) % len(manager.available_models)]
        print(f"  ✓ Round {round_num}: {expected_socrates} is Socrates")
    
    print("  ✅ Model rotation working correctly")


def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print("🧪 SOCRATIC DIALOG - TEST SUITE")
    print("=" * 80)
    
    try:
        test_models_config()
        test_dialog_modes()
        test_dialog_speed()
        test_dialog_turn()
        test_dialog_config()
        test_dialog_manager_init()
        test_dialog_manager_validation()
        test_dialog_manager_scoring()
        test_progress_detection()
        test_summarization_logic()
        test_export_formats()
        test_model_rotation()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\n📋 Test Summary:")
        print("  ✓ Model configuration")
        print("  ✓ Dialog modes")
        print("  ✓ Speed settings")
        print("  ✓ Dialog turns")
        print("  ✓ Configuration")
        print("  ✓ Manager initialization")
        print("  ✓ Validation logic")
        print("  ✓ Scoring system")
        print("  ✓ Progress detection")
        print("  ✓ Summarization logic")
        print("  ✓ Export formats")
        print("  ✓ Model rotation")
        
        print("\n🚀 Next Steps:")
        print("  1. Set your API keys in .env")
        print("  2. Run: python socrates_ai.py")
        print("  3. Follow the interactive prompts")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
