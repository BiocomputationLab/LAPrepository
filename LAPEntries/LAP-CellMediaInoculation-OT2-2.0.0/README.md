# LAP-CellMediaInoculation-OT2-2.0.0

This repository contains the python script, the excel template of variables and a file with the metadata associated with the entry of LAP LAP-CellMediaInoculation-OT2-2.0.0

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Usage](#usage)
- [Script Structure](#script-structurescript)
- [Error Handling](#error-handling)

## Overview

This python script facilitates the creation of customized plates with samples derived from various source plates, each containing different media.

The process is highly configurable, allowing users to set variables such as transfer volumes, sample selection, the number of sample-media combinations, and replication count, among others.

The different customization needs to be provided with the exel file provided in this repository that will be read and handled in the script.

This scripts allows execution of only media distribution or only sample transfer if specified in the input file.

## Requirements

 - Python 3.7+
 - Pandas
 - OpenPyXL
 - Opentrons 7.0.2

## Usage

1. Prepare the excel file
2. Send it to the OT-2's directory /data/user_storage
3. Load the script into the OT-App
4. Run script

For more information about the usage and excel file of this LAP entry go to the following links:
 - https://laprepo.com/protocol/cell-inoculation-in-different-media-v2-0-0/
 - https://www.protocols.io/view/ot-2-media-dispensing-and-culture-inoculation-prot-q26g7yb3kgwz

## Script Structure

The script is divided into several key sections, each handling a specific aspect of the protocol

This is not an explanation of the whole script line by line but an explanation of how the script is structured and what behaviour to expect for the different code blocks. The code  given in this document is modified for better reading and summarize the script's structure, it is not exactly the one in the script.

For the explanation of the functions used in the script go to the directory SetFunctions of this github repository (https://github.com/BiocomputationLab/LAPrepository/tree/main/SetFunctions)

### 1. Reading and Validating Variables
This section reads and excel file situated in /data/user_storage and checks for the existance of all the needed variables cells and their values

```python
# Read Excel
excel_variables = pd.read_excel("/data/user_storage/VariablesPlateIncubation.xlsx", sheet_name = None, engine = "openpyxl")
# Validate Sheets
if not all(item in name_sheets for item in ["GeneralVariables","PerPlateVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","PerPlateVariables" and "PipetteVariables"\nThey must have those names')

# Validate components of sheets
	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in general_variables["Variable Names"].values for item in ['Name Source Plate', 'Number of Source Plates', 'Name Final Plate']):
			raise Exception("'GeneralVariables' sheet table needs to have 3 rows with the following names: 'Name Source Plate', 'Number of Source Plates', 'Name Final Plate'")
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
labware_source = setting_labware(program_variables.numberSourcePlatesWithSamples, user_variables.APINameSamplePlate, dict(zip(protocol.deck.keys(), protocol.deck.values())), protocol, label = labels_source_plate)
```

### 4. Distributing Media
The script distributes media into the designated wells of each plate that are stored in program_variables, taking into account the number of reactions per tube and the volume required.

```python
# We distribute all of the media
for media_type in program_variables.antibioticWells.keys():
    for tube in media_type["Tubes"]: # Go through the tubes of this media
        wells_distribute_antibiotic = []
        # Find out the wells that are going to have this media and that are going to be transferred from this source tube
        for plate_incubation in program_variables.incubationPlates.values():
            if plate_incubation["Antibiotic"] == media_type:
                wells_distribute_antibiotic += plate_incubation["Opentrons Place"].wells()[:number_reactions_tube]
        # Distribute media from the falcon(s) to the final wells 
        distribute_z_tracking_falcon15_50ml(pipette, tube, wells_distribute_antibiotic)
```

### 5. Distribute Samples
This section handles the transfer of samples from source plates to the final incubation plates, which information is stored in program_variables, managing tips and transfer positions as specified.

```python
# Iterate over the source plates with samples
for final_plate in program_variables.incubationPlates.values():
    # Calculate how many columns are we trasnfering
	number_column_samples = math.ceil(final_plate["Number Samples"]/program_variables.pipR.channels)
    for index_column in range(number_column_samples):
        program_variables.pipR.transfer(vol_sample,
                                        program_variables.samplePlates["Source Plate"].columns()[first_column_sample+index_column],
                                        final_plate.columns()[index_column])
```

## Error handling

The protocol includes comprehensive error handling mechanisms to ensure the robustness of the procedure.

Within others, the following checks are performed:

1. **Minimum Variables Check**: Ensures that essential variables such as `numberSourcePlates` and `APINameIncubationPlate` are not empty and meet basic requirements.
2. **Pipette Variables Check**: Verifies that necessary pipette-related variables are correctly set, including `replaceTiprack`, `APINamePipR`, and `startingTipPipR`.
3. **Sample and Plate Variables Check**: Ensures the consistency and validity of variables related to samples per plate, first wells with samples, and antibiotics per plate.
4. **Labware Existence Check**: Confirms that specified labware definitions exist within the Opentrons labware context.
5. **Volume and Mixing Checks**: Validates that volumes for samples and media are correctly specified and handles mixing parameters appropriately.
6. **Consistency Checks**: Verifies that there are no contradictory settings, such as setting both `onlyMediaPlate` and `onlySamplePlate` to true.
