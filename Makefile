.PHONY: start stop backend frontend install

start:          ## Start backend + frontend tegelijk
	@bash start.sh

backend:        ## Alleen backend (FastAPI :8000)
	@source backend/.venv/bin/activate && \
	uvicorn main:app --reload --app-dir backend --host 0.0.0.0 --port 8000

frontend:       ## Alleen frontend (Vite :5173)
	@npm --prefix frontend run dev

install:        ## Installeer alle dependencies (eenmalig)
	@python3 -m venv backend/.venv
	@source backend/.venv/bin/activate && pip install -r backend/requirements.txt
	@npm --prefix frontend install

help:           ## Toon dit overzicht
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
