import sys
import click
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow


@click.command()
@click.option(
    '--file',
    '-f',
    default='graph.yaml',
    help='The YAML file to load and save the graph data.'
)
def run_cli(file: str) -> None:
    """Launch the Planar Map GUI."""
    app = QApplication(sys.argv)
    window = MainWindow(file)
    window.show()
    sys.exit(app.exec())
