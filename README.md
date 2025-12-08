# agueda_analysis

# Running the Syntactic Analyzer

To run the Syntactic Analyzer with the jpamb-suite run the following command in the terminal if the virtual environment is configured

```bash
  cd jpamb
    uv run jpamb test --filter "Simple" -W ./../my_analyzer.py
```




## Running the Symbolic Execution

To run the symbolic execution engine on the JPAMB suite, use the command below
(from the `agueda_analysis` repo, with the virtual environment already set up):

```bash
cd jpamb

SE_VERBOSE=0 \
SE_GUIDED=1 \
RUN_FUZZER=1 \
JAVA_BIN=/opt/homebrew/opt/openjdk@21/bin/java \
uv run jpamb test \
  --filter OkTrue \
  --timeout 0 \
  -W ../src/symbolic_execution/analysis.py
```

