# LAP-NplateMerging-OT2-2.0.0

This repository contains the python script, the excel template of variables and a file with the metadata associated with the entry of LAP entry LAP-NplateMerging-OT2-2.0.0

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Usage](#usage)
- [Script Structure](#script-structurescript)
- [Error Handling](#error-handling)

## Overview

This python script is designed to automate the merging samples from 2+ plates to less final plates and as well can previously transfer volume to the latter ones using an Opentrons OT-2 robot. 

The protocol reads an Excel file that needs to be in the folder /data/user_storage of the robot to set, based on the user's specification, which samples to select from the source plates.

The process is highly configurable, allowing users to set variables such as transfer volumes, type of sample selection, among others. The different customization needs to be provided with the exel file provided in this folder that will be read and handled in the script.

## Requirements

 - Python 3.7+
 - Pandas
 - OpenPyXL
 - Opentrons 7.0.2
 - Numpy

 ## Usage

1. Prepare the excel file
2. Send it to the OT-2's directory /data/user_storage
3. Load the script into the OT-App
4. Run script

For more information about the usage and excel file of this LAP entry go to the following links:
 - https://www.laprepo.com/protocol/colony-n-plates-merging-v-2-0-0/
 - https://www.protocols.io/view/ot-2-protocol-to-transfer-volume-from-several-plat-6qpvr4o62gmk

 ## Script Structure

The script is divided into several key sections, each handling a specific aspect of the protocol

This is not an explanation of the whole script line by line but an explanation of how the script is structured and what behaviour to expect for the different code blocks. The code  given in this document is modified for better reading and summarize the script's structure, it is not exactly the one in the script.

Please note that the code snippets provided in this README are simplified and modified versions of the actual script.

Some commands have been altered for readability and comprehension (do not copy this code because it may not work), and as well the sections of the code are summarized. For the exact code and structure go to the script itself, which is commented as well.

For the explanation of the functions used in the script go to the directory SetFunctions of this github repository (https://github.com/BiocomputationLab/LAPrepository/tree/main/SetFunctions)

### 1. Reading and Validating Variables
This section reads and excel file situated in /data/user_storage and checks for the existance of all the needed variables cells and their values

```python
# Read Excel
excel_variables = pd.read_excel("/data/user_storage/VariablesMergeSamples.xlsx", sheet_name = None, engine = "openpyxl")

# Validate Sheets
if not all(item in name_sheets for item in ["GeneralVariables","PerPlateVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","PerPlateVariables" and "PipetteVariables"\nThey must have those names')

# Validate components of sheets
if not all(item in list(pip_variables.columns) for item in ["Value", "Variable Names"]):
	raise Exception("'PipetteVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
else:
	if not all(item in pip_variables["Variable Names"].values for item in ['API Name Right Pipette','API Name Left Pipette','API Name Tiprack Left Pipette']):
		raise Exception("'PipetteVariables' Sheet table needs to have 3 rows with the following names: API Name Right Pipette','API Name Left Pipette','API Name Tiprack Left Pipette'")
```

### 2. Initializing User and Program Variables as well as check their values

Here, the script initializes user-defined variables and sets program-specific parameters, ensuring they meet required conditions.

```python
# Get initialized user_variables and check for initial errors
user_variables = UserVariables(general_variables, plate_variables, pip_variables)
user_variables.check()

# Initialize program_variables and assign the variables using the values inside of user_variable
program_variables = SettedParameters()
program_variables.assign_variables(user_variables, protocol)
```

### 3. Setting Up Source and Final Labware

Labware (source plates and final plates) is assigned to specific positions on the robot's deck based on the protocol requirements

```python
labware_source = setting_labware(user_variables.numberSourcePlates,
								 user_variables.APINameSamplePlate,
								 dict_positions_deck,
								 protocol,
								 label = list_source_plate_labels)
```

### 4. Set Variables Based on Labware

This part sets variables that depends on previous loaded labware (in the section 3) and variables set by the user (in the section 1) such as the samples available for selection in each source and the final layout maps

```python
for source_plate in program_variables.samplePlates.items():
    list_wells_possible_selection = source_plate["Opentrons Place"].wells()[source_plate["Index First Well Sample"]:]

for final_plate in program_variables.finalPlates.values():
	final_plate["Map Selected Samples"] = MapLabware(final_plate["Opentrons Place"])
```

### 5. Set Falcon Rack(s)

If reactive volume is specified, the script calculates the number of Falcon tubes and racks needed, assigns them positions, and sets their volumes.

```python
if user_variables.volumeReactive != 0:
	# Find out how many tubes we need
	falcon_needed, reactions_tube, volume_tube = number_tubes_needed (user_variables.volumeReactive,
																	  program_variables.sumSamples,
																	  user_variables.volumeFalcons*0.9)
		
	# Place falcon labware
    tuberacks_needed = math.ceil(falcon_needed/number_wells_tuberack)
	labware_falcons = setting_labware(tuberacks_needed,
									  user_variables.APINameFalconPlate,
									  dict_positions_deck,
									  protocol)
		
	# Now we are going to set the reactives in the coldblock positions, we need to keep track of these positions for liquid movement
	# Get the possible positions merging all the labwares from the tuberacks
		
	# Assign the reactive to positions inside of the tube rack
	for volume_tube in program_variables.reactiveWells["Volumes"]:
		program_variables.reactiveWells["Positions"].append(free_position_tube_falcon)
```

### 6. Distribute Reactive
Reactives are distributed to the final wells using the optimal pipette for that volume. The script handles tip picking and liquid transfer

This section is only performed if volumeReactive is greater than 0

```python
if user_variables.volumeReactive != 0:
	# Go through the tubes already defined of reactive and distribute to the final wells
	for volume_tube, reactions_tube, position_tube in zip(volumes_falcon_tubes, positions_per_falcon_tube, positions_tubes):
		distribute_z_tracking_falcon15_50ml (pipette_transfer,
											 tiprack_pipette,
											 dict_positions_deck,
											 volume_tube,
											 ...)
```

### 7. Transfer Samples

Samples are transferred from the source plates to the final plates. The script maps each transfer to ensure accurate tracking and uses the optimal pipette for each transfer.

```python
for plate in list(program_variables.samplePlates.values()):			
    # We go through all the samples that have been selected in the SettedVariables class considering the user variables
	for sample_well in plate["Selected Samples"]:
		optimal_pipette.transfer(plate["Volume Sample Transfer"], sample_well, final_well, new_tip = "never")
		
		# Map the transfer
		for final_plate in list(program_variables.finalPlates.values()):
			if final_plate["Opentrons Place"] == final_well._parent:
				final_plate["Map Selected Samples"].assign_value(source_well_name, well_row_name, well_column_name)
```

### 8. Export Maps

The final mapping of samples is exported to an Excel file for user review and record-keeping in the robot's folder /data/user_storage with the name provided in the provided excel variables file

```python
writer = pd.ExcelWriter(f'/data/user_storage/{user_variables.finalMapName}.xlsx', engine = 'openpyxl')

for final_plate in program_variables.finalPlates.values():
    final_plate["Map Selected Samples"].map.to_excel(writer, sheet_name = f"FinalMapSlot{final_plate['Position']}")

writer.save()
```

## Error handling

The protocol includes comprehensive error handling mechanisms to ensure the robustness of the procedure.

Within others, the following checks are performed:

1. **Minimum Variables Check**: Ensures that essential variables such as `finalMapName` and `APINameSamplePlate` are not empty and meet basic requirements.
2. **Pipette Variables Check**: Verifies that necessary pipette-related variables are correctly set, including `replaceTiprack`, `APINamePipR`, and `startingTipPipR`.
3. **Sample and Plate Variables Check**: Ensures the consistency and validity of variables related to samples per plate, such as the existence of the maps and their dimensions.
4. **Labware Existence Check**: Confirms that specified labware definitions exist within the Opentrons labware context.
5. **Consistency Checks**: Verifies that there are no contradictory settings, such as volumes higher than the capacity of the final plates or trying to select more samples from a source plate that the ones available in it.