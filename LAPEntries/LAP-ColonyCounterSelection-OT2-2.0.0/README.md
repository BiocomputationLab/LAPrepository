# LAP-ColonyCounterSelection-OT2-2.0.0

This repository contains the python script, the excel template of variables and a file with the metadata associated with the entry of LAP entry LAP-ColonyCounterSelection-OT2-2.0.0

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Usage](#usage)
- [Script Structure](#script-structurescript)
- [Error Handling](#error-handling)

## Overview

This Python script is designed for an Opentrons OT-2 robot to perform a counter-selection protocol.

The protocol reads an Excel file that needs to be in the folder /data/user_storage of the robot to identify samples that meet specific criteria: a value higher than a defined threshold in one map of values and lower in another for the same source plate (both provided by an user in the excel file) and then transfer them to the final plate(s).

The process is highly configurable, allowing users to set variables such as transfer volumes, threshold value selection, among others. The different customization needs to be provided with the exel file provided in this folder that will be read and handled in the script.

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
 - https://laprepo.com/protocol/2-criteria-counter-selection-v-2-0-0/
 - https://www.protocols.io/view/ot-2-counter-selection-5qpvor5xdv4o

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
excel_variables = pd.read_excel("/data/user_storage/VariablesCounterSelection.xlsx", sheet_name = None, engine = "openpyxl")
# Validate Sheets
if not all(item in name_sheets for item in ["GeneralVariables","PerPlateVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","PerPlateVariables" and "PipetteVariables"\nThey must have those names')

# Validate components of sheets
	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in general_variables["Variable Names"].values for item in ['API Name Source Plate', 'Number of Source Plates', 'Volume per Reactive (uL)']):
			raise Exception("'GeneralVariables' sheet table needs to have 3 rows with the following names: 'API Name Source Plate', 'Number of Source Plates', 'Volume per Reactive (uL)'")
```

### 2. Initializing User and Program Variables as well as check their values

Here, the script initializes user-defined variables and sets program-specific parameters, ensuring they meet required conditions.

```python
# Get initialized user_variables and check for initial errors
user_variables = UserVariables(general_variables, plate_variables, pip_variables)
user_variables.check()

# Initialize program_variables and assign the variables using the values inside of user_variable
program_variables = SetParameters()
program_variables.assign_variables(user_variables, protocol)
```

### 3. Setting Up Labware

Labware (plates, tip racks, etc) is assigned to specific positions on the robot's deck based on the protocol requirements

```python
source_plates = setting_labware(user_variables.numberSourcePlates, user_variables.APINameSamplePlate, program_variables.deckPositions, protocol, label = labels_source_plate)
```

### 4. Selection of samples that meet criteria

The values given in the maps of values stored in program_variables for each source plate are checked against the threshold provided and the cells that meet the criteria are stored

```python
# Go through all the source plate values
for index_plate, plate_source in enumerate(program_variables.samplePlates.values()):
    # Go through the cells of that source plate
	for column in columns_plate_source:
		for row in row_plate_source:
			# Check if the values are according to the threshold that it was set
			if plate_source['Values for Selection (Lower than Threshold)'].iloc[row, column] <= plate_source["Threshold Value"] and plate_source['Values for Selection (Greater than Threshold)'].iloc[row, column] >= plate_source["Threshold Value"]:
				plate_source["Selected Colonies"].append([row, column])
```

### 5. Distributing Media

The script distributes media into the designated wells of each plate that are stored in program_variables, taking into account the number of reactions per tube and the volume required.

```python
# We distribute all of the media
for reactive_type in program_variables.reactiveWells.keys():
    for tube in reactive_type["Tubes"]: # Go through the tubes of this media
        wells_distribute_reactive = []
        # Find out the wells that are going to have this media and that are going to be transferred from this source tube
        for plate_incubation in program_variables.finalPlates.values():
            if plate_incubation["Medium"] == reactive_type:
                wells_distribute_reactive += plate_incubation["Opentrons Place"].wells()[:number_reactions_tube]
        # Distribute media from the falcon(s) to the final wells 
        distribute_z_tracking_falcon15_50ml(pipette, tube, wells_distribute_reactive)
```

### 5. Distribute Samples

This section handles the transfer of samples from source plates to the different final plates. All this information is stored in program_variables.

```python
# Iterate over the source plates with samples
for source_plate in program_variables.samplePlates.values():
    # Iterate over the selected colonies
    for colony_transfer in source_plate["Selected Colonies"]:

        # Get final wells to transfer
        wells_final = []
        for final_plate in source_plate["Final Plates"]
            wells_final.append(next(final_plate.wells()))
                
        # Distribute to all final wells
        pipette.distribute(volume_transfer, colony_transfer, wells_final)

        # Map in the source plate
        source_plate["Map Selected Colonies"].assign_value(colony_transfer)
```

### 6. Export the final plate layout

The excel file with all the sheets, as many as source plates, with the layout of the selected sampels in the final plate(s) are exported to the
directory/data/user_storage. All the final plates for the same source plate will have the same layout, that is why is only given 1 sheet

```python
writer = pd.ExcelWriter(f'/data/user_storage/{user_variables.finalMapName}.xlsx', engine='openpyxl')
	
for final_plate in program_variables.samplePlates.values():
	final_plate["Map Selected Colonies"].map.to_excel(writer, sheet_name = final_plate["Name Final Map"])

writer.save()
```


## Error handling

The protocol includes comprehensive error handling mechanisms to ensure the robustness of the procedure.

Within others, the following checks are performed:

1. **Minimum Variables Check**: Ensures that essential variables such as `numberSourcePlates` and `APINameFinalPlate` are not empty and meet basic requirements.
2. **Pipette Variables Check**: Verifies that necessary pipette-related variables are correctly set, including `replaceTiprack`, `APINamePipR`, and `startingTipPipR`.
3. **Sample and Plate Variables Check**: Ensures the consistency and validity of variables related to samples per plate, such as the existence of the maps and their dimensions
4. **Labware Existence Check**: Confirms that specified labware definitions exist within the Opentrons labware context.
5. **Volume and Mixing Checks**: Validates that volumes for samples and media are correctly specified and handles mixing parameters appropriately.
6. **Consistency Checks**: Verifies that there are no contradictory settings, such as volumes higher than the capacity of the final plates
