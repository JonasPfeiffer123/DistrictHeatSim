from qgis.core import (QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsProject, QgsRasterLayer, QgsVectorLayer,
                       QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsVectorFileWriter)
from net_generation_qgis_functions import *
import os

def load_layers(osm_street_layer_geojson_file, data_csv_file_name, x_coord, y_coord):
    """
    Laden der erforderlichen Layer in das QGIS-Projekt.
    """
    try:
        import_osm_layer()
        import_osm_street_layer(osm_street_layer_geojson_file)
        # Bestimmen des Pfades des aktuellen Skripts
        current_script_path = os.path.dirname(os.path.abspath(__file__))

        # Aufbau des relativen Pfades zur CSV-Datei
        text_file_path = os.path.join(current_script_path, "..", "geocoding", data_csv_file_name)
        create_data_layer(text_file_path, data_csv_file_name)

        # Koordinaten für den Punkt
        create_point_layer(x_coord, y_coord)

        # Weitere Layer-Initialisierung
        layer_points = QgsProject.instance().mapLayersByName(data_csv_file_name)[0]
        layer_lines = QgsProject.instance().mapLayersByName('Straßen')[0]
        layer_WEA = QgsProject.instance().mapLayersByName('Erzeugerstandorte')[0]
        return layer_points, layer_lines, layer_WEA
    except Exception as e:
        print(f"Fehler beim Laden der Layer: {e}")

def generate_and_export_layers(layer_points, layer_lines, layer_WEA, fixed_angle=0, fixed_distance=1):
    """
    Generieren von Netzwerklayers und deren Export als GeoJSON.
    """
    try:
        # Erzeugen der Layers
        crs = layer_points.crs().toWkt()
        vl_hast, provider_hast = create_layer("HAST", "Linestring", crs)
        vl_rl, provider_rl = create_layer("Rücklauf", "Linestring", crs)
        vl_vl, provider_vl = create_layer("Vorlauf", "Linestring", crs)
        vl_erzeugeranlagen, provider_erzeugeranlagen = create_layer("Erzeugeranlagen", "Linestring", crs)

        # Generieren von Netzwerken
        generate_lines(layer_points, fixed_distance, fixed_angle, provider_hast)
        generate_lines(layer_WEA, fixed_distance, fixed_angle, provider_erzeugeranlagen)
        generate_network_fl(layer_points, layer_WEA, provider_vl, layer_lines)
        generate_network_rl(layer_points, layer_WEA, fixed_distance, fixed_angle, provider_rl, layer_lines)

        # Commit und Export der Änderungen
        commit_and_export_layers([vl_hast, vl_rl, vl_vl, vl_erzeugeranlagen])
    except Exception as e:
        print(f"Fehler beim Generieren und Exportieren der Layers: {e}")

def commit_and_export_layers(layers):
    """
    Speichern von Änderungen und Exportieren von Layers als GeoJSON.
    """
    output_files = ["HAST.geojson", "Rücklauf.geojson", "Vorlauf.geojson", "Erzeugeranlagen.geojson"]
    colors = ["green", "blue", "red", "black"]

    for vl, color, output_file in zip(layers, colors, output_files):
        vl.commitChanges()
        vl.updateExtents()
        vl.triggerRepaint()

        error = QgsVectorFileWriter.writeAsVectorFormat(vl, output_file, "utf-8", vl.crs(), "GeoJSON")
        if error[0] == QgsVectorFileWriter.NoError:
            print(f"Schreiben des Layers {vl.name()} als GeoJSON war erfolgreich!")
            load_and_style_layer(output_file, vl.name(), color)
        else:
            print(f"Fehler beim Schreiben des Layers {vl.name()}: ", error[1])

def load_and_style_layer(file_path, layer_name, color):
    """
    Laden und Stylen eines Layers.
    """
    v_layer = QgsVectorLayer(file_path, layer_name, "ogr")
    symbol = QgsLineSymbol.createSimple({'line_color': color, 'line_width': '0.75'})
    renderer = QgsSingleSymbolRenderer(symbol)
    v_layer.setRenderer(renderer)

    if not v_layer.isValid():
        print(f"Layer {layer_name} konnte nicht geladen werden!")
    else:
        QgsProject.instance().addMapLayer(v_layer)
        print(f"Layer {layer_name} wurde erfolgreich geladen!")


# Hier setzen Sie Ihre Overpass-Abfrage ein
#overpass_query = """
#[out:json][timeout:25];
#area[name="Görlitz"]->.area_0;
#(
#  node["highway"="primary"]["highway"="secondary"]["highway"="tertiary"]["highway"="residential"]["highway"="road"]["highway"="living_street"](area.area_0);
#  way["highway"="primary"]["highway"="secondary"]["highway"="tertiary"]["highway"="residential"]["highway"="road"]["highway"="living_street"](area.area_0);
#  relation["highway"="primary"]["highway"="secondary"]["highway"="tertiary"]["highway"="residential"]["highway"="road"]["highway"="living_street"](area.area_0);
#);
#(._;>;);
#out body;
#"""

# Ausgabedateiname für GeoJSON-Datei
osm_street_layer_geojson_file = "C:/Users/jp66tyda/heating_network_generation/net_generation_QGIS/Beispiel Projekt/Straßen.geojson"

# Download der Daten und Speichern als GeoJSON
#download_osm_street_data(overpass_query, osm_street_layer_geojson_file)

# data points csv file path
#data_csv_file_name = "data_output_ETRS89.csv"
data_csv_file_name = "data_output_gr_ETRS89.csv"

# Koordinaten für den Erzeugerstandort
#x_coord = 486267.306999999971595  # Longitude
#y_coord = 5637294.910000000149012  # Latitude
x_coord = 499827.91  # Longitude
y_coord = 5666288.22  # Latitude

layer_points, layer_lines, layer_WEA = load_layers(osm_street_layer_geojson_file, data_csv_file_name, x_coord, y_coord)
generate_and_export_layers(layer_points, layer_lines, layer_WEA)
