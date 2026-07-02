"""Unit tests for utils/export.py."""

from utils.export import generate_export_filename, sanitize_filename


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_replaces_spaces_with_underscores(self) -> None:
        assert sanitize_filename("My Architecture") == "My_Architecture"

    def test_replaces_special_characters_with_underscores(self) -> None:
        assert sanitize_filename("arch!@#$%test") == "arch_test"

    def test_collapses_consecutive_underscores(self) -> None:
        assert sanitize_filename("a   b") == "a_b"

    def test_strips_leading_trailing_underscores(self) -> None:
        assert sanitize_filename("  hello  ") == "hello"

    def test_preserves_hyphens(self) -> None:
        assert sanitize_filename("my-arch") == "my-arch"

    def test_preserves_alphanumeric(self) -> None:
        assert sanitize_filename("Arch2024v1") == "Arch2024v1"

    def test_empty_string_returns_fallback(self) -> None:
        assert sanitize_filename("") == "untitled"

    def test_whitespace_only_returns_fallback(self) -> None:
        assert sanitize_filename("   \t\n  ") == "untitled"

    def test_special_chars_only_returns_fallback(self) -> None:
        # All special characters get replaced then stripped
        assert sanitize_filename("!!!") == "untitled"


class TestGenerateExportFilename:
    """Tests for generate_export_filename function."""

    def test_basic_filename_format(self) -> None:
        result = generate_export_filename("My Arch", "mermaid", "mmd")
        assert result == "My_Arch_mermaid.mmd"

    def test_drawio_format(self) -> None:
        result = generate_export_filename("Web App", "drawio", "drawio")
        assert result == "Web_App_drawio.drawio"

    def test_json_format(self) -> None:
        result = generate_export_filename("API Gateway", "architecture", "json")
        assert result == "API_Gateway_architecture.json"

    def test_empty_title_uses_fallback(self) -> None:
        result = generate_export_filename("", "mermaid", "mmd")
        assert result == "untitled_mermaid.mmd"

    def test_whitespace_title_uses_fallback(self) -> None:
        result = generate_export_filename("   ", "mermaid", "mmd")
        assert result == "untitled_mermaid.mmd"

    def test_ends_with_format_and_extension(self) -> None:
        result = generate_export_filename("Test Title!", "png", "png")
        assert result.endswith("_png.png")
