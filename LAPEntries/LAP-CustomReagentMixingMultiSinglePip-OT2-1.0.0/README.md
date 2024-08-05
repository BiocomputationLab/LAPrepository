# LAP-CellMediaInoculation-OT2-2.0.0

This repository contains the python script, the excel template of variables and a file with the metadata associated with the entry of LAP LAP-CustomReagentMixingMultiSinglePip-OT2-1.0.0

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Usage](#usage)
- [Script Structure](#script-structurescript)
- [Error Handling](#error-handling)

## Overview

This script is destined to automate the process of filling final plates with specified volumes of various reactants based on user-defined parameters provided in an Excel file. These final plates can be either created with single or multi channel pipettes. Only 1 type of pipette (single or multi) can creta e a final plate, but different plates can be created with different types of pipette in 1 run of the script.

The process is highly configurable, allowing users to set variables such as transfer volumes, the type of source tube, change of tips during distribution, and replication count, among others.

The different customization needs to be provided with the exel file provided in this repository that will be read and handled in the script.

## Requirements

 - Python 3.7+
 - Pandas
 - Numpy
 - OpenPyXL
 - Opentrons 7.0.2

## Usage

1. Prepare the excel file
2. Send it to the OT-2's directory /data/user_storage
3. Load the script into the OT-App
4. Run script

For more information about the usage and excel file of this LAP entry go to the following links:
 - https://www.laprepo.com/protocol/custom-mixing-single-multi-channel-pipette/

## Script Structure

The script is divided into several key sections, each handling a specific aspect of the protocol

Not every line of the script is explained in this README; only selected parts are covered to help understand the overall behavior and structure.

Please note that the code snippets provided in this README are simplified and modified versions of the actual script.

Some commands have been altered for readability and comprehension (do not copy this code because it may not work), and as well the sections of the code are summarized. For the exact code and structure go to the script itself, which is commented as well.

For the explanation of the functions used in the script go to the directory SetFunctions of this github repository (https://github.com/BiocomputationLab/LAPrepository/tree/main/SetFunctions)

### 1. Reading and Validating Variables
This section reads and excel file situated in /data/user_storage and checks for the existance of all the needed variables cells and their values

```python
# Read Excel
excel_variables = pd.read_excel("/data/user_storage/VariablesCustomMixing.xlsx", sheet_name = None, engine = "openpyxl")
# Validate Sheets
if not all(item in name_sheets for item in ["GeneralVariables","FinalPlatesVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","FinalPlatesVariables" and "PipetteVariables"\nThey must have those names')

# Validate components of sheets
if "Variable Names" not in list(plate_variables.columns):
	raise Exception("'FinalPlatesVariables' sheet table needs to have at least 1 column, 'Variable Names'")
else:
	if not all(item in plate_variables["Variable Names"].values for item in ['Number of Replicas','Name Sheet Map Reagents','Name Sheet Map Volumes','Type of Pipette to Create Plate']):
		raise Exception("'FinalPlatesVariables' Sheet table needs to have 4 rows with the following names: 'Number of Replicas', 'Name Sheet Map Reagents', 'Name Sheet Map Volumes', 'Type of Pipette to Create Plate'")
	
```

### 2. Initializing User and Program Variables as well as check their values

Here, the script initializes user-defined variables and sets program-specific parameters, ensuring they meet required conditions.

```python
# Get initialized user_variables and check for initial errors
user_variables = UserVariables(general_variables, plate_variables, pip_variables, excel_variables)
user_variables.check()

# Calculate and set some of the variables that is going to be used in the rest of the script and it is derived from the variables set in excel
program_variables = SettedParameters()
# In this part of the script the source tubes/columns needed are set
program_variables.assign_variables(user_variables, protocol)
```

### 3. Setting Up Labware

Labware (plates, tube racks, etc) is assigned to specific positions on the robot's deck based on the protocol requirements

```python
if any(elem == 'single' for elem in user_variables.pipetteCreationPlate[:user_variables.numberFinalPlates]):
    tubes_reagents_labware = setting_labware(math.ceil(total_tubes/user_variables.numberTubesLabware),
                                                    user_variables.APINameFalconPlate,
                                                    dict(zip(protocol.deck.keys(),
                                                    protocol.deck.values())),
                                                    protocol,
                                                    label = label)
```

### 4. Distributing Regeants with Single-Channel Pipette(s)

The script distributes the reagents to the plates that are going to be created with single channel pipettes in case there are plates with that characteristic

```python
for values_reagents in program_variables.antibioticWells.values():
    for reactions_tube, position_tube, volume_tube in zip(values_reagents["Reactions Per Tube"], values_reagents["Position Tubes"], values_reagents["Volumes Per Tube"]):
        # Establish which pipettes can transfer which volume
        volumes_distribute_pipR, positions_distribute_pipR, volumes_distribute_pipL, positions_distribute_pipL = vol_pipette_matcher (volumes_reagent[:reactions_tube],
																																			  wells_reagent[:reactions_tube],
																																			  program_variables.pipR,
																																			  program_variables.pipL)
        
        # We know that which one is going to be transferred with which pipette so now we need to take in account wich tube is the source and transfer it
		if user_variables.typeTubesReagents == "eppendorf":
            if volumes_distribute_pipL:
                check_tip_and_pick(program_variables.pipL,
								   user_variables.APINameTipL,
								   dict(zip(protocol.deck.keys(), protocol.deck.values())),
								   protocol,
								   ...)
                
                program_variables.pipL.distribute(volumes_distribute_pipL,
												  position_tube,
												  positions_distribute_pipL,
												  new_tip = "never",
												  touch_tip = user_variables.touchTipDistributeMedia)
				
                program_variables.pipL.drop_tip()
            
            if volumes_distribute_pipR:
                check_tip_and_pick(program_variables.pipR,
								   user_variables.APINameTipR,
								   dict(zip(protocol.deck.keys(), protocol.deck.values())),
								   protocol,
								   ...)
                
                program_variables.pipL.distribute(volumes_distribute_pipR,
												  position_tube,
												  positions_distribute_pipR,
												  new_tip = "never",
												  touch_tip = user_variables.touchTipDistributeMedia)
				
                program_variables.pipR.drop_tip()
        else: # Falcon tubes are used
            if volumes_distribute_pipL:
                check_tip_and_pick(program_variables.pipL,
								   user_variables.APINameTipL,
								   dict(zip(protocol.deck.keys(), protocol.deck.values())),
								   protocol,
								   ...)

                volume_tube = distribute_z_tracking_falcon15_50ml(program_variables.pipL,
                                                                  position_tube,
                                                                  positions_distribute_pipL,
                                                                  ...)
            if volumes_distribute_pipR:
                check_tip_and_pick(program_variables.pipR,
								   user_variables.APINameTipR,
								   dict(zip(protocol.deck.keys(), protocol.deck.values())),
								   protocol,
								   ...)

                volume_tube = distribute_z_tracking_falcon15_50ml(program_variables.pipR,
                                                                  position_tube,
                                                                  positions_distribute_pipR,
                                                                  ...)
```

### 5. Distributing Regeants with Multi-Channel Pipette(s)

The script distributes the reagents to the plates that are going to be created with multi channel pipettes in case there are plates with that characteristic

```python
if program_variables.neededColumnsMulti:
    # Go through all the columns we have set previously
    for values_column in program_variables.neededColumnsMulti.sourceColumnsNeeded.values():
        # Now that we have the complet list of final columns where this reagent column needs to be transferred to we will loop over all the columns that we have calculated previously
		# and transfer them from the source columns. We dont need to control the volume because we know how many final wells we can transfer to without running out of volume
        for reactions_column, position_column, volume_column in zip(values_column['Reactions/column'], values_column['Positions Opentrons'], values_column['Volumes/column']):
            volumes_distribute_pipR, positions_distribute_pipR, volumes_distribute_pipL, positions_distribute_pipL = vol_pipette_matcher (all_volumes_transfer_source_column[:reactions_column],
																																		  all_columns_transfer_source_column[:reactions_column],
																																		  program_variables.pipR,
																																		  program_variables.pipL
																																		  )
            
            if volumes_distribute_pipL:
                check_tip_and_pick(program_variables.pipL,
						 		   user_variables.APINameTipL,
								   dict(zip(protocol.deck.keys(), protocol.deck.values())),
								   protocol,
								   ...)
                
                program_variables.pipL.distribute(volumes_distribute_pipL,
										 		  position_column,
												  positions_distribute_pipL,
												  new_tip = "never",
												  disposal_volume = 0,
												  touch_tip = user_variables.touchTipDistributeMedia)
				
                program_variables.pipL.drop_tip()

            if volumes_distribute_pipR:
                check_tip_and_pick(program_variables.pipr,
						 		   user_variables.APINameTipr,
								   dict(zip(protocol.deck.keys(), protocol.deck.values())),
								   protocol,
								   ...)

                program_variables.pipR.distribute(volumes_distribute_pipR,
										 		  position_column,
												  positions_distribute_pipR,
												  new_tip = "never",
												  disposal_volume = 0,
												  touch_tip = user_variables.touchTipDistributeMedia)
                
                program_variables.pipR.drop_tip()
```

## Error handling

The protocol includes comprehensive error handling mechanisms to ensure the robustness of the procedure.

Within others, the following checks are performed:

1. **Minimum Variables Check**: Ensures that essential variables such as `numberSourcePlates` and `APINameIncubationPlate` are not empty and meet basic requirements.
2. **Pipette Variables Check**: Verifies that necessary pipette-related variables are correctly set, including `replaceTiprack`, `APINamePipR`, and `startingTipPipR`.
3. **Sample and Plate Variables Check**: Ensures the consistency and validity of variables related to samples per plate, first wells with samples, if internal replicas fit, etc.
4. **Labware Existence Check**: Confirms that specified labware definitions exist within the Opentrons labware context.
5. **Consistency Checks**: Verifies that there are no contradictory settings, such as setting both `onlyMediaPlate` and `onlySamplePlate` to true.
