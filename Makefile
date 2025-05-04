build:
	rm -rf dist
	uv build

build-and-install:
	rm -rf dist
	uv build
	uv tool install dist/cliz-0.1.3-py3-none-any.whl --force

fix-imports:
	uv run isort .

upload:
	twine upload dist/* --verbose