up: build .env
	docker-compose up
	python -m webbrowser "http://127.0.0.1:8501/"

down:
	docker-compose down

build:
	docker-compose build

# Using ANSI Shadow
define setup_message
\033[0;32m

┌───────────────────────────────────────────────────────────────────┐
│                                                                   │
│  █████╗ ██████╗ ██╗    ███████╗███████╗████████╗██╗   ██╗██████╗  │
│ ██╔══██╗██╔══██╗██║    ██╔════╝██╔════╝╚══██╔══╝██║   ██║██╔══██╗ │
│ ███████║██████╔╝██║    ███████╗█████╗     ██║   ██║   ██║██████╔╝ │
│ ██╔══██║██╔══██╗██║    ╚════██║██╔══╝     ██║   ██║   ██║██╔═══╝  │
│ ██║  ██║██████╔╝██║    ███████║███████╗   ██║   ╚██████╔╝██║      │
│ ╚═╝  ╚═╝╚═════╝ ╚═╝    ╚══════╝╚══════╝   ╚═╝    ╚═════╝ ╚═╝      │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘

We need to setup your .env file. Please provide the required information.
\033[0m
endef
export setup_message

.env:
	@echo "$$setup_message"
	@read -p "OpenAI API Key: " openai_key \
	&& echo "OPENAI_API_KEY=$$openai_key" > .env
