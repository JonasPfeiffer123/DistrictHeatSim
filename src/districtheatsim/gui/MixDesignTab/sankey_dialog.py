import sys
import plotly.graph_objects as go
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import tempfile
import os

class SankeyDialog(QDialog):
    """
    Dialog to display a Sankey diagram using Plotly in a QWebEngineView.
    """

    def __init__(self, results=None, parent=None):
        super().__init__(parent)
        self.results = results
        self.initUI()

    def initUI(self):
        """
        Initialize the Sankey dialog UI and display the Plotly diagram.
        """
        self.setWindowTitle("Sankey-Diagramm - Energieflüsse im Quartier")
        self.resize(800, 600)

        # Set the layout
        layout = QVBoxLayout(self)

        # Create a QWebEngineView to display the Plotly HTML content
        self.browser = QWebEngineView(self)
        layout.addWidget(self.browser)

        # Create the Plotly Sankey diagram using results
        self.plotSankey()

        self.setLayout(layout)

    def plotSankey(self):
        """
        Generate and display a Sankey diagram using Plotly based on results data.
        """
        if self.results is None:
            return

        # Extract relevant data from results
        jahreswaermebedarf = self.results['Jahreswärmebedarf']  # Total heat demand (input)
        waermemengen = self.results['Wärmemengen']  # Heat generated by each generator (outputs)
        erzeuger_labels = self.results['techs']  # Labels for the heat generators
        colors = self.results['colors']  # Colors for the links

        # Define source and target nodes
        # All sources are from the "Input" (index 0)
        sources = [0] * len(erzeuger_labels)
        # Targets are the individual heat generators (indices 1 to len(erzeuger_labels))
        targets = list(range(1, len(erzeuger_labels) + 1))

        # Define labels for the nodes (Input and all generators)
        node_labels = ["Netz (Jahreswärmebedarf)"] + list(erzeuger_labels)

        # Create the Sankey diagram
        fig = go.Figure(go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=node_labels,
                color="blue"  # Color of nodes
            ),
            link=dict(
                source=sources,  # All links originate from the "Netz"
                target=targets,  # Links point to each generator
                value=waermemengen,  # The values correspond to the heat amounts generated
                color=colors  # Apply the custom colors for each link
            )))

        fig.update_layout(title_text="Sankey Diagram - Energieverteilung im Wärmenetz", font_size=10)

        # Save the figure as an HTML file in a temporary directory
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
            fig.write_html(temp_file.name)
            self.html_file_path = temp_file.name

        # Load the HTML file in the QWebEngineView
        self.browser.setUrl(QUrl.fromLocalFile(self.html_file_path))

    def closeEvent(self, event):
        """
        Clean up the temporary HTML file when the dialog is closed.
        """
        if os.path.exists(self.html_file_path):
            os.remove(self.html_file_path)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Simulated 'results' data for testing
    results = {
        'Jahreswärmebedarf': 4392.997250030184,
        'Wärmemengen': [200.34259576, 1505.44989018, 1313.92519592, 1373.27956817],
        'techs': ['Solarthermie_1', 'BHKW_1', 'Biomassekessel_1', 'Gaskessel_1'],
        'colors': ['red', 'yellow', 'green', 'saddlebrown']
    }
    dialog = SankeyDialog(results=results)
    dialog.show()
    sys.exit(app.exec_())
import sys
import plotly.graph_objects as go
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import tempfile
import os

class SankeyDialog(QDialog):
    """
    Dialog to display a Sankey diagram using Plotly in a QWebEngineView.
    """

    def __init__(self, results=None, parent=None):
        super().__init__(parent)
        self.results = results
        self.initUI()

    def initUI(self):
        """
        Initialize the Sankey dialog UI and display the Plotly diagram.
        """
        self.setWindowTitle("Sankey-Diagramm - Energieflüsse im Quartier")
        self.resize(800, 600)

        # Set the layout
        layout = QVBoxLayout(self)

        # Create a QWebEngineView to display the Plotly HTML content
        self.browser = QWebEngineView(self)
        layout.addWidget(self.browser)

        # Create the Plotly Sankey diagram using results
        self.plotSankey()

        self.setLayout(layout)

    def plotSankey(self):
        """
        Generate and display a Sankey diagram using Plotly based on results data.
        """
        if self.results is None:
            return

        # Extract relevant data from results
        jahreswaermebedarf = self.results['Jahreswärmebedarf']  # Total heat demand (input)
        waermemengen = self.results['Wärmemengen']  # Heat generated by each generator (outputs)
        erzeuger_labels = self.results['techs']  # Labels for the heat generators
        colors = self.results['colors']  # Colors for the links

        # Define source and target nodes
        # All sources are from the "Input" (index 0)
        sources = [0] * len(erzeuger_labels)
        # Targets are the individual heat generators (indices 1 to len(erzeuger_labels))
        targets = list(range(1, len(erzeuger_labels) + 1))

        # Define labels for the nodes (Input and all generators)
        node_labels = ["Netz (Jahreswärmebedarf)"] + list(erzeuger_labels)

        # Create the Sankey diagram
        fig = go.Figure(go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=node_labels,
                color="blue"  # Color of nodes
            ),
            link=dict(
                source=sources,  # All links originate from the "Netz"
                target=targets,  # Links point to each generator
                value=waermemengen,  # The values correspond to the heat amounts generated
                color=colors  # Apply the custom colors for each link
            )))

        fig.update_layout(title_text="Sankey Diagram - Energieverteilung im Wärmenetz", font_size=10)

        # Save the figure as an HTML file in a temporary directory
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
            fig.write_html(temp_file.name)
            self.html_file_path = temp_file.name

        # Load the HTML file in the QWebEngineView
        self.browser.setUrl(QUrl.fromLocalFile(self.html_file_path))

    def closeEvent(self, event):
        """
        Clean up the temporary HTML file when the dialog is closed.
        """
        if os.path.exists(self.html_file_path):
            os.remove(self.html_file_path)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Simulated 'results' data for testing
    results = {
        'Jahreswärmebedarf': 4392.997250030184,
        'Wärmemengen': [200.34259576, 1505.44989018, 1313.92519592, 1373.27956817],
        'techs': ['Solarthermie_1', 'BHKW_1', 'Biomassekessel_1', 'Gaskessel_1'],
        'colors': ['red', 'yellow', 'green', 'saddlebrown']
    }
    dialog = SankeyDialog(results=results)
    dialog.show()
    sys.exit(app.exec_())
