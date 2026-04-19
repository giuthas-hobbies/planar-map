
"""
Command-line interface for the Planar Map application.

This module provides the entry point for launching the PyQt6-based
Planar Map graphical user interface. It uses the `click` library to
parse command-line arguments and initialize the application instance.

Examples
--------
Assuming the package is installed or executable, you can run the GUI
from your terminal using the default file:

.. code-block:: bash

    $ python -m planar_map.cli

You can also specify a custom YAML file using the provided options:

.. code-block:: bash

    $ python -m planar_map.cli --file my_custom_graph.yaml
    # or
    $ python -m planar_map.cli -f my_custom_graph.yaml
"""

import sys
import click
from PyQt6.QtWidgets import QApplication
from planar_map.main_window import MainWindow


@click.command()
@click.option(
    '--file',
    '-f',
    default='graph.yaml',
    help='The YAML file to load and save the graph data.'
)
def run_cli(file: str) -> None:
    """
    Launch the Planar Map GUI.

    This function initializes the PyQt6 application loop, instantiates
    the `MainWindow` with the provided file path, and executes the
    application.

    Parameters
    ----------
    file : str
        The path to the YAML file to load and save the graph data.
        Defaults to 'graph.yaml' via the click option.

    Returns
    -------
    None

    Examples
    --------
    While typically invoked directly from the command line, you can
    invoke this command programmatically (e.g., for unit testing)
    using `click.testing.CliRunner`:

    >>> from click.testing import CliRunner
    >>> from planar_map.cli import run_cli
    >>> runner = CliRunner()
    >>> result = runner.invoke(run_cli, ['--file', 'test_graph.yaml'])
    >>> result.exit_code
    0
    """
    app = QApplication(sys.argv)
    window = MainWindow(file)
    window.show()
    sys.exit(app.exec())
