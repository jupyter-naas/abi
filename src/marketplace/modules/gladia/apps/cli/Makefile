# Gladia CLI Makefile

.PHONY: help run clean

# Default target
help:
	@echo "Gladia CLI"
	@echo "=========="
	@echo ""
	@echo "Usage:"
	@echo "  make run URL=<url>   - Transcribe audio/video URL"
	@echo "  make clean           - Clean temp files"
	@echo ""
	@echo "Example:"
	@echo "  make run URL='https://youtube.com/watch?v=...'"

# Run transcription
run:
	@if [ -z "$(URL)" ]; then \
		echo "❌ Error: URL parameter required"; \
		echo "Usage: make run URL='https://youtube.com/watch?v=...'"; \
		exit 1; \
	fi
	python playground.py "$(URL)"

# Clean temporary files
clean:
	@echo "🧹 Cleaning..."
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true