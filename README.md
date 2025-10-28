# agueda_analysis

# Running the Syntactic Analyzer

To run the Syntactic Analyzer with the jpamb-suite run the following command in the terminal if the virtual environment is configured

```bash
    uv run python -m src.static_analysis.analysis \
  "jpamb.cases.Arrays.arrayContent:()V" \
  --src jpamb/src/main/java --debug
```

\_
