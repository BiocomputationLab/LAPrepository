# LAP-PCR-OT2-2.0.0

This repository contains the python script, the excel template of variables and a file with the metadata associated with the entry of LAP entry LAP-PCR-OT2-2.0.0

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Usage](#usage)
- [Script Structure](#script-structurescript)
- [Error Handling](#error-handling)

## Overview

This python script automates the creation of a PCR mix and its associated temperature profile using an Opentrons OT-2 robot.

The process is highly configurable, allowing users to set variables such as the number of primers per set, number and positions of controls, DNA template volume to transfer among others. The different customization needs to be provided with the exel file provided in this folder that will be read and handled in the script.

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
 - https://laprepo.com/protocol/pcr-mix-preparation-and-temperature-profile-v-2-0-0/
 - https://www.protocols.io/view/ot-2-pcr-sample-preparation-protocol-n92ldpyznl5b

## Script Structure

The script is divided into several key sections, each handling a specific aspect of the protocol

This is not an explanation of the whole script line by line but an explanation of how the script is structured and what behaviour to expect for the different code blocks. The code  given in this document is modified for better reading and summarize the script's structure, it is not exactly the one in the script and some command does not exist in reality for the sake of comprehension

For the explanation of the functions used in the script go to the directory SetFunctions of this github repository (https://github.com/BiocomputationLab/LAPrepository/tree/main/SetFunctions)

### 1. Reading and Validating Variables
This section reads and excel file situated in /data/user_storage and checks for the existance of all the needed variables cells and their values

```python
# Read Excel
excel_variables = pd.read_excel("/data/user_storage/VariablesPCR.xlsx", sheet_name = None, engine = "openpyxl")
# Validate Sheets
if not all(item in name_sheets for item in ["GeneralVariables","PerPlateVariables","PipetteVariables"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","PerPlateVariables" and "PipetteVariables"\nThey must have those names')

# Validate components of sheets
	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in general_variables["Variable Names"].values for item in ['API Name Source Plate', 'Number of Source Plates', 'API Name Eppendorf Reagents Rack']):
			raise Exception("'GeneralVariables' sheet table needs to have 3 rows with the following names: 'API Name Source Plate', 'Number of Source Plates', 'API Name Eppendorf Reagents Rack'")
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

### 3. Setting Up Labware and Modules

Labware (plates, tip racks, etc) is assigned to specific positions on the robot's deck based on the protocol requirements. In case modules like the heater-shaker and the thermocycler are needed,
they are also load in this section.

All the calculations of how many of each labware is needed, with the exception of the tip racks, are also done in this section

```python
# Set modules if needed
if user_variables.presenceHS:
    hs_mods = setting_labware(number_hs, "heaterShakerModuleV1", possible_positions_HS, protocol, module = True)
    
    # Set the labwares associated to that module
    for module in hs_mods:
        module.load_labware(user_variables.APINameLabwareHS)

# Set rest of labware
source_plates = setting_labware(user_variables.numberSourcePlates,
                                user_variables.APINameSamplePlate,
                                dict(zip(protocol.deck.keys(), protocol.deck.values())),
                                protocol,
                                label = labels)
```

### 4. Creation of set PCR mix(es)

This section consists in th etransfering of the different reactives to the correspondent tube(s).

The information of which primers go to what set and the different volumes that need to be trasnferred to the different tube(s) are in the object program_variables

```python
# Transfer water
tube_to_tube_transfer(program_variables.volWaterFactor,
					  program_variables.reactiveWells["Water"]["Positions"],
					  program_variables.reactiveWells["Water"]["Reactions Per Tube"],
					  tubes_sets,
					  reactions_tubes[:],
					  program_variables,
					  user_variables,
                      protocol)
# Transfer primers
for primer in set_primer:
    tube_to_tube_transfer(program_variables.volPrimerFactor,
					      program_variables.reactiveWells[primer]["Positions"],
					      program_variables.reactiveWells[primer]["Reactions Per Tube"],
				    	  set_primers["Positions"],
					      set_primers["Reactions Per Tube"][:],
					      program_variables,
					      user_variables,
                          protocol,
                          new_tip = "aspirate")
# Transfer polymerase
pipette.flow_rate = pipette.min_volume

tube_to_tube_transfer(program_variables.volPolymeraseFactor,
					  program_variables.reactiveWells["Polymerase"]["Positions"],
					  program_variables.reactiveWells["Polymerase"]["Reactions Per Tube"],
					  tubes_sets,
					  reactions_tubes[:],
					  program_variables,
					  user_variables,
                      protocol,
                      new_tip = "aspirate")

pipette.flow_rate = pipette.default_speed
```

### 5. Mix the sets and distribute

The script distributes media into the designated wells of each plate that are stored in program_variables, taking into account the number of reactions per tube and the volume required.

```python
# We go through all the different types of set
for set_primer in program_variables.setsWells.values():
    # We go through all the tubes of that set
    for tube in set_primer["Positions"]:
        if user_variables.presenceHS == True:
            # Mix with HS
            program_variables.hs_mods[int(str(tube).split(" ")[-1])].set_and_wait_for_shake_speed(user_variables.rpm)
			protocol.delay(seconds = 15)
			program_variables.hs_mods[int(str(tube).split(" ")[-1])].deactivate_shaker()

            # Distribute
            pipette.distribute(program_variables.volTotal, tube, wells_distribute)
        else:
            mixing_eppendorf_15(tube,
								tube["Volumes"],
								vol_mixing,
								pipette_mixing)
            
            # Distribute
            pipette.distribute(program_variables.volTotal, tube, wells_distribute)
```

### 5. Distribute Samples

This section handles the transfer the DNA templates from source plate(s) to the different final plate(s).

```python
for source_plate in program_variables.samplePlates.values():
    # Find out the wells to transfer 
    wells = source_plate["Opentrons Place"].wells()[source_plate["Index First Well Sample"]:]

    controls_taken = []
    # Take out the controls
    for control in source_plate["Control Positions"]:
        if control in wells:
            wells.remove(control)
    # Take out the not pick samples
    for notPCR in source_plate["Positions Not Perform PCR"]:
        if notPCR in wells:
            wells.remove(notPCR)
    # Add the controls at the end
    wells += controls_taken

    # Transfer
    final_wells = generator_position(wells_distribute)

    for set_primer in range(int(user_variables.sets)):
        for well in wells: 
            pipette.transfer(user_variables.volumesSamplesPerPlate, well, next(final_wells))
```

### 6. Temperature Profile
In this section, in case the thermocycler is set as True, a temperature profile in the thermocycler is performed given the variables established in
user_variables and the module thermocycler in program_variables

```python
if user_variables.presenceTermo:
    run_program_thermocycler (program_variables.tc_mod,
							  user_variables.temperatureProfile,
							  user_variables.temperatureLid,
							  user_variables.finalVolume,
							  final_lid_state = user_variables.finalStateLid,
							  final_block_state = user_variables.finalTemperatureBlock)
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
