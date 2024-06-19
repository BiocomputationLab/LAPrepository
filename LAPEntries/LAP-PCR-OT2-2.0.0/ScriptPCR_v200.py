# LAP-PCR-OT2-2.0.0

# This script automates the creation of a PCR mix and its associated temperature profile using an Opentrons OT-2 robot. 

# Workflow of the script (in a nutshell):
# 1. Input Handling: Read and process the Excel template to retrieve user-defined settings.
# 2. Resource Calculation: Determine the number and placement of plates, heater-shaker(s), reagents, tubes, tip racks, etc.
# 3. Preparation of PCR mix(es)/set(s): Transfer to mix tubes water, primers, and polymerase in that order.
# 4. Mixing and distribute of sets: each tube of the set or sets is mixed with a heater-shaker or pipette and distributed to final plate(s)
# 5. Sample Transfer:Samples are transferred to the final plates, and a map is created to show the location of each sample with its corresponding PCR set
# 6. Export Map: the map with all the sheets corresponding to the layout odf the samples with sets is exported to /data/user_storage folder of teh robot
# 7. Temperature Profile (Optional): a temperature profile, it will be performed using the Opentrons thermocycler.

# Both use of heater-shaker(s) and thermocycler are optional and can be set by the user

# For more info go to:
#  Github page with code: https://github.com/BiocomputationLab/LAPrepository/tree/aeea32437e1b362540d4cd7a49a25e3af6477b0f/LAPEntries/LAP-PCR-OT2-2.0.0
#  Protocols.io page with further instructions of usage: https://www.protocols.io/view/ot-2-pcr-sample-preparation-protocol-n92ldpyznl5b
#  LAP repository entry: https://www.laprepo.com/protocol/pcr-mix-preparation-and-temperature-profile-v-2-0-0

# Packages needed for the running of the protocol
import opentrons
import pandas as pd
import random
import math
import numpy as np
from opentrons.motion_planning.deck_conflict import DeckConflictError
from opentrons.protocol_api.labware import OutOfTipsError

class UserVariables:
	def __init__(self, general, each_plate, pipettes, reagents, modules, profile = None):
		"""
		Class that will contain the parameters setted in the variables csv and will process them to work easily in the rest of the protocol
		The coding of this function is dependant of the variables in the Template of the protocol and the names have to be consistent with the rest of the code
		"""
		self.numberSourcePlates = general[general["Variable Name"] == "Number of Source Plates"]["Value"].values[0]
		self.volumesSamplesPerPlate = reagents[reagents["Variable Name"] == "Volume sample DNA Template (uL)"]["Value"].values[0]
		self.finalMapName = general[general["Variable Name"] == "Final Map Name"]["Value"].values[0]
		self.wellStartFinalPlate = general[general["Variable Name"] == "Well Start Final PCR Plate"]["Value"].values[0]
		
		self.sets = reagents[reagents["Variable Name"] == "Number sets"]["Value"].values[0]
		self.numberPrimerSet = reagents[reagents["Variable Name"] == "Number primer/set"]["Value"].values[0]
		self.polymerase = reagents[reagents["Variable Name"] == "Volume polymerase mix (uL)"]["Value"].values[0]
		self.primer = reagents[reagents["Variable Name"] == "Volume each primer (uL)"]["Value"].values[0]
		self.finalVolume = reagents[reagents["Variable Name"] == "Final volume (uL)"]["Value"].values[0]
		self.extraPipettingFactor = reagents[reagents["Variable Name"] == "Extra Pipetting Factor"]["Value"].values[0]
		
		self.APINamePipL = pipettes[pipettes["Variable Name"] == "API Name Left Pipette"]["Value"].values[0]
		self.APINamePipR = pipettes[pipettes["Variable Name"] == "API Name Right Pipette"]["Value"].values[0]
		self.startingTipPipR = pipettes[pipettes["Variable Name"] == "Initial Tip Right Pipette"]["Value"].values[0]
		self.startingTipPipL = pipettes[pipettes["Variable Name"] == "Initial Tip Left Pipette"]["Value"].values[0]
		self.APINameSamplePlate = general[general["Variable Name"] == "API Name Source Plate"]["Value"].values[0]
		self.APINameFinalPlate = general[general["Variable Name"] == "API Name Final PCR Plate"]["Value"].values[0]
		self.APINameEppendorfPlate = general[general["Variable Name"] == "API Name Eppendorf Reagents Rack"]["Value"].values[0]
		self.APINameTipR = pipettes[pipettes["Variable Name"] == "API Name Tiprack Right Pipette"]["Value"].values[0]
		self.APINameTipL = pipettes[pipettes["Variable Name"] == "API Name Tiprack Left Pipette"]["Value"].values[0]
		self.replaceTiprack = pipettes[pipettes["Variable Name"] == "Replace Tipracks"]["Value"].values[0]
		
		self.positionsControls = list(each_plate[each_plate["Variable Name"] == "Position Controls"].values[0][1:])
		self.positionsNotPCR = list(each_plate[each_plate["Variable Name"] == "Wells not to perform PCR"].values[0][1:])
		self.mapID = list(each_plate[each_plate["Variable Name"] == "Map IDs"].values[0][1:])
		self.samplesPerPlate = list(each_plate[each_plate["Variable Name"] == "Number Samples"].values[0][1:])
		self.firstWellSamplePerPlate = list(each_plate[each_plate["Variable Name"] == "Well Start"].values[0][1:])
		self.nameSourcePlates = list(each_plate.columns)
		self.nameSourcePlates.remove("Variable Name")

		self.presenceHS = modules[modules["Variable Name"] == "Presence Heater-Shaker"]["Value"].values[0]
		self.presenceTermo = modules[modules["Variable Name"] == "Presence Thermocycler"]["Value"].values[0]
		self.finalStateLid = modules[modules["Variable Name"] == "Final Open Lid"]["Value"].values[0]
		self.temperatureLid = modules[modules["Variable Name"] == "Temperature Lid"]["Value"].values[0]
		self.finalTemperatureBlock = modules[modules["Variable Name"] == "Hold Block Temperature"]["Value"].values[0]
		self.rpm = modules[modules["Variable Name"] == "RPM Heater-Shaker"]["Value"].values[0]
		self.APINameLabwareHS = modules[modules["Variable Name"] == "API Name Heater-Shaker Labware"]["Value"].values[0]
		self.volMaxMixTube = modules[modules["Variable Name"] == "Max Volume Per Mix Tube In Shaker"]["Value"].values[0]
		self.pause = modules[modules["Variable Name"] == "Pause Before Temperature Program"]["Value"].values[0]

		# Temperature profile, in case it needs it
		if isinstance(profile, pd.DataFrame):
			self.temperatureProfile = profile.dropna(how="all")
		else:
			self.temperatureProfile = None
		
	def check(self):
		"""
		Function that will check the variables of the Template and will raise errors that will crash the OT run
		It is a validation function of the variables checking errors or inconsistencies

		This function is dependant again with the variabels that we have, some checks are interchangable between protocols, but some of them are specific of the variables
		"""

		labware_context = opentrons.protocol_api.labware
		
		# Check that the minimal needed variables are not left empty
		if pd.isna([self.numberSourcePlates, self.finalMapName, self.wellStartFinalPlate, self.APINameSamplePlate, self.APINameFinalPlate, self.APINameEppendorfPlate]).any():
			raise Exception("No variable in the sheet 'GeneralVariables' can be left empty")
		
		if pd.isna([self.sets, self.numberPrimerSet, self.polymerase, self.primer, self.finalVolume, self.extraPipettingFactor, self.volumesSamplesPerPlate]).any():
			raise Exception("No variable in the sheet 'ReagentsPerReaction' can be left empty")
		
		# We need at least 1 source plate
		if self.numberSourcePlates < 1:
			raise Exception("We need at least 1 DNA template plates to perform the protocol")

		# Check all the boolean values and set them
		if self.presenceHS in ["true", "True", "TRUE", True, 1]:
			self.presenceHS = True
		elif self.presenceHS in ["false", "FALSE", "False", False, 0]:
			self.presenceHS = False
		else:
			raise Exception ("The variable 'Presence Heater-Shaker' only accepts 2 values, True or False")
		
		if self.replaceTiprack in ["true", "TRUE", "True", True, 1]:
			self.replaceTiprack = True
		elif self.replaceTiprack in ["false", "FALSE", "False", False, 0]:
			self.replaceTiprack = False
		else:
			raise Exception ("The variable 'Replace Tipracks' always need to be filled and only accepts 2 values, True or False")
		
		if self.presenceTermo in ["true", "True", "TRUE", True, 1]:
			self.presenceTermo = True
		elif self.presenceTermo in ["false", "FALSE", "False", False, 0]:
			self.presenceTermo = False
		else:
			raise Exception ("The variable 'Presence Thermocycler' only accepts 2 values, True or False")
		
		# Now we check the variables that need to be filled if there is a thermocycler established
		if self.presenceTermo:
			if pd.isna(self.finalStateLid):
				self.finalStateLid = False
			else:
				if self.finalStateLid in ["true", "TRUE", "True", True, 1]:
					self.finalStateLid = True
				elif self.finalStateLid in ["false", "FALSE", "False", False, 0]:
					self.finalStateLid = False
				else:
					raise Exception ("The variable 'Final Open Lid' only accepts 2 values, True or False. If True at the end of the thermocycler steps the lid will be open and closed if False. If left empty, it will be assumed as False")
		
			if self.pause in ["true", "TRUE", "True", True, 1]:
				self.pause = True
			elif self.pause in ["false", "FALSE", "False", False, 0]:
				self.pause = False
			else:
				raise Exception ("The variable 'Pause Before Temperature Program' only accepts 2 values, True or False.")
			
			if not isinstance(self.temperatureProfile, pd.DataFrame):
				raise Exception ("We do not have the Sheet 'TemperatureProfile' but we have the variable 'Presence of Thermocycler' set as True, that is incompatible")
			else: # Let's check the values of the temperature profile dataframe are correct
				# First check that it has the appropiate columns
				if not all(item in self.temperatureProfile.columns for item in ["Temperature", "Time (s)", "Number of Cycles", "Cycle Status"]):
					raise Exception('4 columns are needed in the TemperatureProfile sheet: "Temperature", "Time (s)", "Number of Cycles" and "Cycle Status"')
				for row in self.temperatureProfile.iterrows():
					# Let's check that no cells are left empty
					if any(pd.isna(element) for element in row[1].values):
						raise Exception("In a row in the sheet TemperatureProfile none of the cells can have an empty value")
					# Check that the cycles status have any of the possible values
					if row[1]["Cycle Status"].lower() not in ["start","end","-"]:
						raise Exception("One step of the profile has another value for 'Cycle Status' that is neither 'Start', 'End' nor '-'")
					if pd.isna(row[1]["Time (s)"]) or type(row[1]["Time (s)"]) not in [float, int]:
						raise Exception("The time of each step in the temperature profile need to be filled and with a number")
					if pd.isna(row[1]["Number of Cycles"]) or not (row[1]["Number of Cycles"] == "-" or type(row[1]["Number of Cycles"]) == int):
						raise Exception("The number of cycles for each step in the temperature profile cannot be left empty, it has to be a hyphen or a integer")
					if row[1]["Cycle Status"].lower() == "end" and type(row[1]["Number of Cycles"]) != int:
						raise Exception("In the rows where the value for 'Cycle Status' is End, the value of the column 'Number of Cycles' needs to be a integer")
					if pd.isna(row[1]["Temperature"]) or type(row[1]["Temperature"]) not in [float, int]:
						raise Exception("The temperature of each step in the temperature profile need to be filled and with a number")
					# Not we check that the temperatures are between the ranges
					if row[1]["Temperature"] > 110 or row[1]["Temperature"] < 4:
						raise Exception("One step of the profile cannot be set with the thermocycler, the operative range of the thermocycler is 4-99C")
			
			if pd.isna(self.temperatureLid):
				raise Exception ("If the thermocycler is present, the variable 'Temperature Lid' needs to have a value")
			
			if self.temperatureLid > 110 or self.temperatureLid < 37:
				raise Exception("Lid temperature cannot be set with the thermocycler, the operative range of the thermocycler is 37-110C")
			
		else:
			self.finalStateLid = None
			self.pause = None
			self.temperatureLid = None
		
		# Now we check the variables that need to be filled if there is a heater shaker established
		if self.presenceHS:
			if pd.isna(self.rpm) or pd.isna(self.APINameLabwareHS):
				raise Exception ("If the Heater-Shaker is present there are 2 variables that cannot be left empty: 'RPM Heater-Shaker' and 'API Name Heater-Shaker Labware'")
			try:
				self.rpm = int(self.rpm)
			except ValueError:
				raise Exception("If the Heater-Shaker is present the variable 'RPM Heater-Shaker' needs to be a whole number")
		else:
			self.rpm = None
			self.APINameLabwareHS = None
		
		# Check that there is at least 1 pipette to perform the protocol
		if pd.isna(self.APINamePipL) and pd.isna(self.APINamePipR):
			raise Exception("There must be at least 1 pipette set to perform this protocol")
		
		# Check that there are as many columns, at least, as the number or source plates
		if all(len(list) < self.numberSourcePlates for list in [self.samplesPerPlate, self.firstWellSamplePerPlate, self.positionsControls, self.positionsNotPCR, self.mapID]):
			raise Exception("There should be at least as many columns of source plate values in the sheet SamplesPlateVariables as the number stated in 'Number of Source Plates'")
		
		# Check if there is some value of the plates where it shouldnt in the per plate sheet
		if any(pd.isna(elem) == True for elem in self.samplesPerPlate[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.samplesPerPlate[self.numberSourcePlates:]):
			raise Exception("The values of 'Number Samples' need to be as many as the 'Number of Source Plates' and in consecutive columns")
		if any(pd.isna(elem) == True for elem in self.firstWellSamplePerPlate[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.firstWellSamplePerPlate[self.numberSourcePlates:]):
			raise Exception("The values of 'Well Start' need to be as many as the 'Number of Source Plates' and in consecutive columns")
		if any(pd.isna(elem) == False for elem in self.positionsControls[self.numberSourcePlates:]):
			raise Exception("The values of 'Position Controls' need to be in the column of the plate is going to be used and they have to be in consecutive columns")
		if any(pd.isna(elem) == False for elem in self.positionsNotPCR[self.numberSourcePlates:]):
			raise Exception("The values of 'Wells not to perform PCR' need to be in the column of the plate is going to be used and they have to be in consecutive columns")
		if any(pd.isna(elem) == False for elem in self.mapID[self.numberSourcePlates:]):
			raise Exception("The values of 'Map IDs' need to be in the column of the plate is going to be used and they have to be in consecutive columns. You can leave the values empty as well.")
		
		# Check that if the pipette is not empty, nor the tiprack or the initial pipette should not be empty
		if not pd.isna(self.APINamePipL) and (pd.isna(self.startingTipPipL) or pd.isna(self.APINameTipL)):
			raise Exception("If the variable 'API Name Left Pipette' has a value, both 'API Name Tiprack Left Pipette' and 'Initial Tip Left Pipette' need to be filled")
		
		if pd.isna(self.APINamePipL):
			self.startingTipPipL = None
			self.APINameTipL = None
		
		if not pd.isna(self.APINamePipR) and (pd.isna(self.startingTipPipR) or pd.isna(self.APINameTipR)):
			raise Exception("If the variable 'API Name Right Pipette' has a value, both 'API Name Tiprack Right Pipette' and 'Initial Tip Right Pipette' need to be filled")
		
		if pd.isna(self.APINamePipR):
			self.startingTipPipR = None
			self.APINameTipR = None
		
		# Check that if the tipracks are the same, the initial tips should be the same as well
		if not pd.isna(self.APINamePipL) and not pd.isna(self.APINamePipR):
			if self.APINameTipL == self.APINameTipR:
				if self.startingTipPipL != self.startingTipPipR:
					raise Exception("If the tipracks of the right and left mount pipettes are the same, the initial tip should be as well.")
		
		# Let's check that all the labware that needs to be defined exist in the opentrons space
		try:
			definition_source_plate = labware_context.get_labware_definition(self.APINameSamplePlate)
		except OSError:
			raise Exception(f"The source plate labware {self.APINameSamplePlate} is not in the opentrons labware space. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

		try:
			definition_final_plate = labware_context.get_labware_definition(self.APINameFinalPlate)
		except OSError:
			raise Exception(f"The final plate labware {self.APINameFinalPlate} is not in the opentrons labware space. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
		
		try:
			definition_rack = labware_context.get_labware_definition(self.APINameEppendorfPlate)
		except OSError:
			raise Exception(f"The eppendorf rack labware {self.APINameEppendorfPlate} is not in the opentrons labware space. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
		
		if pd.isna(self.APINamePipR) == False:
			try:
				definition_tiprack_right = labware_context.get_labware_definition(self.APINameTipR)
			except OSError:
				raise Exception(f"The tip rack {self.APINameTipR} is not in the opentrons labware space. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
			
			# Check if there isnt any typo in the starting tip of both pipettes
			if pd.isna(self.APINamePipR) == False and (self.startingTipPipR not in definition_tiprack_right["wells"].keys()):
				raise Exception("Starting tip of right pipette is not valid, check for typos")
		
		if pd.isna(self.APINamePipL) == False:
			try:
				definition_tiprack_left = labware_context.get_labware_definition(self.APINameTipL)
			except OSError:
				raise Exception(f"The tip rack {self.APINameTipL} is not in the opentrons labware space. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

			# Check if there isnt any typo in the starting tip of both pipettes
			if pd.isna(self.APINamePipL) == False and (self.startingTipPipL not in definition_tiprack_left["wells"].keys()):
				raise Exception("Starting tip of left pipette is not valid, check for typos")
		
		if self.presenceHS:
			try:
				definition_rack_HS = labware_context.get_labware_definition(self.APINameLabwareHS)
			except OSError:
				raise Exception(f"The heater-shaker eppendorf rack {self.APINameLabwareHS} is not in the opentrons labware space. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
		
		# Check that the initial, final plate and eppendorf rack (both in HS and not) is homogeneous
		if len(definition_source_plate["groups"]) > 1:
			raise Exception("The source plate needs to have only 1 type of well, i.e, the labware needs to be homogeneous")
		
		if len(definition_final_plate["groups"]) > 1:
			raise Exception("The final plate needs to have only 1 type of well, i.e, the labware needs to be homogeneous")
		
		if len(definition_rack["groups"]) > 1:
			raise Exception("The eppendorf rack needs to have only 1 type of tube, i.e, the labware needs to be homogeneous")
		
		if self.presenceHS:
			if len(definition_rack_HS["groups"]) > 1:
				raise Exception("The eppendorf labware in the heater-shaker needs to have only 1 type of well, i.e, the labware needs to be homogeneous")
		
		# Check if the well of the starting plate exist in their source labware
		for index_plate, initial_well_source_plate in enumerate(self.firstWellSamplePerPlate[:self.numberSourcePlates]):
			if initial_well_source_plate not in definition_source_plate["wells"].keys():
				raise Exception(f"The well '{initial_well_source_plate}' from '{self.nameSourcePlates[index_plate]}' does not exist in the labware {self.APINameSamplePlate}, check for typos")
		
		# Check that the control and not pick positions actually exist in the source labware
		# As well, we are going to check that they are not the same ones
		for index_plate, (control_positions, not_pick_positions) in enumerate(zip(self.positionsControls[:self.numberSourcePlates], self.positionsNotPCR[:self.numberSourcePlates])):
			if pd.isna(control_positions):
				control_positions = []
			else:
				control_positions = control_positions.replace(" ","").split(",")
			
			if pd.isna(not_pick_positions):
				not_pick_positions = []
			else:
				not_pick_positions = not_pick_positions.replace(" ","").split(",")

			for position_control in control_positions:
				if position_control not in definition_source_plate["wells"].keys():
					raise Exception(f"The well '{position_control}' given in 'Position Controls' of '{self.nameSourcePlates[index_plate]}' does not exist in the labware {self.APINameSamplePlate}, check for typos")
			
			for position_notpick in not_pick_positions:
				if position_notpick not in definition_source_plate["wells"].keys():
					raise Exception(f"The well '{position_notpick}' given in 'Wells not to perform PCR' of '{self.nameSourcePlates[index_plate]}' does not exist in the labware {self.APINameSamplePlate}, check for typos")
				
				if position_notpick in position_control:
					raise Exception("There cannot be a well in both 'Position Controls' and 'Wells not to perform PCR' variables for the same source plate")
		
		# We are going to check that the number of samples in each plate is not larger than the capacity of the source plates
		for number_plate, number_cells_per_plate in enumerate(self.samplesPerPlate[:self.numberSourcePlates]):
			if type(number_cells_per_plate) != int and number_plate < self.numberSourcePlates:
				raise Exception("Every cell of 'Samples per plate' has to be a number")
			if len(definition_source_plate["wells"]) < number_cells_per_plate:
				raise Exception(f"Number of cells is larger than the capacity of the source plate labware in '{self.nameSourcePlates[number_plate]}'")
			if not pd.isna(self.positionsControls[number_plate]) and len(definition_source_plate["wells"]) < number_cells_per_plate + len(self.positionsControls[number_plate].replace(" ","").split(",")): # Different one just to make clearer to the user the error
				raise Exception(f"Number of samples and controls is larger than the capacity of the source plate labware in '{self.nameSourcePlates[number_plate]}'") 
			
			index_first_well = definition_source_plate["groups"][0]["wells"].index(self.firstWellSamplePerPlate[number_plate])
			if len(definition_source_plate["wells"]) < index_first_well + number_cells_per_plate:
				raise Exception(f"There cannot be as many samples in the source plate '{self.nameSourcePlates[number_plate]}' taking in account the first well with sample, in this case, {number_cells_per_plate} samples starting in {self.firstWellSamplePerPlate[number_plate]}")
		
		# Check if final start well exists in the final labware
		if self.wellStartFinalPlate not in definition_source_plate["wells"].keys():
			raise Exception(f"The well '{self.wellStartFinalPlate}' given in '{self.nameSourcePlates[number_plate]}' does not exist in the labware {self.APINameSamplePlate}, check for typos")
 
		# Check the positions not to take (for PCR) are inside of the established sample (well_start + number_samples) for every source plate
		for index_plate, pos_notPCR in enumerate(self.positionsNotPCR[:self.numberSourcePlates]):
			index_first_well = definition_source_plate["groups"][0]["wells"].index(self.firstWellSamplePerPlate[index_plate])
			wells_with_samples = definition_source_plate["groups"][0]["wells"][index_first_well:] # Initial list

			# Take out the control positions from the list
			if not pd.isna(self.positionsControls[index_plate]):
				for pos_control in self.positionsControls[index_plate].replace(" ","").split(","):
					try:
						wells_with_samples.remove(pos_control)
					except ValueError: # This error will arise if the control position is outside of the first_well+number_samples
						pass
			
			# Check if the samples fit in the soruce labware when we take out the control positions
			if len(wells_with_samples) < self.samplesPerPlate[index_plate]: 
				raise Exception(f"""There cannot be as many samples taking in account the first well with sample, {self.firstWellSamplePerPlate[index_plate]}, and {self.samplesPerPlate[index_plate]} samples from that point.
Take in account that control positions are not taken in account in this number.
In this case, the number of wells available for samples (to take and not take) are {len(wells_with_samples)}, after taking out the controls the user has established ({self.positionsControls[index_plate]}).""")

			wells_with_samples = wells_with_samples[:self.samplesPerPlate[index_plate]] # All the wells where should be samples, either to take for PCR or not take for PCR

			if not pd.isna(pos_notPCR):
				not_pcr = pos_notPCR.replace(" ","").split(",")
				for pos_notPCR in not_pcr:
					if pos_notPCR not in wells_with_samples:
						raise Exception(f"The well {pos_notPCR} of '{self.nameSourcePlates[index_plate]}' is not inside of the samples given for this plate considering the first well with samples, {self.firstWellSamplePerPlate[index_plate]}, and the number of samples set for this plate, {self.samplesPerPlate[index_plate]}")
		
		# Check that no variable in ReagentsPerReaction is a string
		if any(type(variable) == str for variable in [self.primer, self.numberPrimerSet, self.polymerase, self.sets, self.volumesSamplesPerPlate, self.finalVolume, self.extraPipettingFactor]):
			raise Exception("No variable in the sheet 'ReagentsPerReaction' can be something else than a number")

		# Volume of reactives is larger than the established one
		if (self.primer*self.numberPrimerSet + self.polymerase + self.volumesSamplesPerPlate) > self.finalVolume:
			raise Exception("Volume of each reactive added plus the volume of DNA template is larger than the total volume of reactives")	
		
		# Check if the extra pipetting factor is between 0 an 1
		if pd.isna(self.extraPipettingFactor):
			self.extraPipettingFactor = 0
		else:
			if self.extraPipettingFactor > 1 or self.extraPipettingFactor < 0:
				raise Exception("The variable 'Extra Pipetting Factor' from the sheet 'ReagentsPerReaction' should be a number between 0 and 1")
		
		# Check the variables related to the mixing volume max volume when the heater hsaker is present and need to be checked in that labware
		if self.presenceHS:
			if pd.isna(self.volMaxMixTube): # By default is going to be the 90% of the max volume
				self.volMaxMixTube = 0.9*definition_rack_HS["wells"][list(definition_rack_HS["wells"].keys())[0]]['totalLiquidVolume']
			else:
				# Check that the vol max of the mix tubes is between 0 and the max of the tube
				if self.volMaxMixTube <= 0 or self.volMaxMixTube > definition_rack_HS["wells"][list(definition_rack_HS["wells"].keys())[0]]['totalLiquidVolume']:
					raise Exception(f"The volume in the variable 'Max Volume Per Mix Tube In Shaker' has to be empty, or between 0 and the max volume of the Heater-Shaker Labware, in this case, in the range (0-{definition_rack_HS['wells'][list(definition_rack_HS['wells'].keys())[0]]['totalLiquidVolume']}]")
				
				# Check that at least 1 reaction volume fits in the tube
				if (self.finalVolume - self.volumesSamplesPerPlate)*(1+self.extraPipettingFactor) > self.volMaxMixTube:
					raise Exception(f"The volume in the variable 'Max Volume Per Mix Tube In Shaker' has to be at least equivalent to all the mix/reaction with the extra pipetting factor for 1 sample, in this case the min volume would be {(self.finalVolume - self.volumesSamplesPerPlate)*(1+self.extraPipettingFactor)}")

		# Check the rest of the variables in the sheet ReagentsPerReaction are not 0
		if any(element <= 0 for element in [self.sets, self.numberPrimerSet, self.polymerase, self.primer, self.finalVolume, self.volumesSamplesPerPlate]):
			raise Exception("Only the value of 'Extra Pipetting Factor' in the sheet ReagentsPerReaction can be 0")
		
		# Check that the Number of samples plate is not 0
		if self.numberSourcePlates == 0:
			raise Exception("We need to have at least 1 plate with the DNA templates to create the PCR final plates")
		
		# Check the maps provided for the source plates exist
		for map_name in self.mapID[:self.numberSourcePlates]:
			if pd.isna(map_name):
				pass
			else:
				try:
					# map_dataframe = pd.read_excel("VariablesPCR.xlsx", sheet_name = map_name, index_col = 0, engine = "openpyxl")
					map_dataframe = pd.read_excel("/data/user_storage/VariablesPCR.xlsx", sheet_name = map_name, index_col = 0, engine = "openpyxl")
				except ValueError: # Error that appears when the sheet 'map_name' does not exist in the excel file
					raise Exception(f"The map of IDs '{map_name}' does not exist in the Excel file")
				
				# Check that the provided maps are accord to the set labware
				map_rows, map_columns = map_dataframe.shape
				if map_rows != len(definition_source_plate["ordering"][0]) or map_columns != len(definition_source_plate["ordering"]):
					raise Exception(f"The Sheet '{map_name}' needs to have the same columns and rows as the labware '{self.APINameSamplePlate}'. The names of columns and rows should be included in the sheet")
		
		return
	
class SettedParameters:
	"""
	After the checking the UserVariable class we can assign what we will be using to track the plates
	and working with the variables setted in that class
	"""

	def __init__(self):
		self.sumSamples = 0
		self.pipR = None
		self.pipL = None
		self.sameTiprack = None
		self.samplePlates = {}
		self.finalPlates = {}
		self.reactiveWells = {}
		self.setsWells = {}
		self.volPolymeraseFactor = 0
		self.volPrimerFactor = 0
		self.volTotal = 0
		self.volTotalFactor = 0
		self.volWaterFactor = 0
		self.volWater = 0
		self.tc_mod = None
		self.colors_mediums = ["#ffbb51", "#10D21B", "#3d85c6", "#d3cfcf", "#ff5151", "#783f04"] # Initial filled with the one color of the sample: sample, polymerase, water, mix, not pick samples, controls
		self.liquid_samples = None # Initial
		self.liquid_control = None # Initial
		self.liquid_notpick = None # Initial
		
		return
	
	def assign_variables(self, user_variables, protocol):
		# Assign the colors of the types of samples
		self.liquid_samples = protocol.define_liquid(
			name = "Sample",
			description = "Sample that will be inoculated with the selected medium",
			display_color = "#ffbb51"
		)
		
		self.liquid_notpick = protocol.define_liquid(
			name = "Sample Not Pick",
			description = "Sample that will not be taken to perform a PCR",
			display_color = "#ff5151"
		)
		
		self.liquid_control = protocol.define_liquid(
			name = "Control",
			description = "Sample that will act as control and will be placed at the end of each set",
			display_color = "#783f04"
		)
		
		# Calculate the volumes with the pipette factor for 1 reaction
		self.volTotal = user_variables.finalVolume-user_variables.volumesSamplesPerPlate
		self.volTotalFactor = self.volTotal*(1+user_variables.extraPipettingFactor)
		
		self.volPolymeraseFactor = user_variables.polymerase*(1+user_variables.extraPipettingFactor)
		self.volPrimerFactor = user_variables.primer*(1+user_variables.extraPipettingFactor)
		
		self.volWater = self.volTotal-user_variables.polymerase-(user_variables.primer*user_variables.numberPrimerSet)
		self.volWaterFactor = self.volWater*(1+user_variables.extraPipettingFactor)
		
		self.hs_mods = {} # It will be filled during the run of the protocol ans will contain the heater-shakers
		
		# Pipette Variables
		if pd.isna(user_variables.APINamePipL) == False:
			self.pipL = protocol.load_instrument(user_variables.APINamePipL, mount = "left")
		else:
			# Establish all the variables set to the left pipette as none
			user_variables.APINameTipL = None
			user_variables.startingTipPipL = None
			
		if pd.isna(user_variables.APINamePipR) == False:
			self.pipR = protocol.load_instrument(user_variables.APINamePipR, mount = "right")
		else:
			# Establish all the variables set to the left pipette as none
			user_variables.APINameTipR = None
			user_variables.startingTipPipR = None
		
		if user_variables.APINameTipR == user_variables.APINameTipL:
			self.sameTiprack = True
		else:
			self.sameTiprack = False

		# Establish the thermocycler in case that th evariable set it
		if user_variables.presenceTermo:
			self.tc_mod = protocol.load_module("thermocycler")
			self.tc_mod.open_lid()

		# Source Plates Definition
		for index_plate in range(user_variables.numberSourcePlates):
			# Establish the control positions
			if pd.isna(user_variables.positionsControls[index_plate]):
				control_positions = []
			else:
				control_positions = user_variables.positionsControls[index_plate].replace(" ","").split(",")
			
			# Establish the positions that are not going to be picked
			if pd.isna(user_variables.positionsNotPCR[index_plate]):
				positions_notPCR = []
			else:
				positions_notPCR = user_variables.positionsNotPCR[index_plate].replace(" ","").split(",")

			# Establish the source plates and initialize and/or set their variables
			self.samplePlates[index_plate] = {"Number Samples":user_variables.samplesPerPlate[index_plate],
											  "Position":None,
											  "Opentrons Place":None,
											  "Index First Well Sample": opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameSamplePlate)["groups"][0]["wells"].index(user_variables.firstWellSamplePerPlate[index_plate]),
											  "Control Positions": control_positions,
											  "Number Controls": len(control_positions),
											  "Positions Not Perform PCR": positions_notPCR,
											  "Map Names":None}
			
			# Establish the total ammount of samples that need to be calculated for the total volumes
			self.sumSamples += self.samplePlates[index_plate]["Number Samples"] - len(self.samplePlates[index_plate]["Positions Not Perform PCR"]) + self.samplePlates[index_plate]["Number Controls"] # In this we already take in account the controls because they are inside of the number samples
		
		# Final Plate Variables
		# Lets find first how many final plates do we need
		number_wells_final_plate = len(opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFinalPlate)["wells"])
		number_source_needed = math.ceil((opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFinalPlate)["groups"][0]["wells"].index(user_variables.wellStartFinalPlate)+self.sumSamples*user_variables.sets)/number_wells_final_plate)
		
		# Check if we can establish the final number of plates
		if user_variables.presenceTermo and number_source_needed > 1:
			raise Exception("If 'Presence Thermocycler' is True we can only have 1 final plate and for this protocol to run there is a need for more final plates, try less samples or less set of primers")
		
		# Set the final labware and their variables
		for index_plate in range(number_source_needed):
			self.finalPlates[index_plate] = {"Source Plate":index_plate,
											"Position":None,
											"Opentrons Place":None,
											"Map Samples with Sets":None # We will create this map when we establish the final plate
											}
			
		# Create the reactives dictionary
		# First we define the know reactives
		self.reactiveWells =  {
			"Polymerase":{"Positions":[],
						  "Volumes":None,
						  "Reactions Per Tube":None,
						  "Number Total Reactions":self.sumSamples*user_variables.sets,
						  "Definition Liquid": protocol.define_liquid(name = "Polymerase Mix", description = "Polymerase mix with polymerase, buffer and nucleotides", display_color = "#10D21B")
						  },
			"Water":{"Positions":[],
					 "Volumes":None,
					 "Reactions Per Tube":None,
					 "Number Total Reactions":self.sumSamples*user_variables.sets,
					 "Definition Liquid": protocol.define_liquid(name = "Water", description = "Sterile Water", display_color = "#3d85c6")
					 }
			}
		
		# Now we add the needed primers that can variate depending on the users variables
		for index_primer in range(int(user_variables.sets*user_variables.numberPrimerSet)):
			self.reactiveWells[f"Primer {index_primer+1}"] = {"Positions":[],
															  "Volumes":None,
															  "Reactions Per Tube":None,
															  "Number Total Reactions":self.sumSamples,
															  "Definition Liquid":None
															  }
			primer_number = index_primer+1 # Just for label purposes

			# Establish its color
			while True:
				color_liquid = f"#{random.randint(0, 0xFFFFFF):06x}"
				if color_liquid.lower() not in self.colors_mediums:
					
					self.reactiveWells[f"Primer {primer_number}"]["Definition Liquid"] = protocol.define_liquid(
						name = f"Primer {primer_number}",
						description = f"Reagent Primer {primer_number}",
						display_color = color_liquid
					)
					self.colors_mediums.append(color_liquid)
					
					break

		# Now we add the sets
		for index_set in range(int(user_variables.sets)):
			self.setsWells[f"Set {index_set+1}"] = {"Positions":[], "Reactions Per Tube":None, "Number Total Reactions":self.sumSamples, "Set Primers":[]
													,"Definition Liquid":protocol.define_liquid(
														name = f"Set {index_set+1}",
														description = f"Eppendorf with Set {index_set+1}. Leave empty!",
														display_color = "#d3cfcf")
													}
			
			for primer in range(int(index_set*user_variables.numberPrimerSet), int((index_set*user_variables.numberPrimerSet)+user_variables.numberPrimerSet)):
				self.setsWells[f"Set {index_set+1}"]["Set Primers"].append(f"Primer {primer+1}")
		
		return
	
class MapLabware:
	"""
	Class that will create and store the layout of the final plates so they can be exported at the end
	for the user
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

	3 mandatory arguments are needed for this function to work
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

def run_program_thermocycler (tc_mod, program, lid_temperature, volume_sample, final_lid_state = False, final_block_state = np.nan):
	"""
	Function that will read a table with the steps that the thermocycler should perform and other data needed to establish the steps in the thermocycler

	This function will take 5 mandatory arguments and 2 optional
	"""

	# Error check
	if not all(name in program.columns for name in ["Cycle Status", "Temperature", "Time (s)", "Number of Cycles"]):
		raise Exception("The columns 'Temperature', 'Cycle Status', 'Time (s)' and 'Number of Cycles' need to be in the given table to perform this function")

	# Initialyze the state of the variable cycle that we will use to control if the step is a cycle or a step
	cycle = False
	
	# Set the initial temperature of the lid
	tc_mod.set_lid_temperature(lid_temperature)
	for row in program.iterrows(): # Go through all the table
		# Check if it is a cycle or not, if it is a start of the end of it
		if row[1]["Cycle Status"].lower() == "start": # Start of a set of steps that are goingto be a cycle
			profile_termo =[{"temperature":float(row[1]["Temperature"]),"hold_time_seconds":float(row[1]["Time (s)"])}] # Add the step
			cycle = True
			continue # Go to next row
		elif row[1]["Cycle Status"].lower() == "end": # The cycle has end so it is performed 
			profile_termo.append({"temperature":float(row[1]["Temperature"]),"hold_time_seconds":float(row[1]["Time (s)"])})
			if type(row[1]["Number of Cycles"]) == str:
				raise Exception("A row where the value of the column 'Cycle Status' is End should have a number in the column 'Number of Cycles'")
			elif type(row[1]["Number of Cycles"]) == float:
				raise Exception("The value of 'Number of Cycles' needs to be an integer, it cannot be a float")
			tc_mod.execute_profile(steps = profile_termo,
								   repetitions = row[1]["Number of Cycles"],
								   block_max_volume = volume_sample)
			cycle = False
			continue # Go to next row
		elif row[1]["Cycle Status"].lower() == "-": # Either an isolated step or a step in a cycle
			pass
		else:
			raise Exception (f"The column 'Cycle Status' only accepts 3 values: Start, End or -")
		
		# Now we know if we have to add a step to the cycle or do the step directly
		if cycle == True:
			profile_termo.append({"temperature":float(row[1]["Temperature"]),"hold_time_seconds":float(row[1]["Time (s)"])})
		elif cycle == False:
			tc_mod.set_block_temperature(row[1]["Temperature"],
										 hold_time_seconds = float(row[1]["Time (s)"]),
										 block_max_volume = volume_sample)
	
	
	tc_mod.deactivate_lid()
	
	# Now we are going to put the block at one temeprature and open lid if it is establish like that
	if final_lid_state:
		tc_mod.open_lid()
	
	if not pd.isna(final_block_state):
		tc_mod.set_block_temperature(final_block_state,
									 block_max_volume = volume_sample)
	else:
		tc_mod.deactivate_block()
	
	return

def z_positions_mix_15eppendorf (vol_mixing):
	"""
	Function that will define the positions of mixing according to the volume of each eppendorf tube
	
	These heights have been manually measured for 1.5mL eppendorfs to attach z to aproximatelly the volume associated
	
	We will have 3 mixing heights at the end, but not neccessarilly different within each other
	"""
	
	# Establish the manual measured z height
	position_bottom = 1
	position_100 = 6
	position_100_250 = 9
	position_250 = 11
	position_500 = 16
	position_750 = 20
	position_1000 = 25
	position_1250 = 30
	
	#Assigned to the volume the 3 positions [min, center, max] that we are going to use in the mixing process
	if vol_mixing <= 100: # The values of comparing are volumes (in uL)
		return [position_bottom, position_bottom, position_bottom]
	elif vol_mixing > 100 and vol_mixing <= 250:
		return [position_bottom, position_100, position_100_250]
	elif vol_mixing > 250 and vol_mixing <= 500:
		return [position_bottom, position_100, position_250]
	elif vol_mixing > 500 and vol_mixing <= 750:
		return [position_100, position_250, position_500]
	elif vol_mixing > 750 and vol_mixing <= 1000:
		return [position_100, position_250, position_750]
	elif vol_mixing > 1000 and vol_mixing <= 1250:
		return [position_100, position_500, position_1000]
	elif vol_mixing > 1250:
		return [position_100, position_500, position_1250]

def mixing_eppendorf_15 (location_tube, volume_tube, volume_mixing, pipette):
	"""
	Function that will perform the mixing of a 1.5mL eppendorf tube with a given pipette

	The pipette shoudl have a tip to perform this mixing

	5 arguments are needed for this function
	"""

	# Check if the pipette has a tip
	if not pipette.has_tip:
		raise Exception(f"{pipette} has no tip attached to peform the function 'mixing_eppendorf_15'")

	# Check if the given pipette can aspirate/dispense the volume
	if pipette.min_volume > volume_mixing or pipette.max_volume < volume_mixing:
		raise Exception(f"Volume of mixing, {volume_mixing}uL, should be a value between the {pipette} minimum and maximum aspiration/dispense volume which are {pipette.min_volume}uL and {pipette.max_volume}uL, respectively")
	
	# Check the positions in which the mixing is going to be performed
	positions_mixing = z_positions_mix_15eppendorf (volume_tube) # This is the part that is customized for the 1500uL eppendorfs
	
	# Now we perform the mixing of the eppendorf tube
	# We are going to mix 7 times at different heighs of the tube
	for position in positions_mixing:
		pipette.mix(7, volume_mixing, location_tube.bottom(z = position)) 
	
	for i in range(3):
		pipette.touch_tip(location_tube,v_offset = -20, radius=0.7, speed=30)
	for i in range(3):
		pipette.touch_tip(location_tube,v_offset = -20, radius=0.5, speed=30)
	for i in range(3):
		pipette.touch_tip(location_tube,v_offset = -27, radius=0.3, speed=30)

	# Now we are going to aspirate and dispense 3 times at different heights to mix a little bit more the content of the tube
	for i in range(2):
		pipette.aspirate(volume_mixing, location_tube.bottom(z=positions_mixing[0]))
		pipette.dispense(volume_mixing, location_tube.bottom(z=positions_mixing[2]))
	for i in range(2):
		pipette.aspirate(volume_mixing, location_tube.bottom(z=positions_mixing[2]))
		pipette.dispense(volume_mixing, location_tube.bottom(z=positions_mixing[0]))
	
	# Finally we blow out in the centre of the tube any rests that have been left in the tip
	pipette.blow_out(location_tube.center())
	
	return

def tube_to_tube_transfer (vol_transfer_reaction, positions_source_tubes, reactions_source_tubes, positions_final_tubes, reactions_final_tubes, program_variables, user_variables, protocol, new_tip = "never"):
	"""
	Function that will transfer from n-tubes to m-tubes a volume in relation with the reactions.

	As well, if the pipettes need to be changed to transfer the volume, they will be changed

	If there is a tip attached to the pipette or pipettes, it will be used but at the end it will be dropped
	"""

	# Check that the new_tip has a correct value
	if new_tip not in ["source_tube","final_tube","never","aspirate","tube"]:
		raise Exception("""The function 'tube_to_tuber_transfer' argument 'new_tip' only accepts 5 values:
	* never: it will only change the tip when changing the pipette to transfer
	* source_tube: it will change the tip everytime it changes the pipette to transfer and everytime that the source tube changes
	* final_tube: it will change the tip everytime it changes the pipette to transfer and everytime that the final tube changes
	* tube: it will change the tip everytime it changes the pipette and everytime it changes tubes, both source and final
	* aspirate: it will change the tip everytime it changes the pipette to transfer and everytime it aspirates from teh source plate""")

	# Make sure that we have as many reactions elements as position elements for both source and final
	if len(positions_source_tubes) != len(reactions_source_tubes):
		raise Exception("The length of the lists source tube positions and source tubes reactions should be the same")
	
	if len(positions_final_tubes) != len(reactions_final_tubes):
		raise Exception("The length of the lists final tube positions and final tubes reactions should be the same")
	
	# Initialize the source tube
	source_tubes = generator_positions (list(map(lambda x, y:[x,y], positions_source_tubes, reactions_source_tubes)))
	current_source_tube = next(source_tubes) # It will return a touple (position, reactions)

	# Make sure that the transfer can be done
	if sum(reactions_source_tubes) < sum(reactions_final_tubes):
		raise Exception(f"The source tubes have a total of {sum(reactions_source_tubes)} reactions and the final tubes need {sum(reactions_final_tubes)}, the transfer cannot be done")

	if not program_variables.pipL and not program_variables.pipR:
		raise Exception("There are no pipettes attached in the robot. At least 1 is needed to perform the function 'tube_to_tube_transfer'")

	pipette_use = None # Initial

	# Find out if the tipracks are the same for later purposes
	if user_variables.APINameTipR == user_variables.APINameTipL:
		tipracks_same = True
	else:
		tipracks_same = False

	# Now we will transfer the volumes going through all the destination/final tubes
	for final_tube, reactions_tube in zip(positions_final_tubes, reactions_final_tubes):
		# We are going to control how many reactions are left to go to the next final tube
		while reactions_tube > 0: # Only 1 source tube is going to be used every time it goes to this while loop
			# Calculate how much volume we need to pass from the current source tube to the final one
			if current_source_tube[1] >= reactions_tube: # The current source tube has enough volume
				volume_transfer = vol_transfer_reaction*reactions_tube
				current_source_tube[1] -= reactions_tube
				reactions_tube = 0
			else: # more than 1 tube is needed to transfer the required volume
				volume_transfer = vol_transfer_reaction*current_source_tube[1]
				reactions_tube -= current_source_tube[1]
				current_source_tube[1] = 0

			# We choose the pipette that will transfer it. It can change between one tube and another one (final and/or source tube), that is why we check if it is the same one
			optimal_pipette = give_me_optimal_pipette (volume_transfer, program_variables.pipR, program_variables.pipL)

			# Find out the tiprack associated to the optimal_pipette
			# Also the first tip in case this is the first time the pipette is used
			if optimal_pipette.mount == "right":
				tiprack = user_variables.APINameTipR
				first_tip = user_variables.startingTipPipR
			else:
				tiprack = user_variables.APINameTipL
				first_tip = user_variables.startingTipPipL

			# Now we check if we need to drop the previous pipette tip, in case it changes, because this chnage of tip does not depend on new_tip
			if pipette_use != None and optimal_pipette != pipette_use:
				if pipette_use.has_tip:
					pipette_use.drop_tip()

			# Establish the optimal pipette as the one that is going to be used
			pipette_use = optimal_pipette

			# Pick a tip in case the pipette that is going to transfer the volume does not have it
			if pipette_use.has_tip == False:
				check_tip_and_pick (optimal_pipette, tiprack, dict(zip(protocol.deck.keys(), protocol.deck.values())), protocol, replace_tiprack = user_variables.replaceTiprack, initial_tip = first_tip, same_tiprack = tipracks_same)

			# Transfer volume
			if new_tip != "aspirate": # If it is not aspirate, we are not going to change any tube in this transfer, so we directly do the action
				pipette_use.transfer(volume_transfer, current_source_tube[0], final_tube, new_tip = "never")
			else:
				# We find out how many movements are eneded to transfer the totallity of the volume
				number_transfers, rest_volume = divmod(volume_transfer, pipette_use.max_volume)

				# Now we calculate the volume of each transfer taking in account also the rest volume
				if rest_volume == 0:
					volumes_transfer = [pipette_use.max_volume]*int(number_transfers)
				elif rest_volume < pipette_use.min_volume:
					volumes_transfer = [pipette_use.max_volume]*int(number_transfers-1)
					volumes_transfer += [pipette_use.max_volume/2, ((pipette_use.max_volume/2) + rest_volume)]
				else: # En el caso de que se pueda transferir solo con 1 movimiento entrara aqui sin problemas
					volumes_transfer = [pipette_use.max_volume]*int(number_transfers)
					volumes_transfer.append(rest_volume)

				# Now we transfer chnaging the tip for every movement
				for volume in volumes_transfer:
					if pipette_use.has_tip == False:
						check_tip_and_pick(pipette_use, tiprack, dict(zip(protocol.deck.keys(), protocol.deck.values())), protocol, replace_tiprack = user_variables.replaceTiprack, initial_tip = first_tip, same_tiprack = tipracks_same)
					pipette_use.transfer(volume, current_source_tube[0], final_tube, new_tip = "never")
					pipette_use.drop_tip()

			# Now we have transferred either all the volume to the final tube or all the available volume from the source tube
			# We need to check which case has been

			# In case the source tube has no volume, we go to the next one
			if current_source_tube[1] == 0:
				if new_tip == "tube" or new_tip == "source_tube":
					pipette_use.drop_tip()

				try:
					current_source_tube = next(source_tubes)
				except StopIteration: # This is meant for the last tube
					break # If there were a pass this would be an infinite while
		
		# We have transfered all the reactions of the final tube, so we need to go to the next final tube
		if new_tip in ["final_tube", "tube"]:
			pipette_use.drop_tip()

	# After moving the volumes from the tubes to tubes we drop the tip to finish with no tip
	if pipette_use.has_tip:
		pipette_use.drop_tip()

	return

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
	excel_variables = pd.read_excel("/data/user_storage/VariablesPCR.xlsx", sheet_name = None, engine = "openpyxl")
	# excel_variables = pd.read_excel("VariablesPCR.xlsx", sheet_name = None, engine = "openpyxl")
	# Let's check that the minimal sheets
	name_sheets = list(excel_variables.keys())
	
	if not all(item in name_sheets for item in ["GeneralVariables","ReagentsPerReaction","PipetteVariables","SamplesPlateVariables","ModuleVariables"]):
		raise Exception('The Excel file needs to have min the sheets "GeneralVariables","ReagentsPerReaction","PipetteVariables","SamplesPlateVariables" and "ModuleVariables"\nThey must have those names')
	
	# Check that all variable sheets have the needed columns and variable names
	general_variables = excel_variables.get("GeneralVariables")
	reagents_variables = excel_variables.get("ReagentsPerReaction")
	plate_variables = excel_variables.get("SamplesPlateVariables")
	pip_variables = excel_variables.get("PipetteVariables")
	module_variables = excel_variables.get("ModuleVariables")

	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Name"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Name' and 'Value'")
	else:
		if not all(item in general_variables["Variable Name"].values for item in ['API Name Source Plate','Number of Source Plates','API Name Final PCR Plate','Well Start Final PCR Plate','API Name Eppendorf Reagents Rack','Final Map Name']):
			raise Exception("'GeneralVariables' sheet table needs to have 6 rows with the following names: 'API Name Source Plate','Number of Source Plates', 'API Name Final PCR Plate', 'Well Start Final PCR Plate','API Name Eppendorf Reagents Rack','Final Map Name'")
		
	if "Variable Name" not in list(plate_variables.columns):
		raise Exception("'SamplesPlateVariables' sheet table needs to have at least 1 column, 'Variable Name'")
	else:
		if not all(item in plate_variables["Variable Name"].values for item in ['Number Samples','Well Start','Position Controls', 'Wells not to perform PCR']):
			raise Exception("'SamplesPlateVariables' Sheet table needs to have 4 rows with the following names: 'Number Samples','Well Start','Position Controls', 'Wells not to perform PCR'")
		if plate_variables.shape[1] < 2:
			raise Exception("'SamplesPlateVariables' Sheet table needs to have at least 2 columns, 1 with the variable names and at least another 1 with the information of the source plate (s)")
	
	if not all(item in list(pip_variables.columns) for item in ["Value", "Variable Name"]):
		raise Exception("'PipetteVariables' sheet table needs to have only 2 columns: 'Variable Name' and 'Value'")
	else:
		if not all(item in pip_variables["Variable Name"].values for item in ['API Name Right Pipette','API Name Left Pipette','API Name Tiprack Left Pipette','API Name Tiprack Right Pipette', 'Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks']):
			raise Exception("'PipetteVariables' Sheet table needs to have 7 rows with the following names: 'API Name Right Pipette','API Name Left Pipette','API Name Tiprack Left Pipette','API Name Tiprack Right Pipette', 'Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks'")

	if not all(item in list(reagents_variables.columns) for item in ["Value", "Variable Name"]):
		raise Exception("'ReagentsPerReaction' sheet table needs to have only 2 columns: 'Variable Name' and 'Value'")
	else:
		if not all(item in reagents_variables["Variable Name"].values for item in ['Number primer/set','Number sets','Volume each primer (uL)','Volume polymerase mix (uL)', 'Volume sample DNA Template (uL)', 'Final volume (uL)', 'Extra Pipetting Factor']):
			raise Exception("'ReagentsPerReaction' Sheet table needs to have 7 rows with the following names: 'Number primer/set','Number sets','Volume each primer (uL)','Volume polymerase mix (uL)', 'Volume sample DNA Template (uL)', 'Final volume (uL)', 'Extra Pipetting Factor'")
	
	if not all(item in list(module_variables.columns) for item in ["Value", "Variable Name"]):
		raise Exception("'ModuleVariables' sheet table needs to have only 2 columns: 'Variable Name' and 'Value'")
	else:
		if not all(item in module_variables["Variable Name"].values for item in ['Presence Thermocycler','Presence Heater-Shaker','Final Open Lid','Temperature Lid', 'Hold Block Temperature', 'RPM Heater-Shaker', 'API Name Heater-Shaker Labware','Pause Before Temperature Program']):
			raise Exception("'ModuleVariables' Sheet table needs to have 8 rows with the following names: 'Presence Thermocycler','Presence Heater-Shaker','Final Open Lid','Temperature Lid', 'Hold Block Temperature', 'RPM Heater-Shaker', 'API Name Heater-Shaker Labware','Pause Before Temperature Program'")

	if "TemperatureProfile" in name_sheets:
		temperature_variables = excel_variables.get("TemperatureProfile")
		user_variables = UserVariables(general_variables, plate_variables, pip_variables, reagents_variables, module_variables, temperature_variables)
	else:
		user_variables = UserVariables(general_variables, plate_variables, pip_variables, reagents_variables, module_variables)

	user_variables.check()
	program_variables = SettedParameters()
	program_variables.assign_variables(user_variables, protocol)
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Setting the HS needed because they have more restrictions in the OT-2 and cannot be done with the setting labware function because setting the HS in a position will not give errors but after it wont work
	# First let's find how many tubes we need of mixes in case we have the HS
	if user_variables.presenceHS:
		first_key = list(labware_context.get_labware_definition(user_variables.APINameLabwareHS)["wells"].keys())[0]
		number_wells_labware = len(labware_context.get_labware_definition(user_variables.APINameLabwareHS)["wells"])
		number_tubes_mix_hs, reactions_per_tube_mix_hs, volumes_tubes_mix_hs = number_tubes_needed (program_variables.volTotalFactor,
																									program_variables.sumSamples,
																									user_variables.volMaxMixTube)

		for index_set in range(int(user_variables.sets)):
			program_variables.setsWells[f"Set {index_set+1}"]["Reactions Per Tube"] = reactions_per_tube_mix_hs
			program_variables.setsWells[f"Set {index_set+1}"]["Volumes"] = volumes_tubes_mix_hs
		
		# You cannot put the HS in some positions, even if the opentrons app doesnt raise errors
		possible_positions_HS = {key: protocol.deck[key] for key in [1, 3, 4, 6, 7, 10]}

		number_hs = math.ceil(number_tubes_mix_hs*user_variables.numberPrimerSet/number_wells_labware)
		
		# Establish the hs_mod if possible
		hs_mods = setting_labware(number_hs,
								  "heaterShakerModuleV1",
								  possible_positions_HS,
								  protocol,
								  module = True)

		# Set the labware 
		for position, module in hs_mods.items():
			module.close_labware_latch()
			module.load_labware(user_variables.APINameLabwareHS, label = f"Eppendorf Rack with Mix Slot {position}")
			program_variables.hs_mods[position] = module

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Source Plates
	# We start setting the source labware which number has been provided
	# Get labels of source plates
	labels = []
	for name_plate in user_variables.nameSourcePlates[:user_variables.numberSourcePlates]:
		labels.append(f"Source Plate '{name_plate}'")

	# Set the labware
	labware_source = setting_labware(user_variables.numberSourcePlates,
									 user_variables.APINameSamplePlate,
									 dict(zip(protocol.deck.keys(), protocol.deck.values())),
									 protocol,
									 label = labels)

	# Now we assign each labware position to ther place in the SetteParameters class
	# Get the max volume of the liquid in each well to fill it after with liquid
	vol_max_well_source_labware = list(labware_context.get_labware_definition(user_variables.APINameSamplePlate)["wells"].values())[0]['totalLiquidVolume']
	for index_labware, labware in enumerate(labware_source.items()):
		program_variables.samplePlates[index_labware]["Position"] = labware[0]
		program_variables.samplePlates[index_labware]["Opentrons Place"] = labware[1]
		
		# Establish the maps of the source plate
		if not pd.isna(user_variables.mapID[index_labware]):# There is a map of IDs attach so we need to establish it and check that the dimensions are equivalent
			# program_variables.samplePlates[index_labware]["Map Names"] = pd.read_excel("VariablesPCR.xlsx", sheet_name = user_variables.mapID[index_labware], engine = "openpyxl", index_col = 0)
			program_variables.samplePlates[index_labware]["Map Names"] = pd.read_excel("/data/user_storage/VariablesPCR.xlsx", sheet_name = user_variables.mapID[index_labware], engine = "openpyxl", index_col = 0)
			program_variables.samplePlates[index_labware]["Map Names"].columns = program_variables.samplePlates[index_labware]["Map Names"].columns.map(str)

			# Let's check that the labware and map have the same names of the rows and columns
			row_names = list(labware[1].rows_by_name().keys())
			columns_names = list(labware[1].columns_by_name().keys())
			
			rows_map = list(program_variables.samplePlates[index_labware]['Map Names'].index.values)
			columns_map = list(map(str, list(program_variables.samplePlates[index_labware]['Map Names'].columns.values)))

			if row_names != rows_map or columns_names != columns_map:
				raise Exception(f"""
The columns and rows of the Maps of DNA Parts {user_variables.mapID[index_labware]} need to have the same names as the ones in {user_variables.APINameSamplePlate}:
	Labware Names:
		- Column names: {columns_names}
		- Row names: {row_names}
	Your names:
		- Sheet Columns: {columns_map}
		- Sheet Rows: {rows_map}""")
		else: # If there is not a map of IDs attached we just create one empty 
			program_variables.samplePlates[index_labware]["Map Names"] = pd.DataFrame(np.nan, index = list(labware[1].rows_by_name().keys()), columns = list(labware[1].columns_by_name().keys()))
		
		# Let's find out th elist of wells with samples
		list_wells_samples = program_variables.samplePlates[index_labware]["Opentrons Place"].wells()
		for name_well in program_variables.samplePlates[index_labware]["Control Positions"]:
			list_wells_samples.remove(program_variables.samplePlates[index_labware]["Opentrons Place"][name_well])
		# Now this list will include the samples to pick and not to pick as a DNA template
		list_wells_samples = list_wells_samples[program_variables.samplePlates[index_labware]["Index First Well Sample"]:(program_variables.samplePlates[index_labware]["Index First Well Sample"]+program_variables.samplePlates[index_labware]["Number Samples"])]

		# Set the liquid of samples for each position that will have samples
		for well in program_variables.samplePlates[index_labware]["Opentrons Place"].wells():
			if well._core._name in program_variables.samplePlates[index_labware]["Control Positions"]:
				well.load_liquid(program_variables.liquid_control, volume = 0.9*vol_max_well_source_labware)
			elif well._core._name in program_variables.samplePlates[index_labware]["Positions Not Perform PCR"]:
				well.load_liquid(program_variables.liquid_notpick, volume = 0.9*vol_max_well_source_labware)
			elif well in list_wells_samples: # It will only get into this conditional if it is not a NOT PICK sample
				well.load_liquid(program_variables.liquid_samples, volume = 0.9*vol_max_well_source_labware)
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Final Plate(s)
	# Set the final plates which number has been calculates in the assign_variables method of the clas SettedParameters
	if user_variables.presenceTermo: # If there is a thermocycler attach we need to load the labware into the module
		program_variables.tc_mod.load_labware(user_variables.APINameFinalPlate, label = f"Final PCR Plate Slot 7")
		labware_final = {7: program_variables.tc_mod.labware}
	else: # The final plates are going to be in slots,not in modules
		labware_final = setting_labware(len(program_variables.finalPlates),
										user_variables.APINameFinalPlate,
										dict(zip(protocol.deck.keys(), protocol.deck.values())),
										protocol,
										label = "Final Plate")
	
	# Now we are going to assign to which final plates the samples from the source plates should go
	for index_labware, labware in enumerate(labware_final.items()):
		program_variables.finalPlates[index_labware]["Position"] = labware[0]
		program_variables.finalPlates[index_labware]["Opentrons Place"] = labware[1]
		program_variables.finalPlates[index_labware]["Map Samples with Sets"] = MapLabware(labware[1])

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Setting the coldblocks that we need for the reactives
	# Let's find how many tubes we need for all the reactives
	first_key = list(labware_context.get_labware_definition(user_variables.APINameEppendorfPlate)["wells"].keys())[0]
	vol_max_tube = labware_context.get_labware_definition(user_variables.APINameEppendorfPlate)["wells"][first_key]["totalLiquidVolume"]
	
	total_number_tubes = 0
	
	# Water
	number_tubes_water, program_variables.reactiveWells["Water"]["Reactions Per Tube"], program_variables.reactiveWells["Water"]["Volumes"] = number_tubes_needed (program_variables.volWaterFactor,
																																								   program_variables.sumSamples*int(user_variables.sets),
																																								   vol_max_tube*0.9)
	total_number_tubes += number_tubes_water

	# Polymerase
	number_tubes_poly, program_variables.reactiveWells["Polymerase"]["Reactions Per Tube"], program_variables.reactiveWells["Polymerase"]["Volumes"]  = number_tubes_needed (program_variables.volPolymeraseFactor,
																																											 program_variables.sumSamples*int(user_variables.sets),
																																											 vol_max_tube*0.9)
	total_number_tubes += number_tubes_poly

	# Primers
	number_tubes_primer, reactions_per_tube_primer, volumes_tubes_primer = number_tubes_needed (program_variables.volPrimerFactor,
																								program_variables.sumSamples,
																								vol_max_tube*0.9)
	total_number_tubes += number_tubes_primer*user_variables.numberPrimerSet*user_variables.sets
	for index_primer in range(int(user_variables.sets*user_variables.numberPrimerSet)):
		program_variables.reactiveWells[f"Primer {index_primer+1}"]["Reactions Per Tube"] = reactions_per_tube_primer
		program_variables.reactiveWells[f"Primer {index_primer+1}"]["Volumes"] = volumes_tubes_primer
	
	# Sets in case they go in the coldblocks instead of in the heater shakers
	if user_variables.presenceHS == False:
		number_tubes_mix, reactions_per_tube_mix, volumes_tubes_mix = number_tubes_needed (program_variables.volTotalFactor, program_variables.sumSamples, vol_max_tube*0.9)
		total_number_tubes += number_tubes_mix*user_variables.sets
		for index_set in range(int(user_variables.sets)):
			program_variables.setsWells[f"Set {index_set+1}"]["Reactions Per Tube"] = reactions_per_tube_mix
			program_variables.setsWells[f"Set {index_set+1}"]["Volumes"] = volumes_tubes_mix
	
	# Set the number of tubes in the coldblock
	number_coldblocks = math.ceil (total_number_tubes/len(labware_context.get_labware_definition(user_variables.APINameEppendorfPlate)["wells"]))
	coldblocks = setting_labware (number_coldblocks,
								  user_variables.APINameEppendorfPlate,
								  dict(zip(protocol.deck.keys(), protocol.deck.values())),
								  protocol,
								  label = "Reagents")
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Set the places of the reagents and fill the dictionaries of the different kind of labwares
	# Start with the coldblock(s) labware that for sure it is in it
	positions_eppendorfs = []
	for labware in coldblocks.values():
		positions_eppendorfs += labware.wells()
	generator_positions_reagents = generator_positions(positions_eppendorfs)
	
	# Assign to each reactive the positions on the coldblock(s)
	for reagent_type in program_variables.reactiveWells.keys():
		for volume_tube in program_variables.reactiveWells[reagent_type]["Volumes"]:
			if volume_tube == 0:
				continue
			
			well_tube_eppendorf = next(generator_positions_reagents)
			program_variables.reactiveWells[reagent_type]["Positions"].append(well_tube_eppendorf)
			well_tube_eppendorf.load_liquid(liquid = program_variables.reactiveWells[reagent_type]["Definition Liquid"], volume = math.ceil(volume_tube))

	# Now we state the mix tubes, which can go in the HS or the Coldblock
	if user_variables.presenceHS == False: # They go in the coldblock
		for index_set in range(int(user_variables.sets)):
			for volume_tube in program_variables.setsWells[f"Set {index_set+1}"]["Volumes"]:
				well_tube_eppendorf = next(generator_positions_reagents)
				program_variables.setsWells[f"Set {index_set+1}"]["Positions"].append(well_tube_eppendorf)
				well_tube_eppendorf.load_liquid(liquid = program_variables.setsWells[f"Set {index_set+1}"]["Definition Liquid"], volume = 0)
	else: # They go in the heater shaker
		wells_hs = []
		for hs in list(program_variables.hs_mods.values()):
			wells_hs += hs.labware.wells()
		generator_wells_hs = generator_positions(wells_hs)
		for index_set in range(int(user_variables.sets)):
			for volume_tube in program_variables.setsWells[f"Set {index_set+1}"]["Volumes"]:
				well_tube_eppendorf = next(generator_wells_hs)
				program_variables.setsWells[f"Set {index_set+1}"]["Positions"].append(well_tube_eppendorf)
				well_tube_eppendorf.load_liquid(liquid = program_variables.setsWells[f"Set {index_set+1}"]["Definition Liquid"], volume = 0)
	
	# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Create the mixes
	tubes_sets = []
	reactions_tubes = []
	for set_primers in program_variables.setsWells.values():
		tubes_sets += set_primers["Positions"]
		reactions_tubes += set_primers["Reactions Per Tube"]
	
	# Transfer Water
	if program_variables.volWaterFactor > 0:
		tube_to_tube_transfer(program_variables.volWaterFactor,
							  program_variables.reactiveWells["Water"]["Positions"],
							  program_variables.reactiveWells["Water"]["Reactions Per Tube"],
							  tubes_sets,
							  reactions_tubes[:],
							  program_variables,
							  user_variables, protocol)

	# Transfer Primers
	for set_primers in program_variables.setsWells.values():
		for primer in set_primers["Set Primers"]:
			tube_to_tube_transfer(program_variables.volPrimerFactor,
								  program_variables.reactiveWells[primer]["Positions"],
								  program_variables.reactiveWells[primer]["Reactions Per Tube"][:],
								  set_primers["Positions"],
								  set_primers["Reactions Per Tube"][:],
								  program_variables, user_variables,
								  protocol,
								  new_tip = "aspirate")

	# Transfer Polymerase
	# Lower the aspiration and dispense rate
	if program_variables.pipR != None:
		default_values_pipR = [program_variables.pipR.flow_rate.aspirate, program_variables.pipR.flow_rate.dispense]
		program_variables.pipR.flow_rate.aspirate = program_variables.pipR.min_volume
		program_variables.pipR.flow_rate.dispense= program_variables.pipR.min_volume
	if program_variables.pipL != None:
		default_values_pipL = [program_variables.pipL.flow_rate.aspirate, program_variables.pipL.flow_rate.dispense]
		program_variables.pipL.flow_rate.aspirate = program_variables.pipL.min_volume
		program_variables.pipL.flow_rate.dispense = program_variables.pipL.min_volume

	tube_to_tube_transfer(program_variables.volPolymeraseFactor,
						  program_variables.reactiveWells["Polymerase"]["Positions"],
						  program_variables.reactiveWells["Polymerase"]["Reactions Per Tube"],
						  tubes_sets,
						  reactions_tubes[:],
						  program_variables,
						  user_variables,
						  protocol,
						  new_tip="aspirate")
	
	# Take back the aspirate and dispense speed values of the pipette(s)
	if program_variables.pipR != None:
		program_variables.pipR.flow_rate.aspirate = default_values_pipR[0]
		program_variables.pipR.flow_rate.dispense= default_values_pipR[1]
	if program_variables.pipL != None:
		program_variables.pipL.flow_rate.aspirate = default_values_pipL[0]
		program_variables.pipL.flow_rate.dispense = default_values_pipL[1]

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Mix and Distribute Sets

	index_start_final_plate = opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFinalPlate)["groups"][0]["wells"].index(user_variables.wellStartFinalPlate)
	wells_distribute = []

	for final_labware in program_variables.finalPlates.values():
		wells_distribute += final_labware["Opentrons Place"].wells()
	
	wells_distribute_free = wells_distribute[index_start_final_plate:int(index_start_final_plate+user_variables.sets*program_variables.sumSamples)]
	
	# Set the optimal pipette to distribute the volume to every well
	optimal_pipette = give_me_optimal_pipette (program_variables.volTotal, program_variables.pipR, program_variables.pipL)
	if optimal_pipette.mount == "right":
		tiptack_distribution = user_variables.APINameTipR
		strating_tip_distribution = user_variables.startingTipPipR
	else:
		tiptack_distribution = user_variables.APINameTipL
		strating_tip_distribution = user_variables.startingTipPipL

	for set_primer in program_variables.setsWells.values():
		# Mix and distribute every tube of the set
		for index, tube in enumerate(set_primer["Positions"]):
			if user_variables.presenceHS == True:
				# Find out in which HS is the tube and shake it
				program_variables.hs_mods[int(str(tube).split(" ")[-1])].set_and_wait_for_shake_speed(user_variables.rpm)
				protocol.delay(seconds = 15)
				program_variables.hs_mods[int(str(tube).split(" ")[-1])].deactivate_shaker()
				if optimal_pipette.has_tip == False:
					check_tip_and_pick (optimal_pipette,
										tiptack_distribution,
										dict(zip(protocol.deck.keys(), protocol.deck.values())),
										protocol,
										initial_tip = strating_tip_distribution,
										replace_tiprack = user_variables.replaceTiprack,
										same_tiprack = program_variables.sameTiprack)
				optimal_pipette.distribute(float(program_variables.volTotal),
										   tube,
										   wells_distribute_free[:set_primer["Reactions Per Tube"][index]],
										   new_tip = "never",
										   disposal_volume = 0)
			else:# Mix it with a pipette
				# Find the volume of mixing
				vol_mixing = set_primer["Volumes"][index] / 3
				
				# Find the pipette for mixing
				optimal_pipette_mixing = give_me_optimal_pipette(vol_mixing,
																 program_variables.pipR,
																 program_variables.pipL)

				if optimal_pipette_mixing.max_volume < vol_mixing:
					vol_mixing = optimal_pipette_mixing.max_volume
				
				if optimal_pipette_mixing.mount == "right":
					tiprack_mix = user_variables.APINameTipR
					starting_tip_mix = user_variables.startingTipPipR
				else:
					tiprack_mix = user_variables.APINameTipL
					starting_tip_mix = user_variables.startingTipPipL
				
				# Pick tip if needed
				if optimal_pipette != optimal_pipette_mixing and optimal_pipette.has_tip:
					optimal_pipette.drop_tip()
				
				if optimal_pipette_mixing.has_tip == False:
					check_tip_and_pick(optimal_pipette_mixing,
									   tiprack_mix,
									   dict(zip(protocol.deck.keys(), protocol.deck.values())),
									   protocol,
									   replace_tiprack = user_variables.replaceTiprack,
									   initial_tip = starting_tip_mix,
									   same_tiprack = program_variables.sameTiprack)

				# Mixing
				mixing_eppendorf_15(tube,
									set_primer["Volumes"][index],
									vol_mixing,
									optimal_pipette_mixing)
				
				# Distribute
				if optimal_pipette == optimal_pipette_mixing:
					optimal_pipette.distribute(float(program_variables.volTotal),
											   tube,
											   wells_distribute_free[:set_primer["Reactions Per Tube"][index]],
											   new_tip = "never",
											   disposal_volume = 0)
				else:
					optimal_pipette_mixing.drop_tip()
					check_tip_and_pick (optimal_pipette,
										tiptack_distribution,
										dict(zip(protocol.deck.keys(), protocol.deck.values())),
										protocol,
										replace_tiprack = user_variables.replaceTiprack,
										initial_tip = strating_tip_distribution,
										same_tiprack = program_variables.sameTiprack)
					optimal_pipette.distribute(float(program_variables.volTotal),
											   tube,
											   wells_distribute_free[:set_primer["Reactions Per Tube"][index]],
											   new_tip="never",
											   disposal_volume = 0)
					
			del wells_distribute_free[:set_primer["Reactions Per Tube"][index]]
		
		# Go to the next set changing the tips
		optimal_pipette.drop_tip()

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Transfer Ssmples to final wells
	optimal_pipette = give_me_optimal_pipette (user_variables.volumesSamplesPerPlate, program_variables.pipR, program_variables.pipL)
	if optimal_pipette.mount == "right":
		tiprack = user_variables.APINameTipR
		starting_tip = user_variables.startingTipPipR
	else:
		tiprack = user_variables.APINameTipL
		starting_tip = user_variables.startingTipPipL

	# Take the wells that we are not going to pick up and move the controls to the end
	all_samples_transfer = []
	control_wells = []
	
	# Go throught all the source plates to transfer the samples to the final plates
	for source_plate in program_variables.samplePlates.values():
		# We get the list of all the wells of a source plate from the initial plate
		wells = source_plate["Opentrons Place"].wells()[source_plate["Index First Well Sample"]:]

		# We ar egoing to transfer the controls at the end so we take them out of this list in case they are
		for control in source_plate["Control Positions"]:
			try:
				wells.remove(source_plate["Opentrons Place"][control])
			except ValueError: # The value of the list source_plate["Control Positions"] is not in the list wells but exists in the labware (we checked that before in the script)
				pass
			
			# We add the controls to the list of control_wells that are going to be transferred at the end
			control_wells.append(source_plate["Opentrons Place"][control])

		# Now that we have taken out the controls we take out the not wanted wells
		wells = wells[:source_plate["Number Samples"]]
		for notPCR in source_plate["Positions Not Perform PCR"]:
			try:
				wells.remove(source_plate["Opentrons Place"][notPCR])
			except ValueError: # The value of the list source_plate["Positions Not Perform PCR"] is not in the list wells but exists in the labware (we checked that before in the script)
				pass
		all_samples_transfer += wells

	all_samples_transfer += control_wells

	# Create the generator of wells to distribute
	final_wells = generator_positions(wells_distribute[index_start_final_plate:int(index_start_final_plate+user_variables.sets*program_variables.sumSamples)])
	for number_set in range(int(user_variables.sets)):
		for well_source in all_samples_transfer:
			well_pcr = next(final_wells)
			check_tip_and_pick (optimal_pipette,
								tiprack,
								dict(zip(protocol.deck.keys(), protocol.deck.values())),
								protocol, replace_tiprack = user_variables.replaceTiprack,
								initial_tip = starting_tip,
								same_tiprack = program_variables.sameTiprack)
			optimal_pipette.transfer(float(user_variables.volumesSamplesPerPlate),
									 well_source,
									 well_pcr,
									 new_tip = "never")
			optimal_pipette.drop_tip()
			
			# Map it
			for sampleplate in program_variables.samplePlates.values():
				if str(sampleplate["Position"]) == str(well_source).split(" ")[-1]:
					# Get value of the well source plate
					value_map_source_well = sampleplate["Map Names"][well_source._core._column_name][well_source._core._row_name]
					if pd.isna(value_map_source_well): # If there is no map or in the map there is no value for that cell in the map
						value_map = f"{well_source._core._row_name}{well_source._core._column_name} Slot {str(well_source).split(' ')[-1]} with Set {number_set+1}"
					else:
						value_map = f"{value_map_source_well} Slot {str(well_source).split(' ')[-1]} with Set {number_set+1}"
					
					# Assign it to the place of the final well in its dataframe
					for finalplate in program_variables.finalPlates.values():
						if str(finalplate["Position"]) == str(well_pcr).split(" ")[-1]:
							finalplate["Map Samples with Sets"].assign_value(value_map, well_pcr._core._row_name, well_pcr._core._column_name)
	
	# Export map(s) in an excel
	writer = pd.ExcelWriter(f'/data/user_storage/{user_variables.finalMapName}.xlsx', engine='openpyxl')
	# writer = pd.ExcelWriter(f'{user_variables.finalMapName}.xlsx', engine='openpyxl')
	
	for final_plate in program_variables.finalPlates.values():
		final_plate["Map Samples with Sets"].map.to_excel(writer, sheet_name = f"FinalMapSlot{final_plate['Position']}")
	
	writer.save()
	
	# Perform PCR profile
	if user_variables.presenceTermo:
		if user_variables.pause:
			protocol.pause("Protocol is pause so plate in thermocyler can be mix or user can put caps on it")
		
		program_variables.tc_mod.close_lid()
		run_program_thermocycler (program_variables.tc_mod,
								  user_variables.temperatureProfile,
								  user_variables.temperatureLid,
								  user_variables.finalVolume,
								  final_lid_state = user_variables.finalStateLid,
								  final_block_state = user_variables.finalTemperatureBlock)

	# Final home
	protocol.home()
