"""
Unit tests for OutputValidator.

Tests forbidden terms detection, verbosity checks, freshness requirements,
and repair instruction generation.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cinemind.prompting.output_validator import OutputValidator, ValidationResult
from cinemind.prompting.templates import get_template, ResponseTemplate


class TestForbiddenTerms:
    """Tests for forbidden terms detection and auto-fix."""
    
    @pytest.fixture
    def validator(self):
        """Create OutputValidator with auto-fix enabled."""
        return OutputValidator(enable_auto_fix=True)
    
    @pytest.fixture
    def director_template(self):
        """Get director_info template."""
        return get_template("info", "director_info")
    
    def test_forbidden_term_tier_a_detected(self, validator, director_template):
        """Test that 'Tier A' is detected as forbidden term."""
        response = "The Matrix was directed by the Wachowskis. This information comes from Tier A sources."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response with forbidden term should be invalid"
        assert result.has_violations(), "Should have violations"
        assert any("Tier A" in v or "tier a" in v.lower() for v in result.violations), \
            f"Should flag 'Tier A' violation, got: {result.violations}"
    
    def test_forbidden_term_kaggle_detected(self, validator, director_template):
        """Test that 'Kaggle' is detected as forbidden term."""
        response = "The Matrix was directed by the Wachowskis according to the Kaggle dataset."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response with forbidden term should be invalid"
        assert any("Kaggle" in v or "kaggle" in v.lower() for v in result.violations), \
            f"Should flag 'Kaggle' violation, got: {result.violations}"
    
    def test_forbidden_term_kaggle_dataset_detected(self, validator, director_template):
        """Test that 'Kaggle dataset' is detected as forbidden term."""
        response = "The Matrix was directed by the Wachowskis. This comes from the Kaggle dataset."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response with forbidden term should be invalid"
        assert any("Kaggle" in v or "kaggle" in v.lower() for v in result.violations), \
            f"Should flag 'Kaggle dataset' violation, got: {result.violations}"
    
    def test_forbidden_term_tavily_detected(self, validator, director_template):
        """Test that 'Tavily' is detected as forbidden term."""
        response = "The Matrix was directed by the Wachowskis. Information from Tavily search."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response with forbidden term should be invalid"
        assert any("Tavily" in v or "tavily" in v.lower() for v in result.violations), \
            f"Should flag 'Tavily' violation, got: {result.violations}"
    
    def test_forbidden_term_auto_fix_removes_tier_a(self, validator, director_template):
        """Test that auto-fix removes 'Tier A' from response."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources."
        
        result = validator.validate(response, director_template)
        
        assert result.corrected_text is not None, "Should have corrected text"
        assert "Tier A" not in result.corrected_text, \
            f"Corrected text should not contain 'Tier A', got: {result.corrected_text}"
        assert "Tier" not in result.corrected_text, \
            f"Corrected text should not contain 'Tier', got: {result.corrected_text}"
    
    def test_forbidden_term_auto_fix_replaces_kaggle(self, validator, director_template):
        """Test that auto-fix replaces 'Kaggle' with natural alternative."""
        response = "The Matrix was directed by the Wachowskis according to Kaggle data."
        
        result = validator.validate(response, director_template)
        
        assert result.corrected_text is not None, "Should have corrected text"
        assert "Kaggle" not in result.corrected_text, \
            f"Corrected text should not contain 'Kaggle', got: {result.corrected_text}"
        # Should replace with "structured data"
        assert "structured data" in result.corrected_text.lower() or "data source" in result.corrected_text.lower(), \
            f"Should replace 'Kaggle' with natural alternative, got: {result.corrected_text}"
    
    def test_forbidden_term_auto_fix_replaces_tavily(self, validator, director_template):
        """Test that auto-fix replaces 'Tavily' with natural alternative."""
        response = "The Matrix was directed by the Wachowskis. Information from Tavily."
        
        result = validator.validate(response, director_template)
        
        assert result.corrected_text is not None, "Should have corrected text"
        assert "Tavily" not in result.corrected_text, \
            f"Corrected text should not contain 'Tavily', got: {result.corrected_text}"
        assert "search results" in result.corrected_text.lower(), \
            f"Should replace 'Tavily' with 'search results', got: {result.corrected_text}"
    
    def test_forbidden_term_case_insensitive(self, validator, director_template):
        """Test that forbidden term detection is case-insensitive."""
        response = "The Matrix was directed by the Wachowskis. This comes from tier a sources."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response with forbidden term (lowercase) should be invalid"
        assert result.has_violations(), "Should have violations"
    
    def test_forbidden_term_word_boundary(self, validator, director_template):
        """Test that forbidden terms are matched with word boundaries."""
        # "Kaggle" in "KaggleDataset" should match, but we want to test word boundaries
        response = "The Matrix was directed by the Wachowskis. Kaggle is a platform."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response with forbidden term should be invalid"
        assert any("Kaggle" in v or "kaggle" in v.lower() for v in result.violations)
    
    def test_no_forbidden_terms_valid(self, validator, director_template):
        """Test that response without forbidden terms is valid."""
        response = "The Matrix was directed by the Wachowskis."
        
        result = validator.validate(response, director_template)
        
        assert result.is_valid, "Response without forbidden terms should be valid"
        assert not result.has_violations(), "Should have no violations"
        assert result.corrected_text is None, "Should not have corrected text when valid"


class TestVerbosity:
    """Tests for verbosity constraints (max sentences/words)."""
    
    @pytest.fixture
    def validator(self):
        """Create OutputValidator."""
        return OutputValidator(enable_auto_fix=True)
    
    @pytest.fixture
    def director_template(self):
        """Get director_info template (max 2 sentences, max 50 words)."""
        return get_template("info", "director_info")
    
    def test_verbosity_violation_too_many_sentences(self, validator, director_template):
        """Test that director_info response with 3+ sentences triggers violation."""
        # director_info template has max_sentences=2
        response = "The Matrix was directed by the Wachowskis. They are known for their innovative filmmaking. The film was released in 1999."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response exceeding max sentences should be invalid"
        assert result.has_violations(), "Should have violations"
        assert any("Exceeds max sentences" in v for v in result.violations), \
            f"Should flag sentence count violation, got: {result.violations}"
        assert result.requires_reprompt, "Verbosity violations should require re-prompt"
    
    def test_verbosity_violation_too_many_words(self, validator, director_template):
        """Test that response exceeding max words triggers violation."""
        # director_info template has max_words=50
        long_response = "The Matrix was directed by " + "the Wachowskis " * 30  # Way over 50 words
        
        result = validator.validate(long_response, director_template)
        
        assert not result.is_valid, "Response exceeding max words should be invalid"
        assert any("Exceeds max words" in v for v in result.violations), \
            f"Should flag word count violation, got: {result.violations}"
        assert result.requires_reprompt, "Verbosity violations should require re-prompt"
    
    def test_verbosity_valid_within_limits(self, validator, director_template):
        """Test that response within verbosity limits is valid."""
        response = "The Matrix was directed by the Wachowskis."
        
        result = validator.validate(response, director_template)
        
        # Should be valid (1 sentence, well under 50 words)
        assert result.is_valid, "Response within limits should be valid"
        assert not any("Exceeds" in v for v in result.violations), \
            "Should not have verbosity violations"
    
    def test_verbosity_min_sentences_violation(self, validator):
        """Test that response below min sentences triggers violation."""
        # recommendation template has min_sentences=5
        recommendation_template = get_template("recs", "recommendation")
        short_response = "Here are some movies. They are good."
        
        result = validator.validate(short_response, recommendation_template)
        
        assert not result.is_valid, "Response below min sentences should be invalid"
        assert any("Below min sentences" in v for v in result.violations), \
            f"Should flag min sentence violation, got: {result.violations}"
    
    def test_verbosity_sentence_counting(self, validator, director_template):
        """Test that sentence counting works correctly."""
        # Test with abbreviations that shouldn't count as sentence endings
        response = "The Matrix was directed by Mr. Wachowski. It was released in 1999."
        
        result = validator.validate(response, director_template)
        
        # Should count as 2 sentences (not 3, because "Mr." shouldn't count)
        # director_info has max_sentences=2, so this should be valid
        assert result.is_valid, "Response with 2 sentences should be valid for director_info"
    
    def test_verbosity_no_punctuation_counts_as_one(self, validator, director_template):
        """Test that text without punctuation counts as one sentence."""
        response = "The Matrix was directed by the Wachowskis"
        
        result = validator.validate(response, director_template)
        
        # Should count as 1 sentence
        assert result.is_valid, "Single sentence without punctuation should be valid"


class TestFreshness:
    """Tests for freshness/timestamp requirements."""
    
    @pytest.fixture
    def validator(self):
        """Create OutputValidator."""
        return OutputValidator(enable_auto_fix=True)
    
    @pytest.fixture
    def where_to_watch_template(self):
        """Get where_to_watch template (requires include_as_of_date)."""
        return get_template("info", "where_to_watch")
    
    def test_freshness_violation_missing_as_of(self, validator, where_to_watch_template):
        """Test that where_to_watch response missing 'As of <date>' triggers violation."""
        response = "The Matrix is available on Netflix and HBO Max."
        
        result = validator.validate(
            response, 
            where_to_watch_template,
            need_freshness=True
        )
        
        assert not result.is_valid, "Response missing freshness language should be invalid"
        assert result.has_violations(), "Should have violations"
        assert any("Missing freshness" in v or "timestamp" in v.lower() for v in result.violations), \
            f"Should flag freshness violation, got: {result.violations}"
        assert result.requires_reprompt, "Freshness violations should require re-prompt"
    
    def test_freshness_valid_with_as_of_date(self, validator, where_to_watch_template):
        """Test that response with 'As of <date>' is valid."""
        response = "As of 2024, The Matrix is available on Netflix and HBO Max."
        
        result = validator.validate(
            response,
            where_to_watch_template,
            need_freshness=True
        )
        
        # Should be valid (has freshness language)
        assert result.is_valid or not any("freshness" in v.lower() or "timestamp" in v.lower() for v in result.violations), \
            f"Response with 'as of' should not have freshness violations, got: {result.violations}"
    
    def test_freshness_valid_with_currently(self, validator, where_to_watch_template):
        """Test that response with 'currently' is valid."""
        response = "The Matrix is currently available on Netflix and HBO Max."
        
        result = validator.validate(
            response,
            where_to_watch_template,
            need_freshness=True
        )
        
        # Should be valid (has freshness language)
        assert result.is_valid or not any("freshness" in v.lower() or "timestamp" in v.lower() for v in result.violations), \
            f"Response with 'currently' should not have freshness violations, got: {result.violations}"
    
    def test_freshness_valid_with_as_of_today(self, validator, where_to_watch_template):
        """Test that response with 'as of today' is valid."""
        response = "As of today, The Matrix is available on Netflix and HBO Max."
        
        result = validator.validate(
            response,
            where_to_watch_template,
            need_freshness=True
        )
        
        # Should be valid (has freshness language)
        assert result.is_valid or not any("freshness" in v.lower() or "timestamp" in v.lower() for v in result.violations), \
            f"Response with 'as of today' should not have freshness violations, got: {result.violations}"
    
    def test_freshness_valid_with_iso_date(self, validator, where_to_watch_template):
        """Test that response with ISO date is valid."""
        response = "As of 2024-01-15, The Matrix is available on Netflix and HBO Max."
        
        result = validator.validate(
            response,
            where_to_watch_template,
            need_freshness=True
        )
        
        # Should be valid (has freshness language)
        assert result.is_valid or not any("freshness" in v.lower() or "timestamp" in v.lower() for v in result.violations), \
            f"Response with ISO date should not have freshness violations, got: {result.violations}"
    
    def test_freshness_not_required_when_flag_false(self, validator, where_to_watch_template):
        """Test that freshness check is skipped when need_freshness=False."""
        response = "The Matrix is available on Netflix and HBO Max."
        
        result = validator.validate(
            response,
            where_to_watch_template,
            need_freshness=False
        )
        
        # Should not have freshness violations when flag is False
        assert not any("freshness" in v.lower() or "timestamp" in v.lower() for v in result.violations), \
            f"Should not check freshness when flag is False, got: {result.violations}"
    
    def test_freshness_not_required_when_template_doesnt_require(self, validator):
        """Test that freshness check is skipped when template doesn't require it."""
        director_template = get_template("info", "director_info")
        response = "The Matrix was directed by the Wachowskis."
        
        result = validator.validate(
            response,
            director_template,
            need_freshness=True  # Even if flag is True, template doesn't require it
        )
        
        # Should not have freshness violations (template doesn't have include_as_of_date)
        assert not any("freshness" in v.lower() or "timestamp" in v.lower() for v in result.violations), \
            f"Should not check freshness when template doesn't require it, got: {result.violations}"


class TestRepairInstruction:
    """Tests for repair instruction generation."""
    
    @pytest.fixture
    def validator(self):
        """Create OutputValidator."""
        return OutputValidator(enable_auto_fix=True)
    
    @pytest.fixture
    def director_template(self):
        """Get director_info template."""
        return get_template("info", "director_info")
    
    def test_repair_instruction_contains_violations(self, validator, director_template):
        """Test that repair instruction lists all violations."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources. The film was great. It had amazing visuals."
        result = validator.validate(response, director_template)
        
        repair_instruction = validator.build_correction_instruction(result.violations, director_template)
        
        assert "CORRECTION REQUIRED" in repair_instruction, "Should start with correction header"
        assert "VIOLATIONS:" in repair_instruction, "Should list violations"
        assert "Tier A" in repair_instruction or "tier a" in repair_instruction.lower(), \
            "Should mention Tier A violation"
        assert "Exceeds max sentences" in repair_instruction, \
            "Should mention sentence count violation"
    
    def test_repair_instruction_contains_template_requirements(self, validator, director_template):
        """Test that repair instruction includes template requirements."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources."
        result = validator.validate(response, director_template)
        
        repair_instruction = validator.build_correction_instruction(result.violations, director_template)
        
        assert "STRICT REQUIREMENTS:" in repair_instruction, "Should include strict requirements"
        assert "maximum" in repair_instruction.lower() or "max" in repair_instruction.lower(), \
            "Should include verbosity requirements"
        assert "Forbidden terms" in repair_instruction, \
            "Should include forbidden terms list"
    
    def test_repair_instruction_is_short_and_strict(self, validator, director_template):
        """Test that repair instruction is short and strict."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources."
        result = validator.validate(response, director_template)
        
        repair_instruction = validator.build_correction_instruction(result.violations, director_template)
        
        # Should be reasonably concise (not overly verbose)
        assert len(repair_instruction) < 2000, \
            f"Repair instruction should be concise, got {len(repair_instruction)} chars"
        
        # Should contain strict language
        assert "STRICT" in repair_instruction or "strict" in repair_instruction.lower(), \
            "Should use strict language"
        assert "Do not include" in repair_instruction or "do not" in repair_instruction.lower(), \
            "Should contain prohibitive language"
        assert "regenerate" in repair_instruction.lower() or "following" in repair_instruction.lower(), \
            "Should instruct to regenerate"
    
    def test_repair_instruction_for_freshness_violation(self, validator):
        """Test repair instruction for freshness violation."""
        where_to_watch_template = get_template("info", "where_to_watch")
        response = "The Matrix is available on Netflix and HBO Max."
        result = validator.validate(response, where_to_watch_template, need_freshness=True)
        
        repair_instruction = validator.build_correction_instruction(result.violations, where_to_watch_template)
        
        assert "CORRECTION REQUIRED" in repair_instruction
        assert "Missing freshness" in repair_instruction or "timestamp" in repair_instruction.lower(), \
            "Should mention freshness violation"
        assert "STRICT REQUIREMENTS:" in repair_instruction


class TestMultipleViolations:
    """Tests for multiple violations in a single response."""
    
    @pytest.fixture
    def validator(self):
        """Create OutputValidator."""
        return OutputValidator(enable_auto_fix=True)
    
    @pytest.fixture
    def director_template(self):
        """Get director_info template."""
        return get_template("info", "director_info")
    
    def test_multiple_violations_all_detected(self, validator, director_template):
        """Test that multiple violations are all detected."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources. The film was great. It had amazing visuals. Information from Kaggle dataset."
        
        result = validator.validate(response, director_template)
        
        assert not result.is_valid, "Response with multiple violations should be invalid"
        assert len(result.violations) >= 2, \
            f"Should detect multiple violations, got: {result.violations}"
        
        # Should have forbidden term violations
        forbidden_violations = [v for v in result.violations if "Forbidden" in v or "forbidden" in v.lower()]
        assert len(forbidden_violations) >= 1, "Should detect forbidden term violations"
        
        # Should have verbosity violations
        verbosity_violations = [v for v in result.violations if "Exceeds" in v]
        assert len(verbosity_violations) >= 1, "Should detect verbosity violations"
    
    def test_requires_reprompt_with_multiple_violations(self, validator, director_template):
        """Test that multiple violations require re-prompt."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources. The film was great. It had amazing visuals."
        
        result = validator.validate(response, director_template)
        
        assert result.requires_reprompt, "Multiple violations should require re-prompt"
    
    def test_auto_fix_only_for_forbidden_terms(self, validator, director_template):
        """Test that auto-fix only applies to forbidden terms, not verbosity."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources. The film was great. It had amazing visuals."
        
        result = validator.validate(response, director_template)
        
        # Should have corrected text (forbidden terms fixed)
        assert result.corrected_text is not None, "Should have corrected text for forbidden terms"
        
        # But should still require re-prompt (verbosity can't be auto-fixed)
        assert result.requires_reprompt, "Should still require re-prompt for verbosity violations"


class TestValidatorWithAutoFixDisabled:
    """Tests for validator with auto-fix disabled."""
    
    @pytest.fixture
    def validator_no_fix(self):
        """Create OutputValidator with auto-fix disabled."""
        return OutputValidator(enable_auto_fix=False)
    
    @pytest.fixture
    def director_template(self):
        """Get director_info template."""
        return get_template("info", "director_info")
    
    def test_forbidden_terms_require_reprompt_when_auto_fix_disabled(self, validator_no_fix, director_template):
        """Test that forbidden terms require re-prompt when auto-fix is disabled."""
        response = "The Matrix was directed by the Wachowskis. This comes from Tier A sources."
        
        result = validator_no_fix.validate(response, director_template)
        
        assert not result.is_valid, "Response with forbidden term should be invalid"
        assert result.requires_reprompt, "Should require re-prompt when auto-fix is disabled"
        assert result.corrected_text is None, "Should not have corrected text when auto-fix is disabled"

