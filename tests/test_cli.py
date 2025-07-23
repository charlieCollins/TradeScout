"""
Tests for CLI Interface
"""

import pytest
import tempfile
import os
from click.testing import CliRunner

from src.tradescout.scripts.cli import main


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
        temp_path = temp_file.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner"""
    return CliRunner()


class TestCLI:
    """Test CLI functionality"""

    def test_cli_help(self, cli_runner):
        """Test CLI help command"""
        result = cli_runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "TradeScout - Personal Market Research Assistant" in result.output
        assert "Commands:" in result.output

    def test_cli_version(self, cli_runner):
        """Test CLI version command"""
        result = cli_runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_status_command(self, cli_runner, temp_db_path):
        """Test status command"""
        result = cli_runner.invoke(main, ["--db-path", temp_db_path, "status"])
        assert result.exit_code == 0
        assert "TradeScout System Status" in result.output
        assert "Database Statistics" in result.output

    def test_quote_command_help(self, cli_runner):
        """Test quote command help"""
        result = cli_runner.invoke(main, ["quote", "--help"])
        assert result.exit_code == 0
        assert "Get current market quotes" in result.output
        assert "Examples:" in result.output

    def test_history_command_help(self, cli_runner):
        """Test history command help"""
        result = cli_runner.invoke(main, ["history", "--help"])
        assert result.exit_code == 0
        assert "Show historical quotes" in result.output

    def test_fundamentals_command_help(self, cli_runner):
        """Test fundamentals command help"""
        result = cli_runner.invoke(main, ["fundamentals", "--help"])
        assert result.exit_code == 0
        assert "Show fundamental data" in result.output

    def test_volume_leaders_command_help(self, cli_runner):
        """Test volume-leaders command help"""
        result = cli_runner.invoke(main, ["volume-leaders", "--help"])
        assert result.exit_code == 0
        assert "Scan for stocks with unusual volume" in result.output

    def test_cleanup_command_help(self, cli_runner):
        """Test cleanup command help"""
        result = cli_runner.invoke(main, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "Clean up old data" in result.output

    def test_backup_command_help(self, cli_runner):
        """Test backup command help"""
        result = cli_runner.invoke(main, ["backup", "--help"])
        assert result.exit_code == 0
        assert "Create a backup" in result.output

    def test_invalid_command(self, cli_runner):
        """Test invalid command handling"""
        result = cli_runner.invoke(main, ["invalid-command"])
        assert result.exit_code != 0
        assert "No such command" in result.output

    def test_history_no_data(self, cli_runner, temp_db_path):
        """Test history command with no data"""
        result = cli_runner.invoke(
            main, ["--db-path", temp_db_path, "history", "NONEXISTENT"]
        )
        assert result.exit_code == 0
        assert "No historical data found" in result.output

    def test_cleanup_with_confirmation(self, cli_runner, temp_db_path):
        """Test cleanup command with confirmation flag"""
        result = cli_runner.invoke(
            main, ["--db-path", temp_db_path, "cleanup", "--confirm"]
        )
        assert result.exit_code == 0
        assert "Cleaning up data" in result.output

    def test_backup_command(self, cli_runner, temp_db_path):
        """Test backup command"""
        backup_path = temp_db_path + ".backup"
        try:
            result = cli_runner.invoke(
                main, ["--db-path", temp_db_path, "backup", backup_path]
            )
            assert result.exit_code == 0
            assert "Creating backup" in result.output
            assert os.path.exists(backup_path)
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_verbose_flag(self, cli_runner, temp_db_path):
        """Test verbose logging flag"""
        result = cli_runner.invoke(
            main, ["--verbose", "--db-path", temp_db_path, "status"]
        )
        assert result.exit_code == 0
        # Verbose flag should enable more detailed logging, but still work

    def test_custom_db_path(self, cli_runner, temp_db_path):
        """Test custom database path option"""
        result = cli_runner.invoke(main, ["--db-path", temp_db_path, "status"])
        assert result.exit_code == 0
        assert temp_db_path in result.output or "Database Statistics" in result.output


class TestCLIIntegration:
    """Integration tests for CLI with mocked data"""

    def test_quote_command_no_symbols(self, cli_runner, temp_db_path):
        """Test quote command without symbols (should fail)"""
        result = cli_runner.invoke(main, ["--db-path", temp_db_path, "quote"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_multiple_command_chain(self, cli_runner, temp_db_path):
        """Test running multiple commands in sequence"""
        # First check status
        result1 = cli_runner.invoke(main, ["--db-path", temp_db_path, "status"])
        assert result1.exit_code == 0

        # Then try history (should show no data)
        result2 = cli_runner.invoke(
            main, ["--db-path", temp_db_path, "history", "AAPL"]
        )
        assert result2.exit_code == 0
        assert "No historical data found" in result2.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
