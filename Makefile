build:
	uv build

build-and-install:
	uv build
	uv tool install dist/cliz-0.1.0-py3-none-any.whl --force

clean-build:
	rm -rf dist

fix-imports:
	uv run isort .

upload:
	twine upload dist/* --verbose