# LAP-CellMediaInoculation-OT2-2.0.0

# This python script facilitates the creation of customized plates with samples derived from various source plates, each containing different media.
# The process is highly configurable, allowing users to set variables such as transfer volumes, sample selection, the number of sample-media combinations, and replication count, among others.
# The different customization needs to be provided with an excel file that will be read and handled in the script.

# Workflow of the script (in a nutshell):
# 1. Input Handling: Read and process the Excel template to retrieve user-defined settings.
# 2. Resource Calculation: Determine the number and placement of plates, reagents, tubes, and tip racks.
# 3. Media Distribution: Dispense media into the destination plates using a single-channel pipette.
# 4. Sample Transfer: Transfer samples to the destination plates using a multi-channel pipette.

# This scripts allows execution of only media distribution or only sample transfer if specified in the input file.

# For more info go to:
#  Github page with code: https://github.com/BiocomputationLab/LAPrepository/tree/e70b53e82f9b615f3176662fd9b29b132f6d5b71/LAPEntries/LAP-CellMediaInoculation-OT2-2.0.0
#  Protocols.io page with further instructions of usage: https://www.protocols.io/view/ot-2-media-dispensing-and-culture-inoculation-prot-q26g7yb3kgwz
#  LAP repository entry: https://www.laprepo.cbgp.upm.es/protocol/cell-inoculation-in-different-media-v2-0-0/


# Packages needed for the running of the protocol
import opentrons
import pandas as pd
import math
import random
from opentrons.motion_planning.deck_conflict import DeckConflictError
from opentrons.protocol_api.labware import OutOfTipsError

# Class definitions
# ----------------------------------
# ----------------------------------

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
		self.samplesPerPlate = list(each_plate[each_plate["Variable Names"] == "Samples per plate"].values[0][1:])
		self.firstWellSamplePerPlate = list(each_plate[each_plate["Variable Names"] == "First Well With Sample"].values[0][1:])
		self.nameAntibiotics = general[general["Variable Names"] == "Name Medias"]["Value"].values[0]
		self.changeTipDistribute = general[general["Variable Names"] == "Change Tip In Media Distribution"]["Value"].values[0]
		self.changeTipTransfer = general[general["Variable Names"] == "Change Tip In Sample Transfer"]["Value"].values[0]
		self.volumeAntibiotic = general[general["Variable Names"] == "Volume of Media to Transfer (uL)"]["Value"].values[0]
		self.volumeSample = general[general["Variable Names"] == "Volume of Sample to Transfer (uL)"]["Value"].values[0]
		self.positionTransferSample = general[general["Variable Names"] == "Position Transfer Sample"]["Value"].values[0]
		self.touchTipTransferSample = general[general["Variable Names"] == "Touch Tip After Transferring Sample"]["Value"].values[0]
		self.touchTipDistributeMedia = general[general["Variable Names"] == "Touch Tip In Distribution Media"]["Value"].values[0]
		self.volumeMixing = general[general["Variable Names"] == "Mixing Volume Before Sample Transfer (uL)"]["Value"].values[0]
		self.timesMixing = general[general["Variable Names"] == "Number Times of Mixing Volume"]["Value"].values[0]
		self.rateMixing = general[general["Variable Names"] == "Flow Rate Mixing"]["Value"].values[0]
		self.APINameSamplePlate = general[general["Variable Names"] == "Name Source Plate"]["Value"].values[0]
		self.APINameIncubationPlate = general[general["Variable Names"] == "Name Final Plate"]["Value"].values[0]
		self.APINameFalconPlate = general[general["Variable Names"] == "Name Tuberack"]["Value"].values[0]

		self.APINamePipR = pipettes[pipettes["Variable Names"] == "Name Right Pipette (Multichannel)"]["Value"].values[0]
		self.APINamePipL = pipettes[pipettes["Variable Names"] == "Name Left Pipette (Singlechannel)"]["Value"].values[0]
		self.startingTipPipR = pipettes[pipettes["Variable Names"] == "Initial Tip Right Pipette"]["Value"].values[0]
		self.startingTipPipL = pipettes[pipettes["Variable Names"] == "Initial Tip Left Pipette"]["Value"].values[0]
		self.APINameTipR = pipettes[pipettes["Variable Names"] == "API Name Right Pipette TipRack"]["Value"].values[0]
		self.APINameTipL = pipettes[pipettes["Variable Names"] == "API Name Left Pipette TipRack"]["Value"].values[0]
		self.replaceTiprack = pipettes[pipettes["Variable Names"] == "Replace Tipracks"]["Value"].values[0]

		self.antibioticsPerPlate = list(each_plate[each_plate["Variable Names"] == "Media(s) per plate"].values[0][1:])
		self.onlyMediaPlate = list(each_plate[each_plate["Variable Names"] == "Only Media(s) Plate Creation"].values[0][1:])
		self.onlySamplePlate = list(each_plate[each_plate["Variable Names"] == "Only Sample(s) Plate Creation"].values[0][1:])
		self.numberReplicas = list(each_plate[each_plate["Variable Names"] == "Number of Replicas"].values[0][1:])
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

		# First we check all the minimum variables needed, the ones that does that independently of what the final plate composition
		# We check for the number of source plates which will be defined how many columns we are going to read from the sheet PerPlateVariables
		if pd.isna(self.numberSourcePlates) or pd.isna(self.APINameIncubationPlate):
			raise Exception("The variables 'Number of Source Plates' and 'Name Final Plate' in GeneralVariables cannot be left empty")
		else:
			# Check that we have at least 1 source plate
			if self.numberSourcePlates <= 0:
				raise Exception("We need at least 1 source plate to perform the protocol")
			# Check that there are at least number source plate + the column of the names
			if len(self.samplesPerPlate) < self.numberSourcePlates:
				raise Exception("We need at least as many columns in the 'PerPlateVariables' as the number in the variable 'Number of Source Plates' without taking in account the column with the name of the variables")
		
		# Check the only value in the sheet PipetteVariables that needs to be filled always
		if pd.isna(self.replaceTiprack):
			raise Exception("The variable 'Replace Tipracks' in PipetteVariables cannot be left empty")
		else: # Check that the value of this variable is either True or False
			if self.replaceTiprack in ["False", "FALSE", False, 0, "false"]:
				self.replaceTiprack = False
			elif self.replaceTiprack in ["True", "TRUE", True, 1, "true"]:
				self.replaceTiprack = True
			else:
				raise Exception("Replace Tiprack variable value needs to be True or False, it cannot be empty")
		
		# Check that there are only as many values as number of source plates for the variables Samples per plate
		if any(pd.isna(elem) == True for elem in self.samplesPerPlate[:self.numberSourcePlates]) or any(pd.isna(elem) == False for elem in self.samplesPerPlate[self.numberSourcePlates:]):
			raise Exception("The values of 'Samples per plate' need to be as many as the 'Number of Source Plates' and be in consecutive columns")
		
		# Check that there are no values of First well with sample in columns at the right of the last column that is going to be read
		if any(pd.isna(elem) == False for elem in self.firstWellSamplePerPlate[self.numberSourcePlates:]):
			raise Exception("The values of 'First Well With Sample' can be as many as the 'Number of Source Plates' and in consecutive columns, if empty, it is considered that is the first well")
		else: # Now we just assigned A1 to the ones that are going to be used and does not contain a value 
			for index_plate, first_well in enumerate(self.firstWellSamplePerPlate[:self.numberSourcePlates]):
				if pd.isna(first_well):
					self.firstWellSamplePerPlate[index_plate] = "A1" # We assign the first well, which is in the opentrons definitions, A1
		
		# Process the value of nameAntibiotics so we can check it correctly in the following lines of code because it is going to be a string when it is read from excel
		if pd.isna(self.nameAntibiotics):
			self.nameAntibiotics = []
		else:
			self.nameAntibiotics = self.nameAntibiotics.replace(" ","").split(",")
		
		# The final plates are always going to be created, so we need to check that the labware exists always
		try:
			definition_final_plate = labware_context.get_labware_definition(self.APINameIncubationPlate)
		except OSError: # This would be catching the FileNotFoundError that happens when a labware is not found
			raise Exception(f"The final plate labware {self.APINameIncubationPlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
		
		# Check the values of the variables that will determine which checks are done after depending if a final plate is going to be created with samples and media or any of them
		if any(pd.isna(elem) == False for elem in self.onlyMediaPlate[self.numberSourcePlates:]):
			raise Exception("The values of 'Only Media(s) Plate Creation' can be as many as the 'Number of Source Plates' and in consecutive columns, if empty, it is considered that is as False")
		else: # The values can be empty so we need to fill them
			for index_plate, only_media in enumerate(self.onlyMediaPlate[:self.numberSourcePlates]):
				if pd.isna(only_media):
					self.onlyMediaPlate[index_plate] = False # We assign the default value, False
				else:
					# We change the 1s to True and the 0s to False because excel sometimes does that conversion when the rest of the cells are empty
					if only_media in [1, True, "True", "TRUE", "true"]:
						self.onlyMediaPlate[index_plate] = True
					elif only_media in [0, False, "False", "FALSE", "false"]:
						self.onlyMediaPlate[index_plate] = False
					else:
						raise Exception("The values for the variable 'Only Media(s) Plate Creation' can only be True or False, if left empty it is assumed as False ")
		
		if any(pd.isna(elem) == False for elem in self.onlySamplePlate[self.numberSourcePlates:]):
			raise Exception("The values of 'Only Sample(s) Plate Creation' can be as many as the 'Number of Source Plates' and in consecutive columns, if empty, it is considered that is as False")
		else:
			for index_plate, only_sample in enumerate(self.onlySamplePlate[:self.numberSourcePlates]):
				if pd.isna(only_sample):
					self.onlySamplePlate[index_plate] = False # We assign the default value, False
				else:
					# We change the 1s to True and the 0s to False because excel sometimes does that conversion when teh rest of the cells are empty
					if only_sample in [1, True, "True", "TRUE", "true"]:
						self.onlySamplePlate[index_plate] = True
					elif only_sample in [0, False, "False", "FALSE", "false"]:
						self.onlySamplePlate[index_plate] = False
					else:
						raise Exception("The values for the variable 'Only Sample(s) Plate Creation' can only be True or False, if left empty it is assumed as False")
		
		# Check for inconsistencies in the variables 'Only Media(s) Plate Creation' and 'Only Sample(s)  Plate Creation'
		for only_media, only_sample in zip(self.onlyMediaPlate[:self.numberSourcePlates], self.onlySamplePlate[:self.numberSourcePlates]):
			if only_media and only_sample:
				raise Exception ("There is at least 1 column in the sheet 'PerPlateVariables' that has both 'Only Media(s) Plate Creation' and 'Only Sample(s)  Plate Creation' set as True, that is incompatible\nTo create 1 plate with only sample and 1 with only media with the same 'Samples per plate' and 'First Well With Sample' just duplicate the column but set 'Only Media(s) Plate Creation' as True in one of the columns and 'Only Sample(s)  Plate Creation' as True in the other")

		# Check the variables needed if at some moment it will need to create a plate with source plate samples
		if any(element == False for element in self.onlyMediaPlate[:self.numberSourcePlates]): # It will go in the loop when the source plate is needed for at least for 1 of the final plates
			# Check if the labware of the sample plates it is on the opentrons app, this needs to be first on the checking because if not other checking will do a false exception
			try:
				definition_source_plate = labware_context.get_labware_definition(self.APINameSamplePlate)
			except OSError: # This would be catching the FileNotFoundError that happens when a labware is not found
				raise Exception(f"The source plate labware {self.APINameSamplePlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
			
			# Check that the source plate is not a mixed one
			if not pd.isna(self.APINameSamplePlate) and len(definition_source_plate["groups"]) > 1:
				raise Exception("The source plate needs to have only 1 type of well, i.e, the labware needs to be homogeneous")
			
			# Check that if a final plate with samples is going to be created, the right pipette is defined in the variable file and all the related variables
			if pd.isna(self.APINamePipR):
				raise Exception("If you want to produce at least 1 final plate with samples, the variable 'Name Right Pipette (Multichannel)' cannot be left empty")
			else:
				if pd.isna(self.startingTipPipR) or pd.isna(self.APINameTipR):
					raise Exception("If you need to use the single channel pipette in the run, you need to establish the variables 'API Name Right Pipette TipRack' and 'Initial Tip Right Pipette'")
			
			# Check that the tiprack needed for the right pipette exists in the opentrons app
			try:
				definition_tiprack_right = labware_context.get_labware_definition(self.APINameTipR)
			except OSError: # This would be catching the FileNotFoundError that happens when a labware is not found
				raise Exception(f"The right tip rack {self.APINameTipR} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")
			
			# Check that the first tip for the multichannel is on the first row meaning that there is a column full of tips
			if self.startingTipPipR not in definition_tiprack_right["wells"].keys():
				raise Exception("Starting tip of right pipette is not valid, check for typos")
			else:
				# Control that the multipipette actually starts at A and not other letter, in general that starts with the first place of the column in the tiprack
				# This can only be checked correctly if the tip actually exists
				if "a" not in self.startingTipPipR.lower():
					# Check that has to be A in the multichannel
					raise Exception("The initial tip of the multichannel pipette needs to be at the top of the column, e.g., it has to start with an A")
			
			# Check if the volume of sample is not empty
			if pd.isna(self.volumeSample) or self.volumeSample <= 0:
				raise Exception("If you are going to create final plates with samples you cannot leave the variable 'Volume of Sample to Transfer (uL)' empty or with a volume equal or lower than 0")

			# Check that if the mixing volume is given, at least the times mixing needs to be provided
			if not pd.isna(self.volumeMixing):
				if pd.isna(self.timesMixing):
					self.timesMixing = 1
				elif self.timesMixing == 0:
					raise Exception("If you provide a value in 'Mixing Volume Before Sample Transfer (uL)', you need to provide a value higher than 0 for 'Number Times of Mixing Volume'. If the latter value is left empty, it is assumed as 1")
				else: # Times mixing needs to be an int because you cannot mix something 0.5 times
					self.timesMixing = int(self.timesMixing)
				if pd.isna(self.rateMixing): # If volumeMixing is empty, it will be ignored
					self.rateMixing = 1
				elif self.rateMixing == 0:
					raise Exception("If 'Mixing Volume Before Sample Transfer (uL)' is filled, the value of 'Flow Rate Mixing' cannot be 0, if the latter value is left empty, it is assumed as 1")
			
			# We check that the value of change tip is one of the accepted values. This is only going to be checked if samples are going to be transferred
			if pd.isna(self.changeTipTransfer):
				self.changeTipTransfer = "aspirate"
			elif self.changeTipTransfer not in ["never","column","aspirate","plate"]:
				raise Exception("'Change Tip in Sample Transfer' can only have 4 values: never, column, aspirate and plate. If left empty, 'aspirate' value will be assumed.\nFor the behaviour with each argument check the manual of the LAP entry")

			# We check the position that the dispense in the final wells is one of the accepted values
			if pd.isna(self.positionTransferSample):
				self.positionTransferSample == "bottom"
			elif self.positionTransferSample not in ["top", "bottom", "center"]:
				raise Exception("'Position Transfer Sample' can only have 3 values: top, bottom or center. If left empty, 'bottom' value will be assumed.\nFor the behaviour with each argument check the manual of the LAP entry")

			# We check that the value of toyuch tip after transferring samples is true, false or left empty
			if pd.isna(self.touchTipTransferSample):
				self.touchTipTransferSample = False
			elif self.touchTipTransferSample in [False, 0, "False", "FALSE", "false"]:
				self.touchTipTransferSample = False
			elif self.touchTipTransferSample in [True, 1, "True", "TRUE", "true"]:
				self.touchTipTransferSample = True
			else:
				raise Exception("'Touch Tip After Transferring Sample' can only have 2 values: True or False. If left empty assumed as False")
			
			# If samples are going to be transferred we need to have a dource and final labware that has 8 rows
			if len(definition_source_plate["ordering"][0]) != 8:
				raise Exception("At least 1 final plate is going to contain samples which means that the 8-channel pipette is going to be used. For that reason, the labware defined in 'Name Source Plate' needs to have 8 rows.")
			
			if len(definition_final_plate["ordering"][0]) != 8:
				raise Exception("At least 1 final plate is going to contain samples which means that the 8-channel pipette is going to be used. For that reason, the labware defined in 'Name Final Plate' needs to have 8 rows.")
		else: # Only media plates are going to be created
			self.volumeSample = 0
			self.APINameTipR = None
			self.startingTipPipR = None
			self.APINamePipR = float("nan")
		
		# ---------------------------------------------------------
		
		if any(element == False for element in self.onlySamplePlate[:self.numberSourcePlates]): # It will go in if at least 1 final plate with media will be created
			# We are goign to need the falcon tubes so the labware name variable needs to be defined
			if pd.isna(self.APINameFalconPlate):
				raise Exception("If at least 1 plate is going to be inoculated with media, the variable 'Name Tuberack' needs to be defined")

			# Check if the labware of the falcon tuberack it is on the opentrons app, this needs to be first on the checking because if not other checking will do a false exception
			try:
				definition_rack = labware_context.get_labware_definition(self.APINameFalconPlate)
			except OSError: # This would be catching the FileNotFoundError that happens when a labware is not found
				raise Exception(f"The 15mL falcon tube rack labware {self.APINameFalconPlate} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

			# Check the falcon tube rack is only composed by only 1 type of falcons, 15 or 50mL
			if len(definition_rack["groups"]) > 1:
				raise Exception("The falcon rack needs to have only 1 type of tube admitted, either with 15mL or 50mL falcons. Tube racks such as 'Opentrons 10 Tube Rack with Falcon 4x50 mL, 6x15 mL Conical' are not valid")

			# Check that if a final plate with media is going to be created, the left pipette is defined in the variable file and all the related variables
			if pd.isna(self.APINamePipL):
				raise Exception("If you want to produce at least 1 final plate with samples, the variable 'Name Left Pipette (Singlechannel)' cannot be left empty")
			else:
				if pd.isna(self.startingTipPipL) or pd.isna(self.APINameTipL):
					raise Exception("If you need to use the single channel pipette in the run, you need to establish the variables 'API Name Left Pipette TipRack' and 'Initial Tip Left Pipette'")
			
			# Check that the tiprack needed for the left pipette exists in the opentrons app
			try:
				definition_tiprack_left = labware_context.get_labware_definition(self.APINameTipL)
			except OSError: # This would be catching the FileNotFoundError that happens when a labware is not found
				raise Exception(f"The left tip rack {self.APINameTipL} is not in the opentrons labware space so it cannot be defined. Check for any typo of the api labware name or that the labware is in the Opentrons App.")

			# Checked that the defined first tip of this tiprack exists in the labware  
			if self.startingTipPipL not in definition_tiprack_left["wells"].keys():
				raise Exception("Starting tip of left pipette is not valid, check for typos")

			# Check if there is some value of the plates where it shouldnt in the per plate sheet
			if any(pd.isna(elem) == False for elem in self.antibioticsPerPlate[self.numberSourcePlates:]):
				raise Exception("Only plates that does not have True established in 'Only Sample(s) Plate creation' need to have values in variable 'Media(s) per plate' as well as they need to be maximum the same number as 'Number of Source Plates' and in consequitive columns")
			
			# Check if the volume of media is not empty
			if pd.isna(self.volumeAntibiotic):
				raise Exception("If you are going to create final plates with one or more media you cannot leave the variable 'Volume of Media to Transfer (uL)' empty")
			else:
				try:
					if self.volumeAntibiotic <= 0:
						raise Exception("If you are going to create final plates with one or more media you cannot leave the variable 'Volume of Media to Transfer (uL)' with a volume equal or lower than 0")
				except TypeError:
					raise Exception("'Volume of Media to Transfer (uL)' cannot be more than 1 volume")
				
			
			# Check that there is at least 1 media to transfer because there is at least 1 plate that will have media
			if not self.nameAntibiotics:
				raise Exception("There are no media established in 'Name Medias' and you have established that at least 1 final plate will have media")

			# We are going to check if the number of indexes in antibiotics per plate is the same as number of Name antibiotics, i.e., that all of the medias established in PerPlate variables are in GenerlaVariables
			all_plates_antibiotics = []
			for value_samples, antibiotic_list, value_media in zip(self.onlySamplePlate, self.antibioticsPerPlate, self.onlyMediaPlate):
				if not pd.isna(antibiotic_list) and value_samples == False: # We check that there is something in the media and this plate is not only with sample
					antibiotics_plate = antibiotic_list.replace(" ","").split(",")
					all_plates_antibiotics += antibiotics_plate
				elif (value_media == True and pd.isna(antibiotic_list)) or (value_samples == False and pd.isna(antibiotic_list)): # We need to check that when we only want to create a media plate or a plate with both media or samples we have some media established
					raise Exception("If you have a column in 'PerPlateVariables' with the variable 'Only Media(s) Plate Creation' set as True or 'Only Sample(s) Plate Creation' set as False or empty, 'Media(s) per plate' cannot be left empty in that column")
				
			if len(all_plates_antibiotics) != 0: # There is at least 1 plate with media, which should be true because we are getting into the for loop because at least 1 is going to be created with media
				all_plates_antibiotics = list(dict.fromkeys(all_plates_antibiotics))
				if all(antibiotic in self.nameAntibiotics for antibiotic in all_plates_antibiotics) == False: # Check that all the media that are used for creating final plates are established as well in 'Name Medias'
					raise Exception(f"The following media(s) are not defined in variable 'Name Medias': {set(all_plates_antibiotics)-set(self.nameAntibiotics)}")
				if all(antibiotic in all_plates_antibiotics for antibiotic in self.nameAntibiotics) == False: # Check that all the media in 'Name Medias' are used for creating the final plates
					raise Exception(f"The following media(s) are not being used: {set(self.nameAntibiotics)-set(all_plates_antibiotics)}")
			
			# Check that if the variable changeTipDistribute has somethign and if it has something check that it is according of the values
			if pd.isna(self.changeTipDistribute):
				self.changeTipDistribute = "media" # This will be the default value
			elif self.changeTipDistribute not in ["never", "aspirate", "well", "tube", "media"]:
				raise Exception("The values of the variable 'Change Tip In Media Distribution' has to be one of the following: never, aspirate, well, tube, media. If this well is left empty and there is at least one plate with media, 'media' will be considered as the value of this cell.\nThis cell will be ignored if no final plate with media is going to be created.")
			
			# Check that the touch tip has a true or false value, it will only be checked if there is some media that is going to be distributed
			if pd.isna(self.touchTipDistributeMedia):
				self.touchTipDistributeMedia = False
			elif self.touchTipDistributeMedia in [False, 0, "False", "FALSE"]:
				self.touchTipDistributeMedia = False
			elif self.touchTipDistributeMedia in [True, 1, "True", "TRUE"]:
				self.touchTipDistributeMedia = True
			else:
				raise Exception("'Touch Tip In Distribution Media' can only have 2 values: True or False. If left empty assumed as False")
		else: # There is not going to be a final plate iwth media so we establish some values for variable sthat are going to be checked in the script
			self.volumeAntibiotic = 0
			self.APINameTipL = None
			self.startingTipPipL = None
			self.APINamePipL = float("nan")
			self.nameAntibiotics = [] # No media is going to be needed because all of the plates are going to be with samples and we set it because in assign_variables we are going to read this variable
		
		# ---------------------------------------------------------
		# Now we check variables or set of variables that need to be checked in all scenarios, no taking in account if the final plates have media or samples
		# We are going to check that the number of wells with samples in each plate is not larger than the capacity of the source and final plate(s)
		for index_plate, (name_plate, number_cells_per_plate, initial_well_source_plate, only_media) in enumerate(zip(self.nameSourcePlates[:self.numberSourcePlates], self.samplesPerPlate[:self.numberSourcePlates], self.firstWellSamplePerPlate[:self.numberSourcePlates], self.onlyMediaPlate[:self.numberSourcePlates])):
			try:
				self.samplesPerPlate[index_plate] = int(number_cells_per_plate)
			except ValueError:
				raise Exception("Every cell of 'Samples per plate' has to be a whole number")
			
			if only_media == False: # Both sample or sample+media in the final plate
				# Check that there is enugh space in the source labware to fit the number of samples defined
				if len(definition_source_plate["wells"]) < number_cells_per_plate:
					raise Exception(f"Number of wells with samples is larger than the capacity of the source plate labware in {name_plate}")
				
				# Check that the initial well with sample exist in the labware source
				if initial_well_source_plate not in definition_source_plate["wells"].keys():
					raise Exception(f"The well '{initial_well_source_plate}' does not exist in the labware {self.APINameSamplePlate}, check for typos")
				
				# Check that the first well with a sample + number of samples does not exceed the source plate wells
				if len(definition_source_plate["wells"].keys()) < number_cells_per_plate+definition_source_plate['groups'][0]["wells"].index(initial_well_source_plate):
					raise Exception(f"Having the {initial_well_source_plate} as the first well and {number_cells_per_plate} samples defined in {name_plate} do not fit in the source labware")
				
				# Check that in case that there are going to be samples involve check that it fits when is going to be transfered to the final labware
				if len(definition_final_plate["wells"].keys()) < number_cells_per_plate+definition_final_plate['ordering'][0].index(initial_well_source_plate[0]+"1"):
					raise Exception(f"Having the {initial_well_source_plate} as the first well of the source plate making the first well of the final plate {initial_well_source_plate[0]+'1'} and {number_cells_per_plate} samples defined in {name_plate} do not fit in the final labware")
			elif only_media == True: # We are going to do the checking variables when only the final plate is going to be used for this set
				# Check that the initial well with sample exist in the final labware
				if initial_well_source_plate not in definition_final_plate["wells"].keys():
					raise Exception(f"The well '{initial_well_source_plate}' defined in {name_plate} does not exist in the labware {self.APINameIncubationPlate}, check for typos")
				# Check that the first well with a sample + number of samples does not exceed the number of final plate wells
				if len(definition_final_plate["wells"].keys()) < number_cells_per_plate+definition_final_plate['groups'][0]["wells"].index(initial_well_source_plate):
					raise Exception(f"Having the {initial_well_source_plate} as the first well and {number_cells_per_plate} wells to fill defined in {name_plate} does not fit in the final labware")
			
			# Now we check that the samples fit in the final labware because it will always need to fit in the final labware
			if len(definition_final_plate["wells"]) < number_cells_per_plate:
				raise Exception(f"Number of samples defined in {name_plate} is larger than the capacity of the final plate labware")
		
		# We are going to check that the colonies + antibiotic is not more than the max volume of the wells in the final plates
		max_volume_well = float(list(definition_final_plate["wells"].values())[0]['totalLiquidVolume'])
		if self.volumeAntibiotic + self.volumeSample > max_volume_well: # If final plate only with sample volumeAntibiotic will be 0 and if only with media, volumeSample will be 0
			raise Exception(f"The sum of the volumes to transfer for the samples, {self.volumeSample}uL, and media(s), {self.volumeAntibiotic}uL, exceeds the max volume of final plate wells, {max_volume_well}uL")
		
		# Check that if the tipracks are the same, the initial tips should be the same as well
		if self.APINameTipL == self.APINameTipR and self.startingTipPipL != self.startingTipPipR:
			raise Exception("If the tipracks of the right and left mount pipettes are the same and both will be used, the initial tip of both should be the same as well.")
			# This works because we have established that if it is not used, the tip racks are None

		# Check the replicas variable
		if any(pd.isna(elem) == False for elem in self.numberReplicas[self.numberSourcePlates:]):
			raise Exception("The values of 'Number of Replicas' can be as many as the 'Number of Replicas' and in consecutive columns, if empty, it is considered as 1")
		
		for index_replica, number_replica in enumerate(self.numberReplicas[:self.numberSourcePlates]):
			if pd.isna(number_replica):
				self.numberReplicas[index_replica] = 0
			else:
				try:
					self.numberReplicas[index_replica] = int(number_replica)
				except:
					raise Exception("The values of 'Number of Replicas' need to be either empty, assumed to be 0, or a whole number")

class SetParameters:
	"""
	After the checking the UserVariable class we can assign what we will be using to track the plates
	and working with the variables setted in that class
	"""
	def __init__(self):
		self.pipR = None
		self.pipL = None
		self.samplePlates = {}
		self.incubationPlates = {}
		self.antibioticWells = {}
		self.colors_mediums = ["#ffbb51"] # Initial filled with the one color of the sample
		self.liquid_samples = None # Initial value
		self.sameTiprack = None
		self.numberSourcePlatesWithSamples = 0 # Initial values
		self.argumentNewTipDistribute = None # It does not have to be the same one as in the changeTipDistribute of UserVariables
		self.volMaxPipRTiprackR = 0
		self.volMaxPipLTiprackL = 0
		self.volMaxTubeRack = 0
		self.wellsTubeRack = 0

	def assign_variables(self, user_variables, protocol):
		# Assign the color for the samples, in case it is needed in the future
		self.liquid_samples = protocol.define_liquid(
			name = "Sample",
			description = "Sample that will be inoculated with the selected medium",
			display_color = "#ffbb51"
		)
		
		# Pipette Variables
		# The variables user_variables.APINamePipR and user_variables.APINamePipL will be a NaN value either if they were left empty or not needed, this last part will be established in the check process
		if not pd.isna(user_variables.APINamePipR):
			self.pipR = protocol.load_instrument(user_variables.APINamePipR, mount = "right")
			if self.pipR.channels != 8:
				raise Exception("Right pipette needs to have 8 channels, i.e., multi channel")
			# Check if the volumes can be picked with these set of pipettes
			if self.pipR.min_volume > user_variables.volumeSample:
				raise Exception ("The volume 'Volume of Sample to Transfer (uL)' cannot be picked by the multi-channel pipette, try another volume or pipette")
		
		if not pd.isna(user_variables.APINamePipL):
			self.pipL = protocol.load_instrument(user_variables.APINamePipL, mount = "left")
			if self.pipL.channels != 1:
				raise Exception("Left pipette needs to have 1 channel, i.e., single channel")
			# Check if the volumes can be picked with these set of pipettes
			if self.pipL.min_volume > user_variables.volumeAntibiotic:
				raise Exception ("The volume 'Volume of Media to Transfer (uL)' cannot be picked by the single-channel pipette, try another volume or pipette")
		
		# This variable will be used in check_tip_and_pick to know how to layout the tip racks
		if user_variables.APINameTipR == user_variables.APINameTipL:
			self.sameTiprack = True
		else:
			self.sameTiprack = False

		# We ar egoing to set the different types of media tubes are needed
		for media in user_variables.nameAntibiotics: # This variable is going to be empty if not defined or no final plates with media are going to be created, the latter is established in the check process
			self.antibioticWells[media] = {"Positions":[], "Volumes":None, "Reactions Per Tube":None, "Number Total Reactions":0, "Definition Liquid": None}
			
			while True: # It is inside of while because the color can be taken already by other media type
				color_liquid = f"#{random.randint(0, 0xFFFFFF):06x}"
				if color_liquid.lower() != "#ffbb51" and color_liquid.lower() not in self.colors_mediums:
					self.antibioticWells[media]["Definition Liquid"] = protocol.define_liquid(
						name = f"{media}",
						description = f"Medium {media}",
						display_color = color_liquid
					)
					self.colors_mediums.append(color_liquid)
					break
		
		# Counter needed to establish the index of the plates in our final dictionary of final plates, needed because we may have more than 1 final plate per source plate
		incubation_plates_needed = 0 

		# Create the entries for each column in the sheet 'PerPlateVariables', these entries could be corresponding to the source or final plate characteristics
		# From now one we will be refering to source plates only to avoid redundancies 
		for index_plate in range(user_variables.numberSourcePlates):
			self.samplePlates[index_plate] = {"Number Samples":user_variables.samplesPerPlate[index_plate],
											   "Position":None,
											   "Label":user_variables.nameSourcePlates[index_plate],
											   "Antibiotics":None,
											   "Opentrons Place":None,
											   "Index First Well Sample": None,
											   "First Column Sample": None, # Only needed when samples are being transfered with the multi-channel pipette
											   "Only Media": user_variables.onlyMediaPlate[index_plate],
											   "Replicas": user_variables.numberReplicas[index_plate]}
			
			# Set the variables to create the final plate(s) wanted for each one of the sample plate(s) or for future trasnfering information
			if user_variables.onlySamplePlate[index_plate]: # This means that you will not use for this source plate some media so we leave it empty and it only works if we have checked this variable before
				self.samplePlates[index_plate]["Antibiotics"] = [None] # We add one because even if there is no antibiotic, still you want to do one final plate with volume from the samples
			else:
				self.samplePlates[index_plate]["Antibiotics"] = user_variables.antibioticsPerPlate[index_plate].replace(" ","").split(",")

			if self.samplePlates[index_plate]["Only Media"]:
				self.samplePlates[index_plate]["Index First Well Sample"] = opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameIncubationPlate)["groups"][0]["wells"].index(user_variables.firstWellSamplePerPlate[index_plate])
			else:
				self.samplePlates[index_plate]["Index First Well Sample"] = opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameSamplePlate)["groups"][0]["wells"].index(user_variables.firstWellSamplePerPlate[index_plate])
				self.samplePlates[index_plate]["First Column Sample"] = int(self.samplePlates[index_plate]["Index First Well Sample"]/len(opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameSamplePlate)["ordering"][0]))

			# Set the characteristics and variables we are going to fill during or now of the final plates that are going to be inoculated with samples or/and media
			for antibiotic_source_plate in self.samplePlates[index_plate]["Antibiotics"]:# If it is filles with None is because only samples are going to be transferred
				# For every source plate that is going to be inoculated with a different media or sample we can have 0 replicas (only main plate) or >1 replicas
				# We need to create number_replicas*number_media_per_column*number_of_columns
				for replica_antibiotic in range(1, self.samplePlates[index_plate]["Replicas"]+2): # It is from 1 to number of replicas+2 only for name purposes
					# Initialize with the values
					self.incubationPlates[incubation_plates_needed] = {"Source Plate":index_plate,
																	   "Position":None,
																	   "Label":None,
																	   "Antibiotic":antibiotic_source_plate,
																	   "Number Samples":self.samplePlates[index_plate]["Number Samples"], # Duplicated information for easier access in future
																	   "Opentrons Place":None}

					# Set the label of the plate depending on the replica, the type of plate and what will contain at the end (sample+media/sample/media)
					if self.samplePlates[index_plate]["Replicas"] == 0:
						if self.samplePlates[index_plate]["Only Media"] == True:
							label_this_plate = f"Number of wells as samples in '{user_variables.nameSourcePlates[index_plate]}' with {antibiotic_source_plate}"
						elif antibiotic_source_plate != None and self.samplePlates[index_plate]["Only Media"] == False:
							label_this_plate = f"Samples Plate '{user_variables.nameSourcePlates[index_plate]}' with {antibiotic_source_plate}"
						elif antibiotic_source_plate == None:
							label_this_plate = f"Final plate with only samples from {self.samplePlates[index_plate]['Label']}"
					else:
						if self.samplePlates[index_plate]["Only Media"] == True:
							label_this_plate = f"Number of wells as samples in '{user_variables.nameSourcePlates[index_plate]}' with {antibiotic_source_plate} ({replica_antibiotic})"
						elif antibiotic_source_plate != None and self.samplePlates[index_plate]["Only Media"] == False:
							label_this_plate = f"Samples Plate '{user_variables.nameSourcePlates[index_plate]}' with {antibiotic_source_plate} ({replica_antibiotic})"
						elif antibiotic_source_plate == None:
							label_this_plate = f"Final plate with only samples from {self.samplePlates[index_plate]['Label']} ({replica_antibiotic})"

					self.incubationPlates[incubation_plates_needed]["Label"] = label_this_plate

					incubation_plates_needed += 1

			# We need to establish how many labwares being the samples storage we need to set them in the layout in the future 
			if not self.samplePlates[index_plate]["Only Media"]:
				self.numberSourcePlatesWithSamples += 1

			# Add to the antibiotic number of reactions how many from this source plate does it need taking in account the number of replicas this source plate will have
			for antibiotic_plate in self.samplePlates[index_plate]["Antibiotics"]:
				if antibiotic_plate == None: # It is a plate with only samples
					continue
				
				# We have samples in this final plate so we update how many final wells we need to fill with this media
				self.antibioticWells[antibiotic_plate]["Number Total Reactions"] += self.samplePlates[index_plate]["Number Samples"]*(self.samplePlates[index_plate]["Replicas"]+1) # number_wells_final_plate*(number_replicas+number_main_plates)
		
		# Set the tip change variable that we need for the future functions because the excel allows changing of tip that doesnt correspond to the distribute function 
		# We need this argument to give to the function distribute_z_tracking_falcon15_50ml
		# tube is not a value we can give to distribute_z_tracking_falcon15_50ml because the changes between tubes are going to be done outside of the function
		if user_variables.changeTipDistribute == "tube" or user_variables.changeTipDistribute == "media":
			self.argumentNewTipDistribute = "never"
		else:
			self.argumentNewTipDistribute = user_variables.changeTipDistribute

		# Set the pipettes and check which is the real maximum volume we can handle with the pipettes taking in account the pipette and their associated tip racks
		# This is an important variable to assign if the chnaging tip is every time the pipette aspirates
		if self.pipR != None:
			def_tiprack_right = opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameTipR)
			volMaxTiprackR = def_tiprack_right['wells'][def_tiprack_right['ordering'][0][0]]['totalLiquidVolume']
			if self.pipR.max_volume <= volMaxTiprackR:
				self.volMaxPipRTiprackR = self.pipR.max_volume
			else:
				self.volMaxPipRTiprackR = volMaxTiprackR
		if self.pipL != None:
			def_tiprack_left = opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameTipL)
			volMaxTiprackL = def_tiprack_left['wells'][def_tiprack_left['ordering'][0][0]]['totalLiquidVolume']
			if self.pipL.max_volume <= volMaxTiprackL:
				self.volMaxPipLTiprackL = self.pipL.max_volume
			else:
				self.volMaxPipLTiprackL = volMaxTiprackL
		
		# We define the max volume of the falcon tubes and the number of wells for the future calculation of how many tube racks are needed
		if user_variables.nameAntibiotics:
			first_key = list(opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFalconPlate)["wells"].keys())[0]
			self.volMaxTubeRack = opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFalconPlate)["wells"][first_key]["totalLiquidVolume"]
			self.wellsTubeRack = len(opentrons.protocol_api.labware.get_labware_definition(user_variables.APINameFalconPlate)["wells"])

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

# Body of the Program
# ----------------------------------
# ----------------------------------
	
metadata = {
'apiLevel':'2.14'
}

def run(protocol:opentrons.protocol_api.ProtocolContext):
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Read Variables Excel, define the user and protocol variables and check them for initial errors
	
	# Read Excel
	excel_variables = pd.read_excel("/data/user_storage/VariablesPlateIncubation.xlsx", sheet_name = None, engine = "openpyxl")
	# excel_variables = pd.read_excel("VariablesPlateIncubation.xlsx", sheet_name = None, engine = "openpyxl")

	# Let's check that the minimal sheets exist in the excel
	name_sheets = list(excel_variables.keys())

	if not all(item in name_sheets for item in ["GeneralVariables","PerPlateVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","PerPlateVariables" and "PipetteVariables"\nThey must have those names')
	
	# Check that all variable sheets have the needed columns and variable names
	general_variables = excel_variables.get("GeneralVariables")
	plate_variables = excel_variables.get("PerPlateVariables")
	pip_variables = excel_variables.get("PipetteVariables")

	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in general_variables["Variable Names"].values for item in ['Name Source Plate', 'Number of Source Plates', 'Name Final Plate', 'Volume of Sample to Transfer (uL)', 'Name Medias', 'Volume of Media to Transfer (uL)', 'Name Tuberack', 'Change Tip In Media Distribution','Change Tip In Sample Transfer','Position Transfer Sample','Touch Tip After Transferring Sample','Mixing Volume Before Sample Transfer (uL)','Number Times of Mixing Volume','Flow Rate Mixing']):
			raise Exception("'GeneralVariables' sheet table needs to have 13 rows with the following names: 'Name Source Plate', 'Number of Source Plates', 'Name Final Plate', 'Volume of Sample to Transfer (uL)', 'Name Medias', 'Volume of Media to Transfer (uL)', 'Name Tuberack', 'Change Tip In Media Distribution', 'Change Tip In Sample Transfer', 'Position Transfer Sample', 'Touch Tip After Transferring Sample', 'Mixing Volume Before Sample Transfer (uL)', 'Number Times of Mixing Volume', 'Flow Rate Mixing'")
		
	if "Variable Names" not in list(plate_variables.columns):
		raise Exception("'PerPlateVariables' sheet table needs to have at least 1 column, 'Variable Names'")
	else:
		if not all(item in plate_variables["Variable Names"].values for item in ['Samples per plate', 'Media(s) per plate', 'First Well With Sample', 'Number of Replicas', 'Only Media(s) Plate Creation', 'Only Sample(s) Plate Creation']):
			raise Exception("'PerPlateVariables' Sheet table needs to have 3 rows with the following names: 'Samples per plate', 'Media(s) per plate', 'First Well With Sample', 'Number of Replicas', 'Only Media(s) Plate Creation', 'Only Sample(s) Plate Creation'")
	
	if not all(item in list(pip_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'PipetteVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in pip_variables["Variable Names"].values for item in ['Name Right Pipette (Multichannel)', 'API Name Right Pipette TipRack', 'Name Left Pipette (Singlechannel)', 'API Name Left Pipette TipRack','Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks']):
			raise Exception("'PipetteVariables' Sheet table needs to have 7 rows with the following names: 'Name Right Pipette (Multichannel)', 'API Name Right Pipette TipRack', 'Name Left Pipette (Singlechannel)', 'API Name Left Pipette TipRack','Initial Tip Left Pipette', 'Initial Tip Right Pipette', 'Replace Tipracks'")
	
	# Get initialized user_variables and check for initial errors
	user_variables = UserVariables(general_variables, plate_variables, pip_variables)

	# Initialize program_variables and assign the variables using the values inside of user_variable
	program_variables = SetParameters()
	program_variables.assign_variables(user_variables, protocol)
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Assign the sample source plates and the final ones that the number is already set or calculated in SetParameters
	
	# We start by extracting the labels of the source plates or type of plates that are going to be created
	labels_source_plate = []
	for index, name in enumerate(user_variables.nameSourcePlates[:user_variables.numberSourcePlates]):
		if program_variables.samplePlates[index]["Only Media"] == False:
			labels_source_plate.append(name)
	
	# Set the plates that are going to have samples in the deck
	labware_source = setting_labware(program_variables.numberSourcePlatesWithSamples, user_variables.APINameSamplePlate, dict(zip(protocol.deck.keys(), protocol.deck.values())), protocol, label = labels_source_plate)

	# Now we assign each labware position to their place in the SetteParameters class
	labware_source_loaded = generator_positions(labware_source.items())
	for plate in program_variables.samplePlates.values():
		if plate["Only Media"] == False: # In this case, the final plate(s) will have a source plate associated because samples are going to be transfered to the final ones
			# Define which labware is goign to be assigned to this source plate
			labware = next(labware_source_loaded)

			# Set the correspondant labware
			plate["Position"] = labware[0]
			plate["Opentrons Place"] = labware[1]
			
			# Set the liquid of samples in the wells that the user has established that are filled with 90% of the maximum volume of that well
			for well in plate["Opentrons Place"].wells()[plate["Index First Well Sample"]:(plate["Index First Well Sample"]+plate["Number Samples"])]:
				well.load_liquid(program_variables.liquid_samples, volume = 0.9*plate["Opentrons Place"].wells()[0].max_volume)
	
	# Set the final plates which number has been calculated in the assign_variables method of the class SettedParameters
	# First lets get the labels
	labels_incubation_plates = []
	for final_plate in program_variables.incubationPlates.values():
		labels_incubation_plates.append(final_plate["Label"])

	# Set the final labwares
	labware_final = setting_labware(len(program_variables.incubationPlates.keys()),
									user_variables.APINameIncubationPlate,
									dict(zip(protocol.deck.keys(), protocol.deck.values())),
									protocol,
									label = labels_incubation_plates)

	# Now we are going to assign to which final plates the samples from the source plates should go
	for index_labware, labware in enumerate(labware_final.items()):
		program_variables.incubationPlates[index_labware]["Position"] = labware[0]
		program_variables.incubationPlates[index_labware]["Opentrons Place"] = labware[1]

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Calculate how many falcon labware do we need and set them in the deck

	# First we need to know the max reactive tube volume
	# For that we need to know the maximum volume of the tubes and how many tubes of the reactives we need in total
	# It is only going to the enter the following condition if there is at least 1 plate that is going to have media
	if len(program_variables.antibioticWells) != 0: # It will go in only if there is some media to store in the falcon tube racks
		total_falcons_media = 0 # Initialize
		for antibiotic_type in program_variables.antibioticWells.keys():
			number_tubes, program_variables.antibioticWells[antibiotic_type]["Reactions Per Tube"], program_variables.antibioticWells[antibiotic_type]["Volumes"] = number_tubes_needed(user_variables.volumeAntibiotic,
																																														program_variables.antibioticWells[antibiotic_type]["Number Total Reactions"],
																																														0.9*program_variables.volMaxTubeRack)
			# The 0.9 max well volume is only to not overfill the volume and give space to put more liquid so the pipetting is assure
			total_falcons_media += number_tubes
		
		# Set how many tuberacks now that we now how many tubes of antibiotic we need
		tuberacks_needed = math.ceil(total_falcons_media/program_variables.wellsTubeRack)
		
		labware_falcons = setting_labware(tuberacks_needed,
										  user_variables.APINameFalconPlate,
										  dict(zip(protocol.deck.keys(),protocol.deck.values())),
										  protocol, label = "Reactive Labware")
		
		# Now we are going to set the reactives in the coldblock positions, we need to keep track of these positions for liquid movement
		# Get the possible positions merging all the labwares from the tuberacks
		positions_tuberack = []
		for labware in labware_falcons.values():
			positions_tuberack += labware.wells()
		generator_positions_antibiotics = generator_positions(positions_tuberack)
		
		# Assign to each media the positions of the falcons
		for media_type in program_variables.antibioticWells.keys():
			for volume_tube in program_variables.antibioticWells[media_type]["Volumes"]:
				well_tube_falcon = next(generator_positions_antibiotics)
				program_variables.antibioticWells[media_type]["Positions"].append(well_tube_falcon)
				well_tube_falcon.load_liquid(liquid = program_variables.antibioticWells[media_type]["Definition Liquid"], volume = volume_tube)
	
	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Distribute the media to their corresponding plates
	for media_type in program_variables.antibioticWells.keys(): # It wont go in the loop if there is no antibiotic to distribute
		if program_variables.pipL.has_tip == False:
			check_tip_and_pick(program_variables.pipL,
							   user_variables.APINameTipL,
							   dict(zip(protocol.deck.keys(), protocol.deck.values())),
							   protocol, initial_tip = user_variables.startingTipPipL,
							   replace_tiprack = user_variables.replaceTiprack,
							   same_tiprack = program_variables.sameTiprack)
		
		wells_distribute_antibiotic = []
		
		for plate_incubation in program_variables.incubationPlates.values():
			if plate_incubation["Antibiotic"] == media_type:
				# Find the first well that needs to be filled
				if program_variables.samplePlates[plate_incubation["Source Plate"]]["Only Media"]:
					# Set the wells to distribute the sample
					wells_distribute_antibiotic += plate_incubation["Opentrons Place"].wells()[program_variables.samplePlates[plate_incubation["Source Plate"]]["Index First Well Sample"]:program_variables.samplePlates[plate_incubation["Source Plate"]]["Index First Well Sample"]+plate_incubation["Number Samples"]]
				else:
					# Because we are going to transfer samples and we are going to start at the beginning of the plate we need to know the row we start to distribute that media
					row_well_initial = plate_incubation["Opentrons Place"].wells()[program_variables.samplePlates[plate_incubation["Source Plate"]]["Index First Well Sample"]]._core._row_name
					index_row_initial = list(plate_incubation["Opentrons Place"].rows_by_name().keys()).index(row_well_initial)
					
					# Set the wells to distribute the sample
					wells_distribute_antibiotic += plate_incubation["Opentrons Place"].wells()[index_row_initial:index_row_initial+plate_incubation["Number Samples"]]

		# Distribute the media
		# We are going to use a for loop because we have calculated before how many tubes are needed and how many reactions are going to be distributed from each one
		for index_tube, reactions_tube in enumerate(program_variables.antibioticWells[media_type]["Reactions Per Tube"]):
			if user_variables.changeTipDistribute in ["tube", "aspirate", "well"] and index_tube != 0:
				program_variables.pipL.drop_tip()
				# We dont need to pick another because the function 'distribute_z_tracking_falcon15_50ml' will pick one if needed

			if len(wells_distribute_antibiotic) <= reactions_tube: # There are enough volume in the tube to only transfer from this tube
				program_variables.antibioticWells[media_type]["Volumes"][index_tube] = distribute_z_tracking_falcon15_50ml (program_variables.pipL,
																															user_variables.APINameTipL,
																															dict(zip(protocol.deck.keys(),protocol.deck.values())),
																															program_variables.antibioticWells[media_type]["Volumes"][index_tube],
																															user_variables.volumeAntibiotic,
																															program_variables.antibioticWells[media_type]["Positions"][index_tube],
																															wells_distribute_antibiotic, # This is the different part from the distribute function from the else part
																															program_variables.antibioticWells[media_type]["Positions"][index_tube].max_volume,
																															protocol,
																															program_variables.volMaxPipLTiprackL,
																															new_tip = program_variables.argumentNewTipDistribute,
																															replace_tiprack = user_variables.replaceTiprack,
																															initial_tip_pip = user_variables.startingTipPipL,
																															same_tiprack = program_variables.sameTiprack,
																															touch_tip = user_variables.touchTipDistributeMedia)
				# We dont delete the wells we have distributed to because they are all of them
				reactions_tube -= len(wells_distribute_antibiotic)
			else: # There is not enough volume in the tube so we will need part of this tube and from the next one
				program_variables.antibioticWells[media_type]["Volumes"][index_tube] = distribute_z_tracking_falcon15_50ml (program_variables.pipL,
																															user_variables.APINameTipL,
																															dict(zip(protocol.deck.keys(),protocol.deck.values())),
																															program_variables.antibioticWells[media_type]["Volumes"][index_tube],
																															user_variables.volumeAntibiotic,
																															program_variables.antibioticWells[media_type]["Positions"][index_tube],
																															wells_distribute_antibiotic[:reactions_tube], # This is the different part from the distribute function from the if part
																															program_variables.antibioticWells[media_type]["Positions"][index_tube].max_volume,
																															protocol,
																															program_variables.volMaxPipLTiprackL,
																															new_tip = program_variables.argumentNewTipDistribute,
																															replace_tiprack = user_variables.replaceTiprack,
																															initial_tip_pip = user_variables.startingTipPipL,
																															same_tiprack = program_variables.sameTiprack,
																															touch_tip = user_variables.touchTipDistributeMedia)
				del wells_distribute_antibiotic[:reactions_tube]
				reactions_tube -= len(wells_distribute_antibiotic) # It will end up being 0 because we will need the next tube(s) as well to distribute to all the wells
		
		# Per each media we are going to drop the tip because the function distribute_z_tracking_falcon15_50ml keeps the last tip used unless changetip is never
		if user_variables.changeTipDistribute != "never" and program_variables.pipL.has_tip:
			program_variables.pipL.drop_tip()
	
	# Now that we have finished distributing the media, if needed, we need to drop the tip that will be attached in case the changetip was never
	# We ar eonly going to do that if the pipette is defined
	if program_variables.pipL != None:
		if program_variables.pipL.has_tip:
			program_variables.pipL.drop_tip()

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Transfer samples to different plates
	for final_plate in program_variables.incubationPlates.values():
		# Check if for this final plate samples need to be transfered
		if program_variables.samplePlates[final_plate["Source Plate"]]["Only Media"] == True: # There could be mixed types of final plates
			continue

		# We need to see how many movements are needed to transfer all the volume of sample to the final wells because we need to change tip every time we dispense in a well
		movements = math.ceil(user_variables.volumeSample/program_variables.volMaxPipRTiprackR)
		# Calculate how much volume every movement should transfer
		vol_per_movement = user_variables.volumeSample/movements
		
		# Calculate how many columns are we trasnfering
		number_column_samples = math.ceil(final_plate["Number Samples"]/program_variables.pipR.channels)

		# Either if the new tip is plate or is the first time it goes into the function, we will pick a tip
		if program_variables.pipR.has_tip == False:
			check_tip_and_pick(program_variables.pipR,
							   user_variables.APINameTipR,
							   dict(zip(protocol.deck.keys(),protocol.deck.values())),
							   protocol,
							   replace_tiprack = user_variables.replaceTiprack,
							   initial_tip = user_variables.startingTipPipR,
							   same_tiprack = program_variables.sameTiprack)
		
		# Iterate over the columns to transfer
		for index_column in range(number_column_samples):
			# We pick a tip if needed
			if program_variables.pipR.has_tip == False:
				check_tip_and_pick(program_variables.pipR,
								   user_variables.APINameTipR,
								   dict(zip(protocol.deck.keys(), protocol.deck.values())),
								   protocol,
								   replace_tiprack = user_variables.replaceTiprack,
								   initial_tip = user_variables.startingTipPipR,
								   same_tiprack = program_variables.sameTiprack)
			
			for _ in range(movements): # Iterate through the ammount of the times we need to transfer the samples
				# We pick a tip if needed
				if program_variables.pipR.has_tip == False:
					check_tip_and_pick(program_variables.pipR,
									   user_variables.APINameTipR,
									   dict(zip(protocol.deck.keys(), protocol.deck.values())),
									   protocol,
									   replace_tiprack = user_variables.replaceTiprack,
									   initial_tip = user_variables.startingTipPipR,
									   same_tiprack = program_variables.sameTiprack)
				
				# First we check that the mixing volume is not higher than the volume the pipette can aspirate
				if not pd.isna(user_variables.volumeMixing):
					if user_variables.volumeMixing > program_variables.pipR.max_volume: # This is only going to be checked if the user has decided to mix previously
						raise Exception(f"'Volume of Sample to Transfer (uL)' is going to be transfered with {program_variables.pipR}. This pipette cannot mix {user_variables.volumeMixing}, try another combination of variables")
					program_variables.pipR.mix(user_variables.timesMixing,
											   user_variables.volumeMixing,
											   program_variables.samplePlates[final_plate["Source Plate"]]["Opentrons Place"].columns()[program_variables.samplePlates[final_plate["Source Plate"]]["First Column Sample"]+index_column][0],
											   rate = user_variables.rateMixing)
				
				if user_variables.positionTransferSample == "top":
					final_position = final_plate["Opentrons Place"].columns()[index_column][0].top()
				elif user_variables.positionTransferSample == "center":
					final_position = final_plate["Opentrons Place"].columns()[index_column][0].center()
				else:
					final_position = final_plate["Opentrons Place"].columns()[index_column]
				
				program_variables.pipR.transfer(vol_per_movement,
												program_variables.samplePlates[final_plate["Source Plate"]]["Opentrons Place"].columns()[program_variables.samplePlates[final_plate["Source Plate"]]["First Column Sample"]+index_column],
												final_position,
												new_tip = "never")
				
				if user_variables.touchTipTransferSample:
					program_variables.pipR.touch_tip(final_plate["Opentrons Place"].columns()[index_column][0])
				
				if user_variables.changeTipTransfer == "aspirate": # We change every time a new movement is needed
					program_variables.pipR.drop_tip()
			
			if user_variables.changeTipTransfer == "column": # We change tips every time we move from column to column
				program_variables.pipR.drop_tip()
		
		if user_variables.changeTipTransfer == "plate": # We change tips everytime we start to transfer to a new final plate
			program_variables.pipR.drop_tip()
	
	# We have already trasnferred all the samples to the final plates if needed so we need to make sure there is no tip attached at the end
	# Which will happen always that the chnage tip during transfer is never or there is a leftover of the transferring
	if program_variables.pipR != None:
		if program_variables.pipR.has_tip:
			program_variables.pipR.drop_tip()

	#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# Homing
	protocol.home()