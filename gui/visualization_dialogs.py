import geopandas as gpd
import pandas as pd
import numpy as np
import json
import csv
from math import radians, sin, cos, sqrt, atan2
from shapely.geometry import box, Point
from shapely.ops import transform
import pyproj

from PyQt5.QtWidgets import QVBoxLayout, QLineEdit, QDialog, QComboBox, QPushButton, \
    QFormLayout, QHBoxLayout, QFileDialog, QProgressBar, QMessageBox, QLabel, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.threads import GeocodingThread
from geocoding.geocodingETRS89 import get_coordinates, process_data
from osm.import_osm_data_geojson import build_query, download_data, save_to_file
from osm.Wärmeversorgungsgebiete import clustering_quartiere_hdbscan, postprocessing_hdbscan, allocate_overlapping_area
   
class LayerGenerationDialog(QDialog):
    def __init__(self, base_path, parent=None):
        super().__init__(parent)
        self.base_path = base_path
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        # Formularlayout für Eingaben
        formLayout = QFormLayout()

        self.fileInput, self.fileButton = self.createFileInput(f"{self.base_path}/Raumanalyse/Straßen.geojson")
        # Eingabefelder für Dateipfade und Koordinaten
        self.dataTypeComboBox = QComboBox(self)
        self.dataTypeComboBox.addItems(["CSV", "GeoJSON"])
        self.dataTypeComboBox.currentIndexChanged.connect(self.toggleFileInputMode)
        self.dataInput, self.dataCsvButton = self.createFileInput(f"{self.base_path}/Gebäudedaten/data_output_ETRS89.csv")

        # Auswahlmodus für Erzeugerstandort
        self.locationModeComboBox = QComboBox(self)
        self.locationModeComboBox.addItems(["Koordinaten direkt eingeben", "Adresse eingeben", "Koordinaten aus CSV laden"])
        self.locationModeComboBox.currentIndexChanged.connect(self.toggleLocationInputMode)

        self.xCoordInput = QLineEdit("486267.307", self)
        self.yCoordInput = QLineEdit("5637294.91", self)
        self.countryInput = QLineEdit(self)
        self.countryInput.setPlaceholderText("Land")
        self.countryInput.setEnabled(False)
        self.stateInput = QLineEdit(self)
        self.stateInput.setPlaceholderText("Bundesland")
        self.stateInput.setEnabled(False)
        self.cityInput = QLineEdit(self)
        self.cityInput.setPlaceholderText("Stadt")
        self.cityInput.setEnabled(False)
        self.streetInput = QLineEdit(self)
        self.streetInput.setPlaceholderText("Straße und Hausnummer")
        self.streetInput.setEnabled(False)
        self.coordsCsvInput, self.coordsCsvButton = self.createFileInput(f"{self.base_path}/Gebäudedaten/data_output_ETRS89.csv")
        self.coordsCsvInput.setEnabled(False)
        self.coordsCsvButton.setEnabled(False)

        # Buttons
        self.geocodeButton = QPushButton("Adresse geocodieren", self)
        self.geocodeButton.clicked.connect(self.geocodeAddress)
        self.geocodeButton.setEnabled(False)

        self.loadCoordsButton = QPushButton("Erzeugerkoordinaten aus CSV laden", self)
        self.loadCoordsButton.clicked.connect(self.loadCoordsFromCSV)
        self.loadCoordsButton.setEnabled(False)

        self.loadgeojsonCoordsButton = QPushButton("Gebäudekoordinaten aus geojson laden", self)
        self.loadgeojsonCoordsButton.clicked.connect(self.createCsvFromGeoJson)

        # Hinzufügen von Widgets zum Formularlayout
        formLayout.addRow("GeoJSON-Straßen-Layer:", self.createFileInputLayout(self.fileInput, self.fileButton))
        formLayout.addRow("Dateityp Gebäudestandorte:", self.dataTypeComboBox)
        formLayout.addRow("Datei Gebäudestandorte:", self.createFileInputLayout(self.dataInput, self.dataCsvButton))
        formLayout.addRow(self.loadgeojsonCoordsButton)
        formLayout.addRow("Modus für Erzeugerstandort:", self.locationModeComboBox)
        formLayout.addRow("X-Koordinate Erzeugerstandort:", self.xCoordInput)
        formLayout.addRow("Y-Koordinate Erzeugerstandort:", self.yCoordInput)
        formLayout.addRow("Land:", self.countryInput)
        formLayout.addRow("Bundesland:", self.stateInput)
        formLayout.addRow("Stadt:", self.cityInput)
        formLayout.addRow("Straße:", self.streetInput)
        formLayout.addRow(self.geocodeButton)
        formLayout.addRow("CSV mit Koordinaten:", self.createFileInputLayout(self.coordsCsvInput, self.coordsCsvButton))
        formLayout.addRow(self.loadCoordsButton)

        layout.addLayout(formLayout)

        # OK und Abbrechen Buttons
        self.okButton = QPushButton("OK", self)
        self.okButton.clicked.connect(self.accept)
        self.cancelButton = QPushButton("Abbrechen", self)
        self.cancelButton.clicked.connect(self.reject)

        layout.addWidget(self.okButton)
        layout.addWidget(self.cancelButton)

        self.setLayout(layout)

    def toggleFileInputMode(self, index):
        self.loadgeojsonCoordsButton.setEnabled(index == 1)
        if index == 0:
            self.dataInput.setText(f"{self.base_path}/Gebäudedaten/data_output_ETRS89.csv")
        elif index == 1:
            self.dataInput.setText(f"{self.base_path}/Raumanalyse/waermenetz_buildings.geojson")

    def toggleLocationInputMode(self, index):
        self.xCoordInput.setEnabled(index == 0)
        self.yCoordInput.setEnabled(index == 0)
        self.countryInput.setEnabled(index == 1)
        self.stateInput.setEnabled(index == 1)
        self.cityInput.setEnabled(index == 1)
        self.streetInput.setEnabled(index == 1)
        self.coordsCsvInput.setEnabled(index == 2)
        self.coordsCsvButton.setEnabled(index == 2)
        self.geocodeButton.setEnabled(index == 1)
        self.loadCoordsButton.setEnabled(index == 2)

    def geocodeAddress(self):
        # Zusammensetzen der vollständigen Adresse aus den einzelnen Feldern
        address = f"{self.streetInput.text()}, {self.cityInput.text()}, {self.stateInput.text()}, {self.countryInput.text()}"
        if address.strip(", ").replace(" ", ""):
            utm_x, utm_y = get_coordinates(address)
            if utm_x and utm_y:
                self.xCoordInput.setText(str(utm_x))
                self.yCoordInput.setText(str(utm_y))
            else:
                QMessageBox.warning(self, "Warnung", "Adresse konnte nicht geocodiert werden.")
        else:
            QMessageBox.warning(self, "Warnung", "Bitte geben Sie eine vollständige Adresse ein.")

    def loadCoordsFromCSV(self):
        csv_file_path = self.coordsCsvInput.text()
        if csv_file_path:
            try:
                process_data(csv_file_path, "temporary_output.csv")
                QMessageBox.information(self, "Info", "Koordinaten wurden geladen und in 'temporary_output.csv' gespeichert.")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Ein Fehler ist aufgetreten: {e}")
        else:
            QMessageBox.warning(self, "Warnung", "Bitte wählen Sie eine CSV-Datei aus.")

    def createFileInput(self, default_path):
        lineEdit = QLineEdit(default_path)
        button = QPushButton("Durchsuchen")
        button.clicked.connect(lambda: self.openFileDialog(lineEdit))
        return lineEdit, button

    def openFileDialog(self, lineEdit):
        filename, _ = QFileDialog.getOpenFileName(self, "Datei auswählen", "", "All Files (*)")
        if filename:
            lineEdit.setText(filename)

    def createFileInputLayout(self, lineEdit, button):
        layout = QHBoxLayout()
        layout.addWidget(lineEdit)
        layout.addWidget(button)
        return layout

    def createCsvFromGeoJson(self):
        try:
            geojson_file = self.dataInput.text()
            csv_file = f"{self.base_path}/Gebäudedaten/generated_building_data.csv"
            with open(geojson_file, 'r') as geojson_file:
                data = json.load(geojson_file)
            
            with open(csv_file, 'w', encoding='utf-8', newline='') as csvfile:
                fieldnames = ["Land", "Bundesland", "Stadt", "Adresse", "Wärmebedarf", "UTM_X", "UTM_Y"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()

                for feature in data['features']:
                    if feature['geometry']['type'] == 'MultiPolygon':
                        for polygon_coords in feature['geometry']['coordinates']:
                            centroid = self.calculateCentroid(polygon_coords)
                            writer.writerow({
                                "Land": "",
                                "Bundesland": "",
                                "Stadt": "",
                                "Adresse": "",
                                "Wärmebedarf": "",
                                "UTM_X": centroid[0],
                                "UTM_Y": centroid[1]
                            })
                    elif feature['geometry']['type'] == 'Polygon':
                        centroid = self.calculateCentroid(feature['geometry']['coordinates'])
                        writer.writerow({
                            "Land": "",
                            "Bundesland": "",
                            "Stadt": "",
                            "Adresse": "",
                            "Wärmebedarf": "",
                            "UTM_X": centroid[0],
                            "UTM_Y": centroid[1]
                        })

            QMessageBox.information(self, "Info", "CSV-Datei wurde erfolgreich erstellt.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def calculateCentroid(self, coordinates):
        x_sum = 0
        y_sum = 0
        total_points = 0

        if isinstance(coordinates[0], float):
            x_sum += coordinates[0]
            y_sum += coordinates[1]
            total_points += 1
        else:
            for item in coordinates:
                x, y = self.calculateCentroid(item)
                if x is not None and y is not None:
                    x_sum += x
                    y_sum += y
                    total_points += 1

        if total_points > 0:
            centroid_x = x_sum / total_points
            centroid_y = y_sum / total_points
            return centroid_x, centroid_y
        else:
            return None, None

    
    def getInputs(self):
        return {
            "streetLayer": self.fileInput.text(),
            "dataCsv": self.dataInput.text(),
            "xCoord": self.xCoordInput.text(),
            "yCoord": self.yCoordInput.text()
        }

class DownloadOSMDataDialog(QDialog):
    def __init__(self, base_path, parent=None):
        super().__init__(parent)
        self.base_path = base_path
        self.tags_to_download = []
        self.tagsLayoutList = []

        self.standard_tags = [
            {"highway": "primary"},
            {"highway": "secondary"},
            {"highway": "tertiary"},
            {"highway": "residential"},
            {"highway": "living_street"}
        ]

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Download OSM-Data")
        layout = QVBoxLayout(self)

        # Stadtname Eingabefeld
        self.cityLineEdit = QLineEdit("Zittau")
        layout.addWidget(self.cityLineEdit)
        
        # Dateiname Eingabefeld
        self.filenameLineEdit, fileButton = self.createFileInput(f"{self.base_path}/Raumanalyse/Straßen.geojson")
        layout.addLayout(self.createFileInputLayout(self.filenameLineEdit, fileButton))

        # Dropdown-Menü für einzelne Standard-Tags
        self.standardTagsComboBox = QComboBox(self)
        for tag in self.standard_tags:
            key = next(iter(tag))
            value = tag[key]
            self.standardTagsComboBox.addItem(f"{key}: {value}")

        # Button zum Laden eines ausgewählten Standard-Tags
        self.loadStandardTagButton = QPushButton("Standard-Tag hinzufügen", self)
        self.loadStandardTagButton.clicked.connect(self.loadSelectedStandardTag)
        layout.addWidget(self.standardTagsComboBox)
        layout.addWidget(self.loadStandardTagButton)

        # Tags-Auswahl
        self.tagsLayout = QFormLayout()
        layout.addLayout(self.tagsLayout)
        
        # Buttons zum Hinzufügen/Entfernen von Tags
        #self.addTagButton = QPushButton("Tag hinzufügen", self)
        #self.addTagButton.clicked.connect(self.addTagField)
        #layout.addWidget(self.addTagButton)

        self.removeTagButton = QPushButton("Tag entfernen", self)
        self.removeTagButton.clicked.connect(self.removeTagField)
        layout.addWidget(self.removeTagButton)

        # Abfrage-Button
        self.queryButton = QPushButton("Abfrage starten", self)
        self.queryButton.clicked.connect(self.startQuery)
        layout.addWidget(self.queryButton)
        
        # Buttons für OK und Abbrechen
        self.okButton = QPushButton("OK", self)
        self.okButton.clicked.connect(self.accept)
        layout.addWidget(self.okButton)

        self.cancelButton = QPushButton("Abbrechen", self)
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

    def addTagField(self, key="", value=""):
        # Sicherstellen, dass key und value immer Strings sind
        key = str(key) if key is not None else ""
        value = str(value) if value is not None else ""

        keyLineEdit = QLineEdit(key)
        valueLineEdit = QLineEdit(value)
        self.tagsLayout.addRow(keyLineEdit, valueLineEdit)

        self.tagsLayoutList.append((keyLineEdit, valueLineEdit))
        self.tags_to_download.append((key, value))
        print(self.tags_to_download)

    def removeTagField(self):
        if self.tags_to_download:
            keyLineEdit, valueLineEdit = self.tagsLayoutList.pop()
            self.tags_to_download.pop()
            self.tagsLayout.removeRow(keyLineEdit)
            print(self.tags_to_download)

    def loadAllStandardTags(self):
        for tag in self.standard_tags:
            key = next(iter(tag))
            value = tag[key]
            self.addTagField(key, value)

    def loadSelectedStandardTag(self):
        selected_tag_index = self.standardTagsComboBox.currentIndex()
        tag = self.standard_tags[selected_tag_index]
        key = next(iter(tag))
        value = tag[key]
        self.addTagField(key, value)
    
    def startQuery(self):
        # Daten sammeln
        #postal_code = self.postalCodeLineEdit.text()
        self.filename = self.filenameLineEdit.text()
        print(self.tags_to_download)
        
        city_name =self.cityLineEdit.text()

        # Erstelle die Overpass-Abfrage
        query = build_query(city_name, self.tags_to_download, element_type="way")
        # Lade die Daten herunter
        geojson_data = download_data(query, element_type="way")
        # Speichere die Daten als GeoJSON
        save_to_file(geojson_data, self.filename)
        gdf = gpd.read_file(self.filename, driver='GeoJSON').to_crs(epsg=25833)
        gdf.to_file(self.filename, driver='GeoJSON')

        QMessageBox.information(self, "Erfolg", f"Abfrageergebnisse gespeichert in {self.filename}")
            
        # Rufen Sie die loadNetData-Methode des Haupt-Tabs auf
        self.parent().loadNetData(self.filename)

class OSMBuildingQueryDialog(QDialog):
    def __init__(self, base_path, parent=None):
        super().__init__(parent)
        self.base_path = base_path
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        self.setWindowTitle("OSM Gebäudeabfrage")

        # Stadtname Eingabefeld
        self.cityLineEdit = QLineEdit(self)
        layout.addWidget(QLabel("Stadtname:"))
        layout.addWidget(self.cityLineEdit)

        # Dateiname Eingabefeld
        self.filenameLineEdit = QLineEdit(f"{self.base_path}/Raumanalyse/output_buildings.geojson", self)
        layout.addWidget(QLabel("Ausgabedatei:"))
        layout.addWidget(self.filenameLineEdit)

        # Dropdown für Filteroptionen
        self.filterComboBox = QComboBox(self)
        self.filterComboBox.addItem("Kein Filter")
        self.filterComboBox.addItem("Filtern mit Koordinatenbereich")
        self.filterComboBox.addItem("Filtern mit zentralen Koordinaten und Radius als Abstand")
        self.filterComboBox.addItem("Filtern mit Adressen aus CSV")
        self.filterComboBox.addItem("Filtern mit Polygon-geoJSON")
        layout.addWidget(QLabel("Filteroptionen:"))
        layout.addWidget(self.filterComboBox)

        # Widgets für Koordinaten
        # Koordinaten Eingabefelder
        self.coordWidget = QWidget(self)
        coordLayout = QVBoxLayout(self.coordWidget)
        self.minLatLineEdit = QLineEdit(self)
        self.minLatLineEdit.setPlaceholderText("Minimale Breite")
        coordLayout.addWidget(QLabel("Minimale Breite:"))
        coordLayout.addWidget(self.minLatLineEdit)

        self.minLonLineEdit = QLineEdit(self)
        self.minLonLineEdit.setPlaceholderText("Minimale Länge")
        coordLayout.addWidget(QLabel("Minimale Länge:"))
        coordLayout.addWidget(self.minLonLineEdit)

        self.maxLatLineEdit = QLineEdit(self)
        self.maxLatLineEdit.setPlaceholderText("Maximale Breite")
        coordLayout.addWidget(QLabel("Maximale Breite:"))
        coordLayout.addWidget(self.maxLatLineEdit)

        self.maxLonLineEdit = QLineEdit(self)
        self.maxLonLineEdit.setPlaceholderText("Maximale Länge")
        coordLayout.addWidget(QLabel("Maximale Länge:"))
        coordLayout.addWidget(self.maxLonLineEdit)
        layout.addWidget(self.coordWidget)

        # Widgets für Koordinaten und Radius
        # Koordinaten
        self.coordRadiusWidget = QWidget(self)
        coordRadiusLayout = QVBoxLayout(self.coordRadiusWidget)
        self.centerLatLineEdit = QLineEdit(self)
        self.centerLatLineEdit.setPlaceholderText("Breite")
        coordRadiusLayout.addWidget(QLabel("Minimale Breite:"))
        coordRadiusLayout.addWidget(self.centerLatLineEdit)

        self.centerLonLineEdit = QLineEdit(self)
        self.centerLonLineEdit.setPlaceholderText("Minimale Länge")
        coordRadiusLayout.addWidget(QLabel("Minimale Länge:"))
        coordRadiusLayout.addWidget(self.centerLonLineEdit)

        # Radius
        self.radiusLineEdit = QLineEdit(self)
        self.radiusLineEdit.setPlaceholderText("Radius in Metern")
        coordRadiusLayout.addWidget(QLabel("Radius in Metern:"))
        coordRadiusLayout.addWidget(self.radiusLineEdit)
        layout.addWidget(self.coordRadiusWidget)

        # Widget für Adressen aus CSV
        self.csvWidget = QWidget(self)
        csvLayout = QVBoxLayout(self.csvWidget)
        self.addressCsvLineEdit, self.addressCsvButton = self.createFileInput(f"{self.base_path}/")
        csvLayout.addLayout(self.createFileInputLayout(self.addressCsvLineEdit, self.addressCsvButton))
        layout.addWidget(self.csvWidget)

        # Widget für Gebäude aus geoJSON
        self.geoJSONWidget = QWidget(self)
        geoJSONLayout = QVBoxLayout(self.geoJSONWidget)
        self.geoJSONLineEdit, self.geoJSONButton = self.createFileInput(f"{self.base_path}/")
        geoJSONLayout.addLayout(self.createFileInputLayout(self.geoJSONLineEdit, self.geoJSONButton))
        layout.addWidget(self.geoJSONWidget)

        # Abfrage-Button
        self.queryButton = QPushButton("Abfrage starten", self)
        self.queryButton.clicked.connect(self.startQuery)
        layout.addWidget(self.queryButton)

        # OK und Abbrechen Buttons
        self.okButton = QPushButton("OK", self)
        self.okButton.clicked.connect(self.accept)
        layout.addWidget(self.okButton)
        self.cancelButton = QPushButton("Abbrechen", self)
        self.cancelButton.clicked.connect(self.reject)
        layout.addWidget(self.cancelButton)

        # Verbinden Sie das Dropdown mit der Anzeige der entsprechenden Filteroptionen
        self.filterComboBox.currentIndexChanged.connect(self.showSelectedFilter)

        # Zu Beginn nur Standardmethode anzeigen
        self.showSelectedFilter()

    def createFileInput(self, default_path):
        lineEdit = QLineEdit(default_path)
        button = QPushButton("Durchsuchen")
        button.clicked.connect(lambda: self.selectFile(lineEdit))
        return lineEdit, button

    def selectFile(self, lineEdit):
        filename, _ = QFileDialog.getOpenFileName(self, "Datei auswählen", "", "All Files (*)")
        if filename:
            lineEdit.setText(filename)

    def createFileInputLayout(self, lineEdit, button):
        layout = QHBoxLayout()
        layout.addWidget(lineEdit)
        layout.addWidget(button)
        return layout

    def showSelectedFilter(self):
        selected_filter = self.filterComboBox.currentText()
        self.coordWidget.setVisible(selected_filter == "Filtern mit Koordinatenbereich")
        self.coordRadiusWidget.setVisible(selected_filter == "Filtern mit zentralen Koordinaten und Radius als Abstand")
        self.csvWidget.setVisible(selected_filter == "Filtern mit Adressen aus CSV")
        self.geoJSONWidget.setVisible(selected_filter == "Filtern mit Polygon-geoJSON")

    def haversine(self, lat1, lon1, lat2, lon2):
        # Radius der Erde in Metern
        earth_radius = 6371000.0

        # Umrechnung von Grad in Radian
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])

        # Deltas der Koordinaten
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Haversine-Formel
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = earth_radius * c

        return distance

    def startQuery(self):
        city_name = self.cityLineEdit.text()
        filename = self.filenameLineEdit.text()
        selected_filter = self.filterComboBox.currentText()

        if not city_name or not filename:
            QMessageBox.warning(self, "Warnung", "Bitte geben Sie Stadtname und Ausgabedatei an.")
            return

        # Führen Sie hier Ihre Abfrage-Logik durch
        tags = {"building": "yes"}  # oder andere Tags
        query = build_query(city_name, tags, element_type="building")
        geojson_data = download_data(query, element_type="building")
        gdf = self.prepare_gdf(geojson_data)

        if selected_filter == "Filtern mit Koordinatenbereich":
            self.filter_with_bbox(gdf, filename)
        elif selected_filter == "Filtern mit zentralen Koordinaten und Radius als Abstand":
            self.filter_with_central_coords_and_radius(gdf, filename)
        elif selected_filter == "Filtern mit Adressen aus CSV":
            self.filter_with_csv_addresses(gdf, filename)
        elif selected_filter == "Filtern mit Polygon-geoJSON":
            self.filter_with_polygon(gdf, filename)
        else:
            gdf.to_file(filename, driver='GeoJSON')

        QMessageBox.information(self, "Erfolg", f"Abfrageergebnisse gespeichert in {filename}")
        # Rufen Sie die loadNetData-Methode des Haupt-Tabs auf
        self.parent().loadNetData(filename)

    def prepare_gdf(self, geojson_data):
        gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
        gdf.crs = "EPSG:4326"
        return gdf.to_crs(epsg=25833)

    def filter_with_bbox(self, gdf, filename):
        min_lat = float(self.minLatLineEdit.text())
        min_lon = float(self.minLonLineEdit.text())
        max_lat = float(self.maxLatLineEdit.text())
        max_lon = float(self.maxLonLineEdit.text())

        # Erstelle ein Bounding Box Polygon im WGS84 Koordinatensystem
        bbox_polygon_wgs84 = box(min_lon, min_lat, max_lon, max_lat)

        # Projektionstransformation vorbereiten von WGS84 (EPSG:4326) zu Zielkoordinatensystem des gdf
        project_to_target_crs = pyproj.Transformer.from_proj(
            pyproj.Proj(init='epsg:4326'),  # Quellkoordinatensystem (WGS84)
            pyproj.Proj(init='epsg:25833'),  # Zielkoordinatensystem des gdf
            always_xy=True
        )

        # Transformiere das Bounding Box Polygon ins Zielkoordinatensystem des gdf
        bbox_polygon_transformed = transform(project_to_target_crs.transform, bbox_polygon_wgs84)

        # Filtere die GeoDataFrame basierend auf dem transformierten Bounding Box Polygon
        gdf_filtered = gdf[gdf.intersects(bbox_polygon_transformed)]

        # Speichern der gefilterten GeoDataFrame
        gdf_filtered.to_file(filename, driver='GeoJSON')

    def filter_with_central_coords_and_radius(self, gdf, filename):
        center_lat = float(self.centerLatLineEdit.text())
        center_lon = float(self.centerLonLineEdit.text())
        radius = float(self.radiusLineEdit.text())  # Radius in Kilometern für geopy.distance

        center_point_wgs84 = Point(center_lon, center_lat)
        project = pyproj.Transformer.from_proj(
            pyproj.Proj(init='epsg:4326'),  # Quellkoordinatensystem (WGS84)
            pyproj.Proj(init='epsg:25833')  # Zielkoordinatensystem (hier beispielhaft EPSG:25833)
        )

        center_point_transformed = transform(project.transform, center_point_wgs84)
        gdf['distance'] = gdf.geometry.distance(center_point_transformed)
        radius_m = radius
        gdf_filtered = gdf[gdf['distance'] <= radius_m]
        gdf_filtered.to_file(filename, driver='GeoJSON')

    def filter_with_csv_addresses(self, gdf, filename):
        address_csv_file = self.addressCsvLineEdit.text()
        if address_csv_file:
            csv_df = pd.read_csv(address_csv_file, sep=';')
            addresses_from_csv = csv_df['Adresse'].tolist()
            gdf['full_address'] = gdf['addr:street'] + ' ' + gdf['addr:housenumber']
            gdf_filtered = gdf[gdf['full_address'].isin(addresses_from_csv)]
            gdf_filtered.to_file(filename, driver='GeoJSON')

    def filter_with_polygon(self, gdf, filename):
        geoJSON_file = self.geoJSONLineEdit.text()
        if geoJSON_file:
            # Polygon aus der geoJSON-Datei laden
            polygon_gdf = gpd.read_file(geoJSON_file)
            
            # Annahme: Das Polygon ist das erste Element im GeoDataFrame
            # Falls das Polygon-GeoJSON mehrere Polygone enthält, könnte hier eine Anpassung notwendig sein
            polygon = polygon_gdf.geometry.iloc[0]
            
            # Filtern der Gebäude, die innerhalb des Polygons liegen
            # Verwendung der 'within'-Methode, um zu überprüfen, ob ein Punkt/Gebäude innerhalb des Polygons liegt
            filtered_gdf = gdf[gdf.geometry.within(polygon)]

            filtered_gdf.to_file(filename, driver='GeoJSON')


class SpatialAnalysisDialog(QDialog):
    def __init__(self, base_path, parent=None):
        super().__init__(parent)
        self.base_path = base_path
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        self.setWindowTitle("Räumliche Analyse")

        # Gebäude-geojson
        self.geojsonWidget = QWidget(self)
        geojsonLayout = QVBoxLayout(self.geojsonWidget)
        self.geojsonLineEdit, self.geojsonButton = self.createFileInput(f"{self.base_path}/Raumanalyse/output_buildings.geojson")
        geojsonLayout.addLayout(self.createFileInputLayout(self.geojsonLineEdit, self.geojsonButton))
        layout.addWidget(self.geojsonWidget)

        # Quartier-geojson
        self.geojsonareaWidget = QWidget(self)
        geojsonareaLayout = QVBoxLayout(self.geojsonareaWidget)
        self.geojsonareaLineEdit, self.geojsonareaButton = self.createFileInput(f"{self.base_path}/Raumanalyse/quartiere.geojson")
        geojsonareaLayout.addLayout(self.createFileInputLayout(self.geojsonareaLineEdit, self.geojsonareaButton))
        layout.addWidget(self.geojsonareaWidget)

        # Wärmenetzgebiet-Gebäude-geojson
        self.geojsonfilteredbuildingsWidget = QWidget(self)
        geojsonfilteredbuildingsLayout = QVBoxLayout(self.geojsonfilteredbuildingsWidget)
        self.geojsonfilteredbuildingsLineEdit, self.geojsonfilteredbuildingsButton = self.createFileInput(f"{self.base_path}/Raumanalyse/waermenetz_buildings.geojson")
        geojsonfilteredbuildingsLayout.addLayout(self.createFileInputLayout(self.geojsonfilteredbuildingsLineEdit, self.geojsonfilteredbuildingsButton))
        layout.addWidget(self.geojsonfilteredbuildingsWidget)

        # Abfrage-Button
        self.queryButton = QPushButton("Berechnung Starten", self)
        self.queryButton.clicked.connect(self.calculate)
        layout.addWidget(self.queryButton)

        # OK und Abbrechen Buttons
        self.okButton = QPushButton("OK", self)
        self.okButton.clicked.connect(self.accept)
        layout.addWidget(self.okButton)
        self.cancelButton = QPushButton("Abbrechen", self)
        self.cancelButton.clicked.connect(self.reject)
        layout.addWidget(self.cancelButton)


    def createFileInput(self, default_path):
        lineEdit = QLineEdit(default_path)
        button = QPushButton("Durchsuchen")
        button.clicked.connect(lambda: self.selectFile(lineEdit))
        return lineEdit, button

    def selectFile(self, lineEdit):
        filename, _ = QFileDialog.getOpenFileName(self, "Datei auswählen", "", "All Files (*)")
        if filename:
            lineEdit.setText(filename)

    def createFileInputLayout(self, lineEdit, button):
        layout = QHBoxLayout()
        layout.addWidget(lineEdit)
        layout.addWidget(button)
        return layout

    def calculate_building_data(self, gdf, output_filename):
        # Berechnen der Fläche jedes Gebäudes in Quadratmetern
        gdf['area_sqm'] = gdf['geometry'].area
        # Hinzufügen der Spalte für spezifischen Wärmebedarf mit Zufallszahlen zwischen 50 und 200
        gdf['spez. Wärmebedarf [kWh/m²*a]'] = np.random.uniform(50, 200, gdf.shape[0])
        # Hinzufügen der Spalte für die Anzahl der Geschosse (konstanter Wert 3)
        gdf['Anzahl Geschosse'] = 3
        # Berechnen des Jahreswärmebedarfs
        gdf['Jahreswärmebedarf [kWh/a]'] = gdf['spez. Wärmebedarf [kWh/m²*a]'] * gdf['Anzahl Geschosse'] * gdf['area_sqm']
        # Speichern des erweiterten GeoDataFrame in eine neue GeoJSON-Datei
        gdf.to_file(output_filename, driver='GeoJSON')

        return gdf

    def calculate(self):
        geojson_file_buildings = self.geojsonLineEdit.text()
        geojson_file_areas = self.geojsonareaLineEdit.text()
        geojson_file_filtered_buildings = self.geojsonfilteredbuildingsLineEdit.text()
        gdf = gpd.read_file(geojson_file_buildings, driver='GeoJSON').to_crs(epsg=25833)
        ignore_types = ['ruins', 'greenhouse', 'shed', 'silo', 'slurry_tank', 
                    'toilets', 'hut', 'cabin', 'ger', 'static_caravan', 
                    'construction', 'cowshed', 'garage', 'garages', 'carport',
                    'farm_auxiliary', 'roof', 'digester']

        # Filtere Gebäude heraus, die ignorierten Typen entsprechen
        gdf = gdf[~gdf['building'].isin(ignore_types)]

        gdf = self.calculate_building_data(gdf, geojson_file_buildings)
        
        quartiere = clustering_quartiere_hdbscan(gdf)
        quartiere = postprocessing_hdbscan(quartiere)
        quartiere = allocate_overlapping_area(quartiere)
        quartiere.to_file(geojson_file_areas, driver='GeoJSON')

        # Filtern und speichern Sie Gebäude in Clustern mit der Versorgungsart "Wärmenetzversorgung"
        waermenetz_buildings = gdf[gdf['quartier_label'].isin(quartiere[quartiere['Versorgungsgebiet'] == 'Wärmenetzversorgung'].index)]

        # Lassen Sie nur die benötigte Geometriespalte (z.B. 'geometry') in waermenetz_buildings
        waermenetz_buildings = waermenetz_buildings[['geometry']]

        # Speichern Sie die gefilterten Gebäude in eine separate GeoJSON-Datei
        waermenetz_buildings.to_file(geojson_file_filtered_buildings, driver='GeoJSON')

        # Rufen Sie die loadNetData-Methode des Haupt-Tabs auf
        self.parent().loadNetData(geojson_file_filtered_buildings)
        self.parent().loadNetData(geojson_file_areas)

class GeocodeAddressesDialog(QDialog):
    def __init__(self, base_path, parent=None):
        super().__init__(parent)
        self.base_path = base_path
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Adressdaten geocodieren")
        self.setGeometry(300, 300, 600, 200)  # Anpassung der Fenstergröße
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Abstand zwischen den Widgets
        layout.setContentsMargins(10, 10, 10, 10)  # Rand des Layouts

        font = QFont()
        font.setPointSize(10)  # Größere Schrift für bessere Lesbarkeit
        
        # Eingabefeld für die Eingabedatei
        self.inputfilenameLineEdit, inputFileButton = self.createFileInput(f"{self.base_path}/Gebäudedaten/data_input.csv", font)
        layout.addLayout(self.createFileInputLayout("Eingabedatei:", self.inputfilenameLineEdit, inputFileButton, font))
        
        # Eingabefeld für die Ausgabedatei
        self.outputfilenameLineEdit, outputFileButton = self.createFileInput(f"{self.base_path}/Gebäudedaten/data_output_ETRS89.csv", font)
        layout.addLayout(self.createFileInputLayout("Ausgabedatei:", self.outputfilenameLineEdit, outputFileButton, font))
        
        # Buttons für OK und Abbrechen in einem horizontalen Layout
        buttonLayout = QHBoxLayout()
        self.okButton = QPushButton("OK", self)
        self.okButton.setFont(font)
        self.okButton.clicked.connect(self.onAccept)
        self.cancelButton = QPushButton("Abbrechen", self)
        self.cancelButton.setFont(font)
        self.cancelButton.clicked.connect(self.reject)
        buttonLayout.addWidget(self.okButton)
        buttonLayout.addWidget(self.cancelButton)
        layout.addLayout(buttonLayout)

        # Verbesserte Fortschrittsanzeige
        self.progressBar = QProgressBar(self)
        self.progressBar.setFont(font)
        layout.addWidget(self.progressBar)

    def createFileInput(self, default_path, font):
        lineEdit = QLineEdit(default_path)
        lineEdit.setFont(font)
        button = QPushButton("Durchsuchen")
        button.setFont(font)
        button.clicked.connect(lambda: self.selectFile(lineEdit))
        return lineEdit, button

    def createFileInputLayout(self, label_text, lineEdit, button, font):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFont(font)
        layout.addWidget(label)
        layout.addWidget(lineEdit)
        layout.addWidget(button)
        return layout

    def selectFile(self, lineEdit):
        filename, _ = QFileDialog.getOpenFileName(self, "Datei auswählen", "", "All Files (*)")
        if filename:
            lineEdit.setText(filename)

    def onAccept(self):
        # Daten sammeln
        self.inputfilename = self.inputfilenameLineEdit.text()
        self.outputfilename = self.outputfilenameLineEdit.text()
        
        # Abfrage erstellen und Daten herunterladen
        self.geocodeAdresses(self.inputfilename, self.outputfilename)

    # Die Methode des Dialogs, die die anderen Funktionen aufruft
    def geocodeAdresses(self, inputfilename, outputfilename):
        # Stellen Sie sicher, dass der vorherige Thread beendet wird
        if hasattr(self, 'geocodingThread') and self.geocodingThread.isRunning():
            self.geocodingThread.terminate()
            self.geocodingThread.wait()
        self.geocodingThread = GeocodingThread(inputfilename, outputfilename)
        self.geocodingThread.calculation_done.connect(self.on_generation_done)
        self.geocodingThread.calculation_error.connect(self.on_generation_error)
        self.geocodingThread.start()
        self.progressBar.setRange(0, 0)  # Aktiviert den indeterministischen Modus

    def on_generation_done(self, results):
        self.accept()

    def on_generation_error(self, error_message):
        QMessageBox.critical(self, "Fehler beim Geocoding", str(error_message))
        self.progressBar.setRange(0, 1)  # Deaktiviert den indeterministischen Modus