# LTTng-tools benchmarks

Blackbox benchmarks for LTTng-tools

## Running

From source:

    git clone https://github.com/kienanstewart/lttng-tools-benchmarks.git && cd lttng-tools-benchmarks
    poetry run src/cli.py

## Configuration

### Defaults

A JSON or YAML file

    ---
    # config.yaml
    config:
      runs: 10   # The number of runs for each benchmark
    search_paths:
      - /path/to/x
      - relative/path/to/x

Set the defaults via command-line:


    poetry run src/cli.py --config /path/to/config.yaml

### Benchmark selection


#### via configuration file

A JSON or YAML file

    ---
    # suite.yaml
    search_paths:
      - /path/to/x
      - relative_to_cwd/x

    benchmarks:
      - name: [module.]ClassName
        # Configuration is merged with the defaults
        config:
          runs: 2
        params:
          - # set1
            param_X: vX
            param_Y: vY
          - # set2
            param_X: vX_2
            param_Y: vY_2

Specify it as follows:

    poetry run src/cli.py --benchmarks suite.yaml
