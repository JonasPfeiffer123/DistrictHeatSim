from PyQt5.QtWidgets import QVBoxLayout, QLineEdit, QLabel, QDialog, \
    QDialogButtonBox, QComboBox, QTableWidget, QPushButton, QTableWidgetItem, \
    QFormLayout, QHBoxLayout, QFileDialog

import pandas as pd

from net_generation_QGIS.import_osm_data_geojson import build_query, download_data, save_to_file

class TechInputDialog(QDialog):
    def __init__(self, tech_type):
        super().__init__()

        self.tech_type = tech_type
        self.initUI()

    def initUI(self):
        self.setWindowTitle(f"Eingabe für {self.tech_type}")
        layout = QVBoxLayout()

        # Erstellen Sie hier Eingabefelder basierend auf self.tech_type
        # Beispiel für Solarthermie:
        if self.tech_type == "Solarthermie":
            # area solar
            self.areaSInput = QLineEdit(self)
            self.areaSInput.setText("200")
            layout.addWidget(QLabel("Kollektorbruttofläche in m²"))
            layout.addWidget(self.areaSInput)

            # volume solar heat storage
            self.vsInput = QLineEdit(self)
            self.vsInput.setText("20")
            layout.addWidget(QLabel("Solarspeichervolumen in m³"))
            layout.addWidget(self.vsInput)

            # type
            self.typeInput = QComboBox(self)
            self.techOptions = ["Vakuumröhrenkollektor", "Flachkollektor"]
            self.typeInput.addItems(self.techOptions)
            layout.addWidget(QLabel("Kollektortyp"))
            layout.addWidget(self.typeInput)

        if self.tech_type == "Biomassekessel":
            self.PBMKInput = QLineEdit(self)
            self.PBMKInput.setText("50")
            layout.addWidget(QLabel("thermische Leistung"))
            layout.addWidget(self.PBMKInput)

        if self.tech_type == "Gaskessel":
            layout.addWidget(QLabel("aktuell keine Dimensionierungseingaben, Leistung wird anhand der Gesamtlast berechnet"))

        if self.tech_type == "BHKW":
            self.PBHKWInput = QLineEdit(self)
            self.PBHKWInput.setText("40")
            layout.addWidget(QLabel("thermische Leistung"))
            layout.addWidget(self.PBHKWInput)

        if self.tech_type == "Holzgas-BHKW":
            self.PHBHKWInput = QLineEdit(self)
            self.PHBHKWInput.setText("30")
            layout.addWidget(QLabel("thermische Leistung"))
            layout.addWidget(self.PHBHKWInput)

        if self.tech_type == "Geothermie":
            self.areaGInput = QLineEdit(self)
            self.areaGInput.setText("100")
            self.depthInput = QLineEdit(self)
            self.depthInput.setText("100")
            self.tempGInput = QLineEdit(self)
            self.tempGInput.setText("10")

            layout.addWidget(QLabel("Fläche Erdsondenfeld in m²"))
            layout.addWidget(self.areaGInput)
            layout.addWidget(QLabel("Bohrtiefe Sonden in m³"))
            layout.addWidget(self.depthInput)
            layout.addWidget(QLabel("Quelltemperatur"))
            layout.addWidget(self.tempGInput)
        
        if self.tech_type == "Abwärme":
            self.PWHInput = QLineEdit(self)
            self.PWHInput.setText("30")
            layout.addWidget(QLabel("Kühlleistung Abwärme"))
            layout.addWidget(self.PWHInput)

            self.TWHInput = QLineEdit(self)
            self.TWHInput.setText("30")
            layout.addWidget(QLabel("Temperatur Abwärme"))
            layout.addWidget(self.TWHInput)

        # OK und Abbrechen Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def getInputs(self):
        if self.tech_type == "Solarthermie":
            return {
                "bruttofläche_STA": float(self.areaSInput.text()),
                "vs": float(self.vsInput.text()),
                "Typ": self.typeInput.itemText(self.typeInput.currentIndex())
            }
        elif self.tech_type == "Biomassekessel":
            return {
                "P_BMK": float(self.PBMKInput.text())
            }
        elif self.tech_type == "Gaskessel":
            return {}
        elif self.tech_type == "BHKW":
            return {
                "th_Leistung_BHKW": float(self.PBHKWInput.text())
            }
        elif self.tech_type == "Holzgas-BHKW":
            return {
                "th_Leistung_BHKW": float(self.PHBHKWInput.text())
            }
        elif self.tech_type == "Geothermie":
            return {
                "Fläche": float(self.areaGInput.text()),
                "Bohrtiefe": float(self.depthInput.text()),
                "Temperatur_Geothermie": float(self.tempGInput.text())
            }
        elif self.tech_type == "Abwärme":
            return {
                "Kühlleistung_Abwärme": float(self.PWHInput.text()),
                "Temperatur_Abwärme": float(self.TWHInput.text())
            }
        
class HeatDemandEditDialog(QDialog):
    def __init__(self, gdf_HAST, parent=None):
        super(HeatDemandEditDialog, self).__init__(parent)
        self.gdf_HAST = gdf_HAST
        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)

        # Erstelle eine Tabelle für die Bearbeitung
        self.heatDemandTable = QTableWidget(self)
        self.loadHeatDemandData()
        self.layout.addWidget(self.heatDemandTable)

        # Speicher-Button
        saveButton = QPushButton("Änderungen speichern", self)
        saveButton.clicked.connect(self.saveHeatDemandData)
        self.layout.addWidget(saveButton)

    def loadHeatDemandData(self):
        df = pd.DataFrame(self.gdf_HAST.drop(columns=[self.gdf_HAST.geometry.name]))
        self.heatDemandTable.setRowCount(len(df))
        self.heatDemandTable.setColumnCount(len(df.columns))
        self.heatDemandTable.setHorizontalHeaderLabels(df.columns)

        for i, row in df.iterrows():
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                self.heatDemandTable.setItem(i, j, item)

    def saveHeatDemandData(self):
        for i in range(self.heatDemandTable.rowCount()):
            for j, column_name in enumerate(self.gdf_HAST.drop(columns=[self.gdf_HAST.geometry.name]).columns):
                cell_value = self.heatDemandTable.item(i, j).text()
                self.gdf_HAST.at[i, column_name] = cell_value

        self.gdf_HAST.to_file(self.parent().HASTInput.text(), driver='GeoJSON')
        self.accept()  # Schließt das Dialogfenster

class LayerGenerationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Layer-Generierung")

        layout = QVBoxLayout(self)

        # Formularlayout für Eingaben
        formLayout = QFormLayout()

        # Dateiauswahl für Street Layer und Data CSV
        self.streetLayerInput, self.streetLayerButton = self.createFileInput("C:/Users/jp66tyda/heating_network_generation/net_generation_QGIS/Straßen Zittau.geojson")
        self.dataCsvInput, self.dataCsvButton = self.createFileInput("C:/Users/jp66tyda/heating_network_generation/geocoding/data_output_zi_ETRS89.csv")

        # Koordinateneingaben
        self.xCoordInput = QLineEdit("486267.306999999971595", self)
        self.yCoordInput = QLineEdit("5637294.910000000149012", self)

        formLayout.addRow("GeoJSON-Straßen-Layer:", self.createFileInputLayout(self.streetLayerInput, self.streetLayerButton))
        formLayout.addRow("CSV mit Gebäudestandorten:", self.createFileInputLayout(self.dataCsvInput, self.dataCsvButton))
        formLayout.addRow("X-Koordinate Erzeugerstandort:", self.xCoordInput)
        formLayout.addRow("Y-Koordinate Erzeugerstandort:", self.yCoordInput)

        # Buttons für OK und Abbrechen
        self.okButton = QPushButton("OK", self)
        self.okButton.clicked.connect(self.accept)
        self.cancelButton = QPushButton("Abbrechen", self)
        self.cancelButton.clicked.connect(self.reject)

        layout.addLayout(formLayout)
        layout.addWidget(self.okButton)
        layout.addWidget(self.cancelButton)

    def createFileInput(self, default_path):
        lineEdit = QLineEdit(default_path)
        button = QPushButton("Durchsuchen")
        button.clicked.connect(lambda: self.selectFile(lineEdit))
        return lineEdit, button

    def createFileInputLayout(self, lineEdit, button):
        layout = QHBoxLayout()
        layout.addWidget(lineEdit)
        layout.addWidget(button)
        return layout

    def selectFile(self, lineEdit):
        filename, _ = QFileDialog.getOpenFileName(self, "Datei auswählen", "", "All Files (*)")
        if filename:
            lineEdit.setText(filename)

    def getInputs(self):
        return {
            "streetLayer": self.streetLayerInput.text(),
            "dataCsv": self.dataCsvInput.text(),
            "xCoord": self.xCoordInput.text(),
            "yCoord": self.yCoordInput.text()
        }
    
class DownloadOSMDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags_to_download = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Download OSM-Data")

        layout = QVBoxLayout(self)

        # Stadtname Eingabefeld
        self.cityLineEdit, cityButton = self.createCityInput("Stadtname")
        layout.addLayout(self.createFileInputLayout(self.cityLineEdit, cityButton))
        
        # Dateiname Eingabefeld
        self.filenameLineEdit, fileButton = self.createFileInput("osm_data.geojson")
        layout.addLayout(self.createFileInputLayout(self.filenameLineEdit, fileButton))

        # Tags-Auswahl
        self.tagsLayout = QFormLayout()
        layout.addLayout(self.tagsLayout)
        self.addTagField()  # Erstes Tag-Feld hinzufügen
        
        # Buttons zum Hinzufügen/Entfernen von Tags
        self.addTagButton = QPushButton("Tag hinzufügen", self)
        self.addTagButton.clicked.connect(self.addTagField)
        self.removeTagButton = QPushButton("Tag entfernen", self)
        self.removeTagButton.clicked.connect(self.removeTagField)
        layout.addWidget(self.addTagButton)
        layout.addWidget(self.removeTagButton)
        
        # Buttons für OK und Abbrechen
        self.okButton = QPushButton("OK", self)
        self.okButton.clicked.connect(self.onAccept)
        self.cancelButton = QPushButton("Abbrechen", self)
        self.cancelButton.clicked.connect(self.reject)
        
        layout.addWidget(self.okButton)
        layout.addWidget(self.cancelButton)

    def createFileInput(self, default_path):
        lineEdit = QLineEdit(default_path)
        button = QPushButton("Durchsuchen")
        button.clicked.connect(lambda: self.selectFile(lineEdit))
        return lineEdit, button

    def createFileInputLayout(self, lineEdit, button):
        layout = QHBoxLayout()
        layout.addWidget(lineEdit)
        layout.addWidget(button)
        return layout

    def selectFile(self, lineEdit):
        filename, _ = QFileDialog.getOpenFileName(self, "Datei auswählen", "", "All Files (*)")
        if filename:
            lineEdit.setText(filename)
    
    def createCityInput(self, placeholder_text):
        lineEdit = QLineEdit(placeholder_text)
        button = QPushButton("Stadt bestätigen")
        button.clicked.connect(lambda: self.setCityName(lineEdit))
        return lineEdit, button

    def setCityName(self, lineEdit):
        self.city_name = lineEdit.text()
    
    def addTagField(self):
        keyLineEdit = QLineEdit()
        valueLineEdit = QLineEdit()
        self.tagsLayout.addRow(keyLineEdit, valueLineEdit)
        self.tags_to_download.append((keyLineEdit, valueLineEdit))
    
    def removeTagField(self):
        if self.tags_to_download:
            keyLineEdit, valueLineEdit = self.tags_to_download.pop()
            self.tagsLayout.removeRow(keyLineEdit)
    
    def onAccept(self):
        # Daten sammeln
        self.filename = self.filenameLineEdit.text()
        tags = {key.text(): value.text() for key, value in self.tags_to_download if key.text()}
        
        # Abfrage erstellen und Daten herunterladen
        self.downloadOSMData(self.city_name, tags, self.filename)
        self.accept()

    # Die Methode des Dialogs, die die anderen Funktionen aufruft
    def downloadOSMData(self, city_name, tags, filename):
        # Erstelle die Overpass-Abfrage
        query = build_query(city_name, tags)
        # Lade die Daten herunter
        geojson_data = download_data(query)
        # Speichere die Daten als GeoJSON
        save_to_file(geojson_data, filename)