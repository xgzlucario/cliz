build-app:
	uv add pyinstaller
	uv run pyinstaller --onefile --name cli-agent main.py
	cp dist/cli-agent .

clean-build:
	rm -rf dist
	rm -rf build