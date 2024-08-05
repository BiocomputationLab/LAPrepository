# LAP-CustomReagentMixingMultiSinglePip-OT2-1.0.0

# Python file destined to be run in an OT-2 that automates the process of filling final plates with specified volumes of various reactants based on user-defined parameters provided in an Excel file.
# This code belongs to the entry of the LAP repository LAP-CustomReagentMixingMultiSinglePip-OT2-1.0.0

# For more info go to https://github.com/BiocomputationLab/LAPrepository/tree/main/LAPEntries/LAP-CustomReagentMixingMultiSinglePip-OT2-1.0.0 or
# http://www.laprepo.com entry https://laprepo.com/protocol/custom-mixing-single-multi-channel-pipette/

# The user inputs maps and variables that dictate the following, within other aspects and specificactions of the script:
#  - Volumes and Reactants: Different reactants and their corresponding volumes to be dispensed into each well.
#  - Plate Replication: The number of replicas for each final plate configuration.
#  - Pipetting Method: Whether to use a single-channel pipette or an 8-channel pipette for the dispensing process.

# The script follows these steps:
#  1. Reading and Validating Input: The script reads the Excel file and checks for errors in the input variables, ensuring all required information is correctly provided before proceeding.
#  2. Setting Variables: Based on the input, the script sets up the necessary variables, such as the volume of each reagent to be transferred, the number of tubes required, etc.
#  3. Loading Labware: All necessary labware, including plates, tubes, and pipettes, are loaded and prepared for the dispensing process.
#  4. Distributing Volumes: Using the single-channel and/or 8-channel pipettes, the script distributes the specified volumes of reactants into the final plates.

# For plates created with an 8-channel pipette, the script offers two optimization options for column combinations of reagents:
#  * Low Optimization: This approach sets the columns that must be present (e.g., a column with a single reagent-volume combination) first.
#  Additional reagent-volume combinations are then matched to these initial columns if possible, and any remaining columns are set as per the provided maps.
#  * High Optimization: This approach also starts by setting the mandatory columns. However, it then defines all possible reagent-volume combinations for the remaining sets.
#  These combinations are scored based on their frequency of appearance in other columns or sets, allowing for a more compact and efficient arrangement of columns for dispensing into the final wells.

# Needed packages for the script to run correctly
import opentrons
import pandas as pd
import numpy as np
import math
import random
from itertools import permutations
from opentrons.motion_planning.deck_conflict import DeckConflictError
from opentrons.protocol_api.labware import OutOfTipsError
import time

class UserVariables:
	"""
	Class that will contain the parameters setted in the variables csv and will process them to work easily in the rest of the protocol
	The coding of this function is dependant of the variables in the Template of the protocol and the names have to be consistent with the rest of the code
	"""

	def __init__(self, general, each_plate, pipettes, rest_sheets):
		"""
		This function will take the pandas dataframe that will be the table of the excel variable files
		"""
		# Variables that are set in the sheet GeneralVariables
		self.APINameFalconPlate = general[general["Variable Names"] == "API Name Labware with Reagent(s) in Tube(s)"]["Value"].values[0]
		self.typeTubesReagents = general[general["Variable Names"] == "Type of Reagent Tube"]["Value"].values[0]
		self.APINameReservoirPlate = general[general["Variable Names"] == "API Name Labware with Reagents(s) in Plate(s)"]["Value"].values[0]
		self.APINameIncubationPlate = general[general["Variable Names"] == "API Name Final Plate"]["Value"].values[0]
		self.numberFinalPlates = general[general["Variable Names"] == "Number of Final Plates"]["Value"].values[0]
		self.changeTipDistribute = general[general["Variable Names"] == "Change Tip In Distribution"]["Value"].values[0]
		self.positionDistributeMedia = general[general["Variable Names"] == "Position Dispense Final Well"]["Value"].values[0]
		self.touchTipDistributeMedia = general[general["Variable Names"] == "Touch Tip After Dispense"]["Value"].values[0]
		self.internalReplicas = general[general["Variable Names"] == "Internal Replicas"]["Value"].values[0]
		self.sourceOptimization = general[general["Variable Names"] == "Optimization Space Source Plate Reagents Disposition"]["Value"].values[0]

		# The following variables are not directly set by the user but they are going to be extracted from information that it has set in this sheet
		# These variables are going to be set when the check method is called and they are going to be used in other parts of the program
		# Some of this variables are not going to be called, depending on which pipette is going to perform the transfering of volumes to the final plates
		self.maxVolumeTubeReagent = None
		self.maxVolumeWellReservoirPlate = None
		self.numberTubesLabware = None
		self.dimensionsLabwareReservoir = {"row":None, "columns":None}
		self.dimensionsFinalLabware = {"row":None, "columns":None}
		self.maxVolumeFinalWell = None
		self.maxVolumeTiprackPipetteR = None
		self.maxVolumeTiprackPipetteL = None

		# Variables that are set in the sheet PipetteVariables
		self.APINamePipR = pipettes[pipettes["Variable Names"] == "Name Right Pipette"]["Value"].values[0]
		self.APINamePipL = pipettes[pipettes["Variable Names"] == "Name Left Pipette"]["Value"].values[0]
		self.startingTipPipR = pipettes[pipettes["Variable Names"] == "Initial Tip Right Pipette"]["Value"].values[0]
		self.startingTipPipL = pipettes[pipettes["Variable Names"] == "Initial Tip Left Pipette"]["Value"].values[0]
		self.APINameTipR = pipettes[pipettes["Variable Names"] == "API Name Right Pipette TipRack"]["Value"].values[0]
		self.APINameTipL = pipettes[pipettes["Variable Names"] == "API Name Left Pipette TipRack"]["Value"].values[0]
		self.replaceTiprack = pipettes[pipettes["Variable Names"] == "Replace Tipracks"]["Value"].values[0]
		
		# Variables that are set in the sheet FinalPlatesVariables
		self.nameFinalPlates = list(each_plate.columns)
		self.nameFinalPlates.remove("Variable Names")
		self.numberReplicas = list(each_plate[each_plate["Variable Names"] == "Number of Replicas"].values[0][1:])
		self.nameSheetReagents = list(each_plate[each_plate["Variable Names"] == "Name Sheet Map Reagents"].values[0][1:])
		self.nameSheetVolumes = list(each_plate[each_plate["Variable Names"] == "Name Sheet Map Volumes"].values[0][1:])
		self.pipetteCreationPlate = list(each_plate[each_plate["Variable Names"] == "Type of Pipette to Create Plate"].values[0][1:])
		
		# The next variable is going to hold the rest of the sheets with their names that will correspond, if filled correctly, to the pages established in 'Name Sheet Map Reagents' and 'Name Sheet Map Volumes'
		self.infoPagesWellsCombinatioMaps = rest_sheets
		
		return
	
	def convert_sheet (value, type, name_sheet):
		"""
		This method will take a value, the type of value expected (reagent or volume) and return the value of the cell split by the commas
		with the values being transformed in numbers in case the type is 'volume'

		If the type is a volume and it is not convertable to a number, an error will be raised
		"""
		if pd.isna(value):
			return value
		
		elements = str(value).replace(" ","").split(",")
		if type == "volume":
			try:
				return [float(volume) for volume in elements]
			except ValueError:
				raise Exception(f"Every value of the excel sheets named in the variable 'Name Sheet Map Volumes' need to be numbers (with the exception of row and columns names) and there is at least one value in sheet {name_sheet} that is not convertible to a number")
		else:
			return elements

	def check(self):
		"""
		Function that will check the variables of the Template and will raise errors that will crash the OT run
		It is a validation function of the variables checking errors or inconsistencies
		
		This function is dependant again with the variabels that we have, some checks are interchangable between protocols, but some of them are specific of the variables
		"""

		labware_context = opentrons.protocol_api.labware

		# First we check all the minimum variables needed, the ones that does that independently of what the final plate composition
		# We check for the number of source plates which will be defined how many columns we are going to read from the sheet FinalPlatesVariables
		if pd.isna(self.numberFinalPlates) or pd.isna(self.APINameIncubationPlate):
			raise Exception("The variables 'Number of Final Plates' and 'API Name Final Plate' in GeneralVariables cannot be left empty")
		else:
			# Check that we have at least 1 source plate
			if self.numberFinalPlates <= 0:
				raise Exception("We need at least 1 final plate to perform the protocol")
			# Check that there are at least number source plate + the column of the names
			if len(self.nameSheetReagents) < self.numberFinalPlates or len(self.nameSheetVolumes) < self.numberFinalPlates:
				raise Exception("We need at least as many columns in the 'FinalPlatesVariables' as the number in the variables 'Name Sheet Map Reagents' and 'Name Sheet Map Volumes' without taking in account the column with the name of the variables")

		# Check the only value in the sheet PipetteVariables that needs to be filled always
		if pd.isna(self.replaceTiprack):
			raise Exception("The variable 'Replace Tipracks' in PipetteVariables cannot be left empty")
		else: # Check that the value of this variable is either True or False
			if str(self.replaceTiprack).lower() == "false" or self.replaceTiprack in [0, False]:
				self.replaceTiprack = False
			elif str(self.replaceTiprack).lower() == "true" or self.replaceTiprack in [1, True]:
				self.replaceTiprack = True
			else:
				raise Exception("Replace Tipracks variable value needs to be True or False, it cannot be empty")
		
		# Check that there are only as many values as number of final plates for the variables Name Sheet Map Reagents, Name Sheet Map Volumes and Type of Pipette to Create Plate
		if any(pd.isna(elem) == True for elem in self.nameSheetReagents[:self.numberFinalPlates]) or any(pd.isna(elem) == False for elem in self.nameSheetReagents[self.numberFinalPlates:]):
			raise Exception("The values of 'Name Sheet Map Reagents' need to be as many as the 'Number of Final Plates' and be in consecutive columns")
		else: # Let's check that the reagents maps are in the excel
			for name_reagent_sheet in self.nameSheetReagents[:self.numberFinalPlates]:
				if name_reagent_sheet not in self.infoPagesWellsCombinatioMaps:
					raise Exception(f"The 'Name Sheet Map Reagents' {name_reagent_sheet} sheet does not exist in the variable excel file")
		
		if any(pd.isna(elem) == True for elem in self.nameSheetVolumes[:self.numberFinalPlates]) or any(pd.isna(elem) == False for elem in self.nameSheetVolumes[self.numberFinalPlates:]):
			raise Exception("The values of 'Name Sheet Map Volumes' need to be as many as the 'Number of Final Plates' and be in consecutive columns")
		else: # Let's check that the reagents maps are in the excel
			for name_volumes_sheet in self.nameSheetReagents[:self.numberFinalPlates]:
				if name_volumes_sheet not in self.infoPagesWellsCombinatioMaps:
					raise Exception(f"The 'Name Sheet Map Volumes' {name_volumes_sheet} sheet does not exist in the variable excel file")

		if any(pd.isna(elem) == True for elem in self.pipetteCreationPlate[:self.numberFinalPlates]) or any(pd.isna(elem) == False for elem in self.pipetteCreationPlate[self.numberFinalPlates:]):
			raise Exception("The values of 'Type of Pipette to Create Plate' need to be as many as the 'Number of Final Plates' and be in consecutive columns")
		else: # We are going to check as well that their value is an appropiate one
			for value_pipette in self.pipetteCreationPlate[:self.numberFinalPlates]:
				if value_pipette not in ["single","multi"]:
					raise Exception("The values of 'Type of Pipette to Create Plate' in FinalPlatesVariables can only be 'single' if the plate and its replicas are going to be created with a single-channel pipette or 'multi' if they are created by a multi-channel pipette")

		# Check that there are no values of 'Number of Replicas' in columns at the right of the last column that is going to be read
		if any(pd.isna(elem) == False for elem in self.numberReplicas[self.numberFinalPlates:]):
			raise Exception("The values of 'Number of Replicas' can be as many as the 'Number of Source Plates' and in consecutive columns, if empty, it is considered that is the first well")
		else: # Now we just assigned a 0 to the ones that are going to be used and does not contain a value 
			for index_plate, number_replica in enumerate(self.numberReplicas[:self.numberFinalPlates]):
				if pd.isna(number_replica):
					self.numberReplicas[index_plate] = 0 # We assign no replica to do only the plate described
				elif type(self.numberReplicas[index_plate]) != int:
					raise Exception("The values of 'Number of Replicas' need to be either empty, in that case it is assumed to be 0, or a whole number")
			
			# If we have any plate that needs a replica, we need to perform an additional check in 
			if any(number_replicas > 0 for number_replicas in self.numberReplicas[:self.numberFinalPlates]):
				# Check what kind of replica is going to be performed (internal or external)
				if pd.isna(self.internalReplicas):
					self.internalReplicas = False
				elif self.internalReplicas in [True, 1] or str(self.internalReplicas) == "True":
					self.internalReplicas = True
				elif pd.isna(self.internalReplicas) or self.internalReplicas in [False, 0] or str(self.internalReplicas) == "False":
					self.internalReplicas = False
				else:
					raise Exception("'Internal Replicas' can only have 2 values: True or False. If left empty assumed as False")
			else: # No replicas are going to be generated, so we just fill it with a None value
				self.internalReplicas = None
		
		# The final plates are always going to be created, so we need to check that the labware exists always
		try:
			definition_final_plate = labware_context.get_labware_definition(self.APINameIncubationPlate)
		except OSError: # This would be catching the FileNotFoundError that happens when a labware is not found
			raise Exception(f"The final plate labware {self.APINameIncubationPlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
		
		# We define some characteristic of the final plate for future uses in the script such as checking if the internal replicas fit in the final labware
		self.dimensionsFinalLabware = {"row":len(definition_final_plate["ordering"][0]), "columns":len(definition_final_plate["ordering"])}

		self.maxVolumeFinalWell = list(definition_final_plate["wells"].items())[0][1]['totalLiquidVolume']
		
		# Check the values of the variables that will determine which checks are done after depending if a final plate is going to be created with a single or multi channel pipette
		if any(pd.isna(elem) == True for elem in self.pipetteCreationPlate[:self.numberFinalPlates]):
			raise Exception("The values of 'Type of Pipette to Create Plate' need to be as many as the 'Number of Final Plates' and placed in consecutive columns")
		else: # We are going to check as well that their value is an appropiate one and if the needed variables are there
			for value_pipette in self.pipetteCreationPlate[:self.numberFinalPlates]:
				if value_pipette not in ["single","multi"]:
					raise Exception("The values of 'Type of Pipette to Create Plate' in FinalPlatesVariables can only be 'single' if the plate and its replicas are going to be created with a single-channel pipette or 'multi' if they are created by a multi-channel pipette")
			
			# Check that all the variables needed to perform the protocol with a single-channel are defined
			if any(elem == 'single' for elem in self.pipetteCreationPlate[:self.numberFinalPlates]):
				# We need to have the name of teh labware and the type of tubes it has
				if pd.isna(self.APINameFalconPlate) or pd.isna(self.typeTubesReagents):
					raise Exception("If one of the values of 'Type of Pipette to Create Plate' is 'single', both 'API Name Labware with Reagent(s) in Tube(s)' and 'Type of Reagent Tube' cannot be left empty")
				else:
					# Check that the labware exists
					try:
						definition_labware_tubes_reagents = labware_context.get_labware_definition(self.APINameFalconPlate)
					except:
						raise Exception(f"The labware {self.APINameFalconPlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

					# Check that Type of Reagent Tube has an adecuate value
					if self.typeTubesReagents not in ["falcon", "eppendorf"]:
						raise Exception("Right now this LAP entry only accepts labwares for storing the reagent tubes that are 15 or 50mL falcons or eppendorfs so the only values accepted in 'Type of Reagent Tube' are 'falcon' or 'eppendorf'")

					# Check that the falcons are 15 or 50mL because they are the only one that it accepts
					if self.typeTubesReagents == "falcon" and (list(definition_labware_tubes_reagents["wells"].values())[0]["totalLiquidVolume"] not in [15000, 50000]):
						raise Exception("Right now this LAP entry only accepts labwares for storing the reagent tubes that are 15 or 50mL falcons or eppendorfs")

					# Check that the falcon is not mixed, in other words, that only will have one type of falcon
					if len(definition_labware_tubes_reagents["groups"]) > 1:
						raise Exception("The labware defined in 'Type of Reagent Tube' rack needs to have only 1 type of tube admitted. Tube racks such as 'Opentrons 10 Tube Rack with Falcon 4x50 mL, 6x15 mL Conical' are not valid")

					# Store the maximum volume of the tube and the number of tubes we can establish in 1 labware to use when the number of tubes and locations of the reactives are going to be set 
					self.maxVolumeTubeReagent = list(definition_labware_tubes_reagents["wells"].items())[0][1]['totalLiquidVolume']
					
					self.numberTubesLabware = len(definition_labware_tubes_reagents["wells"])

			# Check that all the variables needed to perform the protocol with a multi-channel are defined
			if any(elem == 'multi' for elem in self.pipetteCreationPlate[:self.numberFinalPlates]):
				# We need to know the name of the labware that is going to be acting as the storage of the reagents
				if pd.isna(self.APINameReservoirPlate):
					raise Exception("If one of the values of 'Type of Pipette to Create Plate' is 'multi', 'API Name Labware with Reagents(s) in Plate(s)' cannot be left empty")
				else:
					# Check that the labware exists
					try:
						definition_labware_plate_reagents = labware_context.get_labware_definition(self.APINameReservoirPlate)
					except:
						raise Exception(f"The labware {self.APINameReservoirPlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

					# Check that has some minimal positions so the multi can work with it. We need one or 8 rows because we are only going to accept multi-channels of 8 channels
					if any(len(column) != 8 for column in definition_labware_plate_reagents["ordering"]) and any(len(column) != 1 for column in definition_labware_plate_reagents["ordering"]):
						raise Exception("The labware defined in 'API Name Labware with Reagents(s) in Plate(s)' need to have columns that have either only 1 well or 8 wells, that way it can be accessed successfully with the 8-channel pipette. Other labware layout is not permited yet in this LAP")

					# Check that the reservoir is not mixed, in other words, that only will have one type of well
					if len(definition_labware_plate_reagents["groups"]) > 1:
						raise Exception("The labware defined in 'API Name Labware with Reagents(s) in Plate(s)' rack needs to have only 1 type of well")
					
					# Check that the final labware has 1 or 8 rows so the multi channel can transfer it correctly
					if any(len(column) != 8 for column in definition_final_plate["ordering"]) and any(len(column) != 1 for column in definition_final_plate["ordering"]):
						raise Exception("If final plates are going to be created with multi-channel pipettes the labware defined in 'API Name Final Plate' need to have columns that have either only 1 well or 8 wells, that way it can be accessed successfully with the 8-channel pipette.\nOther labware layout is not allowed yet in this LAP")
				
					# We store the maximum volume of the reservoir labware and its dimensions for future checks and setting the number and positions of needed columns of reagents
					self.maxVolumeWellReservoirPlate = list(definition_labware_plate_reagents["wells"].items())[0][1]['totalLiquidVolume']

					self.dimensionsLabwareReservoir = {"row":len(definition_labware_plate_reagents["ordering"][0]), "columns":len(definition_labware_plate_reagents["ordering"])}

				# Depending on the dimensions of teh reservoir, we can set the optimization as high or not
				# If the labware only has rows, the optimization wont be powerful because only one reagent per column can be stored
				if self.dimensionsLabwareReservoir["row"] == 1:
					self.sourceOptimization = "low"
				elif self.dimensionsLabwareReservoir["row"] != 1 and pd.isna(self.sourceOptimization):
					raise Exception("If one of the values of 'Type of Pipette to Create Plate' is 'multi' and the labware defined in 'API Name Labware with Reagents(s) in Plate(s)' have more than 1 row, 'Optimization Space Source Plate Reagents Disposition' cannot be left empty")
				else:
					if self.sourceOptimization not in ["high","low"]:
						raise Exception("The variable 'Optimization Space Source Plate Reagents Disposition' in sheet 'General Variable' can only accept 2 values: low and high. For more information about the behaviour of each value check the LAPentry resources")
		
		# Check the pipettes
		# Check that there is at least 1 pipette to perform the protocol
		if pd.isna(self.APINamePipL) and pd.isna(self.APINamePipR):
			raise Exception("At least 1 pipette is needed to perform this protocol")

		# Check that if the pipette is not empty, neither the tiprack or the initial pipette should not be empty
		if not pd.isna(self.APINamePipL) and (pd.isna(self.startingTipPipL) or pd.isna(self.APINameTipL)):
			raise Exception("If the variable 'API Name Left Pipette' has a value, both 'API Name Tiprack Left Pipette' and 'Initial Tip Left Pipette' need to be filled")
		
		if not pd.isna(self.APINamePipR) and (pd.isna(self.startingTipPipR) or pd.isna(self.APINameTipR)):
			raise Exception("If the variable 'API Name Right Pipette' has a value, both 'API Name Tiprack Right Pipette' and 'Initial Tip Right Pipette' need to be filled")
		
		# In case the pipettes names are empty we establish the variables attached to it as None
		if pd.isna(self.APINamePipL):
			self.startingTipPipL = None
			self.APINameTipL = None

		if pd.isna(self.APINamePipR):
			self.startingTipPipR = None
			self.APINameTipR = None

		# Check that if the tipracks are the same, the initial tips should be the same as well so there are no inconsistencies when trying to pick up a tip
		if not pd.isna(self.APINamePipL) and not pd.isna(self.APINamePipR):
			if self.APINameTipL == self.APINameTipR:
				if self.startingTipPipL != self.startingTipPipR:
					raise Exception("If the tipracks of the right and left mount pipettes are the same, the initial tip should be as well.")
		
		# Now we check if the tipracks of each pipette exist and if the first tip actually exists in those tipracks
		# As well, we are going to define here the maximum volume of the tips because the max volume of a pipette and a tip doesnt have to be equal always and it 
		# is important to know which is the max volume it can be transfered with only 1 movement
		if pd.isna(self.APINamePipR) == False:
			try:
				definition_tiprack_right = labware_context.get_labware_definition(self.APINameTipR)
			except:
				raise Exception(f"The tiprack defined in 'API Name Right Pipette TipRack' {self.APINameTipR} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
			# Check if there is any typo in the starting tip of both pipettes
			if self.startingTipPipR not in definition_tiprack_right["wells"].keys():
				raise Exception("Starting tip of right pipette is not valid, check for typos")
			# Add the volume of the pipette to the max volume in case it is the smaller one
			self.maxVolumeTiprackPipetteR = list(definition_tiprack_right["wells"].items())[0][1]['totalLiquidVolume']

		if pd.isna(self.APINamePipL) == False:
			try:
				definition_tiprack_left = labware_context.get_labware_definition(self.APINameTipL)
			except:
				raise Exception(f"The tiprack defined in 'API Name Left Pipette TipRack' {self.APINameTipL} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
			# Check if there is any typo in the starting tip of both pipettes
			if self.startingTipPipL not in definition_tiprack_left["wells"].keys():
				raise Exception("Starting tip of left pipette is not valid, check for typos")
			# Add the volume of the pipette to the max volume in case it is the smaller one
			self.maxVolumeTiprackPipetteL = list(definition_tiprack_left["wells"].items())[0][1]['totalLiquidVolume']
		
		# Check the values of touch tip
		if pd.isna(self.touchTipDistributeMedia):
			self.touchTipDistributeMedia = False
		elif self.touchTipDistributeMedia in [True, 1] or str(self.touchTipDistributeMedia) == "True":
			self.touchTipDistributeMedia = True
		elif pd.isna(self.touchTipDistributeMedia) or self.touchTipDistributeMedia in [False, 0] or str(self.touchTipDistributeMedia) == "False":
			self.touchTipDistributeMedia = False
		else:
			raise Exception("'Touch Tip After Dispense' can only have 2 values: True or False. If left empty assumed as False")

		# Check the values of Change Tip In Distribution
		if pd.isna(self.changeTipDistribute):
			self.changeTipDistribute = "well"
		elif self.changeTipDistribute not in ["never", "reagent", "aspirate", "well"]:
			raise Exception("'Change Tip In Distribution' can only have 4 values: never, reagent, aspirate, well. If left empty, 'well' value will be assumed.\nFor the behaviour with each argument check the manual of this LAP entry")

		# Check the position where the volume is going to be dispensed
		if pd.isna(self.positionDistributeMedia):
			self.positionDistributeMedia = "bottom"
		elif self.positionDistributeMedia not in ["top", "bottom", "center"]:
			raise Exception("'Position Dispense Final Well' can only have 3 values: top, bottom or center. If left empty, 'bottom' value will be assumed.\nFor the behaviour with each argument check the manual of this LAP entry")
		
		# Let's check that the dimensions of the final labware is the same one as the maps of volumes and reagents
		# We are going to define the following variables to not repeat the treatment and check of the same sheet
		# This is perform because 2 different plates can have the same Reagent, volume map or both
		sheets_already_checked = []

		# Lets loop over all the columns in FinalPlatesVariables
		for index_plate, (reagents_sheet, volumes_sheet) in enumerate(zip(self.nameSheetReagents[:self.numberFinalPlates], self.nameSheetVolumes[:self.numberFinalPlates])):
			# We are going to first going to read the values of the dataframes and treat them so we have in each cell a list of reactives or a list of volumes to be transferred
			# Check if the reagent sheet has already been checked and treated
			if reagents_sheet not in sheets_already_checked:
				# We establish the name of the rows of the labware as the first column
				name_rows_reagents = self.infoPagesWellsCombinatioMaps[reagents_sheet].iloc[:, 0].values
				# We extract from the column names the names of the labware's columns
				name_columns_reagents = self.infoPagesWellsCombinatioMaps[reagents_sheet].columns.values[1:]
				# We create the names of all the wells by combining the row names with the column names
				name_wells_reagents = [row + column for row in name_rows_reagents for column in name_columns_reagents]

				# We check that all the wells of the final plate labware are defined in the sheet and with the appropiate names
				if set(name_wells_reagents) != definition_final_plate["wells"].keys():
					raise Exception(f"Either the row or column names of the Sheet '{reagents_sheet}' does not concur with the names of the rows and columns of the labware with the API name '{self.APINameIncubationPlate}'.\nRemember that the first column of the sheet is going to be assumed to be the name of the rows and the first column as the name of the columns. Even if wells are empty, the layout of the plate needs to be defined.\nFor an example of a layout, check the available example files in the LAP entry")

				# After the check we establish the name of the rows as the index
				self.infoPagesWellsCombinatioMaps[reagents_sheet].set_index(self.infoPagesWellsCombinatioMaps[reagents_sheet].columns[0], inplace = True)

				# Now we transform each cell to a list of strings that will be the name of the reagents
				self.infoPagesWellsCombinatioMaps[reagents_sheet] = self.infoPagesWellsCombinatioMaps[reagents_sheet].applymap(lambda x: UserVariables.convert_sheet(x, "reactive", reagents_sheet))

				sheets_already_checked.append(reagents_sheet)
			
			# Now we check the volume sheet
			if volumes_sheet not in sheets_already_checked:
				# We establish the name of the rows of the labware as the first column
				name_rows_volumes = self.infoPagesWellsCombinatioMaps[volumes_sheet].iloc[:, 0].values
				
				# We extract from the column names the names of the labware's columns
				name_columns_volumes = self.infoPagesWellsCombinatioMaps[volumes_sheet].columns.values[1:]
				
				# We create the names of all the wells by combining the row names with the column names
				name_wells_volumes = [row + column for row in name_rows_volumes for column in name_columns_volumes]
				
				# We check that all the wells of the final plate labware are defined in the sheet and with the appropiate names
				if set(name_wells_volumes) != definition_final_plate["wells"].keys():
					raise Exception(f"Either the row or column names of the Sheet '{volumes_sheet}' does not concur with the names of the rows and columns of the labware with the API name '{self.APINameIncubationPlate}'.\nRemember that the first column of the sheet is going to be assumed to be the name of the rows and the first column as the name of the columns. Even if wells are empty, the layout of the plate needs to be defined.\nFor an example of a layout, check the available example files in the LAP entry")		
				
				# After the check we establish the name of the rows as the index
				self.infoPagesWellsCombinatioMaps[volumes_sheet].set_index(self.infoPagesWellsCombinatioMaps[volumes_sheet].columns[0], inplace = True)
				
				# Now we transform each cell to a list of number that will be the volumes to transfer
				self.infoPagesWellsCombinatioMaps[volumes_sheet] = self.infoPagesWellsCombinatioMaps[volumes_sheet].applymap(lambda x: UserVariables.convert_sheet(x, "volume", reagents_sheet))
				
				# Let's check that the sum of the volumes in each cell is not superior to the max volume of the final labware
				# This applymap is going to check only the lists
				result_sum_volumes = self.infoPagesWellsCombinatioMaps[volumes_sheet].applymap(lambda x: sum(x) <= self.maxVolumeFinalWell if isinstance(x, list) else True)

				# Lets extract the cells that excede that volume and drop the empty values (th evalues that does not exceed the volume or are not a list)
				more_max_volume = result_sum_volumes[result_sum_volumes == False].dropna(how = "all")

				if not more_max_volume.empty: # If it is not empty it means that some value exceeds the self.maxVolumeFinalWell
					well_names = [(index, col) for index, col in more_max_volume.stack().index]
					well_names_str = ', '.join([f"{row}{col}" for row, col in well_names])
					raise Exception(f"Sum of volumes in the following cells of Sheet {volumes_sheet} exceeds the maximum volume of the final labware wells: {well_names_str}")
				
				sheets_already_checked.append(volumes_sheet)

			# The fact that individually the sheets are correct does not mean that they match
			# Now we are going to do the checks of the pairs reagents_sheet and volumes_sheet
			for name_column in name_columns_reagents:
				for volumes_well, reagents_well in zip(self.infoPagesWellsCombinatioMaps[volumes_sheet][name_column], self.infoPagesWellsCombinatioMaps[reagents_sheet][name_column]):
					# Check that there are either NaN in the same cells for both dataframes or some value
					if not isinstance(reagents_well, list) and not isinstance(volumes_well, list): # We have NaN for both cells so we dont need to check anything
						continue
					elif not isinstance(reagents_well, list) or not isinstance(volumes_well, list):
						raise Exception(f"The sheets '{reagents_sheet}' and '{volumes_sheet}' for plate '{self.nameFinalPlates[index_plate]}' must have matching cells with values. Each cell with a value in one sheet must have a corresponding value in the same cell of the other sheet")
					
					# Check that there are no duplicates on the reagents well
					if len(reagents_well) != len(set(reagents_well)):
						raise Exception(f"Column '{name_column}' in sheet '{reagents_sheet}' has a cell with a duplicate reagent. While reagents can repeat in the column, each cell must list each reagent only once. Combine the duplicate entries in that cell and rerun the program")

					# Check that no reagents are called None
					if "None" in reagents_well:
						raise Exception(f"No name of a reagent can be called 'None' and that is teh case in {reagents_sheet}, rename the reactive and run the program again")

					# Check if there is the same ammount of reagents as volumes in teh same cell
					if len(volumes_well) != len(reagents_well):
						raise Exception(f"The sheets '{reagents_sheet}' and '{volumes_sheet}' for plate '{self.nameFinalPlates[index_plate]}' must have matching number of elements in each cells with values. Each cell with a value in one sheet must have the same number of reagents as volumes in the same cell of the other sheet")

					# Check if there is any 0 for some wells for the volume
					if any(volume <= 0 for volume in volumes_well):
						raise Exception(f"There is a well in sheet {volumes_sheet} that is lower or equal to 0")

				# Now that we have checked that the sheets are correctly filled and coherent within them let's check if they can be done with the multi-channel pipettes, in case it is set like that
				# These requirements are additional to the previous ones and dont need to be met if the pipette that is going to create the plate is a single channel
				if self.pipetteCreationPlate[index_plate] == "multi":
					# Depending on the reservoir dimensions (columns and rows), different requirements need to be met
					# If the pipette that is going to create the plate is a multi-channel, the combination of volumes of a column needs to be the same
					# This comes from the fact that we need to dispense the same volume to all final wells with this king of pipettes
					if self.dimensionsLabwareReservoir["row"] != 1:
						# If the reservoir has more than 1 row per column, it can have different combination reagent-volumes, but needs to have same combination of volumes all over the column
						# We drop the non empty values because they will be assumed as a reagent itself
						volumes_without_na_or_duplicates = self.infoPagesWellsCombinatioMaps[volumes_sheet].dropna(subset=[name_column])[name_column]
						volumes_without_na_or_duplicates = volumes_without_na_or_duplicates.apply(tuple)

						# We extract the different set of volumes inside a column
						unique_combination_of_volumes = volumes_without_na_or_duplicates.apply(tuple).unique()

						# There should be only 1 set of volumes per column
						if len(unique_combination_of_volumes) != 1 and any(sorted(val) != sorted(unique_combination_of_volumes[0]) for val in unique_combination_of_volumes[1:]):
							raise Exception(f"Plate '{self.nameFinalPlates[index_plate]}' will be created with a multi-channel pipette. Each column in the sheet specified by 'Name Sheet Map Volumes' must have identical volume combinations or be empty. The map '{volumes_sheet}' does not meet these requirements")
					elif self.dimensionsLabwareReservoir["row"] == 1: 
						# If the reservoir only has 1 row all the reagents of a set (column-volume) need to be the same because we dont have the ability to create a mix column in addition to have the same combination of volumes
						# Check if all values are non-empty or all values are NaN,
						if self.infoPagesWellsCombinatioMaps[volumes_sheet][name_column].notna().all() and self.infoPagesWellsCombinatioMaps[reagents_sheet][name_column].notna().all():
							# We are only going to check the values if there are values in the column
							# First we check that the combination of volumes or reagents within the same column is the same
							values_column_vol = self.infoPagesWellsCombinatioMaps[volumes_sheet][name_column]
							values_column_reagent = self.infoPagesWellsCombinatioMaps[reagents_sheet][name_column]
							if any(frozenset(volumes) != frozenset(values_column_vol[0]) for volumes in values_column_vol):
								raise Exception(f"Plate '{self.nameFinalPlates[index_plate]}' will be created with a multi-channel pipette and from a plate that only has 1 well per column. Each column in the sheet specified by 'Name Sheet Map Volumes' must have identical volume combinations. The map '{volumes_sheet}' does not meet these requirements")
							if any(frozenset(reactives) != frozenset(values_column_reagent[0]) for reactives in values_column_reagent):
								raise Exception(f"Plate '{self.nameFinalPlates[index_plate]}' will be created with a multi-channel pipette and from a plate that only has 1 well per column. Each column in the sheet specified by 'Name Sheet Map Reagents' must have identical reagent combinations. The map '{reagents_sheet}' does not meet these requirements")

							# Now that we know that all of the reagents and voluemes are equal between themself, we check that between the 2 colums are the same
							set_reagent_volumes = set(list(zip(values_column_reagent[0], values_column_vol[0])))
							for components_reactives, components_volumes in zip(values_column_reagent, values_column_vol):# Check that the combination of the voluems it is the same along the entire column
								if set(list(zip(components_reactives, components_volumes))) != set_reagent_volumes:
									raise Exception(f"Plate '{self.nameFinalPlates[index_plate]}' will be created with a multi-channel pipette and from a plate that only has 1 well per column. Each column in the sheet specified by 'Name Sheet Map Reagents' and 'Name Sheet Map Volumes' must have identical reagent-volume combinations")
						elif self.infoPagesWellsCombinatioMaps[volumes_sheet][name_column].isna().all() and self.infoPagesWellsCombinatioMaps[reagents_sheet][name_column].isna().all(): # All of the values are empty in this column so it does not need to be checked
							continue
						else: # This means that there is at least one column that has mixed values
							raise Exception(f"Columns in map {reagents_sheet} or {volumes_sheet} has mixed values of NaN and non-empty.")

		return

class SettedParameters:
	"""
	Class that will use the variables set in UserVariables and calculate and extract other variables that are going to be used during the prorgam run
	"""
	def __init__(self):
		"""
		Initilizing the class with all th evariables that are going to be filled when assign_variables is called
		
		This class is going to contain the information of the final plates, the tubes and colums that are going to be used to transfer liquid to them
		that are contained in falcon/eppendorf tubes or columns of reservoirs, respectivelly

		As well, this class is going to contain the pipettes set by the user
		"""

		self.finalPlates = {}
		self.neededColumnsMulti = {}
		self.antibioticWells = {} # These are not antibiotics, they can be any type of reactives but it has this name so I can reuse code from LAP-CellMediaInoculation-OT2-1.0.0
		self.colors_mediums = []
		self.reactives_with_color = [] # This is a variable to hold the different reagents in case the same reagent is used in plates created by a single and a multi channel pipette
		self.color_info_reactives = {}
		self.reagentTubesLabware = {}
		self.reagentColumnLabware = {}

		self.pipR = None
		self.pipL = None
		self.sameTipRack = None

	def assign_variables(self, user_variables, protocol):
		# Pipette Variables
		if pd.isna(user_variables.APINamePipL) == False:
			self.pipL = protocol.load_instrument(user_variables.APINamePipL, mount = "left")
			if self.pipL.channels not in [1,8]:
				raise Exception(f"The pipettes for this protocol need to have either 1 or 8 channels. The pipette established in 'Name Left Pipette' has {self.pipL.channels} channels")
			# Add the volume of the pipette to the max volume in case it is the smaller one
			if user_variables.maxVolumeTiprackPipetteL > self.pipL.max_volume:
				user_variables.maxVolumeTiprackPipetteL = self.pipL.max_volume
		else:
			# Establish all the variables set to the left pipette as none
			user_variables.APINameTipL = None
			user_variables.startingTipPipL = None
		
		if pd.isna(user_variables.APINamePipR) == False:
			self.pipR = protocol.load_instrument(user_variables.APINamePipR, mount = "right")
			if self.pipR.channels not in [1,8]:
				raise Exception(f"The pipettes for this protocol need to have either 1 or 8 channels. The pipette established in 'Name Right Pipette' has {self.pipR.channels} channels")
			# Add the volume of the pipette to the max volume in case it is the smaller one
			if user_variables.maxVolumeTiprackPipetteR > self.pipR.max_volume:
				user_variables.maxVolumeTiprackPipetteR = self.pipR.max_volume
		else:
			# Establish all the variables set to the right pipette as none
			user_variables.APINameTipR = None
			user_variables.startingTipPipR = None
		
		if user_variables.APINameTipR == user_variables.APINameTipL:
			self.sameTipRack = True
		else:
			self.sameTipRack = False

		# Now that we have loaded the pipettes we can check if the plates can be done knowing that at least 1 pipette is set (if thas been checked in UserVariables)
		if any(elem == 'multi' for elem in user_variables.pipetteCreationPlate[:user_variables.numberFinalPlates]):
			if ((self.pipR != None and self.pipR.channels != 8) and (self.pipL != None and self.pipL.channels != 8)) or (self.pipR == None and self.pipL.channels != 8) or (self.pipL == None and self.pipR.channels != 8):
				raise Exception("At least one value of the variable 'Type of Pipette to Create Plate' has been established as 'multi' so at least 1 pipette is required to have 8 channels")

		if any(elem == 'single' for elem in user_variables.pipetteCreationPlate[:user_variables.numberFinalPlates]):
			if ((self.pipR != None and self.pipR.channels != 1) and (self.pipL != None and self.pipL.channels != 1)) or (self.pipR == None and self.pipL.channels != 1) or (self.pipL == None and self.pipR.channels != 1):
				raise Exception("At least one value of the variable 'Type of Pipette to Create Plate' has been established as 'single' so at least 1 pipette is required to have 1 channel")

		# Now we are going to create the entries for the final plate(s) to create set by the user
		for index_plate, name_final_plate in enumerate(user_variables.nameFinalPlates[:user_variables.numberFinalPlates]):
			
			# We wil fill this maps after setting the labware
			# Initialize all the variables that are going to be used in the script
			self.finalPlates[name_final_plate] = {
				"Position":None,
				"Label":user_variables.nameFinalPlates[index_plate],
				"Opentrons Place":None,
				"Map React":user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[index_plate]],
				"Map Vol":user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetVolumes[index_plate]],
				"Pipette Creation":user_variables.pipetteCreationPlate[index_plate],
				"Number Replicas": user_variables.numberReplicas[index_plate],
				"Plates Replicas":{},
				"Last Column With Value": user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[index_plate]].columns.tolist().index(user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[index_plate]].apply(lambda col: col.last_valid_index()).last_valid_index()),
				"Last Row With Value in Last Column": None,
				"Wells Needed for the Plate Layout": None,
												  }
			self.finalPlates[name_final_plate]["Last Row With Value in Last Column"] = user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[index_plate]].index.tolist().index(user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[index_plate]].iloc[:, self.finalPlates[name_final_plate]["Last Column With Value"]].last_valid_index())
			self.finalPlates[name_final_plate]["Wells Needed for the Plate Layout"] = ((self.finalPlates[name_final_plate]['Last Column With Value']+1)*user_variables.dimensionsFinalLabware['row'])-(user_variables.dimensionsFinalLabware['row']-(self.finalPlates[name_final_plate]['Last Row With Value in Last Column']+1))
			
			# Add the plates with replicas in case that they are needed
			if not user_variables.internalReplicas:
				for number_replica in range(self.finalPlates[name_final_plate]["Number Replicas"]):
					self.finalPlates[name_final_plate]["Plates Replicas"][f'{name_final_plate}_{number_replica}'] = None # Initialize and the plate will be added when the source plate are going to be
		
		# In case some plate is going to be created with the single channel pipette we are going to calculate how much volume is needed of each reagent
		if any(pipette == "single" for pipette in user_variables.pipetteCreationPlate):
			# Before doing more assigns I will get the ids of the cells of the final labware that is going to be used in case there are internal replicas
			# All the plates are going to have the same well names because they are the same labware
			final_plate_cells_ids = [f"{row}{col}" for col in user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[0]].columns for row in user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[0]].index]

			# If the pipette that is going to create the plate is not a single, we dont check anything and directly go to the next one
			for index_plate, name_plate in enumerate(user_variables.nameFinalPlates[:user_variables.numberFinalPlates]):
				if user_variables.pipetteCreationPlate[index_plate] == "multi": # SWe conly go throught this for loop if the final plate is going to be created with a single-channel pipette
					continue
				
				# Check if the number of internal replicas fit in the labware
				if user_variables.numberReplicas[index_plate] > 0 and user_variables.internalReplicas == True:
					if self.finalPlates[name_plate]["Wells Needed for the Plate Layout"]*(user_variables.numberReplicas[index_plate]+1) > (user_variables.dimensionsFinalLabware["row"]*user_variables.dimensionsFinalLabware["columns"]):
						raise Exception(f"The number of internal replicas ({user_variables.numberReplicas[index_plate]}) for plate '{name_plate}' does not fit in the labware '{user_variables.APINameIncubationPlate}'. Empty cells or columns are maintained during replication. Consider removing them or setting 'Internal Replicas' to False to create a separate plate for each replica")
				
				# Let's check the min volume between the set single channel pipettes and check that all volumes can be transfered with them
				if (self.pipR != None and self.pipR.channels == 1) and (self.pipL != None and self.pipL.channels == 1):
					if self.pipR.min_volume < self.pipL.min_volume:
						threshold = self.pipR.min_volume
					else:
						threshold = self.pipL.min_volume
				elif self.pipL != None and self.pipL.channels == 1:
					threshold = self.pipL.min_volume
				elif self.pipR != None and self.pipR.channels == 1:
					threshold = self.pipR.min_volume
				else:
					raise Exception("At least one of the final plates is going to be created with a single-channel pipette and no single-channel pipettes are established")

				try:
					user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetVolumes[index_plate]].applymap(lambda x: SettedParameters.check_volumes_with_pipettes(x, threshold))
				except ValueError:
					raise Exception(f"One of the volumes of the plate {name_plate} cannot be picked with the established single-channel pipette(s), the minimum volume able to be picked with the given pipette(s) combination is {threshold}ul")
				
				# Now that we know everything can be transfered we assign the voluems and positions that each reagent is going to be transfered to
				for (index1, row1), (index2, row2) in zip(user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[index_plate]].iterrows(), user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetVolumes[index_plate]].iterrows()):
					for (column1, value1),(column2, value2) in zip(row1.items(), row2.items()):
						if isinstance(value1, list) and isinstance(value2, list): # We just check the values if they are a list (if they ar enot that means that the cell is empty)
							# We go through each value in that cell
							for reactive, volume in zip(value1, value2):
								if reactive in self.antibioticWells.keys(): # In case the reagent has been already set, we just add the values
									self.antibioticWells[reactive]["Positions"][name_plate].append(index1+column1) # Add the well to the positions that the reagent is going to go
									self.antibioticWells[reactive]["Volumes/Position"][name_plate].append(volume) # And also the volume
								else: # If the reagent is not defined already, we do it now that is has appeared
									# Initialized it
									self.antibioticWells[reactive] = {
										"Positions":{},
										"Volumes/Position":{},
										"Volumes Per Tube":[],
										"Reactions Per Tube":[],
										"Position Tubes":[]}
									
									# Create an entry in Positions for each possible final plate
									for final_plate in user_variables.nameFinalPlates[:user_variables.numberFinalPlates]:
										if final_plate == name_plate: # This is the plate that has called this reagent the first time so we add it
											self.antibioticWells[reactive]["Positions"][final_plate] = [index1+column1]
											self.antibioticWells[reactive]["Volumes/Position"][final_plate] = [volume]
										else: # Add the rest of the plates to the dictionary entry
											self.antibioticWells[reactive]["Positions"][final_plate] = []
											self.antibioticWells[reactive]["Volumes/Position"][final_plate] = []
										
										# As well, we add the plates that are external replicas to this dictionary (we will add the positions and volumes after)
										for replica_final_plate in  self.finalPlates[final_plate]["Plates Replicas"].keys():
											self.antibioticWells[reactive]["Positions"][replica_final_plate] = []
											self.antibioticWells[reactive]["Volumes/Position"][replica_final_plate] = []
									
									# Set the color info of this reactive
									self.color_info_reactives[reactive] = {}
									while True:
										color_liquid = f"#{random.randint(0, 0xFFFFFF):06x}"
										if color_liquid.lower() not in self.colors_mediums:
											self.color_info_reactives[reactive]["Definition Liquid"] = protocol.define_liquid(
												name = f"{reactive}",
												description = f"Medium {reactive}",
												display_color = color_liquid
											)
											self.colors_mediums.append(color_liquid)
											break
								
								# Now we add the wells of the replicas in case there are distinguising if they are internal or external replicas
								if user_variables.numberReplicas[index_plate] > 0:
									for replica in range(user_variables.numberReplicas[index_plate]):
										if user_variables.internalReplicas:
											self.antibioticWells[reactive]["Positions"][name_plate].append(final_plate_cells_ids[final_plate_cells_ids.index(index1+column1)+((replica+1)*self.finalPlates[name_plate]["Wells Needed for the Plate Layout"])])
											self.antibioticWells[reactive]["Volumes/Position"][name_plate].append(volume)
										else:
											self.antibioticWells[reactive]["Positions"][list(self.finalPlates[name_plate]["Plates Replicas"].keys())[replica]].append(index1+column1)
											self.antibioticWells[reactive]["Volumes/Position"][list(self.finalPlates[name_plate]["Plates Replicas"].keys())[replica]].append(volume)

		# In case some plate is going to be created with the multi channel pipette we are going to calculate how much volume is needed of each needed column type
		if any(pipette == "multi" for pipette in user_variables.pipetteCreationPlate):
			columns_final_plate = user_variables.infoPagesWellsCombinatioMaps[user_variables.nameSheetReagents[0]].columns.tolist()
			plates_with_multi = {}

			# We are going to loop over all of the plates and if some is going to be created with a multi we check that the volumes can be transfer and extract the last column and well with a value
			for index_plate, (name_plate, plate_info) in enumerate(self.finalPlates.items()):
				if plate_info["Pipette Creation"] == "multi":
					# Check the min volume that a set multi-channel pipette can transfer
					if (self.pipR != None and self.pipR.channels == 8) and (self.pipL != None and self.pipL.channels == 8):
						if self.pipR.min_volume < self.pipL.min_volume:
							threshold = self.pipR.min_volume
						else:
							threshold = self.pipL.min_volume
					elif self.pipL != None and self.pipL.channels == 8:
						threshold = self.pipL.min_volume
					elif self.pipR != None and self.pipR.channels == 8:
						threshold = self.pipR.min_volume
					else:
						raise Exception("At least one of the final plates is going to be created with a multi-channel pipette and no multi-channel pipettes are established")
					
					# Check that every volume can be transferred
					try:
						plate_info["Map Vol"].applymap(lambda x: SettedParameters.check_volumes_with_pipettes(x, threshold, number_rows = user_variables.dimensionsFinalLabware["row"]))
					except ValueError:
						raise Exception(f"One of the volumes of the plate {name_plate} cannot be picked with the established multi-channel pipettes, the minimum volume able to be picked with the given pipette(s) combination is {threshold}ul.\nRemember that if the number of rows the final labware is 1 the volume what you have established in the wells is the total volume and it needs to be split in 8 to be tranferred with an 8-channel pipette and that can make it lower than the minimal volume possible")
					
					# Check if the internal replicas fit
					if user_variables.numberReplicas[index_plate] > 0 and user_variables.internalReplicas == True:
						if (plate_info["Last Column With Value"]+1)*(user_variables.numberReplicas[index_plate]+1) > user_variables.dimensionsFinalLabware["columns"]:
							raise Exception(f"The number of internal replicas ({user_variables.numberReplicas[index_plate]}) for plate '{name_plate}' does not fit in the labware '{user_variables.APINameIncubationPlate}'. Empty cells or columns are maintained during replication. Consider removing them or setting 'Internal Replicas' to False to create a separate plate for each replica")
					
					# Put the information in the multi data table that is going to be used after to get all the combination of column needed to perform this protocol
					plates_with_multi[name_plate] = plate_info
			
			# Initialize the object that is goign to be used for the combination of columns needed to do this protocol
			self.neededColumnsMulti = MultiChannelSourcePlates(plates_with_multi)
			
			# Depending on the optimization set from the user and the dimensions of the reservoir plate we are going to perform more or less actions to the MultiChannelSourcePlates object
			# When the columns are selected they are also tracked to what columns of the final plates are going to be holding the reagents from
			if user_variables.dimensionsLabwareReservoir["row"] != 1 and user_variables.sourceOptimization == "high":
				# Extract the columns that need to be there in a mandatory way because there is no combination of them
				self.neededColumnsMulti.initial_set()
				# Generate all the possible combinations of those columns or set within the columns that could be created
				self.neededColumnsMulti.generation_sets()
				# Score them in base of them matching with the columns in the initial_set and the other columns possibilities created in generation_sets
				self.neededColumnsMulti.scoring_sets()
				# The combination per set of possible columns per each final column is created until all final combination plates can be created with the columns defined in neededColumnsMulti
				self.neededColumnsMulti.seleccion_update()
			else: # Either the optimization is set as low or the number of rows of the reservoir is 1, which makes the high optimization pointless because 1 column can only have 1 reagent
				# Extract the columns that need to be there in a mandatory way because there is no combination of them
				self.neededColumnsMulti.initial_set()
				# If the possible reagents of each set can match the initial set they are selected to minimize space, otherwise, they are added as named in the reagent map
				self.neededColumnsMulti.low_opti_column_choosing()
			
			# Now that we have the needed source reagent columns we add the replcias of each final plate, in case that they are set and calculate how many columns of each source column will be needed
			# We just add the name of the column (in this case, teh first well, such as A1) because themovements are going to be by column
			for index_column, column_needed in self.neededColumnsMulti.sourceColumnsNeeded.items():
				plates_add = {}
				for plate, column_volume_transfer in column_needed["Final Columns"].items():
					if self.finalPlates[plate]["Number Replicas"] > 0:
						if user_variables.internalReplicas: # Internal replicas so we need to add it successively to the last column with a value
							columns_volumes_add = []
							for column, volume in column_volume_transfer:
								for number_replica in range(1, self.finalPlates[plate]["Number Replicas"] + 1):
									columns_volumes_add.append((str(columns_final_plate.index(column)+1+(number_replica*(self.finalPlates[plate]["Last Column With Value"]+1))), volume))
							self.neededColumnsMulti.sourceColumnsNeeded[index_column]["Final Columns"][plate] += columns_volumes_add
						else: # They are external replicas so we just copy the wells of the original plate
							for plate_replica_name in self.finalPlates[plate]["Plates Replicas"]: # We cannot change this dictionary while we loop it and that is why we will store all the changes and add them at the end
								plates_add[plate_replica_name] = column_volume_transfer
				
				if plates_add: # If tehre is something inside here is because there are external replicas that need to be added
					self.neededColumnsMulti.sourceColumnsNeeded[index_column]["Final Columns"].update(plates_add)

			# We are going to set the colors of the reagents in case that they are not already set on the single channel plates
			for column in self.neededColumnsMulti.sourceColumnsNeeded.values():
				for reactive in set(string for string in column["Reagents"] if string != "None"): # The reagent does not exist in the dictionary of colors
					if reactive not in self.color_info_reactives.keys():
						self.color_info_reactives[reactive] = {}
						while True:
							color_liquid = f"#{random.randint(0, 0xFFFFFF):06x}"
							if color_liquid.lower() not in self.colors_mediums:
								self.color_info_reactives[reactive]["Definition Liquid"] = protocol.define_liquid(
									name = f"{reactive}",
									description = f"Medium {reactive}",
									display_color = color_liquid
								)
								self.colors_mediums.append(color_liquid)
								break
		return

	def check_volumes_with_pipettes(list_volumes, min_volume_pip, number_rows = 8):
		"""
		This functions is going to be used to check that none of the values in list_volumes is smaller than min_volume_pip

		In our case, we are going to apply this to a whole dataframe of volumes to check that every value cna be transferred
		with the given pipettes
		
		If the pipette that is going to transfer the volumes is a multi-channel and the number of rows of the final plate is 1,
		the volume that is going to be transferred is divided by 8 (the number of channels) because the volume provided in list_volumes
		is the final volume, not the one that needs to be trasferred

		That is why number_rows shoudl ONLY be provided when the pipette is a multi-channel
		"""

		if isinstance(list_volumes, list):
			if number_rows == 1:
				list_volumes_final = [item/8 for item in list_volumes]
			else:
				list_volumes_final = list_volumes
			if any(item < min_volume_pip for item in list_volumes_final):
				raise ValueError(list_volumes)
		
		return

class MultiChannelSourcePlates():
	"""
	Class that will create an object that will find the needed source columns combinations to create the final plates, and depending on how
	high the optimization is set for the script, generate all possible combinations to perform a search of the most commons columns to try to minimize
	the use of columns in the reservoirs or just try to match the columns to the ones that are already set in the first mandatory set of columns

	In both cases, it will have at the end a set of combinations of different columns with the final wells/columns that they will source volume from
	when th eappropiate methods are called as it can be seen in the method assign_variables of the class SettedParameters
	"""

	def __init__ (self, dict_maps):
		self.sourceColumnsNeeded = {} # This will hold the needed source columns with their volumes and final columns to transfer from them
		self.combinationsPerFinalColumns = {} # This will hold all the possible set of column combinitions to score and select to add to sourceColumnsNeeded
		self.numberNeededColumnsSource = 0
		self.combinationsReactivesFinalMaps = 0

		for name_plate, maps_plate in dict_maps.items(): # Go through all the final plates that need to be created with a multi-channel
			for name_column_reactives, name_column_volumes in zip(maps_plate["Map React"].columns, maps_plate["Map Vol"].columns): # Go through all the columns in this map
				# If it is an empty column we go to the next one
				if maps_plate["Map React"][name_column_reactives].isna().all() or maps_plate["Map Vol"][name_column_volumes].isna().all():
					continue

				# We are going to substitute the empty cells by 'None' so the combination method works
				# As well, we are going to check that the combination of volumes along the column is the same one so it can be transferred with a multi-channel pipette
				# We also are going to create the dictionaries with the combinations volume-reagents to know which one has more than 1 possibility
				elements_max_volumes = max((x for x in maps_plate["Map Vol"][name_column_volumes] if isinstance(x, list)), key = len, default = np.nan)
				reactive_volumes_column = {}
				for reactives_well, volumes_well in zip(maps_plate["Map React"][name_column_reactives], maps_plate["Map Vol"][name_column_volumes]):
					if type(reactives_well) != list and (pd.isna(reactives_well) or pd.isna(volumes_well)):
						volumes_well = elements_max_volumes
						reactives_well = ["None"]*len(volumes_well)
					different_reactives_volumes_well = {}

					for reactive, volume in zip(reactives_well, volumes_well):
						if volume not in different_reactives_volumes_well.keys():
							different_reactives_volumes_well[volume] = [reactive]
						else:
							different_reactives_volumes_well[volume].append(reactive)

					for volume, reactives in different_reactives_volumes_well.items():
						if volume not in reactive_volumes_column.keys():
							reactive_volumes_column[volume] = [reactives]
						else:
							reactive_volumes_column[volume].append(reactives)

				# In self.combinationsPerFinalColumns we are going to create all the type of final columns we need to create the final plates.
				# This is the item we are going to use as an input of the optimization
				for volume_combinations, reagents in reactive_volumes_column.items():
					self.combinationsPerFinalColumns[self.combinationsReactivesFinalMaps] = {"Reagents/Row": reagents,
																							  "Plate Name": name_plate,
																							  "Column Final Plate": name_column_reactives,
																							  "Volume Transfer": volume_combinations,
																							  "Sets": {},
																							  "Max Score Combination":0,
																							  "Name Combination Max Score":0}
					self.combinationsReactivesFinalMaps += 1

	@staticmethod
	def _generation_combination(reagents, start_time, all_sets, current_set = None, index = 0, memo = None, timeout = 20):
		"""
		Create all the possible combination sets for a given combination of reagents in a column
		Reagents is going to be a list in which each element of that list is going to be the possible reactives in each cell of tha column
		With these combinations sets are going to be created because the combinations need to have all the reagents
		Because this is a combinatorial problem that can take a lot of time, timeout cap is established
		"""

		if memo is None:
			memo = {}

		if current_set is None:
			current_set = []
			
		if index == len(reagents):
			frozen_set = frozenset(zip(*current_set))
			if frozen_set in memo:
				return
			else:
				memo[frozen_set] = True
				all_sets.append(list(zip(*current_set)))
			return

		for permutation in permutations(reagents[index]):
			elapsed_time = time.time() - start_time
			if elapsed_time > timeout: # It is going ot be checked everytime it enters in the _generation_combination function but only with the start_time given in generation_sets 
				raise TimeoutError(f"""One of the sets of a column in a plate created by a multi-channel pipette has too many reagents to combine for the high optimization and ha staken too long to create the combinations (>20 seconds).
This time limit is set so protocols dont run for that long. Opentrons need to simulate and then execute the protocol and this is a preventite decision.
This error does not mean the protocol cannot be done, try setting 'Optimization Space Source Plate Reagents Disposition' as 'low' or give less ragent-volume combinations per final well
Sorry for the inconvenience""")
			current_set.append(permutation)
			MultiChannelSourcePlates._generation_combination(reagents, start_time, all_sets, current_set = current_set, index = index + 1, memo = memo)
			current_set.pop()

	def generation_sets(self):
		"""
		This method will set the item of all the final combinations given by generation_combination()
		and create for each one the value for that set with the socres and dependencies associated
		"""
		for needed_movements_column_name, needed_movements_column_values in self.combinationsPerFinalColumns.items():
			all_sets = []

			MultiChannelSourcePlates._generation_combination(needed_movements_column_values["Reagents/Row"], time.time(), all_sets)

			for index, set in enumerate(all_sets):
				self.combinationsPerFinalColumns[needed_movements_column_name]["Sets"][index] = {"Combination":set, # Esta va a ser el set de combinaciones, por lo que estaran varias columnas
																								 "Score Combination":0,
																								 "Score Dependencies":{}
																								}

	def initial_set (self):
		"""
		Function that will separate the columns that have to be in the source plate. In other words, if for 1 given volume there is only 1 ccolumn combination,
		this columns needs to be in the source plate so it is directly assigned
		"""

		id_movements_to_remove = []
		for id_type_movement, values_type_movement in self.combinationsPerFinalColumns.items():
			if all(len(values_well) == 1 for values_well in values_type_movement["Reagents/Row"]):
				id_movements_to_remove.append(id_type_movement)
				column_reagents_add = tuple(row[0] for row in values_type_movement["Reagents/Row"])
				
				if len(self.sourceColumnsNeeded) == 0: # First time a column is going to be add
					self.sourceColumnsNeeded[self.numberNeededColumnsSource] = {"Reagents":column_reagents_add,
																				"Final Columns":{values_type_movement["Plate Name"]:[(values_type_movement["Column Final Plate"], values_type_movement["Volume Transfer"])]},
																				"Positions Opentrons":[],
																				"Reactions/column":[], # More than 1 column could be needed if the volume neded surpases the capacity of the well(s) in the source plate reservoir
																				"Volumes/column":[] # Volume of each one of the columns, this is gong to be actually the volume of each well inside of the column
																				}
					self.numberNeededColumnsSource += 1
				else:
					for id_selected_column, values_selected_column in self.sourceColumnsNeeded.items():
						if column_reagents_add == values_selected_column["Reagents"]:
							if values_type_movement["Plate Name"] in values_selected_column["Final Columns"].keys():
								self.sourceColumnsNeeded[id_selected_column]["Final Columns"][values_type_movement["Plate Name"]].append((values_type_movement["Column Final Plate"], values_type_movement["Volume Transfer"]))
							else:
								self.sourceColumnsNeeded[id_selected_column]["Final Columns"][values_type_movement["Plate Name"]] = [(values_type_movement["Column Final Plate"], values_type_movement["Volume Transfer"])]
							selected_column_placed = True
							break
						else:
							selected_column_placed = False

					if selected_column_placed == False:    
						self.sourceColumnsNeeded[self.numberNeededColumnsSource] = {"Reagents":column_reagents_add,
																					"Final Columns":{values_type_movement["Plate Name"]:[(values_type_movement["Column Final Plate"], values_type_movement["Volume Transfer"])]},
																					"Positions Opentrons":[],
																					"Reactions/column":[], # More than 1 column could be needed if the volume neded surpases the capacity of the well(s) in the source plate reservoir
																					"Volumes/column":[] # Volume of each one of the columns, this is gong to be actually the volume of each well inside of the column
																					}
						self.numberNeededColumnsSource += 1

		for id in id_movements_to_remove:
			del self.combinationsPerFinalColumns[id]

	def low_opti_column_choosing(self):
		"""
		This is going to be used as the low optimization method of the columns in which it is searched if inside of the combination reagents-volume any of the columns in the initial set 
		can be created so that column can be re-used and save space.
		If that is not the case or not all the reagents are assigned, columns are created sequentially in the order they are given in the maps the user has defined for the final
		layout
		"""

		for combination_mov in self.combinationsPerFinalColumns.values():
			reagents = combination_mov["Reagents/Row"]
			for index_selected_col, selected_col in self.sourceColumnsNeeded.items():
				if len(reagents[0]) > 0:
					equal_column = []
					for reactive, row in zip(selected_col["Reagents"], reagents):
						if reactive in row:
							equal_column.append(reactive)

					if len(equal_column) == len(selected_col["Reagents"]):
						if combination_mov["Plate Name"] in selected_col["Final Columns"].keys():
							self.sourceColumnsNeeded[index_selected_col]["Final Columns"][combination_mov["Plate Name"]].append((combination_mov["Column Final Plate"], combination_mov["Volume Transfer"]))
						else:
							self.sourceColumnsNeeded[index_selected_col]["Final Columns"][combination_mov["Plate Name"]] = [(combination_mov["Column Final Plate"], combination_mov["Volume Transfer"])]

						for index, element in enumerate(equal_column):
							reagents[index].remove(element)
				else:
					break

			adding_columns = list(map(list, zip(*reagents)))
			for column in adding_columns:
				self.sourceColumnsNeeded[self.numberNeededColumnsSource] = {"Reagents":tuple(column),
																			"Final Columns":{combination_mov["Plate Name"]:[(combination_mov["Column Final Plate"], combination_mov["Volume Transfer"])]},
																			"Positions Opentrons":[],
																			"Reactions/column":[],
																			"Volumes/column":[]                               
																			}
				self.numberNeededColumnsSource += 1

	def scoring_sets (self):
		"""
		Function that scores the sets of columns in a combination
		This score is done adding how much that columsn appears in already selected columns and in the other combination sets by a ratio making a score of how much
		the columns in this set are likely to be re-used for other columns in the final plate layout
		For example, if 1 set has 3 columns and 1 of them is in the initial set and the other 2 appear in half of the other combination sets this set will have a score of
		1 (appears in the already assigned source coluns) + 0.5 ( 1 column appears in half of the other sets) + 0.5 (1 column appears in half of the other sets)
		As well, in which other column the set takes this score (dependency) is also tracked, so when all the combinations are updated, scores can be changed directly

		This score is going to be used in the method seleccion update to select the best set, the one with the higher score and this method is going to be used only once for each object
		it is created of this class
		"""

		# We need to loop for every set of columns of every type of volume movement is needed for the final plates layout to be created
		for id_combination, combination_values in self.combinationsPerFinalColumns.items():
			for id_set_combination, values_set in combination_values["Sets"].items():
				for column_set in values_set["Combination"]: # We loop through all the columns because teh score is going to be additive
					for id_combination_compare, values_combination_compare in self.combinationsPerFinalColumns.items(): # We loop through the other set so we can compare them to generate the score
						if id_combination_compare == id_combination:
							continue

						score_dependecy_column = 0 # Initialize the score of this column to 0

						for combination_compare in values_combination_compare["Sets"].values(): # Loop through the other sets
							if column_set in combination_compare["Combination"]:
								score_dependecy_column += 1

						if score_dependecy_column > 0: # This column has dependencies with this set of combinations 
							# Add the dependencies calculating the ratio so columns with more sets does not have an advantage over other that have less
							if id_combination_compare in values_set["Score Dependencies"].keys():
								self.combinationsPerFinalColumns[id_combination]["Sets"][id_set_combination]["Score Dependencies"][id_combination_compare] += score_dependecy_column/len(values_combination_compare["Sets"])
							else:
								self.combinationsPerFinalColumns[id_combination]["Sets"][id_set_combination]["Score Dependencies"][id_combination_compare] = score_dependecy_column/len(values_combination_compare["Sets"])

							# Add the score of the column to the set we are doing the scores, again, we add the ratio
							self.combinationsPerFinalColumns[id_combination]["Sets"][id_set_combination]["Score Combination"] += score_dependecy_column/len(values_combination_compare["Sets"])

					for initial_set_column in self.sourceColumnsNeeded.values(): # Add the score of the columns being in the assigned source columns
						if column_set == initial_set_column["Reagents"]:
							self.combinationsPerFinalColumns[id_combination]["Sets"][id_set_combination]["Score Combination"] += 1

				# We check if this set is the maximum scorer of this final column
				if self.combinationsPerFinalColumns[id_combination]["Sets"][id_set_combination]["Score Combination"] > self.combinationsPerFinalColumns[id_combination]["Max Score Combination"]:
					self.combinationsPerFinalColumns[id_combination]["Max Score Combination"] = self.combinationsPerFinalColumns[id_combination]["Sets"][id_set_combination]["Score Combination"]
					self.combinationsPerFinalColumns[id_combination]["Name Combination Max Score"] = id_set_combination

	def seleccion_update (self):
		"""
		Function that takes the initial scores of each set gave by scoring_set, picks the best one and updates the scores of other sets that have dependencies with the selected column
		or set of columns.
		This process is done recursivelly until every column of the final layout given by the user can be formed.
		If more than one column have the same scores, being that one the max, the first one will be chosen
		"""

		while len(self.combinationsPerFinalColumns) > 0: # Loop until no final column combinations are left
			# Get the column with the set with the max score
			columna_seleccionada = next(iter(sorted(self.combinationsPerFinalColumns, key = lambda x: self.combinationsPerFinalColumns[x]["Max Score Combination"], reverse = True))) # sort and then pick the first one
			set_seleccionado = self.combinationsPerFinalColumns[columna_seleccionada]["Sets"][self.combinationsPerFinalColumns[columna_seleccionada]["Name Combination Max Score"]]["Combination"]

			if len(self.sourceColumnsNeeded) == 0: # First time a column or set of columns is added to the source plate
				for column_set_selected in set_seleccionado:
					self.sourceColumnsNeeded[self.numberNeededColumnsSource] = {"Reagents":self.combinationsPerFinalColumns[columna_seleccionada]["Sets"][self.combinationsPerFinalColumns[columna_seleccionada]["Name Combination Max Score"]]["Combination"],
																				"Final Columns":{self.combinationsPerFinalColumns[columna_seleccionada]["Plate Name"]:[(self.combinationsPerFinalColumns[columna_seleccionada]["Column Final Plate"], self.combinationsPerFinalColumns[columna_seleccionada]["Volume Transfer"])]},
																				"Positions Opentrons":[],
																				"Reactions/column":[], # More than 1 column can be needed for this combination because of volume capacity of the labware
																				"Volumes/column":[] # Volumne of each column  
																				}
					self.numberNeededColumnsSource += 1
			else:
				# Check that some of the columns are not already on the sourceColumnsNeeded
				# If they are, just add the volume, else, just add the column with with the fields needed for the entry
				# After tha addition, the scores are updated for the sets that have any of the columns selected in their own sets, either adding if it was selected or substract if other columns are selected

				for column_set_selected in set_seleccionado:
					for id_selected_column, values_selected_column in self.sourceColumnsNeeded.items():
						if column_set_selected ==  values_selected_column["Reagents"]:
							if self.combinationsPerFinalColumns[columna_seleccionada]["Plate Name"] in values_selected_column["Final Columns"].keys():
								self.sourceColumnsNeeded[id_selected_column]["Final Columns"][self.combinationsPerFinalColumns[columna_seleccionada]["Plate Name"]].append((self.combinationsPerFinalColumns[columna_seleccionada]["Column Final Plate"], self.combinationsPerFinalColumns[columna_seleccionada]["Volume Transfer"]))
							else:
								self.sourceColumnsNeeded[id_selected_column]["Final Columns"][self.combinationsPerFinalColumns[columna_seleccionada]["Plate Name"]] = [(self.combinationsPerFinalColumns[columna_seleccionada]["Column Final Plate"], self.combinationsPerFinalColumns[columna_seleccionada]["Volume Transfer"])]
							selected_column_placed = True
							break
						else:
							selected_column_placed = False

					if selected_column_placed == False:
						self.sourceColumnsNeeded[self.numberNeededColumnsSource] = {"Reagents":column_set_selected,
																					"Final Columns":{self.combinationsPerFinalColumns[columna_seleccionada]["Plate Name"]:[(self.combinationsPerFinalColumns[columna_seleccionada]["Column Final Plate"], self.combinationsPerFinalColumns[columna_seleccionada]["Volume Transfer"])]},
																					"Positions Opentrons":[],
																					"Reactions/column":[],
																					"Volumes/column":[]    
																					}
						self.numberNeededColumnsSource += 1

			# Delete all the sets of tha column because a set of columns are already selected and the scores are updated
			del self.combinationsPerFinalColumns[columna_seleccionada]

			# Update scores
			for needed_type_movement in self.combinationsPerFinalColumns.keys():
				# Reset the best score
				self.combinationsPerFinalColumns[needed_type_movement]["Max Score Combination"] = 0
				self.combinationsPerFinalColumns[needed_type_movement]["Name Combination Max Score"] = 0
				for name_combination, combination in self.combinationsPerFinalColumns[needed_type_movement]["Sets"].items():
					if columna_seleccionada in combination["Score Dependencies"].keys(): # Update the score if there is any dependencies with the column we have selected
						# We substract the value it gave as a set and add the value that each column give
						self.combinationsPerFinalColumns[needed_type_movement]["Sets"][name_combination]["Score Combination"] -= combination["Score Dependencies"][columna_seleccionada]
						del self.combinationsPerFinalColumns[needed_type_movement]["Sets"][name_combination]["Score Dependencies"][columna_seleccionada]
						number_common_columns = sum(1 for element in set_seleccionado if element in combination["Combination"])
						self.combinationsPerFinalColumns[needed_type_movement]["Sets"][name_combination]["Score Combination"] += number_common_columns

					# If the additions have made it the best one, it is updated the max score
					if self.combinationsPerFinalColumns[needed_type_movement]["Sets"][name_combination]["Score Combination"] > self.combinationsPerFinalColumns[needed_type_movement]["Max Score Combination"]:
						self.combinationsPerFinalColumns[needed_type_movement]["Max Score Combination"] = self.combinationsPerFinalColumns[needed_type_movement]["Sets"][name_combination]["Score Combination"]
						self.combinationsPerFinalColumns[needed_type_movement]["Name Combination Max Score"] = name_combination

class TimeoutError(Exception):
	"""
	Custom errordefined for errors in the object MultiChannelSourcePlates

	It is going to be used when the generation of combinations are taking too long and an exception will be raised
	for the user to choose another set of options

	This is a preventive measure taken just so the simulation of the protocol does not take too much time
	"""

	pass

class NotSuitablePipette(Exception):
	"""
	Custom Error raised when there is no pipette that can transfer the volume
	"""
	def __init__(self, value):
		message = f"Not a suitable pipette to aspirate/dispense {value}uL"
		super().__init__(message)
	
	pass

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

def generator_positions (labware_wells_name):
	"""
	Function that will return the next element everytime is called from a given list
	"""
	for well in labware_wells_name:
		yield well

def vol_pipette_matcher (volumes_distribute, positions_distribute, pip_r, pip_l):
	"""
	Function that taking 2 pipettes and a list of volumes it established which volume should be transfered with
	which pipette. All of those volumes are matched with a location

	4 arguments are needed for the function. The arguments that correspond to pip_r and pip_l can be None, but
	if both of them are None an exception will be raised
	"""
	
	# Initiate the variables that are going to be returned
	vol_r = []
	pos_r = []
	vol_l = []
	pos_l = []

	# Error control
	if not pip_r and not pip_l:
		raise Exception("There are no pipettes attached to perform the function 'vol_pipette_matcher'")

	if len (volumes_distribute) != len (positions_distribute):
		raise Exception("The lists representing the positions and volumes to distribute need to be of equal length")

	# Go through all the volumes to define which pipette should transfer it
	for volume_transfer, position in zip (volumes_distribute, positions_distribute):
		# No pipette is needed to transfer that volume
		if volume_transfer == 0:
			continue
		
		selected_pipette = give_me_optimal_pipette (volume_transfer, pip_l, pip_r)

		if selected_pipette.mount == "right":
			vol_r.append(volume_transfer)
			pos_r.append(position)
		else:
			vol_l.append(volume_transfer)
			pos_l.append(position)

	return vol_r, pos_r, vol_l, pos_l

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
		
		# Finally, we pick up the needed tip
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

def conversor_well_position_sorter (wells, position, volumes = None, sort = False, ordering = "ascending"):
	"""
	Function that will take a list of wells or an instance of a well and will return the position provided
	of that or those wells.
	In case the sort argument is set as True, the list of wells will be sorted in function to the volumes list and
	be returned sorted by volume in a descending or ascending way, depending on the value given in ordering

	Only 3 type of positions will be provided, either the top position, the center or the original one if position is set
	as bottom
	"""

	# We do the checks for the arguments
	if position not in ["top", "bottom", "center"]:
		raise Exception("The function 'conversor_well_position_sorter' only accepts 3 values for the position argument: bottom, center or top")
	
	if sort not in [True, False]:
		raise Exception("The function 'conversor_well_position_sorter' only accepts 2 values for the optional sort argument: True or False. By default the value is False")
	
	if ordering not in ["ascending", "descending"]:
		raise Exception("The function 'conversor_well_position_sorter' only accepts 2 values for the optional ordering argument: ascending or descending.\nBy default the value is ascending.")

	if sort and not isinstance(volumes, list):
		raise Exception("If sort set as True in 'conversor_well_position_sorter' the argument volumes need to be provided and needs to be a list with the same dimension as the list provided in wells")
	elif sort == False:
		pass
	else:
		if not isinstance(wells, list):
			raise Exception("If sort set as True in 'conversor_well_position_sorter' the argument wells needs to be a list with the same dimension as the list provided in volumes")
		if len(wells) != len(volumes):
			raise Exception("If sort set as True in 'conversor_well_position_sorter' the list provided in argument wells needs to be the same length as the list provided in volumes")

	# First, lets sort the volumes
	if sort:
		dict_wells_volumes = dict(zip(wells, volumes))
		dict_wells_volumes_sorted = dict(sorted(dict_wells_volumes.items(), key=lambda x:x[1]))
		volumes = list(dict_wells_volumes_sorted.values())
		wells = list(dict_wells_volumes_sorted.keys())

	# Now we just establish the positions
	if isinstance(wells, list):
		positions = []
		for well in wells:
			if position == "top":
				positions.append(well.top())
			elif position == "bottom":
				positions.append(well)
			else:
				positions.append(well.center())
	else:
		if position == "top":
			return wells.top()
		elif position == "bottom":
			return wells
		else:
			return wells.center()

	return (positions, volumes)

metadata = {
'apiLevel':'2.14'
}

def run(protocol:opentrons.protocol_api.ProtocolContext):
	# Read Excel
	excel_variables = pd.read_excel("/data/user_storage/VariablesCustomMixing.xlsx", sheet_name = None, engine = "openpyxl")

	# Let's check that the minimal sheets exist in the excel
	name_sheets = list(excel_variables.keys())
	if not all(item in name_sheets for item in ["GeneralVariables","FinalPlatesVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","FinalPlatesVariables" and "PipetteVariables"\nThey must have those names')

	# Check that all variable sheets have the needed columns and variable names
	general_variables = excel_variables.get("GeneralVariables")
	del excel_variables["GeneralVariables"]
	plate_variables = excel_variables.get("FinalPlatesVariables")
	del excel_variables["FinalPlatesVariables"]
	pip_variables = excel_variables.get("PipetteVariables")
	del excel_variables["PipetteVariables"]

	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in general_variables["Variable Names"].values for item in ['API Name Labware with Reagent(s) in Tube(s)','Type of Reagent Tube','API Name Labware with Reagents(s) in Plate(s)','API Name Final Plate','Number of Final Plates','Change Tip In Distribution','Position Dispense Final Well','Touch Tip After Dispense','Touch Tip After Dispense','Optimization Space Source Plate Reagents Disposition']):
			raise Exception("'GeneralVariables' sheet table needs to have 10 rows with the following names: 'API Name Labware with Reagent(s) in Tube(s)', 'Type of Reagent Tube','API Name Labware with Reagents(s) in Plate(s)', 'API Name Final Plate', 'Number of Final Plates', 'Change Tip In Distribution', 'Position Dispense Final Well', 'Touch Tip After Dispense', 'Touch Tip After Dispense', 'Optimization Space Source Plate Reagents Disposition'")

	if "Variable Names" not in list(plate_variables.columns):
		raise Exception("'FinalPlatesVariables' sheet table needs to have at least 1 column, 'Variable Names'")
	else:
		if not all(item in plate_variables["Variable Names"].values for item in ['Number of Replicas','Name Sheet Map Reagents','Name Sheet Map Volumes','Type of Pipette to Create Plate']):
			raise Exception("'FinalPlatesVariables' Sheet table needs to have 4 rows with the following names: 'Number of Replicas', 'Name Sheet Map Reagents', 'Name Sheet Map Volumes', 'Type of Pipette to Create Plate'")
	
	if not all(item in list(pip_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'PipetteVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in pip_variables["Variable Names"].values for item in ['Name Right Pipette', 'API Name Right Pipette TipRack', 'Name Left Pipette', 'API Name Left Pipette TipRack','Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks']):
			raise Exception("'PipetteVariables' Sheet table needs to have 7 rows with the following names: 'Name Right Pipette', 'API Name Right Pipette TipRack', 'Name Left Pipette', 'API Name Left Pipette TipRack','Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks'")
	
	# We set the variables given in the excel file and check that the values are correct
	user_variables = UserVariables(general_variables, plate_variables, pip_variables, excel_variables)
	user_variables.check()
	
	# Calculate and set some of the variables that is going to be used in the rest of the script and it is derived from the variables set in excel
	program_variables = SettedParameters()
	program_variables.assign_variables(user_variables, protocol)

	# Set the final plates because we have already calculated how many of them are neede in program_variables
	for name_plate, items_plate in program_variables.finalPlates.items():
		# Create the labels that will be displayed to the user and will help them place them correctly
		if user_variables.internalReplicas: # Replcias internas
			labels = f"{items_plate['Label']} with {items_plate['Number Replicas']} Internal Replica(s)"
		else: # There are either external replicas that will create more plates or no replicas
			labels = [items_plate["Label"]]
			for plate_replica in range(1, len(items_plate["Plates Replicas"])+1):
				labels.append(f"Replica {plate_replica} of {items_plate['Label']}")

		final_labware = setting_labware (1+len(items_plate["Plates Replicas"]),
								   		 user_variables.APINameIncubationPlate,
										 dict(zip(protocol.deck.keys(),protocol.deck.values())),
										 protocol,
										 module = False,
										 label = labels) # Por ahora no le pondre labels

		program_variables.finalPlates[name_plate]["Opentrons Place"] = list(final_labware.values())[0]

		for position_labware, name_replica in zip(list(final_labware.values())[1:], items_plate["Plates Replicas"].keys()):
			program_variables.finalPlates[name_plate]["Plates Replicas"][name_replica] = position_labware


	# The needed columns and/or tube of reagents with the needed volume of each one is already calculated in program_variables.assign_variables
	# Now we need to load the labwares needed for each one of them and track where each one is going to be placed

	# Only if there is at least 1 plate that is going to be created with a single channel pipette the eppendorf or falcon tubes and their labwares are going to be loaded
	# The structures that we are using in this conditional are based on the ones used in LAP-MoCloAssembly-OT2-1.0.1
	# It is not completly optimized the use of tubes so it is something that it can be improved in the future
	if any(elem == 'single' for elem in user_variables.pipetteCreationPlate[:user_variables.numberFinalPlates]):
		vol_max_tube = user_variables.maxVolumeTubeReagent
		total_tubes = 0
		# We are going to set the tubes for each of the reactives storing the volumes of each one to display after in the OT app
		# and the number of final wells (reactions) each tube is going to contain the volume for
		# We will be adding the volumes of each well one by one and checking if that fits or should another tube be created
		# The volume maximum that we will be taking in account is the 95% of the tube so there is some space for the pipette to access the tube
		# without spilling and as well to put some extra volume to take in account the pippetting error
		for name_reactive, values_reactive in program_variables.antibioticWells.items():
			volume_all_plates = []
			for values in values_reactive["Volumes/Position"].values(): # We cretae a list with all the volumes that need to be transferred regardinless the final plate it belongs to
				volume_all_plates += values
			
			volume_reactive_needed = sum(volume_all_plates)

			if any(volume > (vol_max_tube*0.95) for volume in volume_all_plates) == True:
				raise Exception(f"One of the volumes of the reactive {name_reactive} does not fit in tubes (adding pipetting extra volume which is the 0.05 of the maximum volume of the Labware), check combinations. \n Every individual volume of the reactives needs to fit in 1 tube")
				
			if volume_reactive_needed <= 0.95*vol_max_tube: # All the volume can be placed in 1 tube so it is a straighforward assignation
				program_variables.antibioticWells[name_reactive]["Volumes Per Tube"] = [volume_reactive_needed]
				program_variables.antibioticWells[name_reactive]["Reactions Per Tube"] = [len(volume_all_plates)]
				total_tubes += 1
			else: # We need to figure out how many of the final well's volumes can fit in this tube
				current_volume_tube = 0
				current_tube_reactions = 0
				for index_volume, volume in enumerate(volume_all_plates):
					# We check if the current tube can fit the volume but no more than that or if it fits in the tube na dit is the last position
					if (current_volume_tube+volume == 0.95*vol_max_tube) or (current_volume_tube+volume < 0.95*vol_max_tube and index_volume == len(volume_all_plates) - 1):
						# Set the volumes and how many of the final wells the tube has the volume for
						program_variables.antibioticWells[name_reactive]["Volumes Per Tube"].append(current_volume_tube+volume)
						program_variables.antibioticWells[name_reactive]["Reactions Per Tube"].append(current_tube_reactions+1)
						total_tubes += 1
						# Restart the volume and reactions
						current_volume_tube = 0
						current_tube_reactions = 0
					elif current_volume_tube+volume > 0.95*vol_max_tube: # The volume does not fit, a new tube is need to be created
						# Record the information of the tube that is completed
						program_variables.antibioticWells[name_reactive]["Volumes Per Tube"].append(current_volume_tube)
						program_variables.antibioticWells[name_reactive]["Reactions Per Tube"].append(current_tube_reactions)
						total_tubes += 1
						# Restart the new tube with the volume of the reaction that did not fit in the current one
						current_volume_tube = volume
						current_tube_reactions = 1

						if index_volume == len(volume_all_plates) - 1: # If it is the last reaction we just create the tube with the volume of the last well
							program_variables.antibioticWells[name_reactive]["Volumes Per Tube"].append(current_volume_tube)
							program_variables.antibioticWells[name_reactive]["Reactions Per Tube"].append(current_tube_reactions)
							total_tubes += 1
					else: # The volume fits, there is more space in the tube and it is not the last volume that needs to be added
						current_volume_tube += volume
						current_tube_reactions += 1
		
		# We have already the needed tubes and their volumes, now we load the labware that is going to contain them and load each tube
		if user_variables.typeTubesReagents == "falcon":
			label = "Falcon Tube(s) with Reagent(s) to be Transferred with Single-Channel Pipette(s)"
		else:
			label = "Eppendorf Tube(s) with Reagent(s) to be Transferred with Single-Channel Pipette(s)"
		
		tubes_reagents_labware = setting_labware(math.ceil(total_tubes/user_variables.numberTubesLabware),
												 user_variables.APINameFalconPlate,
												 dict(zip(protocol.deck.keys(),
												 protocol.deck.values())),
												 protocol,
												 label = label)

		positions_tuberack = []
		for labware in tubes_reagents_labware.values():
			positions_tuberack += labware.wells()
		
		generator_position_tubes = generator_positions(positions_tuberack)
		
		for name_reactive, values_reactive in program_variables.antibioticWells.items():
			for volume_tube in values_reactive['Volumes Per Tube']:
				well_tube = next(generator_position_tubes)
				program_variables.antibioticWells[name_reactive]["Position Tubes"].append(well_tube)

				# Load liquid so the user knows how much volume it needs to have in each tube
				well_tube.load_liquid(liquid = program_variables.color_info_reactives[name_reactive]["Definition Liquid"], volume = volume_tube)
	
	# ----------------------------------------------------------------------------------------------------------------------------------------
	
	# Only if there is at least 1 plate that is going to be created with a multi channel pipette the reservoir labwares are going to be loaded
	# The structures that we are using in this conditional are based on the ones used in LAP-MoCloAssembly-OT2-1.0.1
	# It is not completly optimized the use of columns so it is something that it can be improved in the future

	if any(elem == 'multi' for elem in user_variables.pipetteCreationPlate[:user_variables.numberFinalPlates]):
		vol_max_well = user_variables.maxVolumeWellReservoirPlate
		total_columns = 0

		# We will loop through all the needed columns that have been set in program_variables.assign_variables()
		for name_column_needed, column_needed in program_variables.neededColumnsMulti.sourceColumnsNeeded.items():
			volume_all_multi_plates = []
			# We group all the volumes of the final columns that are going to be having this column as a source irrespectivelly of the final plate they are situated
			for name_plate, values in column_needed["Final Columns"].items():
				# Depending on the dimensions of the reservoir and final plates we are going to be adding to the columns different volumes
				# This s due to the fact that the volumes set in the maps are the final ones, but because we are going to transfer it with a multi-channel
				# We need to take in account that is going to be split in 8
				# As well, the volume swe are storing are only of 1 well and if the final labware has 8 wells per column, the need of volume for that specific
				# column will be 8 time greater than the volume we have stored
				for final_column_plate in values:
					# If the dimensions are the same, each well of the column is going to be feeding  the same well of the final column so no need to do volume adjustments
					if user_variables.dimensionsFinalLabware["row"] == user_variables.dimensionsLabwareReservoir["row"]:
						volume_all_multi_plates.append(final_column_plate[1])
					else: # The source and final labware have different dimensions which mean that may need some adjustments
						# We already know that both either have 8 or 1 rows because it is checked in user_variables.check()
						if user_variables.dimensionsFinalLabware["row"] == 1: # This means that the final labware has 1 row and the reservoir has 8 rows
							# We divide the needed volume of the final column in 8 so we can distribute equitatevilly the volume in the 8 wells of the reservoir
							volume_all_multi_plates.append(final_column_plate[1]/user_variables.dimensionsLabwareReservoir["row"])
						elif user_variables.dimensionsFinalLabware["row"] == 8: # This means that the final labware has 8 rows and the reservoir 1 row
							# Multiply the volume needed in each well of the final labware because all of them are going to be stored in 1 well of the reservoir 
							volume_all_multi_plates.append(final_column_plate[1]*user_variables.dimensionsFinalLabware["row"])
			
			# Now that we have established how much volume is needed from each one of the final columns we sum them so we can distribute them into the reservoir columns
			volume_column_needed = sum(volume_all_multi_plates)

			# The final results is going to be that in the "Volumes/column" we are going to store the ammount of volume per well in the column taking in account
			if any(volume+(vol_max_well*0.05) > vol_max_well for volume in volume_all_multi_plates) == True:
				raise Exception(f"""One of the volumes of the column {column_needed['Reagents']} does not fit in columns (adding pipetting extra volume which is the 0.05 of the maximum volume of the Labware), check combinations.
Each individual volume of the reagents cannot be over the maximum volume of each well of the column of the source plate.
If the final labware has only 1 row and the initial labware has 8 rows the final volume is going to be slit in 8 well so that splited volume is the one that it should not be major than the maximum capacity of the reservoir plate wells.
The opposite case, in which the final labware has 8 rows and the reservoir plate has only 1 row has the opposite maximum volume, the sum of the volumes in the final labware should not be greater than the maximum capacity of the reservoir""")
				
			if volume_column_needed <= 0.95*vol_max_well: # Everything fits in 1 column so the assignment is straightworfard
				program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Volumes/column"] = [volume_column_needed]
				program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Reactions/column"] = [len(volume_all_multi_plates)]
				total_columns += 1
			else: # The volume does not fit in a single column so we need to find out how many final wells can feed each column
				current_volume_column = 0
				current_column_reactions = 0
				for index_volume, volume in enumerate(volume_all_multi_plates):
					# We check if the current column can fit the volume but no more than that or if it fits in the tube na dit is the last position
					if (current_volume_column+volume == 0.95*vol_max_well) or (current_volume_column+volume < 0.95*vol_max_well and index_volume == len(volume_all_multi_plates) - 1):
						program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Volumes/column"].append(current_volume_column+volume)
						program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Reactions/column"].append(current_column_reactions+1)
						total_columns += 1
						# Restart the volume and reactions
						current_volume_column = 0
						current_column_reactions = 0
					elif current_volume_column+volume > 0.95*vol_max_well:
						# Record the information of the tube that is completed
						program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Volumes/column"].append(current_volume_column)
						program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Reactions/column"].append(current_column_reactions)
						total_columns += 1
						# Restart the new tube with the volume of the reaction that did not fit in the current one
						current_volume_column = volume
						current_column_reactions = 1
						if index_volume == len(volume_all_multi_plates) - 1:
							program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Volumes/column"].append(current_volume_column)
							program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column_needed]["Reactions/column"].append(current_column_reactions)
							total_columns += 1
					else: # The volume fits, there is more space in the tube and it is not the last volume that needs to be added
						current_volume_column += volume
						current_column_reactions += 1

		# We know now how many columns we need so we will just set the needed number of labwares
		columns_reagents_labware = setting_labware(math.ceil(total_columns/user_variables.dimensionsLabwareReservoir["columns"]),
												   user_variables.APINameReservoirPlate,
												   dict(zip(protocol.deck.keys(), protocol.deck.values())),
												   protocol,
												   label = "Plates with Reagents to be Transferred with Multi-Channel Pipette(s)")
	
		# Lets set the place of each set of columns
		positions_columns = []
		for labware in columns_reagents_labware.values():
			positions_columns += labware.columns()
		generator_position_columns = generator_positions(positions_columns)

		for name_column, values_column in program_variables.neededColumnsMulti.sourceColumnsNeeded.items():
			for volume_column in values_column["Volumes/column"]:
				column = next(generator_position_columns)
				program_variables.neededColumnsMulti.sourceColumnsNeeded[name_column]["Positions Opentrons"].append(column)
				# Load liquid so the user knows how much volume it needs to have in each well
				for index_well, well in enumerate(column):
					if values_column["Reagents"][index_well] == "None":
						continue
					well.load_liquid(liquid = program_variables.color_info_reactives[values_column["Reagents"][index_well]]["Definition Liquid"], volume = volume_column)

	# ------------------------------------------------------------------------------------------------------------------------
	# We have already set every reagent and record where they are and the final wells that they need to transfer the liquid to
	# Now we are going to transfer them

	# Iterate over all the reagents, there is only going to be items in program_variables.antibioticWells if at least 1 plate is going to be created with a single channel pipette
	for values_reagents in program_variables.antibioticWells.values():
		# Up until know we have only had the names of the wells where the volume is going to be transferred and now we will get the wells from those names
		wells_reagent = []
		volumes_reagent = []

		for plate, positions in values_reagents["Positions"].items():
			if plate not in program_variables.finalPlates.keys(): # If it is not in these keys it will be a replica plate
				for main_plate in program_variables.finalPlates.values(): # Now we check the plates in the replicas
					if plate in main_plate['Plates Replicas']:
						# Set which one is the plate
						ot_labware = main_plate['Plates Replicas'][plate]
						break # We have found the plate so we will just break this for loop
			else: # The plate is one of the main ones that the user sets
				# Set the plate
				ot_labware = program_variables.finalPlates[plate]["Opentrons Place"]
			
			# We add to the reagent volumes the ones that are from this plate correspondent to the reactive
			volumes_reagent += values_reagents["Volumes/Position"][plate]
			
			# Now we loop through the names of the wells and store the wells themselves
			for final_well in positions:
				wells_reagent.append(ot_labware[final_well])

		# We have now the positions and the volumes for each final well that this reagents needs to be transferred
		# Now we are going to loop through the tubes to dispense those volumes
		# We dont need to check for the volume because we have already calculated how many final volumes can each tube can act as a source
		# Although, we are going to track the volume of each tube in case there is the need of aspirating in determinated heights as it will be if the initial tubes are falcons
		for reactions_tube, position_tube, volume_tube in zip(values_reagents["Reactions Per Tube"], values_reagents["Position Tubes"], values_reagents["Volumes Per Tube"]):
			# To do a lower ammount of movements if the change tip is set as aspirate we are going to sort the volumes from lower to higher to try to condense the lower volumes together in less movements
			if user_variables.changeTipDistribute == "aspirate":
				sort = True
			else:
				sort = False

			# We define which pipettes can transfer these reactives, in this case, only the single-channels
			if (program_variables.pipL == None or program_variables.pipR == None) or ((program_variables.pipL != None and program_variables.pipL.channels == 1) and (program_variables.pipR != None and program_variables.pipR.channels == 1)):
				volumes_distribute_pipR, positions_distribute_pipR, volumes_distribute_pipL, positions_distribute_pipL = vol_pipette_matcher (volumes_reagent[:reactions_tube],
																																			  wells_reagent[:reactions_tube],
																																			  program_variables.pipR,
																																			  program_variables.pipL)
				
				# Establish the position inside the wells (top, bottom or center) and i fneeded, sort them
				positions_distribute_pipR, volumes_distribute_pipR = conversor_well_position_sorter (positions_distribute_pipR,
																						 			 user_variables.positionDistributeMedia,
																									 volumes = volumes_distribute_pipR,
																									 sort = sort)
				positions_distribute_pipL, volumes_distribute_pipL = conversor_well_position_sorter (positions_distribute_pipL,
																						 			 user_variables.positionDistributeMedia,
																									 volumes = volumes_distribute_pipL,
																									 sort = sort)
			elif program_variables.pipL != None and program_variables.pipL.channels == 1:
				volumes_distribute_pipR = []
				positions_distribute_pipR = []
				volumes_distribute_pipL = volumes_reagent[:reactions_tube]
				positions_distribute_pipL = wells_reagent[:reactions_tube]

				# Establish the position inside the wells (top, bottom or center) and i fneeded, sort them
				positions_distribute_pipL, volumes_distribute_pipL = conversor_well_position_sorter (positions_distribute_pipL,
																						 			 user_variables.positionDistributeMedia,
																									 volumes = volumes_distribute_pipL,
																									 sort = sort)
			elif program_variables.pipR != None and program_variables.pipR.channels == 1:
				volumes_distribute_pipR = volumes_reagent[:reactions_tube]
				positions_distribute_pipR = wells_reagent[:reactions_tube]
				volumes_distribute_pipL = []
				positions_distribute_pipL = []

				# Establish the position inside the wells (top, bottom or center) and if needed, sort them
				positions_distribute_pipR, volumes_distribute_pipR = conversor_well_position_sorter (positions_distribute_pipR,
																						 			 user_variables.positionDistributeMedia,
																									 volumes = volumes_distribute_pipR,
																									 sort = sort)

			# We know that which one is going to be transferred with which pipette so now we need to take in account wich tube is the source and transfer it
			if user_variables.typeTubesReagents == "eppendorf":
				# Distribute the volumes with the left pipette, if there are volumes that need tobe distributed with it
				if volumes_distribute_pipL:
					# In case there are reminiscent tips from the right pipette, we drop that tip and pick one with the left pipette
					if program_variables.pipR != None and program_variables.pipR.has_tip == True:
						program_variables.pipR.drop_tip()
					if program_variables.pipL.has_tip == False:
						check_tip_and_pick(program_variables.pipL,
										   user_variables.APINameTipL,
										   dict(zip(protocol.deck.keys(), protocol.deck.values())),
										   protocol,
										   replace_tiprack = user_variables.replaceTiprack,
										   initial_tip = user_variables.startingTipPipL,
										   same_tiprack = program_variables.sameTipRack)

					# If new tip is well we transfer 1 by 1 the volumes throwing the tip each time and in case the ovlume cannot be transferred in 1 movement a tip is picked up
					# every time the well is accessed
					if user_variables.changeTipDistribute == "well":
						for volume, position in zip(volumes_distribute_pipL, positions_distribute_pipL):
							if volume <= user_variables.maxVolumeTiprackPipetteL: # The volume is going to be transferred in 1 movement
								if program_variables.pipL.has_tip == False:
									check_tip_and_pick(program_variables.pipL,
													   user_variables.APINameTipL,
													   dict(zip(protocol.deck.keys(), protocol.deck.values())),
													   protocol,
													   replace_tiprack = user_variables.replaceTiprack,
													   initial_tip = user_variables.startingTipPipL,
													   same_tiprack = program_variables.sameTipRack)
								program_variables.pipL.transfer(volume,
																position_tube,
																position,
																new_tip = "never",
																touch_tip = user_variables.touchTipDistributeMedia)
								program_variables.pipL.drop_tip()
							else: # There is a need to do more than 1 movement to transfer the volume
								# Find out how many movements it needs to transfer all the volume
								min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteL)

								# We create a list with all the volumes that are going to be transfered to create the final volume in the well
								if rest_volume > 0 and rest_volume < program_variables.pipL.min_volume:
									vol_transfer = int(min_full_movements-1)*[user_variables.maxVolumeTiprackPipetteL]
									vol_transfer += [(user_variables.maxVolumeTiprackPipetteL/2)+rest_volume, user_variables.maxVolumeTiprackPipetteL/2]
								elif rest_volume == 0:
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteL]
								else: # The rest volume cannot be transferred with the pipette so we change the number of maximum volume movements
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteL]
									vol_transfer.append(rest_volume)
								
								# Transfer the volume changing the tip every time it aspirates
								for volumen in vol_transfer:
									if program_variables.pipL.has_tip == False:
										check_tip_and_pick(program_variables.pipL,
							 							   user_variables.APINameTipL,
														   dict(zip(protocol.deck.keys(), protocol.deck.values())),
														   protocol,
														   replace_tiprack = user_variables.replaceTiprack,
														   initial_tip = user_variables.startingTipPipL,
														   same_tiprack = program_variables.sameTipRack)
									program_variables.pipL.transfer(volumen,
																	position_tube,
																	position,
																	new_tip = "never",
																	touch_tip = user_variables.touchTipDistributeMedia)
									program_variables.pipL.drop_tip()
					elif user_variables.changeTipDistribute == "aspirate":
						# If the new tip is aspirate every time it goes to the source tube the tip will be changed
						# We are going to find out the positions and volume sthat can be transferred with 1 movement and between group and group we will change the tip
						groups_positions = []
						group_volumes = []
						current_group_pos = []
						current_group_vol = []
						for volume, position in zip(volumes_distribute_pipL, positions_distribute_pipL):
							if sum(current_group_vol) + volume <= user_variables.maxVolumeTiprackPipetteL:
								# Add the volume and position if it still fits in the pipette movement
								current_group_vol.append(volume)
								current_group_pos.append(position)
							else: # The volume does not fit in the pipette so an additional movement needs to be added
								if len(current_group_vol) > 0: # Add to the groups of transfering the current one and reset it
									group_volumes.append(current_group_vol)
									groups_positions.append(current_group_pos)
									current_group_pos = []
									current_group_vol = []
								
								# We check if the volume can be transferred with 1 movement
								if volume <= user_variables.maxVolumeTiprackPipetteL: # Can be transferred with one movement
									# We add to the group the volume
									current_group_vol.append(volume)
									current_group_pos.append(position)
								else: # More than 1 movement is needed to transfer this volume, so we will split it and added it to the groups making sure to add always the same position
									# Find how many maximum volume movemnts can we do, it is going to be more than 1
									min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteL)
									if rest_volume == 0:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteL])
											groups_positions.append([position])
									elif rest_volume >= program_variables.pipL.min_volume:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteL])
											groups_positions.append([position])
										current_group_vol.append(rest_volume)
										current_group_pos.append(position)
									else: # rest_volume < pipL.min_volume
										for _ in range(int(min_full_movements)-1):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteL])
											groups_positions.append([position])
										group_volumes.append([(user_variables.maxVolumeTiprackPipetteL/2)+rest_volume])
										groups_positions.append([position])
										current_group_vol.append(user_variables.maxVolumeTiprackPipetteL/2)
										current_group_pos.append(position)
						
						if current_group_vol: # The current group that contains the last position to tranfer needs to be added to the groups as well if it hasnt been added already
							group_volumes.append(current_group_vol)
							groups_positions.append(current_group_pos)
						
						# Distribute to the different group of final wells changing the tip between aspirates
						for volumes_distribute, positions_distribute in zip(group_volumes, groups_positions):
							if program_variables.pipL.has_tip == False:
								check_tip_and_pick(program_variables.pipL,
												   user_variables.APINameTipL,
												   dict(zip(protocol.deck.keys(), protocol.deck.values())),
												   protocol,
												   replace_tiprack = user_variables.replaceTiprack,
												   initial_tip = user_variables.startingTipPipL,
												   same_tiprack = program_variables.sameTipRack)
							program_variables.pipL.distribute(volumes_distribute,
															  position_tube,
															  positions_distribute,
															  new_tip = "never",
															  disposal_volume = 0,
															  touch_tip = user_variables.touchTipDistributeMedia)
							program_variables.pipL.drop_tip()
					else: # The change tip variable is never or reagent which mean that is not going to be changed inside of this loop and we just distribute
						# Pick up tip if the pipette does not have one
						if program_variables.pipL.has_tip == False:
							check_tip_and_pick(program_variables.pipL,
											   user_variables.APINameTipL,
											   dict(zip(protocol.deck.keys(), protocol.deck.values())),
											   protocol,
											   replace_tiprack = user_variables.replaceTiprack,
											   initial_tip = user_variables.startingTipPipL,
											   same_tiprack = program_variables.sameTipRack)
						# Distribute
						program_variables.pipL.distribute(volumes_distribute_pipL,
														  position_tube,
														  positions_distribute_pipL,
														  new_tip = "never",
														  disposal_volume = 0,
														  touch_tip = user_variables.touchTipDistributeMedia)
				
				# Now we do the same with the positions and volumes tha tare assigne dto the right pipette as we did with the ones assigned to the right one
				if volumes_distribute_pipR:
					if program_variables.pipL != None and program_variables.pipL.has_tip == True:
						program_variables.pipL.drop_tip()
					if program_variables.pipR.has_tip == False:
						check_tip_and_pick(program_variables.pipR,
						 				   user_variables.APINameTipR,
										   dict(zip(protocol.deck.keys(), protocol.deck.values())),
										   protocol,
										   replace_tiprack = user_variables.replaceTiprack,
										   initial_tip=user_variables.startingTipPipR,
										   same_tiprack=program_variables.sameTipRack)

					if user_variables.changeTipDistribute == "well":
						for volume, position in zip(volumes_distribute_pipR, positions_distribute_pipR):
							if volume <= user_variables.maxVolumeTiprackPipetteR:
								if program_variables.pipR.has_tip == False:
									check_tip_and_pick(program_variables.pipR,
													   user_variables.APINameTipR,
													   dict(zip(protocol.deck.keys(), protocol.deck.values())),
													   protocol, replace_tiprack=user_variables.replaceTiprack,
													   initial_tip = user_variables.startingTipPipR,
													   same_tiprack = program_variables.sameTipRack)
								program_variables.pipR.transfer(volume, position_tube, position, new_tip = "never", touch_tip = user_variables.touchTipDistributeMedia)
								program_variables.pipR.drop_tip()
							else:
								min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteR)
								if rest_volume > 0 and rest_volume < program_variables.pipR.min_volume:
									vol_transfer = int(min_full_movements-1)*[user_variables.maxVolumeTiprackPipetteR]
									vol_transfer += [(user_variables.maxVolumeTiprackPipetteR/2)+rest_volume, user_variables.maxVolumeTiprackPipetteR/2]
								elif rest_volume == 0:
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteR]
								else:
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteR]
									vol_transfer.append(rest_volume)

								for volumen in vol_transfer:
									if program_variables.pipL.has_tip == False:
										check_tip_and_pick(program_variables.pipR,
							 							   user_variables.APINameTipR,
														   dict(zip(protocol.deck.keys(), protocol.deck.values())),
														   protocol,
														   replace_tiprack = user_variables.replaceTiprack,
														   initial_tip = user_variables.startingTipPipR,
														   same_tiprack = program_variables.sameTipRack)
									program_variables.pipR.transfer(volumen,
										 							position_tube,
																	position,
																	new_tip = "never",
																	touch_tip = user_variables.touchTipDistributeMedia)
									program_variables.pipR.drop_tip()
					elif user_variables.changeTipDistribute == "aspirate":
						groups_positions = []
						group_volumes = []
						current_group_pos = []
						current_group_vol = []
						for volume, position in zip(volumes_distribute_pipR, positions_distribute_pipR):
							if sum(current_group_vol) + volume <= user_variables.maxVolumeTiprackPipetteR:
								current_group_vol.append(volume)
								current_group_pos.append(position)
							else:
								if len(current_group_vol) > 0:
									group_volumes.append(current_group_vol)
									groups_positions.append(current_group_pos)
									current_group_pos = []
									current_group_vol = []

								if volume <= user_variables.maxVolumeTiprackPipetteR:
									current_group_vol.append(volume)
									current_group_pos.append(position)
								else:
									min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteR)
									if rest_volume == 0:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteR])
											groups_positions.append([position])
									elif rest_volume >= program_variables.pipR.min_volume:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteR])
											groups_positions.append([position])
										current_group_vol.append(rest_volume)
										current_group_pos.append(position)
									else:
										for _ in range(int(min_full_movements)-1):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteR])
											groups_positions.append([position])
										group_volumes.append([(user_variables.maxVolumeTiprackPipetteR/2)+rest_volume])
										groups_positions.append([position])
										current_group_vol.append(user_variables.maxVolumeTiprackPipetteR/2)
										current_group_pos.append(position)

						if current_group_vol:
							group_volumes.append(current_group_vol)
							groups_positions.append(current_group_pos)
						
						for volumes_distribute, positions_distribute in zip(group_volumes, groups_positions):
							if program_variables.pipR.has_tip == False:
								check_tip_and_pick(program_variables.pipR,
												   user_variables.APINameTipR,
												   dict(zip(protocol.deck.keys(), protocol.deck.values())),
												   protocol,
												   replace_tiprack = user_variables.replaceTiprack,
												   initial_tip = user_variables.startingTipPipR,
												   same_tiprack = program_variables.sameTipRack)
							program_variables.pipR.distribute(volumes_distribute,
										 					  position_tube,
															  positions_distribute,
															  new_tip = "never",
															  disposal_volume = 0,
															  touch_tip = user_variables.touchTipDistributeMedia)
							program_variables.pipR.drop_tip()
					else:
						if program_variables.pipR.has_tip == False:
							check_tip_and_pick(program_variables.pipR,
											   user_variables.APINameTipR,
											   dict(zip(protocol.deck.keys(), protocol.deck.values())),
											   protocol,
											   replace_tiprack = user_variables.replaceTiprack,
											   initial_tip=user_variables.startingTipPipR,
											   same_tiprack=program_variables.sameTipRack)
						program_variables.pipR.distribute(volumes_distribute_pipR,
														  position_tube,
														  positions_distribute_pipR,
														  new_tip = "never",
														  disposal_volume = 0,
														  touch_tip = user_variables.touchTipDistributeMedia)
			else: # The tubes are not eppendorfs, they are falcons and for the distribution of volumes we have a function that will track the height of aspiration so the pipette does not get wet
				# The function does not have the option to have new_tip reagent because it will only will distribute from 1 tube so we will change it to never that will do the same effect for the function
				if user_variables.changeTipDistribute == "reagent":
					tip_distribute_function = "never"
				else:
					tip_distribute_function = user_variables.changeTipDistribute

				# Distribute the volumes attributet to the left pipette if there are any
				if volumes_distribute_pipL:
					if program_variables.pipR != None and program_variables.pipR.has_tip == True:
						program_variables.pipR.drop_tip()
					if program_variables.pipL.has_tip == False:
						check_tip_and_pick(program_variables.pipL,
						 				   user_variables.APINameTipL,
										   dict(zip(protocol.deck.keys(), protocol.deck.values())),
										   protocol,
										   replace_tiprack = user_variables.replaceTiprack,
										   initial_tip = user_variables.startingTipPipL,
										   same_tiprack = program_variables.sameTipRack)

					# To use the distribute_z_tracking_falcon15_50ml function we need to group the same wells with the same volume
					grouped_wells_L = {}
					for volume, well in zip(volumes_distribute_pipL, positions_distribute_pipL):
						if volume not in grouped_wells_L:
							grouped_wells_L[volume] = []
						grouped_wells_L[volume].append(well)
					
					# We distribute the different groups of same volumes that we have created previously
					for volume_distribute, positions_distribute in grouped_wells_L.items():
						# PIck up a tip in case teh pipette doesnt have 1
						if program_variables.pipL.has_tip == False:
							check_tip_and_pick(program_variables.pipL,
											   user_variables.APINameTipL,
											   dict(zip(protocol.deck.keys(), protocol.deck.values())),
											   protocol,
											   replace_tiprack = user_variables.replaceTiprack,
											   initial_tip = user_variables.startingTipPipL,
											   same_tiprack = program_variables.sameTipRack)
						
						# We distribute it and update the volume that is left in the falcon so the height aspiration goes smoothly
						volume_tube = distribute_z_tracking_falcon15_50ml (program_variables.pipL,
														user_variables.APINameTipL,
														dict(zip(protocol.deck.keys(), protocol.deck.values())),
														volume_tube,
														volume_distribute,
														position_tube,
														positions_distribute,
														user_variables.maxVolumeTubeReagent,
														protocol,
														user_variables.maxVolumeTiprackPipetteL,
														new_tip = tip_distribute_function,
														replace_tiprack = user_variables.replaceTiprack,
														initial_tip_pip = user_variables.startingTipPipL,
														same_tiprack = program_variables.sameTipRack,
														touch_tip = user_variables.touchTipDistributeMedia)
						
						if (user_variables.changeTipDistribute == "well" or user_variables.changeTipDistribute == "aspirate") and program_variables.pipL.has_tip == True:
							program_variables.pipL.drop_tip()
				
				# We perform the same as we did with the left pipette but distributing the volume assigned to the right one
				if volumes_distribute_pipR:
					if program_variables.pipL != None and program_variables.pipL.has_tip == True:
						program_variables.pipL.drop_tip()
					if program_variables.pipR.has_tip == False:
						check_tip_and_pick(program_variables.pipR,
						 				   user_variables.APINameTipR,
										   dict(zip(protocol.deck.keys(), protocol.deck.values())),
										   protocol,
										   replace_tiprack = user_variables.replaceTiprack,
										   initial_tip = user_variables.startingTipPipR,
										   same_tiprack = program_variables.sameTipRack)

					grouped_wells_R = {}
					for volume, well in zip(volumes_distribute_pipR, positions_distribute_pipR):
						if volume not in grouped_wells_R:
							grouped_wells_R[volume] = []
						grouped_wells_R[volume].append(well)
					
					for volume_distribute, positions_distribute in grouped_wells_R.items():
						if program_variables.pipR.has_tip == False:
							check_tip_and_pick(program_variables.pipR,
											   user_variables.APINameTipR,
											   dict(zip(protocol.deck.keys(), protocol.deck.values())),
											   protocol,
											   replace_tiprack = user_variables.replaceTiprack,
											   initial_tip = user_variables.startingTipPipR,
											   same_tiprack=program_variables.sameTipRack)

						volume_tube = distribute_z_tracking_falcon15_50ml (program_variables.pipR,
														user_variables.APINameTipR,
														dict(zip(protocol.deck.keys(), protocol.deck.values())),
														volume_tube,
														volume_distribute,
														position_tube,
														positions_distribute,
														user_variables.maxVolumeTubeReagent,
														protocol,
														user_variables.maxVolumeTiprackPipetteR,
														new_tip = tip_distribute_function,
														replace_tiprack = user_variables.replaceTiprack,
														initial_tip_pip = user_variables.startingTipPipR,
														same_tiprack = program_variables.sameTipRack,
														touch_tip = user_variables.touchTipDistributeMedia)
						
						if (user_variables.changeTipDistribute == "well" or user_variables.changeTipDistribute == "aspirate") and program_variables.pipR.has_tip == True:
							program_variables.pipR.drop_tip()

			# We take the voluems and positions that we have already transferred volume to
			del volumes_reagent[:reactions_tube]
			del wells_reagent[:reactions_tube]
		
		# We throw the tips unless the chnage tip is never to go to the next reagent and distribute its volumes
		if user_variables.changeTipDistribute != "never":
			if program_variables.pipR != None and program_variables.pipR.has_tip == True:
				program_variables.pipR.drop_tip()
			if program_variables.pipL != None and program_variables.pipL.has_tip == True:
				program_variables.pipL.drop_tip()
	
	# We have finished distributing the volumes with the single channel and we will not use it again so we just throw every tip that is attached to them
	# Only the pipettes that are single channel will have tips because we have not used the multi-channel ones in case there is any attached
	if program_variables.pipR != None and program_variables.pipR.has_tip == True:
		program_variables.pipR.drop_tip()
	if program_variables.pipL != None and program_variables.pipL.has_tip == True:
		program_variables.pipL.drop_tip()

	#-------------------------------------------------------------------------------------------------------------------------------
	# Now we will  transfer the volumes of the final plates that are going to be completed with a multi-channel
	# program_variables.neededColumnsMulti will exist if at least 1 final plate is going to be created with a multi-channel
	if program_variables.neededColumnsMulti:
		# We find out if the sorting is needed, which we will do it if the change tip is set as aspirate
		if user_variables.changeTipDistribute == "aspirate":
			sort = True
		else:
			sort = False

		for values_column in program_variables.neededColumnsMulti.sourceColumnsNeeded.values():
			# We are going to create a list with all the columns and volumes of all the final plates that are going to be sourced by this column
			all_columns_transfer_source_column = []
			all_volumes_transfer_source_column = []

			for name_plate, list_positions_volumes in values_column["Final Columns"].items():
				if name_plate not in program_variables.finalPlates.keys(): # If it goes inside of this conditio it is because is a plate that comes from a replica
					for main_plate in program_variables.finalPlates.values():
						if name_plate in main_plate['Plates Replicas']:
							# Define the plate
							ot_labware = main_plate['Plates Replicas'][name_plate]
							break # We have already found the plate os we break the loop
				else: # If it goes inside of this loop it is a plate set by the user
					# Define the plate
					ot_labware = program_variables.finalPlates[name_plate]["Opentrons Place"]

				# Now we are going to transform the list of column names of that plate to the actual well positions thta we can work with
				for name_column, volume_column in list_positions_volumes:
					# We are going to add the volume that the pipette needs to transfer, which if the final labware has 1 wlel it is the final volume divided by 8
					if user_variables.dimensionsFinalLabware["row"] == 1:
						all_volumes_transfer_source_column.append(volume_column/8)
					else:
						all_volumes_transfer_source_column.append(volume_column)
					
					# We are only going to add to the list of positions the first well of that column because for opentrons when using a multi channel pipette is equivalent to say the whole column
					all_columns_transfer_source_column.append(ot_labware.columns_by_name()[name_column][0])

			# Now that we have the complet list of final columns where this reagent column needs to be transferred to we will loop over all the columns that we have calculated previously
			# and transfer them from the source columns. We dont need to control the volume because we know how many final wells we can transfer to without running out of volume
			for reactions_column, position_column, volume_column in zip(values_column['Reactions/column'], values_column['Positions Opentrons'], values_column['Volumes/column']):
				# Define which pipette needs to transfer  which volumes
				# We are goign to as well define the position where the volume shoudl be dispensed in the final wells (top, botoom or center)
				# and in case the change tip is defined as aspirate, we are going to sort the volumes to try to minimize the movements the pipette will have to do

				if (program_variables.pipL == None or program_variables.pipR == None) or ((program_variables.pipL != None and program_variables.pipL.channels == 8) and (program_variables.pipR != None and program_variables.pipR.channels == 8)):
					volumes_distribute_pipR, positions_distribute_pipR, volumes_distribute_pipL, positions_distribute_pipL = vol_pipette_matcher (all_volumes_transfer_source_column[:reactions_column],
																																				  all_columns_transfer_source_column[:reactions_column],
																																				  program_variables.pipR,
																																				  program_variables.pipL
																																				  )
					# Establish the position inside the wells (top, bottom or center) and i fneeded, sort them
					positions_distribute_pipR, volumes_distribute_pipR = conversor_well_position_sorter (positions_distribute_pipR, user_variables.positionDistributeMedia, volumes = volumes_distribute_pipR, sort = sort)
					positions_distribute_pipL, volumes_distribute_pipL = conversor_well_position_sorter (positions_distribute_pipL, user_variables.positionDistributeMedia, volumes = volumes_distribute_pipL, sort = sort)
				elif program_variables.pipL != None and program_variables.pipL.channels == 8:
					volumes_distribute_pipR = []
					positions_distribute_pipR = []
					volumes_distribute_pipL = all_volumes_transfer_source_column[:reactions_column]
					positions_distribute_pipL = all_columns_transfer_source_column[:reactions_column]
					
					positions_distribute_pipL, volumes_distribute_pipL = conversor_well_position_sorter (positions_distribute_pipL, user_variables.positionDistributeMedia, volumes = volumes_distribute_pipL, sort = sort)
				elif program_variables.pipR != None and program_variables.pipR.channels == 8:
					volumes_distribute_pipR = all_volumes_transfer_source_column[:reactions_column]
					positions_distribute_pipR = all_columns_transfer_source_column[:reactions_column]
					volumes_distribute_pipL = []
					positions_distribute_pipL = []
					
					positions_distribute_pipR, volumes_distribute_pipR = conversor_well_position_sorter (positions_distribute_pipR, user_variables.positionDistributeMedia, volumes = volumes_distribute_pipR, sort = sort)

				# Distribute with the left pipette
				if volumes_distribute_pipL:
					# We drop the tip in case that there are one left from the previous loop and we pick up a tip with the left pipette
					if program_variables.pipR != None and program_variables.pipR.has_tip == True:
						program_variables.pipR.drop_tip()
					
					if program_variables.pipL.has_tip == False:
						check_tip_and_pick(program_variables.pipL,
						 				   user_variables.APINameTipL,
										   dict(zip(protocol.deck.keys(), protocol.deck.values())),
										   protocol,
										   replace_tiprack = user_variables.replaceTiprack,
										   initial_tip = user_variables.startingTipPipL,
										   same_tiprack=program_variables.sameTipRack)

					# If the change tip is well we re going to pick up a tip every time we access to the final well which means that also when we aspirate we pick up a tip
					if user_variables.changeTipDistribute == "well":
						for volume, position in zip(volumes_distribute_pipL, positions_distribute_pipL):
							if volume <= user_variables.maxVolumeTiprackPipetteL: # The volume can be transferred with 1 movement
								if program_variables.pipL.has_tip == False:
									check_tip_and_pick(program_variables.pipL,
													   user_variables.APINameTipL,
													   dict(zip(protocol.deck.keys(), protocol.deck.values())),
													   protocol,
													   replace_tiprack = user_variables.replaceTiprack,
													   initial_tip = user_variables.startingTipPipL,
													   same_tiprack = program_variables.sameTipRack)
								program_variables.pipL.transfer(volume, position_column, position, new_tip = "never", touch_tip = user_variables.touchTipDistributeMedia)
								program_variables.pipL.drop_tip()
							else: # The volume needs to be transferred with more than 1 movement
								# We calculate how many full movements we can do
								min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteL)
								if rest_volume > 0 and rest_volume < program_variables.pipL.min_volume:
									vol_transfer = int(min_full_movements-1)*[user_variables.maxVolumeTiprackPipetteL]
									vol_transfer += [(user_variables.maxVolumeTiprackPipetteL/2)+rest_volume, user_variables.maxVolumeTiprackPipetteL/2]
								elif rest_volume == 0:
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteL]
								else: # The rest volume cannot be transferred with the pipette and needs to be readjusted lowering by a unit the min_full_movements
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteL]
									vol_transfer.append(rest_volume)
								
								# Transfer the volumes changing the tip for every movement
								for volumen in vol_transfer:
									if program_variables.pipL.has_tip == False:
										check_tip_and_pick(program_variables.pipL,
							 							   user_variables.APINameTipL,
														   dict(zip(protocol.deck.keys(), protocol.deck.values())),
														   protocol,
														   replace_tiprack = user_variables.replaceTiprack,
														   initial_tip = user_variables.startingTipPipL,
														   same_tiprack = program_variables.sameTipRack)
									program_variables.pipL.transfer(volumen,
										 							position_column,
																	position,
																	new_tip = "never",
																	touch_tip = user_variables.touchTipDistributeMedia)
									program_variables.pipL.drop_tip()
					elif user_variables.changeTipDistribute == "aspirate":
						# If the new tip is aspirate every time it goes to the source tube the tip will be changed
						# We are going to find out the positions and volumes that can be transferred with 1 movement and between group and group we will change the tip
						groups_positions = []
						group_volumes = []
						current_group_pos = []
						current_group_vol = []
						# We iterate over all the volumes to create the groups of pipette movements
						for volume, position in zip(volumes_distribute_pipL, positions_distribute_pipL):
							if sum(current_group_vol) + volume <= user_variables.maxVolumeTiprackPipetteL:
								# The volume fits in the current pipette movement but nothing more does so a new pipette movement is needed
								current_group_vol.append(volume)
								current_group_pos.append(position)
							else: # The volume does not fit in that movement
								if len(current_group_vol) > 0: # We add the group and we re start a new one
									group_volumes.append(current_group_vol)
									groups_positions.append(current_group_pos)
									current_group_pos = []
									current_group_vol = []
								
								# If the volume that needs to be added can we transferred with only 1 movement we directly add it
								if volume <= user_variables.maxVolumeTiprackPipetteL:
									current_group_vol.append(volume)
									current_group_pos.append(position)
								else: # The volume needs to be transferred with more than 1 movement so we 
									min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteL)
									if rest_volume == 0:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteL])
											groups_positions.append([position])
									elif rest_volume >= program_variables.pipL.min_volume:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteL])
											groups_positions.append([position])
										current_group_vol.append(rest_volume)
										current_group_pos.append(position)
									else: # rest_volume < pipL.min_volume
										for _ in range(int(min_full_movements)-1):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteL])
											groups_positions.append([position])
										group_volumes.append([(user_variables.maxVolumeTiprackPipetteL/2)+rest_volume])
										groups_positions.append([position])
										current_group_vol.append(user_variables.maxVolumeTiprackPipetteL/2)
										current_group_pos.append(position)

						if current_group_vol: # The last volume group needs to be add as well
							group_volumes.append(current_group_vol)
							groups_positions.append(current_group_pos)

						# We distribute those group of volumes knowing that will be only 1 movement
						for volumes_distribute, positions_distribute in zip(group_volumes, groups_positions):
							if program_variables.pipL.has_tip == False:
								check_tip_and_pick(program_variables.pipL,
												   user_variables.APINameTipL,
												   dict(zip(protocol.deck.keys(), protocol.deck.values())),
												   protocol,
												   replace_tiprack = user_variables.replaceTiprack,
												   initial_tip = user_variables.startingTipPipL,
												   same_tiprack = program_variables.sameTipRack)
							program_variables.pipL.distribute(volumes_distribute,
										 					  position_column,
															  positions_distribute,
															  new_tip = "never",
															  disposal_volume = 0,
															  touch_tip = user_variables.touchTipDistributeMedia)
							program_variables.pipL.drop_tip()
					else: # The change tip is never or reagent so we directly distribute the volumes to their positions
						if program_variables.pipL.has_tip == False:
							check_tip_and_pick(program_variables.pipL,
											   user_variables.APINameTipL,
											   dict(zip(protocol.deck.keys(), protocol.deck.values())),
											   protocol,
											   replace_tiprack = user_variables.replaceTiprack,
											   initial_tip = user_variables.startingTipPipL,
											   same_tiprack = program_variables.sameTipRack)
						program_variables.pipL.distribute(volumes_distribute_pipL,
														  position_column,
														  positions_distribute_pipL,
														  new_tip = "never",
														  disposal_volume = 0,
														  touch_tip = user_variables.touchTipDistributeMedia)
				
				# We do the same as with the volumes that had to be distributed with the left pipette
				if volumes_distribute_pipR:
					if program_variables.pipL != None and program_variables.pipL.has_tip == True:
						program_variables.pipL.drop_tip()
					
					if program_variables.pipR.has_tip == False:
						check_tip_and_pick(program_variables.pipR,
										   user_variables.APINameTipR,
										   dict(zip(protocol.deck.keys(), protocol.deck.values())),
										   protocol,
										   replace_tiprack = user_variables.replaceTiprack,
										   initial_tip = user_variables.startingTipPipR,
										   same_tiprack = program_variables.sameTipRack)
				
					if user_variables.changeTipDistribute == "well":
						for volume, position in zip(volumes_distribute_pipR, positions_distribute_pipR):
							if volume <= user_variables.maxVolumeTiprackPipetteR:
								if program_variables.pipR.has_tip == False:
									check_tip_and_pick(program_variables.pipR,
													   user_variables.APINameTipR,
													   dict(zip(protocol.deck.keys(), protocol.deck.values())),
													   protocol,
													   replace_tiprack = user_variables.replaceTiprack,
													   initial_tip = user_variables.startingTipPipR,
													   same_tiprack = program_variables.sameTipRack)
								program_variables.pipR.transfer(volume,
																position_column,
																position,
																new_tip = "never",
																touch_tip = user_variables.touchTipDistributeMedia)
								program_variables.pipR.drop_tip()
							else:
								min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteR)
								if rest_volume > 0 and rest_volume < program_variables.pipR.min_volume:
									vol_transfer = int(min_full_movements-1)*[user_variables.maxVolumeTiprackPipetteR]
									vol_transfer += [(user_variables.maxVolumeTiprackPipetteR/2)+rest_volume, user_variables.maxVolumeTiprackPipetteR/2]
								elif rest_volume == 0:
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteR]
								else:
									vol_transfer = int(min_full_movements)*[user_variables.maxVolumeTiprackPipetteR]
									vol_transfer.append(rest_volume)

								for volumen in vol_transfer:
									if program_variables.pipR.has_tip == False:
										check_tip_and_pick(program_variables.pipR,
														   user_variables.APINameTipR,
														   dict(zip(protocol.deck.keys(), protocol.deck.values())),
														   protocol,
														   replace_tiprack = user_variables.replaceTiprack,
														   initial_tip = user_variables.startingTipPipR,
														   same_tiprack = program_variables.sameTipRack)
									program_variables.pipR.transfer(volumen,
																	position_column,
																	position,
																	new_tip = "never",
																	touch_tip = user_variables.touchTipDistributeMedia)
									program_variables.pipR.drop_tip()
					elif user_variables.changeTipDistribute == "aspirate":
						groups_positions = []
						group_volumes = []
						current_group_pos = []
						current_group_vol = []
						for volume, position in zip(volumes_distribute_pipR, positions_distribute_pipR):
							if sum(current_group_vol) + volume <= user_variables.maxVolumeTiprackPipetteR:
								current_group_vol.append(volume)
								current_group_pos.append(position)
							else:
								if len(current_group_vol) > 0:
									group_volumes.append(current_group_vol)
									groups_positions.append(current_group_pos)
									current_group_pos = []
									current_group_vol = []

								if volume <= user_variables.maxVolumeTiprackPipetteR:
									current_group_vol.append(volume)
									current_group_pos.append(position)
								else:
									min_full_movements, rest_volume = divmod(volume, user_variables.maxVolumeTiprackPipetteR)
									if rest_volume == 0:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteR])
											groups_positions.append([position])
									elif rest_volume >= program_variables.pipR.min_volume:
										for _ in range(int(min_full_movements)):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteR])
											groups_positions.append([position])
										current_group_vol.append(rest_volume)
										current_group_pos.append(position)
									else:
										for _ in range(int(min_full_movements)-1):
											group_volumes.append([user_variables.maxVolumeTiprackPipetteR])
											groups_positions.append([position])
										group_volumes.append([(user_variables.maxVolumeTiprackPipetteR/2)+rest_volume])
										groups_positions.append([position])
										current_group_vol.append(user_variables.maxVolumeTiprackPipetteR/2)
										current_group_pos.append(position)

						if current_group_vol:
							group_volumes.append(current_group_vol)
							groups_positions.append(current_group_pos)
						
						for volumes_distribute, positions_distribute in zip(group_volumes, groups_positions):
							if program_variables.pipR.has_tip == False:
								check_tip_and_pick(program_variables.pipR,
												   user_variables.APINameTipR,
												   dict(zip(protocol.deck.keys(), protocol.deck.values())),
												   protocol,
												   replace_tiprack = user_variables.replaceTiprack,
												   initial_tip = user_variables.startingTipPipR,
												   same_tiprack = program_variables.sameTipRack)
							program_variables.pipR.distribute(volumes_distribute,
															  position_column,
															  positions_distribute,
															  new_tip = "never",
															  disposal_volume = 0,
															  touch_tip = user_variables.touchTipDistributeMedia)
							program_variables.pipR.drop_tip()
					else:
						if program_variables.pipR.has_tip == False:
							check_tip_and_pick(program_variables.pipR,
											   user_variables.APINameTipR,
											   dict(zip(protocol.deck.keys(), protocol.deck.values())),
											   protocol,
											   replace_tiprack = user_variables.replaceTiprack,
											   initial_tip = user_variables.startingTipPipR,
											   same_tiprack = program_variables.sameTipRack)
						program_variables.pipR.distribute(volumes_distribute_pipR,
														  position_column,
														  positions_distribute_pipR,
														  new_tip = "never",
														  disposal_volume = 0,
														  touch_tip = user_variables.touchTipDistributeMedia)

				# We take from the list of final columns the ones that we have already transferred the volumes
				del all_columns_transfer_source_column[:reactions_column]
				del all_volumes_transfer_source_column[:reactions_column]

			# Unless the change tip is never we will drop the tip to go to the next reagent
			if user_variables.changeTipDistribute != "never":
				if program_variables.pipR != None and program_variables.pipR.has_tip == True:
					program_variables.pipR.drop_tip()
				if program_variables.pipL != None and program_variables.pipL.has_tip == True:
					program_variables.pipL.drop_tip()
	
	# We have finished transferring the volumes with the multi channel pipette so we drop the tips that are still attached
	if program_variables.pipR != None and program_variables.pipR.has_tip == True:
		program_variables.pipR.drop_tip()
	if program_variables.pipL != None and program_variables.pipL.has_tip == True:
		program_variables.pipL.drop_tip()

	# Home the robot
	protocol.home()