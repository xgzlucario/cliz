build-app:
	uv run pyinstaller --onefile --name cliq --add-data "cliq.yaml:." main.py

clean-build:
	rm -rf dist
	rm -rf build