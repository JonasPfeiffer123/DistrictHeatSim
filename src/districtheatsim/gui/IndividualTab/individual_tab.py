"""
Filename: individual_tab.py
Author: Dipl.-Ing. (FH) Jonas Pfeiffer
Date: 2024-09-04
Description: Contains the IndividualTab for managing building data and calculating heat generation technologies.
"""

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFileDialog, QPushButton, QComboBox, QLineEdit, QMessageBox,
                             QFormLayout, QScrollArea, QHBoxLayout, QTabWidget, QMenuBar, QMenu, QListWidget,
                             QAbstractItemView, QDialog, QListWidgetItem, QTableWidgetItem, QTableWidget, QHeaderView)
from PyQt5.QtCore import pyqtSignal, Qt
import json
from gui.utilities import CheckableComboBox  # Assuming you have this implemented
from gui.MixDesignTab.heat_generator_dialogs import TechInputDialog  # Import your dialogs
from heat_generators.heat_generator_classes import *
from gui.IndividualTab.building_thread import CalculateBuildingMixThread
from utilities.test_reference_year import import_TRY

class IndividualTab(QWidget):
    """
    Main tab that manages the menu bar and three sub-tabs: DiagramTab, TechnologyTab, and ResultsTab.
    """

    def __init__(self, folder_manager, data_manager, parent=None):
        super().__init__(parent)
        self.folder_manager = folder_manager
        self.data_manager = data_manager
        self.parent = parent
        self.base_path = None

        self.folder_manager.project_folder_changed.connect(self.update_default_path)
        self.update_default_path(self.folder_manager.project_folder)

        self.initUI()

    def update_default_path(self, new_base_path):
        self.base_path = new_base_path

    def initUI(self):
        main_layout = QVBoxLayout(self)

        # Create a menu bar
        menubar = QMenuBar(self)
        menubar.setFixedHeight(30)  # Set a fixed height for the menu bar
        file_menu = QMenu('File', self)
        menubar.addMenu(file_menu)

        load_action = file_menu.addAction('Load JSON Data')
        load_action.triggered.connect(self.load_json_file)

        # Create tab widget to hold the individual tabs
        self.tab_widget = QTabWidget(self)

        # Create the sub-tabs
        self.diagram_tab = DiagramTab(self)
        self.technology_tab = TechnologyTab(self)
        self.results_tab = ResultsTab(self)

        # Add the tabs to the tab widget
        self.tab_widget.addTab(self.diagram_tab, "Diagram + Data")
        self.tab_widget.addTab(self.technology_tab, "Technology Selection")
        self.tab_widget.addTab(self.results_tab, "Results")

        # Add the menu bar and tab widget to the layout
        main_layout.setMenuBar(menubar)
        main_layout.addWidget(self.tab_widget)

        self.setLayout(main_layout)

    def load_json_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select JSON File', f"{self.base_path}/Lastgang", 'JSON Files (*.json);;All Files (*)')
        if file_path:
            self.diagram_tab.load_json(file_path)  # Load JSON data into the diagram tab


class DiagramTab(QWidget):
    """
    Handles the data selection and diagram plotting functionality.
    """

    data_loaded = pyqtSignal(dict)  # Signal to notify when data is loaded

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.results = {}
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        # Initialize the plot area
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.canvas)
        layout.addWidget(self.toolbar)

        # Initialize the comboboxes for data selection
        self.data_type_combobox = CheckableComboBox(self)
        self.data_type_combobox.addItem("Heat Demand")
        self.data_type_combobox.addItem("Heating Demand")
        self.data_type_combobox.addItem("Warmwater Demand")
        self.data_type_combobox.addItem("Supply Temperature")
        self.data_type_combobox.addItem("Return Temperature")

        self.building_combobox = CheckableComboBox(self)

        layout.addWidget(QLabel("Select Data Types"))
        layout.addWidget(self.data_type_combobox)
        layout.addWidget(QLabel("Select Buildings"))
        layout.addWidget(self.building_combobox)

        # Connect combobox changes to replotting
        self.data_type_combobox.view().pressed.connect(self.on_combobox_selection_changed)
        self.building_combobox.view().pressed.connect(self.on_combobox_selection_changed)

        self.setLayout(layout)

    def load_json(self, file_path):
        """
        Loads the data from a JSON file and populates the view.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.results = json.load(f)
            self.populate_building_combobox(self.results)
            self.plot(self.results)  # Initial plot with first selection
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading JSON file: {e}")

    def populate_building_combobox(self, results):
        """
        Populates the building combobox with the results data and selects the first building.

        Args:
            results (dict): The results data to populate the combobox with.
        """
        self.building_combobox.clear()
        for key in results.keys():
            self.building_combobox.addItem(f'Building {key}')
            item = self.building_combobox.model().item(self.building_combobox.count() - 1, 0)
            item.setCheckState(Qt.Checked)

        # Automatically select the first building and replot
        if self.building_combobox.count() > 0:
            first_item = self.building_combobox.model().item(0)
            first_item.setCheckState(Qt.Checked)

        # Automatically select the first data type
        if self.data_type_combobox.count() > 0:
            first_data_item = self.data_type_combobox.model().item(0)
            first_data_item.setCheckState(Qt.Checked)

        # Generate configuration UI for each building
        self.parent.technology_tab.populate_generator_configuration(self.results)

    def on_combobox_selection_changed(self):
        """
        Replots the data when the combobox selection changes.
        """
        self.plot(self.results)

    def plot(self, results=None):
        """
        Plots the selected data types for the selected buildings, adjusting the figure size for the legend outside.
        
        Args:
            results (dict, optional): The results data to plot. Defaults to None.
        """
        if results is None:
            return

        self.figure.clear()
        ax1 = self.figure.add_subplot(111)
        ax2 = ax1.twinx()

        selected_data_types = self.data_type_combobox.checkedItems()
        selected_buildings = self.building_combobox.checkedItems()

        for building in selected_buildings:
            key = building.split()[-1]
            value = results[key]

            if "Heat Demand" in selected_data_types:
                ax1.plot(value["wärme"], label=f'Building {key} Heat Demand')
            if "Heating Demand" in selected_data_types:
                ax1.plot(value["heizwärme"], label=f'Building {key} Heating Demand', linestyle='--')
            if "Warmwater Demand" in selected_data_types:
                ax1.plot(value["warmwasserwärme"], label=f'Building {key} Warmwater Demand', linestyle=':')
            if "Supply Temperature" in selected_data_types:
                ax2.plot(value["vorlauftemperatur"], label=f'Building {key} Supply Temp', linestyle='-.')
            if "Return Temperature" in selected_data_types:
                ax2.plot(value["rücklauftemperatur"], label=f'Building {key} Return Temp', linestyle='-.')

        ax1.set_xlabel('Time (hours)')
        ax1.set_ylabel('Heat Demand (W)')
        ax2.set_ylabel('Temperature (°C)')

        # Legend for ax1 on the left
        ax1.legend(loc='center right', bbox_to_anchor=(-0.2, 0.5))  # Left of the plot
        # Legend for ax2 on the right
        ax2.legend(loc='center left', bbox_to_anchor=(1.2, 0.5))  # Right of the plot

        # Adjust layout to ensure the legends do not overlap the plot
        self.figure.subplots_adjust(left=0.25, right=0.75, top=0.9, bottom=0.1)

        ax1.grid()

        self.canvas.draw()


class TechnologyTab(QWidget):
    """
    A QWidget subclass for configuring heat generation technologies for individual buildings.
    This version includes a CustomListWidget for each building to manage the selected technologies.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.generator_configs = {}  # Store configurations for each building
        self.tech_objects = {}  # Store technology objects per building
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        # Scroll area for generator configuration per building
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        container_widget = QWidget()
        scroll_area.setWidget(container_widget)

        self.form_layout = QFormLayout(container_widget)
        layout.addWidget(QLabel("Configure Heat Generators for Selected Buildings"))
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def populate_generator_configuration(self, buildings):
        """
        Populates the form layout with generator configurations for each selected building.
        Adds a configuration button and a CustomListWidget for managing technologies per building.
        """
        # Clear the previous layout
        for i in reversed(range(self.form_layout.count())):
            widget = self.form_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        for building_id in buildings:
            row_layout = QHBoxLayout()

            # Dropdown for selecting technologies
            generator_combobox = QComboBox(self)
            generator_combobox.addItem("Gaskessel")
            generator_combobox.addItem("Biomassekessel")
            generator_combobox.addItem("BHKW")
            generator_combobox.addItem("Holzgas-BHKW")
            generator_combobox.addItem("Geothermie")
            generator_combobox.addItem("Abwärme")
            generator_combobox.addItem("Flusswasser")
            generator_combobox.addItem("AqvaHeat")
            generator_combobox.addItem("Solarthermie")
            generator_combobox.setFixedWidth(150)

            # Add button to add the selected technology to the list
            add_button = QPushButton(f"Add {building_id}", self)
            add_button.setFixedWidth(120)
            add_button.clicked.connect(lambda _, b_id=building_id, g_cbox=generator_combobox: self.add_technology(b_id, g_cbox))

            # Remove button to remove selected technology
            remove_button = QPushButton(f"Remove {building_id}", self)
            remove_button.setFixedWidth(120)
            remove_button.clicked.connect(lambda _, b_id=building_id: self.remove_selected_technology(b_id))

            # Create a CustomListWidget for each building to manage the technologies
            self.tech_list_widget = CustomListWidget(self, building_id=building_id)
            self.tech_list_widget.itemDoubleClicked.connect(self.edit_technology)

            # Store configurations in dictionary for each building
            self.generator_configs[building_id] = {
                "generator_combobox": generator_combobox,
                "tech_list_widget": self.tech_list_widget  # Store the list widget for later updates
            }

            # Initialize the tech_objects for this building
            self.tech_objects[building_id] = []  # Empty list for each building's tech objects

            row_layout.addWidget(QLabel(f"Building {building_id} Generator:"))
            row_layout.addWidget(generator_combobox)
            row_layout.addWidget(add_button)
            row_layout.addWidget(remove_button)
            row_layout.addWidget(self.tech_list_widget)  # Add the technology list widget to the row

            self.form_layout.addRow(row_layout)

    def updateTechObjectsOrder(self, building_id):
        """
        Updates the order of technology objects based on the list display for a specific building.
        """
        tech_list_widget = self.generator_configs[building_id]["tech_list_widget"]
        new_order = []

        # Loop through the items in the list widget for the specific building
        for index in range(tech_list_widget.count()):
            item_text = tech_list_widget.item(index).text()
            for tech in self.tech_objects[building_id]:  # Only check the tech objects for the specific building
                if self.formatTechForDisplay(tech) == item_text:
                    new_order.append(tech)
                    break

        # Update the order of tech objects for the specific building
        self.tech_objects[building_id] = new_order

    def add_technology(self, building_id, generator_combobox):
        """
        Adds a selected technology from the combobox to the CustomListWidget for a specific building.
        """
        generator_type = generator_combobox.currentText()
        tech_data = self.generator_configs.get(building_id, {})

        # Open the appropriate dialog based on the generator type
        dialog = TechInputDialog(generator_type, tech_data)
        if dialog.exec_():
            # Retrieve the inputs after the dialog is accepted
            tech_inputs = dialog.getInputs()

            # Create and store the new tech object
            new_tech = self.createTechnology(generator_type, tech_inputs)
            self.tech_objects[building_id].append(new_tech)

            # Add the configuration to the CustomListWidget for the building
            tech_list_widget = self.generator_configs[building_id]["tech_list_widget"]
            list_item = QListWidgetItem(self.formatTechForDisplay(new_tech))
            
            # Store the tech object in the list item
            list_item.setData(Qt.UserRole, new_tech)
            
            tech_list_widget.addItem(list_item)

            QMessageBox.information(self, "Generator Configured", f"Configuration for {generator_type} saved for Building {building_id}.")


    def remove_selected_technology(self, building_id):
        """
        Removes the selected technology from the CustomListWidget for a specific building.
        """
        tech_list_widget = self.generator_configs[building_id]["tech_list_widget"]
        selected_row = tech_list_widget.currentRow()
        if selected_row != -1:
            # Remove from the list widget
            tech_list_widget.takeItem(selected_row)

            # Also remove from the tech_objects for the building
            del self.tech_objects[building_id][selected_row]

    def edit_technology(self, item):
        """
        Opens a dialog to edit the selected technology from the CustomListWidget.
        """
        # Retrieve the associated technology object directly
        tech_object = item.data(Qt.UserRole)

        if tech_object:
            # Create a mapping between the class names and expected strings
            tech_type_mapping = {
                "GasBoiler": "Gaskessel",
                "BiomassBoiler": "Biomassekessel",
                "CHP": "BHKW",  # Mapping from class name to expected string
                "SolarThermal": "Solarthermie",
                "Geothermal": "Geothermie",
                "WasteHeatPump": "Abwärme",
                "RiverHeatPump": "Flusswasser",
                "AqvaHeat": "AqvaHeat"
            }

            # Get the class name of the technology object and map it to the expected string
            tech_class_name = tech_object.__class__.__name__
            tech_type = tech_type_mapping.get(tech_class_name, tech_class_name)

            # Open the dialog with the correct technology type and its current data
            dialog = TechInputDialog(tech_type, tech_object.__dict__)
            if dialog.exec_():
                updated_inputs = dialog.getInputs()

                # Update the technology object with the modified data
                for key, value in updated_inputs.items():
                    setattr(tech_object, key, value)

                # Update the displayed text in the list item
                item.setText(self.formatTechForDisplay(tech_object))


    def createTechnology(self, tech_type, inputs):
        """
        Creates a technology object based on the type and inputs.
        Ensures that the technology has a unique name by including the building ID and technology type.
        
        Args:
            tech_type (str): The type of technology.
            inputs (dict): The inputs for the technology.

        Returns:
            Technology: The created technology object.
        """
        tech_classes = {
            "Solarthermie": SolarThermal,
            "BHKW": CHP,
            "Holzgas-BHKW": CHP,
            "Geothermie": Geothermal,
            "Abwärme": WasteHeatPump,
            "Flusswasser": RiverHeatPump,
            "Biomassekessel": BiomassBoiler,
            "Gaskessel": GasBoiler,
            "AqvaHeat": AqvaHeat
        }

        base_tech_type = tech_type.split('_')[0]  # Ensure we are working with the base type
        tech_class = tech_classes.get(base_tech_type)
        
        if not tech_class:
            raise ValueError(f"Unknown technology type: {tech_type}")

        # Generate a unique name for the technology, including its type and a count for uniqueness
        tech_count = len(self.tech_objects)  # Total number of tech objects across buildings
        unique_name = f"{base_tech_type}_{tech_count + 1}"

        # Ensure the inputs contain a 'name' field
        inputs['name'] = unique_name

        # Return the created technology object
        return tech_class(**inputs)

    
    def formatTechForDisplay(self, tech):
        """
        Formats a technology object for display in the list.

        Args:
            tech (Technology): The technology object.

        Returns:
            str: The formatted string for display.
        """
        display_text = f"{tech.name}: "
        if isinstance(tech, RiverHeatPump):
            display_text += f"Wärmeleistung FW WP: {tech.Wärmeleistung_FW_WP} kW, Temperatur FW WP: {tech.Temperatur_FW_WP} °C, dT: {tech.dT} K, spez. Investitionskosten Flusswärme: {tech.spez_Investitionskosten_Flusswasser} €/kW, spez. Investitionskosten Wärmepumpe: {tech.spezifische_Investitionskosten_WP} €/kW"
        elif isinstance(tech, WasteHeatPump):
            display_text += f"Kühlleistung Abwärme: {tech.Kühlleistung_Abwärme} kW, Temperatur Abwärme: {tech.Temperatur_Abwärme} °C, spez. Investitionskosten Abwärme: {tech.spez_Investitionskosten_Abwärme} €/kW, spez. Investitionskosten Wärmepumpe: {tech.spezifische_Investitionskosten_WP} €/kW"
        elif isinstance(tech, Geothermal):
            display_text += f"Fläche Sondenfeld: {tech.Fläche} m², Bohrtiefe: {tech.Bohrtiefe} m, Quelltemperatur Erdreich: {tech.Temperatur_Geothermie} °C, spez. Bohrkosten: {tech.spez_Bohrkosten} €/m, spez. Entzugsleistung: {tech.spez_Entzugsleistung} W/m, Vollbenutzungsstunden: {tech.Vollbenutzungsstunden} h, Abstand Sonden: {tech.Abstand_Sonden} m, spez. Investitionskosten Wärmepumpe: {tech.spezifische_Investitionskosten_WP} €/kW"
        elif isinstance(tech, CHP):
            display_text += f"th. Leistung: {tech.th_Leistung_BHKW} kW, spez. Investitionskosten Erdgas-BHKW: {tech.spez_Investitionskosten_GBHKW} €/kW, spez. Investitionskosten Holzgas-BHKW: {tech.spez_Investitionskosten_HBHKW} €/kW"
        elif isinstance(tech, BiomassBoiler):
            display_text += f"th. Leistung: {tech.P_BMK}, Größe Holzlager: {tech.Größe_Holzlager} t, spez. Investitionskosten Kessel: {tech.spez_Investitionskosten} €/kW, spez. Investitionskosten Holzlager: {tech.spez_Investitionskosten_Holzlager} €/t"
        elif isinstance(tech, GasBoiler):
            display_text += f"spez. Investitionskosten: {tech.spez_Investitionskosten} €/kW"
        elif isinstance(tech, SolarThermal):
            display_text += f"Bruttokollektorfläche: {tech.bruttofläche_STA} m², Volumen Solarspeicher: {tech.vs} m³, Kollektortyp: {tech.Typ}, spez. Kosten Speicher: {tech.kosten_speicher_spez} €/m³, spez. Kosten Flachkollektor: {tech.kosten_fk_spez} €/m², spez. Kosten Röhrenkollektor: {tech.kosten_vrk_spez} €/m²"
        elif isinstance(tech, AqvaHeat):
            display_text += "technische Daten"
        else:
            display_text = f"Unbekannte Technologieklasse: {type(tech).__name__}"

        return display_text


class ResultsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.building_costs = {}  # Store costs per building
        self.results = {}  # Store the results for each building
        self.total_cost = 0
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        # Button to trigger the calculation
        self.calc_button = QPushButton("Start Generator Calculation", self)
        self.calc_button.clicked.connect(self.start_calculation_for_all_buildings)
        layout.addWidget(self.calc_button)

        # Table to display the calculation results
        self.resultsTable = QTableWidget()
        self.resultsTable.setColumnCount(4)
        self.resultsTable.setHorizontalHeaderLabels(['Name', 'Anlagendimensionen', 'Kosten', 'Gesamtkosten'])
        layout.addWidget(self.resultsTable)

        # Label to show the total cost across all buildings
        self.totalCostLabel = QLabel()
        layout.addWidget(self.totalCostLabel)

        self.setLayout(layout)

    def start_calculation_for_all_buildings(self):
        """
        Starts the calculation for all buildings.
        """
        self.building_costs = {}
        self.total_cost = 0

        # Iterate over each building in the technology tab
        for building_id, config in self.parent.technology_tab.generator_configs.items():
            tech_objects = self.parent.technology_tab.tech_objects[building_id]

            # Extract building-specific data from the loaded JSON (from DiagramTab)
            if building_id in self.parent.diagram_tab.results:
                building_data = self.parent.diagram_tab.results[building_id]

                # Run the calculation thread with the building-specific data
                self.run_building_calculation_thread(building_id, building_data, tech_objects)

    def run_building_calculation_thread(self, building_id, building_data, tech_objects):
        """
        Runs the calculation thread for a specific building.
        """
        self.calculationThread = CalculateBuildingMixThread(
            building_id=building_id,
            building_data=building_data,
            tech_objects=tech_objects,
            TRY_data=import_TRY(self.parent.data_manager.get_try_filename()),
            COP_data=np.genfromtxt(self.parent.data_manager.get_cop_filename(), delimiter=';'),
            gas_price=self.parent.parent.mixDesignTab.gaspreis,
            electricity_price=self.parent.parent.mixDesignTab.strompreis,
            wood_price=self.parent.parent.mixDesignTab.holzpreis,
            BEW=self.parent.parent.mixDesignTab.BEW,
            interest_on_capital=self.parent.parent.mixDesignTab.kapitalzins,
            price_increase_rate=self.parent.parent.mixDesignTab.preissteigerungsrate,
            period=self.parent.parent.mixDesignTab.betrachtungszeitraum,
            wage=self.parent.parent.mixDesignTab.stundensatz
        )

        self.calculationThread.calculation_done.connect(self.on_building_calculation_done)
        self.calculationThread.calculation_error.connect(self.on_calculation_error)
        self.calculationThread.start()

    def on_building_calculation_done(self, result):
        """
        Handles the completion of the calculation for a building.
        """
        building_id = result["building_id"]
        self.results[building_id] = result  # Store the result for this building
        self.calculate_building_costs(building_id)
        self.update_results_table()

    def calculate_building_costs(self, building_id):
        """
        Calculates the costs for the technologies in a specific building after the calculation.
        """
        tech_objects = self.parent.technology_tab.tech_objects[building_id]
        building_total_cost = 0

        for tech_object in tech_objects:
            cost = self.calculate_tech_cost(tech_object)
            building_total_cost += cost

        self.building_costs[building_id] = building_total_cost
        self.total_cost += building_total_cost

    def calculate_tech_cost(self, tech_object):
        """
        Calculates the cost of a given technology object.
        """
        try:
            # Calculate the cost for each tech object based on its type
            if isinstance(tech_object, GasBoiler):
                print(tech_object.P_max, tech_object.spez_Investitionskosten)
                cost = tech_object.P_max * tech_object.spez_Investitionskosten
            elif isinstance(tech_object, BiomassBoiler):
                print(tech_object.P_BMK, tech_object.spez_Investitionskosten, tech_object.Größe_Holzlager, tech_object.spez_Investitionskosten_Holzlager)
                cost = tech_object.P_BMK * tech_object.spez_Investitionskosten + \
                    tech_object.Größe_Holzlager * tech_object.spez_Investitionskosten_Holzlager
            elif isinstance(tech_object, CHP):
                print(tech_object.th_Leistung_BHKW, tech_object.spez_Investitionskosten_GBHKW)
                cost = tech_object.th_Leistung_BHKW * tech_object.spez_Investitionskosten_GBHKW
            elif isinstance(tech_object, SolarThermal):
                print(tech_object.bruttofläche_STA, tech_object.kosten_fk_spez, tech_object.vs, tech_object.kosten_speicher_spez)
                cost = tech_object.bruttofläche_STA * tech_object.kosten_fk_spez + \
                    tech_object.vs * tech_object.kosten_speicher_spez
            elif isinstance(tech_object, Geothermal):
                print(tech_object.Fläche, tech_object.spez_Bohrkosten, tech_object.max_Wärmeleistung, tech_object.spezifische_Investitionskosten_WP)    
                cost = tech_object.Fläche * tech_object.spez_Bohrkosten + \
                    tech_object.max_Wärmeleistung * tech_object.spezifische_Investitionskosten_WP
            elif isinstance(tech_object, WasteHeatPump):
                print(tech_object.Kühlleistung_Abwärme, tech_object.spez_Investitionskosten_Abwärme, tech_object.max_Wärmeleistung, tech_object.spezifische_Investitionskosten_WP)  
                cost = tech_object.Kühlleistung_Abwärme * tech_object.spez_Investitionskosten_Abwärme + \
                    tech_object.max_Wärmeleistung * tech_object.spezifische_Investitionskosten_WP
            elif isinstance(tech_object, RiverHeatPump):
                print(tech_object.Wärmeleistung_FW_WP, tech_object.spez_Investitionskosten_Flusswasser, tech_object.spezifische_Investitionskosten_WP)
                cost = tech_object.Wärmeleistung_FW_WP * tech_object.spez_Investitionskosten_Flusswasser + \
                    tech_object.Wärmeleistung_FW_WP * tech_object.spezifische_Investitionskosten_WP
            else:
                cost = 0  # Fallback for unknown technology types
            return cost
        except Exception as e:
            print(f"Error calculating cost for technology: {e}")
            return 0


    def update_results_table(self):
        """
        Updates the table with the calculated costs for each building and technology.
        """
        self.resultsTable.setRowCount(0)  # Clear the table

        for building_id, total_cost in self.building_costs.items():
            tech_objects = self.parent.technology_tab.tech_objects[building_id]
            building_total = 0

            for tech in tech_objects:
                row_position = self.resultsTable.rowCount()
                self.resultsTable.insertRow(row_position)

                # Set technology details
                self.resultsTable.setItem(row_position, 0, QTableWidgetItem(tech.__class__.__name__))
                dimensions, cost, total = self.extract_tech_data(tech)
                self.resultsTable.setItem(row_position, 1, QTableWidgetItem(dimensions))
                self.resultsTable.setItem(row_position, 2, QTableWidgetItem(f"{cost:.2f} €"))
                self.resultsTable.setItem(row_position, 3, QTableWidgetItem(f"{total:.2f} €"))

                building_total += total

            # Insert subtotal for the building
            row_position = self.resultsTable.rowCount()
            self.resultsTable.insertRow(row_position)
            self.resultsTable.setItem(row_position, 0, QTableWidgetItem(f"Building {building_id} subtotal"))
            self.resultsTable.setItem(row_position, 3, QTableWidgetItem(f"{building_total:.2f} €"))

        # Update the total cost label
        self.update_total_cost_label()
    
    def extract_tech_data(self, tech):
        """
        Extracts the data for a given technology object.

        Args:
            tech (object): The technology object being extracted.

        Returns:
            tuple: Dimensions, cost, and total cost for the technology.
        """
        try:
            if isinstance(tech, GasBoiler):
                dimensions = f"th. Leistung: {tech.P_max:.2f} kW"
                cost = tech.P_max * tech.spez_Investitionskosten
                total = cost  # No additional costs for GasBoiler
            elif isinstance(tech, BiomassBoiler):
                dimensions = f"th. Leistung: {tech.P_BMK:.2f} kW, Holzlager: {tech.Größe_Holzlager:.2f} m³"
                cost = tech.P_BMK * tech.spez_Investitionskosten
                total = cost + (tech.Größe_Holzlager * tech.spez_Investitionskosten_Holzlager)
            elif isinstance(tech, CHP):
                dimensions = f"th. Leistung: {tech.th_Leistung_BHKW:.2f} kW, el. Leistung: {tech.el_Leistung_Soll:.2f} kW"
                cost = tech.spez_Investitionskosten_GBHKW * tech.th_Leistung_BHKW
                total = cost  # No additional costs for CHP
            elif isinstance(tech, SolarThermal):
                dimensions = f"Kollektorfläche: {tech.bruttofläche_STA:.2f} m², Speichervolumen: {tech.vs:.2f} m³"
                cost = tech.bruttofläche_STA * tech.kosten_fk_spez
                total = cost + (tech.vs * tech.kosten_speicher_spez)
            elif isinstance(tech, Geothermal):
                dimensions = f"Bohrfläche: {tech.Fläche:.2f} m², Bohrtiefe: {tech.Bohrtiefe:.2f} m"
                cost = tech.Fläche * tech.spez_Bohrkosten
                total = cost + (tech.max_Wärmeleistung * tech.spezifische_Investitionskosten_WP)
            elif isinstance(tech, WasteHeatPump):
                dimensions = f"Kühlleistung Abwärme: {tech.Kühlleistung_Abwärme:.2f} kW, th. Leistung: {tech.max_Wärmeleistung:.2f} kW"
                cost = tech.Kühlleistung_Abwärme * tech.spez_Investitionskosten_Abwärme
                total = cost + (tech.max_Wärmeleistung * tech.spezifische_Investitionskosten_WP)
            elif isinstance(tech, RiverHeatPump):
                dimensions = f"th. Leistung: {tech.Wärmeleistung_FW_WP:.2f} kW"
                cost = tech.Wärmeleistung_FW_WP * tech.spez_Investitionskosten_Flusswasser
                total = cost + (tech.Wärmeleistung_FW_WP * tech.spezifische_Investitionskosten_WP)
            else:
                dimensions = "N/A"
                cost = 0
                total = 0
        except Exception as e:
            print(f"Error extracting tech data: {e}")
            dimensions = "N/A"
            cost = 0
            total = 0

        return dimensions, cost, total

    def update_total_cost_label(self):
        """
        Updates the label that shows the total cost across all buildings.
        """
        self.totalCostLabel.setText(f"Total Cost: {self.total_cost:.2f} €")

    def on_calculation_error(self, error_message):
        """
        Handles calculation errors.
        """
        QMessageBox.critical(self, "Berechnungsfehler", str(error_message))

class CustomListWidget(QListWidget):
    """
    A custom QListWidget to manage technology objects for a building.
    This widget supports drag-and-drop reordering of items.
    """
    def __init__(self, parent=None, building_id=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.parent_tab = parent
        self.building_id = building_id  # Store building_id to identify which building is being updated

    def dropEvent(self, event):
        """
        Updates the order of technology objects in the parent after drag and drop.
        """
        super().dropEvent(event)
        if self.parent_tab:
            self.parent_tab.updateTechObjectsOrder(self.building_id)
