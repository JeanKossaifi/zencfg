# ZenCFG Documentation

## Install Dependencies

```bash
pip install sphinx pydata-sphinx-theme sphinx-copybutton sphinx-design
```

## Build the Documentation

You can build the documentation website using `sphinx-build`: 

```bash
sphinx-build -b html docs docs/_build/html
```

Note that you also can generate a single page documentation or a pdf:
```
# Single HTML page
sphinx-build -b singlehtml docs docs/_build/singlehtml

# PDF
sphinx-build -b latex docs docs/_build/latex
cd docs/_build/latex && make
```

Then simply point your browser to `docs/_build/html/index.html`.

