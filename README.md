# Fellowship Sim Project

This project is a simple simulation model for the game [fellowship](https://coffeestain.com/game/fellowship/).
For the time being, only elarion is available.

- **Github repository**: <https://github.com/maxiQE/fellowship_sim/>

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

## Installation

1. Clone repository: `git clone https://github.com/maxiQE/fellowship_sim.git`
1. Create a local environment and install the library.

**With uv (recommended):**

[uv installation documentation](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv sync                         # create the local environment and install dependencies
source .venv/bin/activate       # activate local environment
```

**With pip:**

NB: first create a virtual environment with your prefered manager! Do not install packages globally.

```bash
# First create virtual env !!
pip install .
```

## Usage

For the time being, usage is only through manual interaction with the library code.

The [script folder](scripts) contains multiple examples.
Run them as `python scripts/NAME.py`

- [Running multiple runs to compare builds and rotations accross multiple scenarios](scripts/compare.py)
- Running a single simulation, to understand the mechancics of the sim and check interactions:
    - [barrage build simple rotation](scripts/simple_example__barrage.py)
    - [hwa build simple rotation](scripts/simple_example__highwind.py)
- [Interacting via the python console with the simulation (barrage build)](scripts/interactive_example__barrage.py).
    Run this script as `python -i scripts/interactive_example__barrage.py`.

## Development

### Tooling

1. Package manager: uv (by astral)
1. Testing: pytest; run with `pytest`
1. Linter / formatter: ruff (by astral); run with `ruff check` or `ruff check --output-format=concise`
1. type check: ty (by astral); run with `ty check` or `ty check --output-format=concise`
1. IDE: VSCode

### Documentation 

**WIP**

[For the time being, refer to the contents of the documentation folder](/documentation/)

## License

[Released under the MIT license](LICENSE).


---

Repository initiated with [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv).
