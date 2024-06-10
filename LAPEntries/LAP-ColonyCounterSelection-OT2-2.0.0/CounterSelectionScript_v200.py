# LAP-ColonyCounterSelection-OT2-2.0.0

# This Python script is designed for an Opentrons OT-2 robot to perform a counter-selection
# protocol. The protocol reads an Excel file that needs to be in the folder /data/user_storage of the robot
# to identify samples that meet specific criteria: a value higher than a defined threshold in one map of values
# and lower in another for the same source plate (both provided by an user in the excel file) and then
# transfer them to the final plate(s).

# Workflow of the script (in a nutshell):
# 1. Input Handling: Read and process the Excel template to retrieve user-defined settings.
# 2. Selection of samples: Selects samples locations based on user-defined thresholds and maps.
# 3. Resource Calculation: Determine the number and placement of plates, reagents, tubes, and tip racks.
# 4. (Optional) Transfer of the media to the final plate(s)
# 5. Transfer of the samples to the final plate(s)
# 6. Export of an excel file that contain the final maps of the selected samples

# For more info go to:
#  Github page with code: https://github.com/BiocomputationLab/LAPrepository/tree/ad79d8da16e1be319361ef6fc372113f4e281741/LAPEntries/LAP-ColonyCounterSelection-OT2-2.0.0
#  Protocols.io page with further usage instructions: https://www.protocols.io/view/ot-2-counter-selection-5qpvor5xdv4o
#  LAP repository entry: https://www.laprepo.com/protocol/2-criteria-counter-selection-v-2-0-0

## Packages needed for the running of the protocol
import opentrons
import pandas as pd
import random
import math
import numpy as np
from opentrons.motion_planning.deck_conflict import DeckConflictError
from opentrons.protocol_api.labware import OutOfTipsError

class UserVariables:
	"""
	Class that will contain the parameters setted in the variables csv and will process them to work easily in the rest of the protocol
	The coding of this function is dependant of the variables in the Template of the protocol and the names have to be consistent with the rest of the code
	"""

	def __init__(self, general, each_plate, pipettes):
		"""
		This function will take the pandas dataframe that will be the table of the excel variable files
		"""
		self.numberSourcePlates = general[general["Variable Names"] == "Number of Source Plates"]["Value"].values[0]
		self.nameReactives = general[general["Variable Names"] == "Name Reactives"]["Value"].values[0]
		self.volumesReactivePerPlate = general[general["Variable Names"] == "Volume per Reactive (uL)"]["Value"].values[0]
		self.finalMapName = general[general["Variable Names"] == "Name Final File Maps"]["Value"].values[0]

		if type(self.nameReactives) == str:
			self.nameReactives = self.nameReactives.replace(" ","").split(",")
			if type(self.volumesReactivePerPlate) == str:
				self.volumesReactivePerPlate = self.volumesReactivePerPlate.replace(" ","").split(",")
			else:
				self.volumesReactivePerPlate = [self.volumesReactivePerPlate]
		else:
			self.nameReactives = None
			self.volumesReactivePerPlate = None
			
		self.APINameSamplePlate = general[general["Variable Names"] == "API Name Source Plate"]["Value"].values[0]
		self.APINameFalconPlate = general[general["Variable Names"] == "API Name Rack Falcon Reactives"]["Value"].values[0]
		self.APINameFinalPlate = general[general["Variable Names"] == "API Name Final Plate"]["Value"].values[0]
		self.dimensionsFalcon = {"rows":None, "columns":None, "volume":None} # It will get filled after the check and it will be needed for the future
		
		self.APINamePipR = pipettes[pipettes["Variable Names"] == "API Name Right Pipette"]["Value"].values[0]
		self.APINamePipL = pipettes[pipettes["Variable Names"] == "API Name Left Pipette"]["Value"].values[0]
		self.startingTipPipR = pipettes[pipettes["Variable Names"] == "Initial Tip Right Pipette"]["Value"].values[0]
		self.startingTipPipL = pipettes[pipettes["Variable Names"] == "Initial Tip Left Pipette"]["Value"].values[0]
		self.APINameTipR = pipettes[pipettes["Variable Names"] == "API Name Tiprack Right Pipette"]["Value"].values[0]
		self.APINameTipL = pipettes[pipettes["Variable Names"] == "API Name Tiprack Left Pipette"]["Value"].values[0]
		self.replaceTiprack = pipettes[pipettes["Variable Names"] == "Replace Tipracks"]["Value"].values[0]
		self.volMaxTipR = 0 # Initialized
		self.volMaxTipL = 0 # Initialized
		
		self.threshold = list(each_plate[each_plate["Variable Names"] == "Threshold Selection Value"].values[0][1:])
		self.reactivesPerPlate = list(each_plate[each_plate["Variable Names"] == "Reactives Per Plate"].values[0][1:])
		self.nameSheetLowerThreshold = list(each_plate[each_plate["Variable Names"] == "Name Sheet Selection Value<Threshold"].values[0][1:])
		self.nameSheetHigherThreshold = list(each_plate[each_plate["Variable Names"] == "Name Sheet Selection Value>Threshold"].values[0][1:])
		self.wellStartFinalPlate = list(each_plate[each_plate["Variable Names"] == "Well Start Final Plate"].values[0][1:])
		
		self.nameFinalSheet = list(each_plate[each_plate["Variable Names"] == "Final Map Name"].values[0][1:])
		self.volumesSamplesPerPlate = list(each_plate[each_plate["Variable Names"] == "Volume Transfer Sample (uL)"].values[0][1:])
		
		self.nameSourcePlates = list(each_plate.columns)
		self.nameSourcePlates.remove("Variable Names")
		
		return
		
	def check(self):
		"""
		Function that will check the variables of the Template and will raise errors that will crash the OT run
		
		It is a validation function of the variables checking errors or inconsistencies
		
		This function is dependant again with the variabels that we have, some checks are interchangable between protocols, but some of them are specific of the variables
		"""
		
		labware_context = opentrons.protocol_api.labware
		
		# Check that the minimal values need to be there, the ones that never can be empty
		if any(pd.isna(element) for element in [self.APINameSamplePlate, self.APINameFinalPlate, self.numberSourcePlates, self.finalMapName]):
			raise Exception("The variables 'API Name Source Plate', 'API Name Final Plate', 'Number of Source Plates' and 'Name Final File Maps' from Sheet 'GeneralVariables' cannot be left empty")
		
		if pd.isna(self.replaceTiprack):
			raise Exception("The variables 'Replace Tipracks' from Sheet 'PipetteVariables' cannot be left empty")
		
		if self.nameReactives != None and pd.isna(self.APINameFalconPlate):
			raise Exception("If the variable 'Name Reactives' has a value, 'API Name Rack Falcon Reactives' must have one too")
			
		if self.replaceTiprack in [1, True, "True", "true", "TRUE"]:
			self.replaceTiprack = True
		elif self.replaceTiprack in [0, False, "False", "false", "FALSE"]:
			self.replaceTiprack = False
		else:
			raise Exception("Replace Tiprack variable value needs to be True or False")
		
		# Check that there is at least one pipette attached
		if pd.isna(self.APINamePipR) and pd.isna(self.APINamePipL):
			raise Exception ("We need at least 1 pipette to perform the protocol")
		
		# Check if for the established pipettes we have their tip rack and first tip also established
		if not pd.isna(self.APINamePipR): # There is a right pipette established
			if pd.isna(self.APINameTipR):
				raise Exception("If 'API Name Right Pipette' has a value defined, 'API Name Tiprack Right Pipette' should as well")
			if pd.isna(self.startingTipPipR):
				raise Exception("If 'API Name Right Pipette' has a value defined, 'Initial Tip Right Pipette' should as well")
		else:
			self.startingTipPipR = None
			self.APINameTipR = None
		
		if not pd.isna(self.APINamePipL): # There is a left pipette attached
			if pd.isna(self.APINameTipL):
				raise Exception("If 'API Name Left Pipette' has a value defined, 'API Name Tiprack Left Pipette' should as well")
			if pd.isna(self.startingTipPipL):
				raise Exception("If 'API Name Left Pipette' has a value defined, 'Initial Tip Left Pipette' should as well")
		else:
			self.startingTipPipL = None
			self.APINameTipL = None
		
		# Check that if the tipracks are the same, the initial tips should be the same as well
		if not pd.isna(self.APINamePipL) and not pd.isna(self.APINamePipR): # Both pipettes are established
			if self.APINameTipL == self.APINameTipR:
				if self.startingTipPipL != self.startingTipPipR:
					raise Exception("If the tipracks of the right and left mount pipettes are the same, the initial tip should be as well.")
		
		# Start to define the different establish labwares so we check that they are in the opentrons app
		# Source plate where the samples are going to be placed
		try:
			definition_source_plate = labware_context.get_labware_definition(self.APINameSamplePlate)
		except OSError: # This would be catching the FileNotFoundError that happens when a labware is not found
			raise Exception("One or more of the introduced labwares or tipracks are not in the labware directory of the opentrons. Check for any typo of the api labware name.")
		
		# Finla plate where the samples with the meida (optional) are going to be transferred to
		try:
			definition_final_plate = labware_context.get_labware_definition(self.APINameFinalPlate)
		except OSError:
			raise Exception(f"The final plate labware {self.APINameFinalPlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

		if self.nameReactives != None:
			try:
				definition_rack = labware_context.get_labware_definition(self.APINameFalconPlate)
			except OSError:
				raise Exception(f"The falcon tube rack labware {self.APINameFalconPlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

			# Check the falcon tube rack is only composed by only 1 type of falcons, 15 or 50mL
			if len(definition_rack["groups"]) > 1:
				raise Exception("The falcon rack needs to have only 1 type of tube admitted, either with 15mL or 50mL falcons. Tube racks such as 'Opentrons 10 Tube Rack with Falcon 4x50 mL, 6x15 mL Conical' are not valid")
			
			# Check that the volume is either 500000 and 150000
			volume_rack = list(definition_rack["wells"].values())[0]["totalLiquidVolume"]
			if volume_rack not in [15000, 50000]:
				raise Exception("The falcon rack needs to have only 15mL or 50mL falcon, this protocol does not accept more types of falcons")
			
			# Establish the values of dimensionsFalcon that are going to be used in other parts of the script
			self.dimensionsFalcon["rows"] = len(definition_rack["ordering"][0])
			self.dimensionsFalcon["columns"] = len(definition_rack["ordering"])
			self.dimensionsFalcon["volume"] = volume_rack


		if pd.isna(self.APINamePipR) == False:
			try:
				definition_tiprack_right = labware_context.get_labware_definition(self.APINameTipR)
			except OSError:
				raise Exception(f"The right tip rack {self.APINameTipR} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
			
			# Establish the max volume of the tips
			self.volMaxTipR = list(definition_tiprack_right["wells"].values())[0]["totalLiquidVolume"]
		
		if pd.isna(self.APINamePipL) == False:
			try:
				definition_tiprack_left = labware_context.get_labware_definition(self.APINameTipL)
			except OSError:
				raise Exception(f"The left tip rack {self.APINameTipL} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
			
			# Establish the max volume of the tips
			self.volMaxTipL = list(definition_tiprack_left["wells"].values())[0]["totalLiquidVolume"]

		# Check that the number of source plates is at least 1
		if self.numberSourcePlates < 1:
			raise Exception("The variable 'Number of Source Plates' needs to be equal or greater than 1")

		# Check if there is some value of the plates where it shouldnt in the per plate sheet
		if len(self.threshold) < (self.numberSourcePlates) or len(self.nameSheetLowerThreshold) < (self.numberSourcePlates) or len(self.nameSheetHigherThreshold) < (self.numberSourcePlates) or len(self.reactivesPerPlate) < (self.numberSourcePlates) or len(self.wellStartFinalPlate) < (self.numberSourcePlates) or len(self.nameFinalSheet) < (self.numberSourcePlates) or len(self.volumesSamplesPerPlate) < (self.numberSourcePlates):
			raise Exception("We need to have at least the same number of plate columns on the Sheet 'PerPlateVariables' as in 'Number of Source Plates'")
		
		if any(pd.isna(elem) == True for elem in self.threshold[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.threshold[self.numberSourcePlates:]):
			raise Exception("The cell values of 'Threshold Selection Value' need to be as many as the 'Number of Source Plates' and be in consecutive columns")
		if any(pd.isna(elem) == True for elem in self.nameSheetLowerThreshold[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.nameSheetLowerThreshold[self.numberSourcePlates:]):
			raise Exception("The cell values of 'Name Sheet Selection Value<Threshold' need to be as many as the 'Number of Source Plates' and be in consecutive columns")
		if any(pd.isna(elem) == True for elem in self.nameSheetHigherThreshold[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.nameSheetHigherThreshold[self.numberSourcePlates:]):
			raise Exception("The cell values of 'Name Sheet Selection Value>Threshold' need to be as many as the 'Number of Source Plates' and be in consecutive columns")
		if any(pd.isna(elem) == False for elem in self.reactivesPerPlate[self.numberSourcePlates:]):
			raise Exception("The cell values of 'Reactives Per Plate' cannot be more than the 'Number of Source Plates'")
		if any(pd.isna(elem) == True for elem in self.wellStartFinalPlate[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.wellStartFinalPlate[self.numberSourcePlates:]):
			raise Exception("The cell values of 'Well Start Final Plate' need to be as many as the 'Number of Source Plates' and be in consecutive columns")
		if any(pd.isna(elem) == True for elem in self.finalMapName[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.nameFinalSheet[self.numberSourcePlates:]):
			raise Exception("The cell values of 'Final Map Name' need to be as many as the 'Number of Source Plates' and be in consecutive columns")
		if any(pd.isna(elem) == True for elem in self.volumesSamplesPerPlate[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.volumesSamplesPerPlate[self.numberSourcePlates:]):
			raise Exception("The cell values of 'Volume Transfer Sample (uL)' need to be as many as the 'Number of Source Plates' and be in consecutive columns")
		
		# Check that the volume that transfer of samples is not 0
		if any(elem <= 0 for elem in self.volumesSamplesPerPlate[:self.numberSourcePlates]):
			raise Exception("The cell values of 'Volume Transfer Sample (uL)' need to be greater than 0")
		
		# Check if some value of the media is 0
		if self.volumesReactivePerPlate != None and any(float(elem) <= 0 for elem in self.volumesReactivePerPlate):
			raise Exception("The value for each media needs to be greater than 0")
		
		# Check if the sheet names for the selection values exist and if they fit the labware source description
		for sheet_name_lowerThreshold in self.nameSheetLowerThreshold[:self.numberSourcePlates]:
			try:
				# values_lower = pd.read_excel("VariablesCounterSelection.xlsx", sheet_name = sheet_name_lowerThreshold, engine = "openpyxl", header = None)
				values_lower = pd.read_excel("/data/user_storage/VariablesCounterSelection.xlsx", sheet_name = sheet_name_lowerThreshold, engine = "openpyxl", header = None)
			except ValueError: # Error that appears when the sheet 'sheet_name_lowerThreshold' does not exist in the excel file
				raise Exception(f"The Sheet Name {sheet_name_lowerThreshold} does not exist in excel file")
			
			if values_lower.shape[0] != len(definition_source_plate["ordering"][0]) or values_lower.shape[1] != len(definition_source_plate["ordering"]):
				raise Exception(f"Selecting Sheet Values should have the dimension of the source labware (in this case {len(definition_source_plate['ordering'][0])} rows and {len(definition_source_plate['ordering'])} columns).\nDo not include the names of the rows or the columns in the sheet, only values.")
			
			# Check if there is an empty cell or something that is not a float or int
			if values_lower.isnull().values.any():
				raise Exception(f"The Sheet {sheet_name_lowerThreshold} has an empty cell")
			if not pd.api.types.is_numeric_dtype(values_lower.to_numpy()):
				raise Exception(f"The Sheet {sheet_name_lowerThreshold} has a value that is not a number")
			
		for sheet_name_higherThreshold in self.nameSheetHigherThreshold[:self.numberSourcePlates]:
			try:
				# values_higher = pd.read_excel("VariablesCounterSelection.xlsx", sheet_name = sheet_name_higherThreshold, engine = "openpyxl", header = None)
				values_higher = pd.read_excel("/data/user_storage/VariablesCounterSelection.xlsx", sheet_name = sheet_name_higherThreshold, engine = "openpyxl", header = None)
			except ValueError: # Error that appears when the sheet 'sheet_name_higherThreshold' does not exist in the excel file
				raise Exception(f"The Sheet Name {sheet_name_higherThreshold} does not exist in excel file")
			
			if values_higher.shape[0] != len(definition_source_plate["ordering"][0]) or values_higher.shape[1] != len(definition_source_plate["ordering"]):
				raise Exception(f"Selecting Sheet Values should have the dimension of the source labware ({len(definition_source_plate['ordering'][0])} rows and {len(definition_source_plate['ordering'])} columns).\nDo not include the names of the rows or the columns in the sheet, only values.")
			
			# Check if there is an empty cell or something that is not a float or int
			if values_higher.isnull().values.any():
				raise Exception(f"The Sheet {sheet_name_higherThreshold} has an empty cell")
			if not pd.api.types.is_numeric_dtype(values_higher.to_numpy()):
				raise Exception(f"The Sheet {sheet_name_higherThreshold} has a value that is not a number")
			
		# Check if there is any typo in the starting tip of both pipettes
		if pd.isna(self.APINamePipR) == False and (self.startingTipPipR not in definition_tiprack_right["groups"][0]["wells"]):
			raise Exception("Starting tip of right pipette is not valid, check for typos")
		if pd.isna(self.APINamePipL) == False and (self.startingTipPipL not in definition_tiprack_left["groups"][0]["wells"]):
			raise Exception("Starting tip of left pipette is not valid, check for typos")		
		
		# Check if the well of the starting plate exist in the final labware
		for index_labware in range(self.numberSourcePlates):
			if pd.isna(self.reactivesPerPlate[index_labware]):
				vol_sample_needed = self.volumesSamplesPerPlate[index_labware] # We only need the volume of the sample for the plate without anything
			else:
				vol_sample_needed = len(self.reactivesPerPlate[index_labware].split(","))*self.volumesSamplesPerPlate[index_labware]
			if float(list(definition_source_plate["wells"].values())[0]['totalLiquidVolume']) < vol_sample_needed:
				raise Exception(f"Volume of Sample needed in {self.nameSourcePlates[index_labware]} is greater than the max volume of the wells in that labware")

		# We are going to check if the number of indexes in antibiotics per plate is the same as number of Name antibiotics
		reactives_per_plate_without_nan = [element for element in self.reactivesPerPlate[:self.numberSourcePlates] if not pd.isna(element)]
		all_plates_media = ",".join(reactives_per_plate_without_nan).replace(" ","").split(",")
		all_plates_media = list(dict.fromkeys(all_plates_media))
		if type(self.nameReactives) in [str, list]:
			# We are going to check that there as many 'Volume per Reactive' as 'Name Reactives'
			if len(self.volumesReactivePerPlate) != len(self.nameReactives) or pd.isna(self.volumesReactivePerPlate[0]):
				raise Exception("We need as many volumes in 'Volume per Reactive (uL)' as reactives in 'Name Reactives'")
			
			if len(reactives_per_plate_without_nan) == 0:
				raise Exception("There are reactives set in the variable 'Name Reactives' but no plate is going to be incubated with reactives")
			
			if all(antibiotic in self.nameReactives for antibiotic in all_plates_media) == False:
				raise Exception(f"Following reactive(s) are not defined in variable 'Name Reactives': {set(all_plates_media)-set(self.nameReactives)}")
			if all(antibiotic in all_plates_media for antibiotic in self.nameReactives) == False:
				raise Exception(f"Following reactive(s) are not being used: {set(self.nameReactives)-set(all_plates_media)}. Remove it from the variable file and re-run the script")
	
class SettedParameters:
	"""
	After the checking the UserVariable class we can assign what we will be using to track the plates
	and working with the variables setted in that class
	"""
	def __init__(self, deck_positions):
		self.numberReactives = 0
		self.pipR = None
		self.pipL = None
		self.sameTiprack = None
		self.samplePlates = {}
		self.finalPlates = {}
		self.reactiveWells = {}
		self.deckPositions = {key: None for key in range(1,deck_positions)}
		self.colors_mediums = ["#ffbb51"] # Initial filled with the one color of the sample
		self.liquid_samples = None # Initial
		self.maxVolumePipR = None
		self.maxVolumePipL = None
		return
	
	def assign_variables(self, user_variables, protocol):
		# Define the liquid that is always going to be needed
		self.liquid_samples = protocol.define_liquid(
			name = "Sample",
			description = "Sample that will be inoculated with the selected medium",
			display_color = "#ffbb51"
		)
		
		if type(user_variables.nameReactives) != list:
			self.numberReactives = 0
		else:
			self.numberReactives = len(user_variables.nameReactives)
		
		# Define the pipettes and some related variables variables
		if pd.isna(user_variables.APINamePipR) == False:
			self.pipR = protocol.load_instrument(user_variables.APINamePipR, mount = "right")
			if self.pipR.channels != 1:
				raise Exception("Both Right Mount Pipette and Left Mount pipette have to be single channel")
			# Set the max volume of the right pipette
			if self.pipR.max_volume <= user_variables.volMaxTipR:
				self.maxVolumePipR = self.pipR.max_volume
			else:
				self.maxVolumePipR = user_variables.volMaxTipR
			
		if pd.isna(user_variables.APINamePipL) == False:
			self.pipL = protocol.load_instrument(user_variables.APINamePipL, mount = "left")
			if self.pipL.channels != 1:
				raise Exception("Both Right Mount Pipette and Left Mount pipette have to be single channel")
			# Set the max volume of the left pipette
			if self.pipL.max_volume <= user_variables.volMaxTipL:
				self.maxVolumePipL = self.pipL.max_volume
			else:
				self.maxVolumePipL = user_variables.volMaxTipL

		if user_variables.APINamePipR == user_variables.APINamePipL:
			self.sameTiprack = True
		else:
			self.sameTiprack = False

		# We are going to define the entry (initial) to every reactive that is needed
		if self.numberReactives > 0:
			for index_reactive, reactive in enumerate(user_variables.nameReactives):
				self.reactiveWells[reactive] = {"Positions":[], "Volumes":None, "Reactions Per Tube":None, "Number Total Reactions":0, "Definition Liquid": None, "Volume Per Sample":float(user_variables.volumesReactivePerPlate[index_reactive])}
				
				# Give the colour
				while True:
					color_liquid = f"#{random.randint(0, 0xFFFFFF):06x}"
					if color_liquid.lower() != "#ffbb51" and color_liquid.lower() not in self.colors_mediums:
						self.reactiveWells[reactive]["Definition Liquid"] = protocol.define_liquid(
							name = f"{reactive}",
							description = f"Medium {reactive}",
							display_color = color_liquid
						)
						self.colors_mediums.append(color_liquid)
						break

		# Define the initial entries of the source plate(s) so we can store the data related to it to future handling
		incubation_plates_needed = 0
		for index_plate in range(user_variables.numberSourcePlates):
			self.samplePlates[index_plate] = {"Position":None,
									 		  "Name Plate":user_variables.nameSourcePlates[index_plate],
											  "Label":f"Source Plate '{user_variables.nameSourcePlates[index_plate]}'",
											  "Mediums":None,
											  "Opentrons Place":None,
											  "Values for Selection (Lower than Threshold)":pd.read_excel("/data/user_storage/VariablesCounterSelection.xlsx", sheet_name = user_variables.nameSheetLowerThreshold[index_plate], engine = "openpyxl", header = None),
											  "Values for Selection (Greater than Threshold)":pd.read_excel("/data/user_storage/VariablesCounterSelection.xlsx", sheet_name = user_variables.nameSheetHigherThreshold[index_plate], engine = "openpyxl", header = None),
											#   "Values for Selection (Lower than Threshold)":pd.read_excel("VariablesCounterSelection.xlsx", sheet_name = user_variables.nameSheetLowerThreshold[index_plate], engine = "openpyxl", header = None),
											#   "Values for Selection (Greater than Threshold)":pd.read_excel("VariablesCounterSelection.xlsx", sheet_name = user_variables.nameSheetHigherThreshold[index_plate], engine = "openpyxl", header = None),
											  "Threshold Value":user_variables.threshold[index_plate],
											  "Map Selected Colonies":None, # We will create this map when we establish the final plates
											  "Name Final Map":user_variables.nameFinalSheet[index_plate],
											  "Selected Colonies": [],
											  "Volume Transfer Sample":float(user_variables.volumesSamplesPerPlate[index_plate])}
			if self.numberReactives > 0 and pd.isna(user_variables.reactivesPerPlate[index_plate]) == False:
				self.samplePlates[index_plate]["Mediums"] = user_variables.reactivesPerPlate[index_plate].replace(" ","").split(",")	

			# We are goign to define the final plates associated with this source plate and define if they are going to have media or not
			if self.samplePlates[index_plate]["Mediums"] == None:
				self.finalPlates[incubation_plates_needed] = {"Source Plate":index_plate,
														   "Position":None,
														   "Label":f"Selected Samples from '{user_variables.nameSourcePlates[index_plate]}' with only Selected Colonies",
														   "Medium":None,
														   "Number Samples":None, # We will have to select and see how many
														   "Opentrons Place":None,
														   "Index Well Start":opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFinalPlate)["groups"][0]["wells"].index(user_variables.wellStartFinalPlate[index_plate])}
				incubation_plates_needed += 1
			else:
				for reactive_source_plate in self.samplePlates[index_plate]["Mediums"]:
					# Initialize with the values that we can set now
					self.finalPlates[incubation_plates_needed] = {"Source Plate":index_plate,
															   "Position":None,
															   "Label":f"Selected Samples from '{user_variables.nameSourcePlates[index_plate]}' with {reactive_source_plate}",
															   "Medium":reactive_source_plate,
															   "Number Samples":None, # We will have to select and see how many
															   "Opentrons Place":None,
															   "Index Well Start":opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFinalPlate)["groups"][0]["wells"].index(user_variables.wellStartFinalPlate[index_plate])}
					incubation_plates_needed += 1
		return

class MapLabware:
	"""
	Class that will store the map of each of the source plates to final export
	"""
	def __init__(self, labware):

		self.name_rows = list(labware.rows_by_name().keys())
		self.name_columns = list(labware.columns_by_name().keys())
		number_rows = len(self.name_rows)
		number_columns = len(self.name_columns)
		
		self.map = pd.DataFrame(np.full((number_rows,number_columns),None),columns=self.name_columns,index=self.name_rows)
		self.map.index.name = "Row/Column"

	def assign_value(self, value, row, column):
		self.map.loc[row, column] = value
		
class NotSuitablePipette(Exception):
	"""
	Custom Error raised when there is no pipette that can transfer the volume
	"""
	def __init__(self, value):
		message = f"Not a suitable pipette to aspirate/dispense {value}uL"
		super().__init__(message)
	pass

# Functions definitions
# ----------------------------------
# ----------------------------------

def setting_labware (number_labware, labware_name, positions, protocol, module = False, label = None):
	"""
	In this function we will set how many labwares we need of every category (source labwares, final, coldblocks, falcon tube racks, etc)
	
	4 mandatory arguments and 2 optional 
	"""
	position_plates = [position for position, labware in positions.items() if labware == None] # We obtain the positions in which there are not labwares
	all_plates = {}
	if type(label) == list and len(label) != number_labware:
		raise Exception("If the argument 'label' is a list as many names should be provided as the argument 'number_labware'")

	for i in range (number_labware):
		labware_set = False # Control variable
		for position in position_plates:
			try:
				if not module: # Meaning that we are going to load labwares
					if label == None:
						plate = protocol.load_labware(labware_name, position)
					elif type(label) == str:
						plate = protocol.load_labware(labware_name, position, label = f"{label} {i+1} Slot {position}")
					elif type(label) == list:
						plate = protocol.load_labware(labware_name, position, label = f"{label[i]} Slot {position}")
				else: # We are going to load modules
					if label == None:
						plate = protocol.load_module(labware_name, position)
					elif type(label) == str:
						plate = protocol.load_module(labware_name, position, label = f"{label} {i+1} Slot {position}")
					elif type(label) == list:
						plate = protocol.load_module(labware_name, position, label = f"{label[i]} Slot {position}")
				# If it reaches this point the labware as been set
				all_plates[position] = plate
				labware_set = True
				break # It has set the labware so we can break from the loop of positions
			except DeckConflictError:
				continue
			except ValueError: # This will be raised when a thermocycler is tried to set in a position where it cannot be and if the position does not exist
				continue
		
		# Control to see if the labware has been able to load in some free space. This will be tested after trying all the positions
		if labware_set:
			position_plates.remove(position) # We take from the list the value that has been used or the last
		else:
			raise Exception(f"Not all {labware_name} have been able to be placed, try less samples or another combination of variables")

	return all_plates

def number_tubes_needed (vol_reactive_per_reaction_factor, number_reactions, vol_max_tube):
	"""
	Function that will return the number of tubes that is needed for a given number of reactions

	3 arguments functions are needed for this function to work
	"""

	# Set initial values
	number_tubes = 1
	reactions_per_tube = [number_reactions]
	volumes_tubes = [vol_reactive_per_reaction_factor*number_reactions]*number_tubes
	
	# Check if it can be done
	if vol_reactive_per_reaction_factor > vol_max_tube:
		raise Exception(f"The volume of each reaction, {vol_reactive_per_reaction_factor}uL, is greater than the max volume of the tube, {vol_max_tube}uL")

	while any(volume > vol_max_tube for volume in volumes_tubes): # If there is some volume that is greater than the max volume we are going to enter in the loop
		number_tubes += 1 # We add one tube so the volume can fit in the tubes
		
		# Now we redistribute the reactions (and volume) to the tubes so it will be the most homogeneus way
		reactions_per_tube = [int(number_reactions/number_tubes)]*number_tubes
		tubes_to_add_reaction = number_reactions%number_tubes # This is the remainder of the division #reactions / #tubes so it can never be greater than #tubes
		
		for i in range(tubes_to_add_reaction): # We will add 1 reaction to every tube until there are no more reaction remainders
			reactions_per_tube[i] += 1
		# Adding one will make the volume of the tubes more homogeneous

		# Calculate the new volumes
		volumes_tubes = [vol_reactive_per_reaction_factor*number_reactions_tube for number_reactions_tube in reactions_per_tube]
	
	# When the volume can fit every tube (exit from the while loop) we return the number of tubes and the reactions that will fit in every tube
	return (number_tubes, reactions_per_tube, volumes_tubes)

def generator_positions (labware_wells_name):
	"""
	Function that will return the next element everytime is called from a given list
	"""
	for well in labware_wells_name:
		yield well

def calculate_max_reactions_constant_height_15mLfalcon (tube, vol_tube, total_number_reactions, vol_per_reaction):
	"""
	Function that will return how many reactions of a certain volume can be transfered/distribute without changing the height that the pipette can aspirate
	without getting wet and having volume to aspirate

	4 mandatory arguments are needed for this function
	"""

	# Check if there is enough volume in the tube to transfer all the reactions
	if vol_tube - (total_number_reactions*vol_per_reaction) < -0.001:
		raise Exception(f"Not enough volume in the source tube, {vol_tube}uL, to distribute {vol_per_reaction}uL to {total_number_reactions} reactions")
	
	react_distr = 0

	# Let's see if at least there is 1*volume reaction can be transferred without changing
	if find_safe_15mLfalcon_height(vol_tube, tube).point != find_safe_15mLfalcon_height(vol_tube - vol_per_reaction, tube).point:
		return 0 # This will mean that no volume of reaction can be moved without changing the volume so it needs another way to deal with it

	# Loop adding 1 reaction until the height of aspirate change
	while find_safe_15mLfalcon_height(vol_tube, tube).point == find_safe_15mLfalcon_height(vol_tube - (react_distr*vol_per_reaction), tube).point:
		if react_distr + 1 > total_number_reactions:
			break
		else: # One more reaction can be transfered
			react_distr += 1
	
	return react_distr

def calculate_max_reactions_constant_height_50mLfalcon (tube, vol_tube, total_number_reactions, vol_per_reaction):
	"""
	Function that will return how many reactions of a certain volume can be transfered/distribute without changing the height that the pipette can aspirate
	without getting wet and having volume to aspirate

	4 mandatory arguments are needed for this function
	"""

	# Check if there is enough volume in the tube to transfer all the reactions
	if vol_tube - (total_number_reactions*vol_per_reaction) < -0.001:
		raise Exception(f"Not enough volume in the source tube, {vol_tube}uL, to distribute {vol_per_reaction}uL to {total_number_reactions} reactions")
	
	react_distr = 0
	
	# Let's see if at least there is 1*volume reaction can be transferred without changing
	if find_safe_50mLfalcon_height (vol_tube, tube).point != find_safe_50mLfalcon_height (vol_tube - vol_per_reaction, tube).point:
		return 0 # This will mean that no volume of reaction can be moved without changing the volume so it needs another way to deal with it

	# Loop adding 1 reaction until the height of aspirate change
	while find_safe_50mLfalcon_height (vol_tube, tube).point == find_safe_50mLfalcon_height (vol_tube - react_distr*vol_per_reaction, tube).point:
		if react_distr + 1 > total_number_reactions:
			break
		else: # One more reaction can be transfered
			react_distr += 1
	
	return react_distr

def distribute_z_tracking_falcon15_50ml (pipette_used, tip_rack_pipette, deck_situation, vol_source, vol_distribute_well, pos_source, pos_final, vol_max_falcon, protocol, vol_max_transfer, new_tip = "never", replace_tiprack = False, initial_tip_pip = "A1", same_tiprack = False, touch_tip = False):
	"""
	Function that will distribute with a pipette (pipette_used) the same volume (vol_distribute_well) from 1 initial falcon tube position (pos_source) to a list of 1 or more final positions (pos_final) tracking the height of aspiration of the falcon tube
	by tracking the current volume of that tube.

	For that purpose is needed to provide different information to the function:
		- pipette_used: pipette that is going to be used to transfer the volumes
		- tip_rack_pipette: the API name of the tiprack that is going to be defined in case that the pipette is out of tips
		- deck_situation: dictionary that represents the slot as keys and the loaded labware that is in each of them as values. It is used in case a tiprack needs to be defined
		- vol_source: initial volume of the source falcon tube
		- vol_distribute_well: volume that is going to be transferred to each one of the final positions
		- pos_source: position of the initial falcon tube
		- pos_final: list of final wells to distribute the volume to
		- vol_max_falcon: the maximum volume, in ul, that 1 falcon tube can have. Only 2 options are allowed: 15000 and 50000
		- protocol: the opentrons protocol context of the script
		- vol_max_transfer: the maximum volume that cna be transferred with pipette_used in 1 aspiration, for example, the max of the pipette or the maximum of the tips attached to th e pipette
		- new_tip: optional argument that establish when the tip should be changed. It can be every time it aspirates (aspirate), every time the pipette goes to the final well (well) or neever (never). By default is set as never
		- replace_tiprack: optional argument that establish that once a tip rack is empty, if this one should be replaced or 1 additional tip rack should be added to the protocol deck. By default is set as False
		- initial_tip_pip: optional argument that establish in case that a tiprack is defined for the first time this will set which tip should be picked first, by default is set as "A1"
		- same_tiprack: optional argument that establish defines thatboth pipettes set during the protocol have the same tip rack attached. By default is set as False
		- touch_tip: optional argument that establish that during the transfer there would be a touc htip in the source and final position
	"""

	# We define the minimum volume that the pipette can transfer in case we need it
	pipette_min_volume = pipette_used.min_volume
	
	# Check that the new_tip argument has a correct value
	if new_tip not in ["never", "aspirate", "well"]:
		raise Exception("The argument new_tip only accepts 3 values: never, aspirate, well")

	# Check that actually is a falcon of 15 or 50mL because they are the only ones allowed for the moment
	if vol_max_falcon not in [15000, 50000]:
		raise Exception("The function 'distribute_z_tracking_falcon_15_50ml' only accepts falcons of 15mL and 50mL")

	# Check if actually the pipette can transfer vol_distribute_well
	if vol_distribute_well < pipette_min_volume:
		raise Exception(f"The pipette {pipette_used} cannot transfer the volume assigned for each well, {vol_distribute_well}ul")
	
	# Check that there is enough volume to distribute that volume
	# Because we are using floats and there is the problem of the error caused when doing floating-point arithmetic we are going to give a range of error in the substractions
	# by comparing with -0.001 instead of 0
	if vol_source - len(pos_final)*vol_distribute_well < -0.001:
		raise Exception(f"Not enough volume in the source tube, {vol_source}uL, to distribute {vol_distribute_well}uL to {len(pos_final)} positions")
	
	# Initialize the positions that the pos_source tube is going to feed
	start_position = 0

	# We will be keeping track of the positions that have already been the final well in a volume transfer until there has been the transferring to all of them
	while start_position != len(pos_final):
		# It wont have a tip if the new_tip is aspirate or well or if it is the first time it gets into the function
		if not pipette_used.has_tip:
			check_tip_and_pick (pipette_used,
								tip_rack_pipette,
								deck_situation,
								protocol,
								replace_tiprack = replace_tiprack,
								initial_tip = initial_tip_pip,
								same_tiprack = same_tiprack)
		
		# Now we need to find if we can tranfer to at least 1 final well without changing the height of aspiraction
		if (vol_max_falcon == 15000 and find_safe_15mLfalcon_height(vol_source, pos_source) == find_safe_15mLfalcon_height(vol_source - vol_distribute_well, pos_source)) or (vol_max_falcon == 50000 and find_safe_50mLfalcon_height(vol_source, pos_source) == find_safe_50mLfalcon_height(vol_source - vol_distribute_well, pos_source)):
			# Find how many position can be transfered taking in account the new_tip value

			# We ar egoing to set a control varaible because there is a case in which the volume gets transferred befor all others
			volume_transferred = False
			
			# Depending on the value of new_tip we can transfer 1 or more volumes to final positions
			if new_tip == "never":
				# If the new_tip is never we can transfer the maximum ammount of final wells that can be transferred without changing the height
				# We have already check it is at least 1 so we dont need to account of calculate_max_reactions_constant_height_15mLfalcon or calculate_max_reactions_constant_height_50mLfalcon returning a 0
				# On base of the falcon that is being used we calculate how many positions can be distributed without changing the height of aspiration
				if vol_max_falcon == 15000: 
					# Calculate how many reactions we can distribute aspirating from the same height
					number_pos_distr = calculate_max_reactions_constant_height_15mLfalcon (pos_source, vol_source, len(pos_final[start_position:]), vol_distribute_well)
				else: # In this case the vol of the falcon is 50000 
					number_pos_distr = calculate_max_reactions_constant_height_50mLfalcon (pos_source, vol_source, len(pos_final[start_position:]), vol_distribute_well)
			elif new_tip == "aspirate":
				# If the tip is aspirate we need to calculate how many finla wells we can transfer volume to without changing the height
				# In case that this ammount of final positions is higher than the maximum ammount of final wells that can be distributed
				# with only 1 movement, this latter ammount is the one transferred

				# First, we calculate what is the max number of final wells that the combination pipette-tiprack can transfer
				# Then, we check with the maximum of the tube and choose the lower ammount
				pos_max = int(vol_max_transfer/vol_distribute_well) # Maximum number of final wells the pipette can transfer to in 1 movement
				if pos_max > 0:
					if pos_max > len(pos_final[start_position:]): # Check that this pos_max is not higher than the total ammount of positions we need to transfer
						pos_max = len(pos_final[start_position:])
					# Now we check that actually that is not higher to the max reactions without height change
					if vol_max_falcon == 15000:
						number_pos_distr = calculate_max_reactions_constant_height_15mLfalcon (pos_source, vol_source, pos_max, vol_distribute_well)
					else:
						number_pos_distr = calculate_max_reactions_constant_height_50mLfalcon (pos_source, vol_source, pos_max, vol_distribute_well)

					# Finally, we check if those numbers are lower than the number of reactions that are still needed
					if number_pos_distr > len(pos_final[start_position:]):
						number_pos_distr = len(pos_final[start_position:])
				else: # We can not transfer with the pipette not even 1 vol_distribute_well with 1 movement, so we just transfer 1
					# First we figure out how many movements do we need
					min_full_movements, rest_volume = divmod(vol_distribute_well, vol_max_transfer)
					# Now we establish the volumes of those movements making sure all of the movements can be done with this pipette
					if rest_volume > 0 and rest_volume < pipette_min_volume: # All volume scna be transferred and the rest volume is 0
						vol_transfer = int(min_full_movements-1)*[vol_max_transfer]
						vol_transfer += [(vol_max_transfer/2)+rest_volume, vol_max_transfer/2]
					elif rest_volume == 0:
						vol_transfer = int(min_full_movements)*[vol_max_transfer]
					else: # This means the rest_volume cannot be transferred with the pipette so we need to balance the volumes so it can be done
						vol_transfer = int(min_full_movements)*[vol_max_transfer]
						vol_transfer.append(rest_volume)
					
					# Transfer the volumes changing the tip every time
					for volumen in vol_transfer:
						if pipette_used.has_tip == False:
							check_tip_and_pick (pipette_used,
												tip_rack_pipette,
												deck_situation,
												protocol,
												replace_tiprack = replace_tiprack,
												initial_tip = initial_tip_pip,
												same_tiprack = same_tiprack)

						# Transfer the volumes aspirating with the proper height
						if vol_max_falcon == 15000:
							pipette_used.transfer(volumen,
												  find_safe_15mLfalcon_height(vol_source, pos_source),
												  pos_final[start_position],
												  new_tip = "never",
												  touch_tip = touch_tip)
						else:
							pipette_used.transfer(volumen,
												  find_safe_50mLfalcon_height(vol_source, pos_source),
												  pos_final[start_position],
												  new_tip = "never",
												  touch_tip = touch_tip)

						pipette_used.drop_tip()
					
					# We set the number of positions that have been transferred and that the volume has already been transferred
					volume_transferred = True
					number_pos_distr = 1
			elif new_tip == "well":
				# In this case the new_tip is set as well, meaning that we will need to change the tip every time we go to the fina lposition
				# This means that in every loop of the while loop the strat_position is going to increas only in 1 unit
				# If the transferring of the volume to the final positions needs more than 1 movement, that also implies changing the tip

				# First we figure out how many movements of the pipette are needed to transfer all the volume to the final well
				if vol_max_transfer < vol_distribute_well: # More than 1 movement is needed
					min_full_movements, rest_volume = divmod(vol_distribute_well, vol_max_transfer)
					if rest_volume > 0 and rest_volume < pipette_min_volume:
						vol_transfer = int(min_full_movements-1)*[vol_max_transfer]
						vol_transfer += [(vol_max_transfer/2)+rest_volume, vol_max_transfer/2]
					elif rest_volume == 0:
						vol_transfer = int(min_full_movements)*[vol_max_transfer]
					else: # Esto significa que el rest_volume no es 0 yt s epuede tr5ansferir con la pipeta
						vol_transfer = int(min_full_movements)*[vol_max_transfer]
						vol_transfer.append(rest_volume)
					
					# Transferimos el volumen
					for volumen in vol_transfer:
						if pipette_used.has_tip == False:
							check_tip_and_pick (pipette_used,
												tip_rack_pipette,
												deck_situation,
												protocol,
												replace_tiprack = replace_tiprack,
												initial_tip = initial_tip_pip,
												same_tiprack = same_tiprack)
						
						# We transfer the volumes aspirating at a correct height
						if vol_max_falcon == 15000:
							pipette_used.transfer(volumen,
												  find_safe_15mLfalcon_height(vol_source, pos_source),
												  pos_final[start_position],
												  new_tip = "never",
												  touch_tip = touch_tip)
						else:
							pipette_used.transfer(volumen,
												  find_safe_50mLfalcon_height(vol_source, pos_source),
												  pos_final[start_position],
												  new_tip = "never",
												  touch_tip = touch_tip)
					
						pipette_used.drop_tip()
					
					volume_transferred = True
				
				# If only one movement is required it will be transferred in a latter moment of the code 
				number_pos_distr = 1

			# Here we establish the finla positions that are goint to receive a volume in case it has not been already transferred
			# This is why we always establish the number_pos_distr, no matter if it has or not been already transferred
			# Establish the positions taking in account how many positions are we distribute
			position_distribute = pos_final[start_position:start_position+number_pos_distr]

			# Distribute them
			if volume_transferred == False:
				if vol_max_falcon == 15000:
					pipette_used.distribute(vol_distribute_well, find_safe_15mLfalcon_height(vol_source, pos_source), position_distribute, new_tip = "never", disposal_volume = 0, touch_tip = touch_tip)
				else:
					pipette_used.distribute(vol_distribute_well, find_safe_50mLfalcon_height(vol_source, pos_source), position_distribute, new_tip = "never", disposal_volume = 0, touch_tip = touch_tip)

			# Update the volume of the tube (pos_source)
			vol_source = vol_source - (number_pos_distr*vol_distribute_well)
		else: # This means that not even 1 volume_distribute_well can be transfered without changing the height so we are going to treat it differently
			# We are going to transfer to o nly 1 final well
			# Find out how many maximum movements we would need to do by only transferring the minimum volume of the pipette, this would be a worst case scenario
			max_movements_minvol_pipette, volume_rest_minvol_movements = divmod(vol_distribute_well, pipette_min_volume)
			
			# Because we are doing the calculation with the minimum volume, that would mean that if there is a volume_rest_minvol_movements, it cannot be taken with the pipette
			# For that reason, we are ging to sort out the number of moments requires and the rest volume to make every volume pickable with the pipette
			if volume_rest_minvol_movements > 0: # Claramente si ha quedado esto es porque este retso no se puede coger
				max_movements_minvol_pipette -= 1
				volume_rest_minvol_movements += pipette_min_volume
				# This will be a number that will range (0, pipette_used.min_volume*2) and we just make sure that it can be transferred, this volume should not be higher than the max volume of the pipette
			
			# We are going to transfer to only 1 position, so we set it here and we will reference it for the rest of the code
			final_well_transfer = pos_final[start_position]
			
			# Let's tranfer the max_movements_minvol_pipette
			while max_movements_minvol_pipette > 0:
				if pipette_used.has_tip == False:
					check_tip_and_pick (pipette_used,
										tip_rack_pipette,
										deck_situation,
										protocol,
										replace_tiprack = replace_tiprack,
										initial_tip = initial_tip_pip,
										same_tiprack = same_tiprack)

				# We need to take account while doing the movements the value of new_tip
				# Because we are going to dispense only to a well we just need to take in account the aspirate option and if new tip is well, changing tip when aspirating is needed as well
				if new_tip == "aspirate" or new_tip == "well":
					# Calculate max reactions that can take the pipette
					pos_max = int(vol_max_transfer/pipette_min_volume)

					# Check if that pos_max is higher than the needed volume to transfer
					if pos_max > max_movements_minvol_pipette:
						pos_max =  max_movements_minvol_pipette
					
					# Now we check that actually that is not higher to the max reactions without height change
					if vol_max_falcon == 15000: 
						number_react_transfer = calculate_max_reactions_constant_height_15mLfalcon (pos_source, vol_source, pos_max, pipette_min_volume)
					else:
						number_react_transfer = calculate_max_reactions_constant_height_50mLfalcon (pos_source, vol_source, pos_max, pipette_min_volume)
				else: # The new_tip is going to be never so we will not change the tips
					# We are goign to transfer the maximum volume possible
					if vol_max_falcon == 15000:
						number_react_transfer = calculate_max_reactions_constant_height_15mLfalcon (pos_source, vol_source, max_movements_minvol_pipette, pipette_min_volume)
					else:
						number_react_transfer = calculate_max_reactions_constant_height_50mLfalcon (pos_source, vol_source, max_movements_minvol_pipette, pipette_min_volume)

				# If even with that pipette_used.min_volume you need to change the height, this would be never more than 1, 20 and 100ul for the p20, p300 and p1000 pipettes so we consider that it is not as big a volume
				# that it would get the pipette wet if it goes to the next one
				if number_react_transfer != 0:
					if vol_max_falcon == 15000:
						pipette_used.transfer(number_react_transfer*pipette_min_volume,
											  find_safe_15mLfalcon_height(vol_source, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)
					else:
						pipette_used.transfer(number_react_transfer*pipette_min_volume,
											  find_safe_50mLfalcon_height(vol_source, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)
				else:
					number_react_transfer = 1 # We will transfer only minimum volume of the pipette volume
					if vol_max_falcon == 15000:
						pipette_used.transfer(pipette_min_volume,
											  find_safe_15mLfalcon_height(vol_source - pipette_min_volume, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)
					else:
						pipette_used.transfer(pipette_min_volume,
											  find_safe_50mLfalcon_height(vol_source - pipette_min_volume, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)

				# We update the remaining movements
				max_movements_minvol_pipette -= number_react_transfer

				if (new_tip == "aspirate" or new_tip == "well") and max_movements_minvol_pipette != 0: # If it is the last movement from this part of the code, the tip will be cared about later in the code
					pipette_used.drop_tip()
				elif (new_tip == "aspirate" or new_tip == "well") and max_movements_minvol_pipette == 0 and volume_rest_minvol_movements != 0:
					pipette_used.drop_tip()
				
				# We update the volume of the tube (pos_source) where we are taking the liquid
				vol_source -= number_react_transfer*pipette_min_volume
			
			# We have already distributed all max_movements_minvol_pipette
			# Now we distribute the rest of the volume to that final well
			# This is going to be only 1 movement because we made sure that is going to be max 2*pip.min_volume which will be lower than the pip.max_volume
			if volume_rest_minvol_movements > 0:
				if pipette_used.has_tip == False:
					check_tip_and_pick (pipette_used,
										tip_rack_pipette,
										deck_situation,
										protocol,
										replace_tiprack = replace_tiprack,
										initial_tip = initial_tip_pip,
										same_tiprack = same_tiprack)

				if vol_max_falcon == 15000:
					if find_safe_15mLfalcon_height (vol_source - pipette_min_volume, pos_source) != find_safe_15mLfalcon_height (vol_source - pipette_min_volume, pos_source):
						pipette_used.transfer(volume_rest_minvol_movements,
											  find_safe_15mLfalcon_height(vol_source - pipette_min_volume, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)
					else:
						pipette_used.transfer(volume_rest_minvol_movements,
											  find_safe_15mLfalcon_height(vol_source, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)
				elif vol_max_falcon == 50000:
					if find_safe_50mLfalcon_height (vol_source - pipette_min_volume, pos_source) != find_safe_15mLfalcon_height (vol_source - pipette_min_volume, pos_source):
						pipette_used.transfer(volume_rest_minvol_movements,
											  find_safe_50mLfalcon_height(vol_source - pipette_min_volume, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)
					else:
						pipette_used.transfer(volume_rest_minvol_movements,
											  find_safe_50mLfalcon_height(vol_source, pos_source),
											  final_well_transfer,
											  new_tip = "never",
											  touch_tip = touch_tip)

				# We update the volume of the tube (pos_source) where we are taking the liquid after transfering the rest of the volume
				vol_source = vol_source - (volume_rest_minvol_movements)
			
			# We have distributed only to 1 well so the start_position is updated because the volume has been updated accordingly to the transfering that has been done 
			number_pos_distr = 1

		# Update the start position of the final wells either if it was only 1 or more positions thansferred
		start_position = start_position + number_pos_distr
		
		# We take care of the tips
		if new_tip != "never" and start_position != len(pos_final) and pipette_used.has_tip:
			pipette_used.drop_tip()

	# Return the remaining volume in the tube used in case it had more than needed and wants to be used again
	return vol_source

def find_safe_15mLfalcon_height (vol_falcon, theory_position):
	"""
	This function will return the height in which the pipette should aspirate and or dispense the volume to not get wet while doing it
	
	It is manually measured, meaning that if you change the tubes you should test if this work or redo the heights

	This function takes 2 inputs, the tube position and the volume it has and will return the same position with the according height
	"""

	if vol_falcon <= 100: # The values of comparing are volumes (in uL)
		final_position = theory_position.bottom(z=0.7)
	elif vol_falcon > 100 and vol_falcon <= 3000:
		final_position = theory_position.bottom(z=1)
	elif vol_falcon > 3000 and vol_falcon <= 6000:
		final_position = theory_position.bottom(z = 25)
	elif vol_falcon > 6000 and vol_falcon <= 9000:
		final_position = theory_position.bottom(z = 45)
	elif vol_falcon > 9000:
		final_position = theory_position.bottom(z = 65)
	return final_position

def find_safe_50mLfalcon_height (vol_falcon, theory_position):
	"""
	This function will return the height in which the pipette should aspirate and or dispense the volume to not get wet while doing it
	
	It is manually measured, meaning that if you change the tubes you should test if this work or redo the heights

	This function takes 2 inputs, the tube position and the volume it has and will return the same position with the according height
	"""

	if vol_falcon < 5000 : # The values of comparing are volumes (in uL)
		final_position = theory_position.bottom(z=1) # It will go to the normal position that will go when it aspirates or dispense
	elif vol_falcon >= 5000 and vol_falcon < 12500:
		final_position = theory_position.bottom(z = 12)
	elif vol_falcon >= 12500 and vol_falcon < 22500:
		final_position = theory_position.bottom(z = 28)
	elif vol_falcon >= 22500 and vol_falcon < 32500:
		final_position = theory_position.bottom(z = 45)
	elif vol_falcon >= 32500 and vol_falcon < 42500:
		final_position = theory_position.bottom(z = 62)
	elif vol_falcon >= 42500:
		final_position = theory_position.bottom(z = 81)
	return final_position

def check_tip_and_pick (pipette_used, tiprack, position_deck, protocol, replace_tiprack = False, initial_tip = "A1", same_tiprack = False):
	"""
	Function that will pick a tip and if there is not a tip available it will define a new tip rack and pick one in case it is possible to establish
	a new tip rack.
	For that purpose it will need 7 arguments, 3 optional (replace_tiprack, initial_tip, same_tiprack) and 4 mandatory (pipette_used, tiprack, position_deck, protocol)
	"""
	try:
		pipette_used.pick_up_tip()
		# When there are no tips left in the tiprack OT will raise an error
	except OutOfTipsError:
		if len(pipette_used.tip_racks) == 0: # There are no tip racks attached to the pipette
			# If it is possible a tiprack will be established
			position_deck = {**position_deck , **define_tiprack (pipette_used, tiprack, position_deck, protocol, same_tiprack = same_tiprack)}
			
			# We establish now the starting tip, it will only be with the first addition, the rest will be establish that the first tip is in A1 directly
			if same_tiprack and "right" in protocol.loaded_instruments.keys() and "left" in protocol.loaded_instruments.keys(): # Same tipracks
				protocol.loaded_instruments["right"].starting_tip = pipette_used.tip_racks[0][initial_tip]
				protocol.loaded_instruments["left"].starting_tip = pipette_used.tip_racks[0][initial_tip]
			else: # Different tipracks
				protocol.loaded_instruments[pipette_used.mount].starting_tip = pipette_used.tip_racks[0][initial_tip]
			
		else:# There is already a tiprack attached to the pipette 
			if replace_tiprack == False: # A tip rack will be added to the layout in case it is possible
				position_deck = {**position_deck , **define_tiprack (pipette_used, tiprack, position_deck, protocol, same_tiprack = same_tiprack)}
			else: # The tip rack will be replaced by the one already placed
				# Careful with this part if you are traspassing this script into jupyter because this will crash your jupyter (will wait until resume and it does not exist)
				protocol.pause("Replace Empty Tiprack With A Full One And Press Resume In OT-App")
				if same_tiprack and "right" in protocol.loaded_instruments.keys() and "left" in protocol.loaded_instruments.keys():
					protocol.loaded_instruments["right"].reset_tipracks()
					protocol.loaded_instruments["left"].reset_tipracks()
				else:
					pipette_used.reset_tipracks()
		
		#Finally, we pick up the needed tip        
		pipette_used.pick_up_tip()
	
	return
	
def define_tiprack (pipette, tiprack_name, position_deck, protocol, same_tiprack = False):
	"""
	Function that will define, if possible, a tip rack in the first position free that does not raise a deck conflict
	and assigned it to the pipette.

	In case that the right and left pipette have the same tiprack, menaing the same_tiprack variable is set as True,
	the tip rack will be assigned to both pipettes

	This function needs 4 mandatory arguments and 1 optional
	"""

	# First we find out how many positions are available
	positions_free = [position for position, labware in position_deck.items() if labware == None]
	
	if len(positions_free) == 0:
		raise Exception("There is not enough space in the deck for the tip rack needed")
	
	for position in positions_free: # Loop in case there is a position that has deck conflicts but it can still be placed in another one
		
		try:
			tiprack = protocol.load_labware(tiprack_name, position)
			position_deck[position] = tiprack_name
		except OSError:
			raise Exception (f"The tip rack '{tiprack_name}' is not found in the opentrons namespace, check for typos or add it to the custom labware")
		except DeckConflictError: # Continue to the next position
			continue
		
		# Attach the tip rack to the right pipette(s)
		if same_tiprack and "right" in protocol.loaded_instruments.keys() and "left" in protocol.loaded_instruments.keys():# Both tip racks are the same
			protocol.loaded_instruments["right"].tip_racks.append(tiprack)
			protocol.loaded_instruments["left"].tip_racks.append(tiprack)
		else:
			protocol.loaded_instruments[pipette.mount].tip_racks.append(tiprack)
		
		# If it has reached this point it means that the tiprack has been defined
		return {position:tiprack_name}
	
	# If it has reached this point it means that the tip rack has not been able to be defined
	raise Exception(f"Due to deck conflicts, the tiprack '{tiprack_name}' has not been able to be placed. Try another combination of variables")

def give_me_optimal_pipette (aVolume, pipette_r = None, pipette_l = None):
	"""
	Function that given a set of pipettes  will return the one more that will transfer the volume with less movements

	This function requires 1 mandatory argument and 2 optional
	"""

	if pipette_r == None and pipette_l == None: # No pipettes attached
		raise Exception(f"There is not a pippette attached to aspirate/dispense {aVolume}uL")
	
	# Look if one of them is the only option
	elif pipette_r == None and aVolume >= pipette_l.min_volume: # One mount is free, only need that the volume is more than the min of the pipette
		return pipette_l
	
	elif pipette_l == None and aVolume >= pipette_r.min_volume:
		return pipette_r
	
	# Now we look if there are 2 and the most apropiate should be returned
	elif pipette_r != None and pipette_l != None:
		# Define if both of the pipettes can take the volume
		if aVolume >= pipette_l.min_volume and aVolume >= pipette_r.min_volume:
			if pipette_l.min_volume >= pipette_r.min_volume:
				return pipette_l
			else:
				return pipette_r
		# Not both of them can pick it, so it is a matter to figure out if 1 of them can do it
		elif aVolume >= pipette_l.min_volume:
			return pipette_l
		elif aVolume >= pipette_r.min_volume:
			return pipette_r
		else: # None of the pipettes can hold that volume
			raise NotSuitablePipette(aVolume)
	
	else: # This will be the case if there is 1 pipette attached but it can take the volume
		raise NotSuitablePipette(aVolume)

# Body of the Program
# ----------------------------------
# ----------------------------------
		
metadata = {
'apiLevel':'2.14'
}

def run(protocol:opentrons.protocol_api.ProtocolContext):
	labware_context = opentrons.protocol_api.labware
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Read Variables Excel, define the user and protocol variables and check them for initial errors
	
	excel_variables = pd.read_excel("/data/user_storage/VariablesCounterSelection.xlsx", sheet_name = None, engine = "openpyxl")
	# excel_variables = pd.read_excel("VariablesCounterSelection.xlsx", sheet_name = None, engine = "openpyxl")
	
	# Let's check that the minimal needed sheets are in the document
	name_sheets = list(excel_variables.keys())
	
	if not all(item in name_sheets for item in ["GeneralVariables","PerPlateVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have min the sheets "GeneralVariables","PerPlateVariables","PipetteVariables"\nThey must have those names')
	
	# Check that all variable sheets have the needed columns and variable names
	general_variables = excel_variables.get("GeneralVariables")
	plate_variables = excel_variables.get("PerPlateVariables")
	pip_variables = excel_variables.get("PipetteVariables")

	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in general_variables["Variable Names"].values for item in ['API Name Source Plate', 'API Name Final Plate', 'API Name Rack Falcon Reactives', 'Name Reactives', 'Number of Source Plates', 'Volume per Reactive (uL)', 'Name Final File Maps']):
			raise Exception("'GeneralVariables' sheet table needs to have 7 rows with the following names: 'API Name Source Plate', 'API Name Final Plate', 'API Name Rack Falcon Reactives', 'Name Reactives', 'Number of Source Plates', 'Volume per Reactive (uL)', 'Name Final File Maps'")
		
	if "Variable Names" not in list(plate_variables.columns):
		raise Exception("'PerPlateVariables' sheet table needs to have at least 1 column, 'Variable Names'")
	else:
		if not all(item in plate_variables["Variable Names"].values for item in ['Threshold Selection Value', 'Name Sheet Selection Value<Threshold', 'Name Sheet Selection Value>Threshold', 'Reactives Per Plate', 'Well Start Final Plate', 'Final Map Name', 'Volume Transfer Sample (uL)']):
			raise Exception("'PerPlateVariables' Sheet table needs to have 7 rows with the following names: 'Threshold Selection Value', 'Name Sheet Selection Value<Threshold', 'Name Sheet Selection Value>Threshold', 'Reactives Per Plate', 'Well Start Final Plate', 'Final Map Name', 'Volume Transfer Sample (uL)'")
		if plate_variables.shape[1] < 2:
			raise Exception("'PerPlateVariables' Sheet needs to have at least 2 columns, the 'Variable Names' column and 1 with a source plate information")

	if not all(item in list(pip_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'PipetteVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in pip_variables["Variable Names"].values for item in ['API Name Right Pipette','API Name Left Pipette','API Name Tiprack Left Pipette','API Name Tiprack Right Pipette', 'Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks']):
			raise Exception("'PipetteVariables' Sheet table needs to have 7 rows with the following names: 'API Name Right Pipette','API Name Left Pipette','API Name Tiprack Left Pipette','API Name Tiprack Right Pipette', 'Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks'")
	

	user_variables = UserVariables(general_variables, plate_variables, pip_variables)
	user_variables.check()
	program_variables = SettedParameters(len(protocol.deck))
	program_variables.assign_variables(user_variables, protocol)

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Set the source and final plates because we know how much we have of both
	# Get the labels for the source plates
	labels_source_plate = []
	for name in user_variables.nameSourcePlates[:user_variables.numberSourcePlates]:
		labels_source_plate.append(f"Source Plate '{name}'")
	source_plates = setting_labware(user_variables.numberSourcePlates, user_variables.APINameSamplePlate, program_variables.deckPositions, protocol, label = labels_source_plate)
	program_variables.deckPositions = {**program_variables.deckPositions , **source_plates}
	vol_max_well_source_labware = list(labware_context.get_labware_definition(user_variables.APINameSamplePlate)["wells"].values())[0]['totalLiquidVolume']
	for index_labware, labware in enumerate(source_plates.items()):
		program_variables.samplePlates[index_labware]["Position"] = labware[0]
		program_variables.samplePlates[index_labware]["Opentrons Place"] = labware[1]
		
		# Set the liquid of samples
		for well in program_variables.samplePlates[index_labware]["Opentrons Place"].wells():
			well.load_liquid(program_variables.liquid_samples, volume = 0.9*vol_max_well_source_labware)
	
	for index_plate, plate in program_variables.finalPlates.items():
		final_plate = setting_labware(1, user_variables.APINameFinalPlate, program_variables.deckPositions, protocol, label = [plate["Label"]])
		program_variables.deckPositions = {**program_variables.deckPositions , **final_plate}
		plate["Position"] = list(final_plate.keys())[0]
		plate["Opentrons Place"] = list(final_plate.values())[0]
		if program_variables.samplePlates[plate['Source Plate']]["Map Selected Colonies"] == None:
			program_variables.samplePlates[plate['Source Plate']]["Map Selected Colonies"] = MapLabware(list(final_plate.values())[0])
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Select which colonies are going to be transferred to the final plate(s)
	for index_plate, plate_source in enumerate(program_variables.samplePlates.values()):
		for index_column in range(len(plate_source["Opentrons Place"].columns())): # Go through columns
			for index_row in range(len(plate_source["Opentrons Place"].rows())): # Go through rows
				# Check if the values are according to the threshold that it was set
				if plate_source['Values for Selection (Lower than Threshold)'].iloc[index_row, index_column] <= plate_source["Threshold Value"] and plate_source['Values for Selection (Greater than Threshold)'].iloc[index_row, index_column] >= plate_source["Threshold Value"]:
					plate_source["Selected Colonies"].append([index_row, index_column])
		
		# Let's check that there is at least 1 sample that is going to be selected, because it does not make sense to run with this one if no sample is going to be selected
		if len(plate_source["Selected Colonies"]) == 0:
			raise Exception(f"The Source Plate '{user_variables.nameSourcePlates[index_plate]}' does not have any sample that fulfills the set of selection variables")
		
		# Let's check if the numebr of selected colonies fit in the final labware given the first well in which it should be placed the first selected colony
		if len(plate_source["Selected Colonies"])+list(plate_source["Opentrons Place"].wells_by_name().keys()).index(user_variables.wellStartFinalPlate[index_plate]) > len(labware_context.get_labware_definition(user_variables.APINameFinalPlate)["wells"]):
			raise Exception(f"There are {len(plate_source['Selected Colonies'])} samples in '{user_variables.nameSourcePlates[index_plate]}' that fulfill the parameters given but they do not fit in the final plate given the {user_variables.APINameFinalPlate} labware and the start well provided")
	

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Define mediums and their wells
	# First we need to know how many reactions each medium will have
	for labware_final in program_variables.finalPlates.values():
		if labware_final["Medium"] != None:
			program_variables.reactiveWells[labware_final["Medium"]]["Number Total Reactions"] += len(program_variables.samplePlates[labware_final["Source Plate"]]["Selected Colonies"])
		
		# This number is needed for both when there is no medium and when it is
		labware_final["Number Samples"] = len(program_variables.samplePlates[labware_final["Source Plate"]]["Selected Colonies"])


	# We need to know the max reactive tube volume
	# For that we need to know the maximum volume of the tubes and how many tubes of the reactives we need in total
	if user_variables.nameReactives != None:
		total_falcons_medium = 0 # Initialize
		for reactive_type in program_variables.reactiveWells.keys():
			number_tubes, program_variables.reactiveWells[reactive_type]["Reactions Per Tube"], program_variables.reactiveWells[reactive_type]["Volumes"] = number_tubes_needed(program_variables.reactiveWells[reactive_type]["Volume Per Sample"],
																																												program_variables.reactiveWells[reactive_type]["Number Total Reactions"],
																																												0.9*user_variables.dimensionsFalcon["volume"])
			# The 0.9 max well volume is only to not overfill the volume and give space to put more liquid so the pipetting is assure
			total_falcons_medium += number_tubes
		
		# Set how many tuberacks now that we now how many tubes of antibiotic we need
		number_wells_tuberack = user_variables.dimensionsFalcon["rows"]*user_variables.dimensionsFalcon["columns"]
		tuberacks_needed = math.ceil(total_falcons_medium/number_wells_tuberack)
		
		if tuberacks_needed > 0:
			labware_falcons = setting_labware(tuberacks_needed,
											  user_variables.APINameFalconPlate,
											  program_variables.deckPositions,
											  protocol,
											  label = "Reactive Labware")
			program_variables.deckPositions = {**program_variables.deckPositions , **labware_falcons}
			
			# Now we are going to set the reactives in the coldblock positions, we need to keep track of these positions for liquid movement
			# Get the possible positions merging all the labwares from the tuberacks
			positions_tuberack = []
			for labware in labware_falcons.values():
				positions_tuberack += labware.wells()
			generator_positions_reactives = generator_positions(positions_tuberack)
			
			# Assign to each reactive the positions of the falcons
			for reactive_type in program_variables.reactiveWells.keys():
				for volume_tube in program_variables.reactiveWells[reactive_type]["Volumes"]:
					well_tube_falcon = next(generator_positions_reactives)
					program_variables.reactiveWells[reactive_type]["Positions"].append(well_tube_falcon)
					well_tube_falcon.load_liquid(liquid = program_variables.reactiveWells[reactive_type]["Definition Liquid"], volume = volume_tube)
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Transfer the reactives to their plates

	for reactive_type in program_variables.reactiveWells.keys():
		optimal_pipette = give_me_optimal_pipette (program_variables.reactiveWells[reactive_type]["Volume Per Sample"],
												   program_variables.pipR,
												   program_variables.pipL)
		if optimal_pipette.mount == "right":
			tiprack = user_variables.APINameTipR
			starting_tip = user_variables.startingTipPipR
			volume_max = program_variables.maxVolumePipR
		else:
			tiprack = user_variables.APINameTipL
			starting_tip = user_variables.startingTipPipL
			volume_max = program_variables.maxVolumePipL

		check_tip_and_pick(optimal_pipette,
						   tiprack,
						   program_variables.deckPositions,
						   protocol,
						   replace_tiprack = user_variables.replaceTiprack,
						   initial_tip = starting_tip,
						   same_tiprack = program_variables.sameTiprack)
		
		# Define the wells that are going to be the final position for the transferring of this specific reactive
		wells_distribute_reactive = []

		for plate_incubation in program_variables.finalPlates.values():
			if plate_incubation["Medium"] == reactive_type:
				wells_distribute_reactive += plate_incubation["Opentrons Place"].wells()[plate_incubation["Index Well Start"]:plate_incubation["Index Well Start"]+plate_incubation["Number Samples"]]
		
		# We transfer with the given falcon tubes to the final wells tracking the height of the volume
		for index_tube, tube in enumerate(program_variables.reactiveWells[reactive_type]["Reactions Per Tube"]):
			if len(wells_distribute_reactive) <= tube:
				program_variables.reactiveWells[reactive_type]["Volumes"][index_tube] = distribute_z_tracking_falcon15_50ml (optimal_pipette,
																												 			 tiprack,
																															 dict(zip(protocol.deck.keys(), protocol.deck.values())),
																															 program_variables.reactiveWells[reactive_type]["Volumes"][index_tube],
																															 program_variables.reactiveWells[reactive_type]["Volume Per Sample"],
																															 program_variables.reactiveWells[reactive_type]["Positions"][index_tube],
																															 wells_distribute_reactive,
																															 user_variables.dimensionsFalcon["volume"],
																															 protocol,
																															 volume_max,
																															 replace_tiprack = user_variables.replaceTiprack,
																															 initial_tip_pip = starting_tip,
																															 same_tiprack = program_variables.sameTiprack)
				tube -= len(wells_distribute_reactive)
			else:
				program_variables.reactiveWells[reactive_type]["Volumes"][index_tube] = distribute_z_tracking_falcon15_50ml (optimal_pipette,
																															 tiprack,
																															 dict(zip(protocol.deck.keys(), protocol.deck.values())),
																															 program_variables.reactiveWells[reactive_type]["Volumes"][index_tube],
																															 program_variables.reactiveWells[reactive_type]["Volume Per Sample"],
																															 program_variables.reactiveWells[reactive_type]["Positions"][index_tube],
																															 wells_distribute_reactive[:tube],
																															 user_variables.dimensionsFalcon["volume"],
																															 protocol,
																															 volume_max,
																															 replace_tiprack = user_variables.replaceTiprack,
																															 initial_tip_pip = starting_tip,
																															 same_tiprack = program_variables.sameTiprack)
				del wells_distribute_reactive[:tube]
				tube -= len(wells_distribute_reactive)
				
		optimal_pipette.drop_tip()
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Transfer the samples to their plates

	for index_source, source_plate in program_variables.samplePlates.items(): # We go trhough all the source plates
		# We find out the pipette to transfer the samples, it can change from plate to plate
		optimal_pipette = give_me_optimal_pipette (source_plate["Volume Transfer Sample"], program_variables.pipR, program_variables.pipL)
		
		if optimal_pipette.mount == "right":
			tiprack = user_variables.APINameTipR
			starting_tip = user_variables.startingTipPipR
		else:
			tiprack = user_variables.APINameTipL
			starting_tip = user_variables.startingTipPipL

		wells_generator = []

		# Create the possible positions generator
		for final_plate in program_variables.finalPlates.values():
			if final_plate["Source Plate"] == index_source:
				wells_generator.append(generator_positions(final_plate["Opentrons Place"].wells()[final_plate["Index Well Start"]:final_plate["Index Well Start"]+final_plate["Number Samples"]]))
		
		for colony_transfer in source_plate["Selected Colonies"]: # each item is [index_rows, index_column]
			check_tip_and_pick(optimal_pipette,
							   tiprack,
							   program_variables.deckPositions,
							   protocol,
							   replace_tiprack = user_variables.replaceTiprack,
							   initial_tip = starting_tip,
							   same_tiprack = program_variables.sameTiprack)
			wells_final = []

			# Create combination of final wells
			for final_plate_wells in wells_generator:
				wells_final.append(next(final_plate_wells))
			well_source = list(source_plate["Opentrons Place"].rows_by_name())[colony_transfer[0]]+list(source_plate["Opentrons Place"].columns_by_name())[colony_transfer[1]]
			
			# Distribute to all final wells
			optimal_pipette.distribute(source_plate["Volume Transfer Sample"],
									   source_plate["Opentrons Place"][well_source],
									   wells_final,
									   new_tip = "never",
									   disposal_volume = 0)
			
			optimal_pipette.drop_tip()
			
			# Map in the source plate
			source_plate["Map Selected Colonies"].assign_value(f"{well_source} {source_plate['Name Plate']}", wells_final[0]._core._row_name, wells_final[0]._core._column_name)
	
	# Export every map as a sheet in a final excel
	writer = pd.ExcelWriter(f'/data/user_storage/{user_variables.finalMapName}.xlsx', engine='openpyxl')
	# writer = pd.ExcelWriter(f'{user_variables.finalMapName}.xlsx', engine = 'openpyxl')
	
	for final_plate in program_variables.samplePlates.values():
		final_plate["Map Selected Colonies"].map.to_excel(writer, sheet_name = final_plate["Name Final Map"])
	
	writer.save()

	# Home the robot
	protocol.home()