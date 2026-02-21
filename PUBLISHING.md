# 📦 Publishing Gabay to PyPI

Follow these steps to build and upload Gabay to the Python Package Index (PyPI).

## 1. Prerequisites

Ensure you have the latest versions of `build` and `twine` installed:

```bash
pip install --upgrade build twine
```

## 2. Check Metadata

Review `pyproject.toml` to ensure the version number and metadata are correct. 

> [!IMPORTANT]
> PyPI does not allow overwriting versions. Always increment the version (e.g., `0.1.1` → `0.1.2`) before publishing.

## 3. Build the Package

Run the following command from the project root:

```bash
python -m build
```

This will create a `dist/` directory containing:
- A `.tar.gz` source distribution.
- A `.whl` binary wheel.

## 4. Verify the Build

You can check if the package long description (README) will render correctly on PyPI:

```bash
twine check dist/*
```

## 5. Upload to PyPI

### To TestPyPI (Recommended first)
Test your upload on the staging server:

```bash
twine upload --repository testpypi dist/*
```

### To PyPI
Upload your package to the official index:

```bash
twine upload dist/*
```

You will be prompted for your PyPI username and password (or API token).

## 6. Verify Installation

Once uploaded, you can try installing it:

```bash
pip install gabay
```

Then run the command:
```bash
gabay --help
```
