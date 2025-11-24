# agueda_analysis

# Running the Syntactic Analyzer

To run the Syntactic Analyzer with the jpamb-suite run the following command in the terminal if the virtual environment is configured

```bash
  cd jpamb
    uv run jpamb test --filter "Simple" -W ./../my_analyzer.py
```




# Running the Symbolic Execution

To run the Symbolic Execution with the jpamb-suite run the following command in the terminal if the virtual environment is configured

```bash
  cd jpamb
    uv run jpamb test --filter Simple -W ../src/symbolic_execution/analysis.py
```
