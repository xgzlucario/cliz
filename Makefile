build-app:
	uv tool install pyinstaller
	uv run pyinstaller --onefile --name cliq main.py

clean-build:
	rm -rf dist
	rm -rf build
	rm -f *.spec

fix-imports:
	uv run isort .
