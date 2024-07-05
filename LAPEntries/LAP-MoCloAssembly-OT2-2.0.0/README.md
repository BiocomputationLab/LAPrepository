# LAP-MoCloAssembly-OT2-2.0.0

This repository contains the python script, the excel template of variables and a file with the metadata associated with the entry of LAP entry LAP-MoCloAssembly-OT2-2.0.0

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Usage](#usage)
- [Script Structure](#script-structure)
- [Error Handling](#error-handling)

## Overview

This Python script automates the construction of modular cloning (MoClo) constructs in an OT environment. It prepares a MoClo mix by distributing ligase, buffer, restriction enzyme, and serum, and dispenses it into final wells along with the specified DNA parts and water to achieve uniform final volumes, as defined by the user in an Excel file.
This protocol is highly customizable allowing the users to select pipettes, specify the number of combinations, adjust reagent quantities, etc. This is done by filling the excle file that this repository contains and sending it to the /data/user_storage directory of the robot where this script is going to be run.

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
 - https://www.laprepo.com/protocol/modular-cloning-constructs-assembly-v-2-0-0/
 - https://www.protocols.io/view/ot-2-modular-cloning-construct-assembly-c6egzbbw

## Script Structure

The script is divided into several key sections, each handling a specific aspect of the protocol

This is not an explanation of the whole script line by line but an explanation of how the script is structured and what behaviour to expect for the different code blocks. The code given in this document is modified for better reading and summarize the script's structure, it is not exactly the one in the script

Please note that the code snippets provided in this README are simplified and modified versions of the actual script.

Some commands have been altered for readability and comprehension (do not copy this code because it may not work), and as well the sections of the code are summarized. For the exact code and structure go to the script itself, which is commented as well.

For the explanation of the functions used in the script go to the directory SetFunctions of this github repository (https://github.com/BiocomputationLab/LAPrepository/tree/main/SetFunctions)

### 1. Reading and validate variables

This section reads and excel file situated in /data/user_storage and checks for the existance of all the needed variables cells and their values

```python
# Read Excel
excel_variables = pd.read_excel("/data/user_storage/VariablesMoCloAssembly.xlsx", sheet_name = None, engine = "openpyxl")

# Validate Sheets
if not all(item in name_sheets for item in ["GeneralVariables","PerPlateVariables","PipetteVariables", "ReactionVariables", "ModuleVariables", "Combinations"]):
		raise Exception('The Excel file needs to have the sheets "GeneralVariables","PerPlateVariables", "PipetteVariables", "ReactionVariables", "ModuleVariables" and "Combinations"\nThey must have those names')

# Validate components of sheets
	if not all(item in list(general_variables.columns) for item in ["Value", "Variable Names"]):
		raise Exception("'GeneralVariables' sheet table needs to have only 2 columns: 'Variable Names' and 'Value'")
	else:
		if not all(item in general_variables["Variable Names"].values for item in ['API Name Final Plate', 'API Name Labware Eppe ndorfs Reagents', 'Name File Final Constructs', 'Well Start Final Labware', 'API Name Labware DNA Constructs', 'Number DNA Parts Plates']):
			raise Exception("'GeneralVariables' sheet table needs to have 6 rows with the following names: 'API Name Final Plate', 'API Name Labware Eppe ndorfs Reagents', 'Name File Final Constructs', 'Well Start Final Labware', 'API Name Labware DNA Constructs', 'Number DNA Parts Plates'")
```

### 2. Initializing User and ProgramVaribles and check them

Here, the script initializes user-defined variables and sets program-specific parameters, ensuring they meet required conditions.

```python
# Get initialized user_variables and check for initial errors
user_variables = UserVariables(general_variables, plate_variables, pip_variables, ...)
user_variables.check()

# Initialize program_variables and assign the variables using the values inside of user_variable
program_variables = SettedParameters(len(protocol.deck))
program_variables.assign_variables(user_variables, protocol)
```

### 3. Setting Heater-Shaker and the mix tubes (Optional)

In this section we restablished the heater-shaker, which positions are limited, and load/define the tubes that woill hold the MoClo mixes to distribute 

```python
if user_variables.presenceHS and program_variables.volTotalFactor > 0:
	number_tubes_mix_hs, reactions_per_tube_mix_hs, volumes_tubes_mix_hs = number_tubes_needed (program_variables.volTotalFactor,
																								program_variables.sumSamples,
																								user_variables.volMaxMixTube)
		
	# You cannot put the HS in some position according to their documentation, even if the opentrons app doesnt raise errors
	possible_positions_HS = {key: program_variables.deckPositions[key] for key in [1, 3, 4, 6, 7, 10]}

	# Establish the hs_mod if possible
	hs_mods = setting_labware(number_hs,
							  "heaterShakerModuleV1",
							  possible_positions_HS,
							  protocol,
							  module = True)
			
	# Set the volumes of the mixes within the HS
	for volume_tube in program_variables.mixWells["Volumes"]:
		well_tube_eppendorf = next(generator_wells_hs)
		program_variables.mixWells["Positions"].append(well_tube_eppendorf)
		well_tube_eppendorf.load_liquid(liquid = program_variables.mixWells["Definition Liquid"], volume = 0)
```

### 4. Setting DNA Plates

Set the Plates that will contain the DNA Partsthat will be transferred to the final combination wells

```python
labware_source = setting_labware(user_variables.numberSourcePlates, user_variables.APINameSamplePlate, program_variables.deckPositions, protocol, label = labels)
```

### 5. Define volumes and the final destination combinations for each DNA Part

In this section based on the combinations and the positions of the DNA parts in their labware, the different maps attached to that source labware are filled with the required volumes of each DNA part and which DNA part is part of with combination

```python
# Now we assign each labware position to ther place in the SetteParameters class
for index_labware, source_labware in enumerate(labware_source.items()):
	# We are going to establish some maps that are going to contain the information of each place
	source_labware['Map Names'] = pd.read_excel("/data/user_storage/VariablesMoCloAssembly.xlsx", sheet_name = user_variables.nameSheetMapParts[index_labware], index_col = 0, engine = "openpyxl")
	source_labware['Map Volumes'] = pd.DataFrame(0, index = name_rows, columns = name_columns)
	source_labware['Map Final Combinations Acceptor'] = pd.DataFrame(np.nan, index = name_rows, columns = name_columns)
	source_labware['Map Final Combinations Module'] = pd.DataFrame(np.nan, index = name_rows, columns = name_columns)

	# Define volumes of each part, their liquid definition, the final constructs they are going to give volume to
	for id_combination, combination in program_variables.combinations.items():
		# Let's see if the acceptor of this combination is in the map of this labware
		well = source_labware['Map Names'][source_labware['Map Names'].isin([combination["acceptor"]])].stack()
		if len(well) > 0: # If it enters this loop, the acceptor is in this labware
			# Add the volume of the acceptor to that well
			source_labware['Map Volumes'].loc[row_well, str(column_well)] += user_variables.acceptorVolume

			# Add that combination to the final wells where this acceptor is going to be transferred to
			source_labware['Map Final Combinations Acceptor'].loc[row_well, str(column_well)].append(id_combination)
			
        # Now we add the module parts on the same way
		for dna_module in combination["modules"]:
			well = source_labware['Map Names'][source_labware['Map Names'].isin([dna_module])].stack()
			if len(well) > 0:
				# Add the volume of the module to that well
				source_labware['Map Volumes'].loc[row_well, str(column_well)] += user_variables.moduleVolume
				
				# Add that combination to the final wells where this module is going to be transferred to
				source_labware['Map Final Combinations Module'].loc[row_well, str(column_well)].append(id_combination)
```

### 6. Setting Final Plates

In this part we assign the final plates to the OT layout

```python
if user_variables.presenceTermo:
	program_variables.tc_mod.load_labware(user_variables.APINameFinalPlate, label = "Final Plate with Combinations Slot 7")
else:
	labware_final = setting_labware(len(program_variables.finalPlates), user_variables.APINameFinalPlate, program_variables.deckPositions, protocol, label = "Final Plate With Combinations")
```

### 7. Setting reactives labware and tubes positions

Calculate the tubes of each reagent, calculate the ammount of eppendorf labware and set the positions of the different tubes

```python
total_number_tubes = 0
	
number_tubes_ligase, program_variables.reactiveWells["Ligase"]["Reactions Per Tube"], program_variables.reactiveWells["Ligase"]["Volumes"] = number_tubes_needed (program_variables.volLigaseFactor, program_variables.reactiveWells["Ligase"]["Number Total Reactions"], vol_max_tube*0.9)

total_number_tubes += number_tubes_ligase

# Set the number of tubes in the coldblock
number_coldblocks = math.ceil(total_number_tubes/len(labware_context.get_labware_definition(user_variables.APINameEppendorfPlate)["wells"]))
coldblocks = setting_labware(number_coldblocks,
							 user_variables.APINameEppendorfPlate,
							 dict(sorted(program_variables.deckPositions.items(), reverse=True)),
							 protocol,
							 label = "Reagents") # We do the inverse deckPositions because it is less likely to have deck conflict error
program_variables.deckPositions = {**program_variables.deckPositions , **coldblocks}

# Assign to each reactive the positions on the coldblock(s)
for reagent_type in program_variables.reactiveWells.keys():
	for volume_tube in program_variables.reactiveWells[reagent_type]["Volumes"]:
		if volume_tube > 0:
			program_variables.reactiveWells[reagent_type]["Positions"].append(well_tube_eppendorf)
			well_tube_eppendorf.load_liquid(liquid = program_variables.reactiveWells[reagent_type]["Definition Liquid"], volume = math.ceil(volume_tube))
	
```

### 8. Distribute Water



```python
for tube in program_variables.reactiveWells["Water"]:
    volWaterPipR, posWaterPipR, volWaterPipL, posWaterPipL = vol_pipette_matcher (tube["Volume"],
																				  tube["Wells to distribute With Tube"],
																				  program_variables.pipR,
																				  program_variables.pipL)
	
    if volWaterPipL:
        check_tip_and_pick(program_variables.pipL,
						   user_variables.APINameTipL,
						   program_variables.deckPositions,
						   protocol,
						   replace_tiprack = user_variables.replaceTiprack,
						   initial_tip = user_variables.startingTipPipL,
						   same_tiprack = program_variables.sameTipRack)
						
		program_variables.pipL.transfer(volume_well,
										position_tube,
										position,
										new_tip = "never",
										touch_tip = user_variables.touchTipTransferWater)
						
		program_variables.pipL.drop_tip()

    if volWaterPipR:
        check_tip_and_pick(program_variables.pipR,
						   user_variables.APINameTipR,
						   program_variables.deckPositions,
						   protocol,
						   replace_tiprack = user_variables.replaceTiprack,
						   initial_tip = user_variables.startingTipPipR,
						   same_tiprack = program_variables.sameTipRack)
						
		program_variables.pipR.transfer(volume_well,
										position_tube,
										position,
										new_tip = "never",
										touch_tip = user_variables.touchTipTransferWater)
						
		program_variables.pipR.drop_tip()
```

### 9. MoClo Mix Creation

Transfer to the final tubes,either in the reagents labware or the heater-shaker, all the different reagents to create the MoClo mix (ligase, buffer, restriction enzyme and serum)

```python
# Transfer Ligase
if program_variables.volLigaseFactor > 0:
	try:
		tube_to_tube_transfer(program_variables.volLigaseFactor,
							program_variables.reactiveWells["Ligase"]["Positions"],
							program_variables.reactiveWells["Ligase"]["Reactions Per Tube"],
							program_variables.mixWells["Positions"],
							program_variables.mixWells["Reactions Per Tube"][:],
							program_variables,
							user_variables,
							protocol,
							new_tip = new_tip_value)
	except NotSuitablePipette as e:
		raise Exception(f"""When transfering the Ligase to the mix tubes the error '{e}' was raised.
Possible ways to fix this error:
	- Try another combination of pipettes
	- If 'Presence Heater-Shaker' is set as True, try another labware in 'API Name Heater-Shaker Labware' or another 'Max Volume Per Mix Tube In Shaker'
	- If 'Presence Heater-Shaker' is set as False, try another 'API Name Labware Eppendorfs Reagents'""")
```

### 10. Mix and Distribute MoClo Mix

```python
if program_variables.volTotal > 0:
    optimal_pipette = give_me_optimal_pipette (program_variables.volTotal,
												   program_variables.pipR,
												   program_variables.pipL)
    
    # Go through all the tubes with a MoClo mix
    for index, tube in enumerate(program_variables.mixWells["Positions"]):
        # Mix the tube
        if user_variables.presenceHS == True:
            program_variables.hs_mods.set_and_wait_for_shake_speed(user_variables.rpm)
			protocol.delay(seconds = 15)
			program_variables.hs_mods.deactivate_shaker()
        else:
            mixing_eppendorf_15(tube, program_variables.mixWells["Volumes"][index], vol_mixing, optimal_pipette_mixing, protocol)
        
        # Distribute
        check_tip_and_pick (optimal_pipette,
							tiprack,
							program_variables.deckPositions,
							protocol,
							initial_tip = starting_tip,
							same_tiprack = program_variables.sameTipRack,
							replace_tiprack = user_variables.replaceTiprack)

        optimal_pipette.distribute(program_variables.volTotal,
								   tube,
								   positions_distribute,
								   new_tip = "never",
                                   disposal_volume = 0,
								   touch_tip = user_variables.touchTipDistributeMix)

		optimal_pipette.drop_tip()
```

### 11. Distribute acceptors DNA parts

Go through all the acceptor parts and distribute them to the final combinations that have them

```python
for source_plate in program_variables.samplePlates.values():
	for col in source_plate['Map Final Combinations Acceptor'].columns:
		for row in source_plate['Map Final Combinations Acceptor'].index:
			if isinstance(source_plate['Map Final Combinations Acceptor'].at[row, col], list):
				# Now we distribute to the final wells this scpecific acceptor taking in account the new_tip argument
				optimal_pipette_acceptor.distribute(user_variables.acceptorVolume,
													source_plate["Opentrons Place"].wells_by_name()[str(row)+str(col)],
													final_wells,
													new_tip = "never",
													disposal_volume = 0,
													touch_tip = user_variables.touchTipTransferSample)
```

### 12. Distribute module DNA parts

Go through all the module parts and distribute them to the final combinations that have them

```python
for source_plate in program_variables.samplePlates.values():
	for col in source_plate['Map Final Combinations Module'].columns:
		for row in source_plate['Map Final Combinations Module'].index:
			if isinstance(source_plate['Map Final Combinations Module'].at[row, col], list):
				# Now we distribute to the final wells this scpecific acceptor taking in account the new_tip argument
				optimal_pipette_acceptor.distribute(user_variables.acceptorVolume,
													source_plate["Opentrons Place"].wells_by_name()[str(row)+str(col)],
													final_wells,
													new_tip = "never",
													disposal_volume = 0,
													touch_tip = user_variables.touchTipTransferSample)
```

### 13. Temperature Profile

In this section, in case the thermocycler is set as True, a temperature profile in the thermocycler is performed given the variables established in
user_variables and the module thermocycler in program_variables

```python
if user_variables.presenceTermo:
    run_program_thermocycler (program_variables.tc_mod,
							  user_variables.temperatureProfile,
							  user_variables.temperatureLid,
							  user_variables.finalVolume,
                              protocol,
							  final_lid_state = user_variables.finalStateLid,
							  final_block_state = user_variables.finalTemperatureBlock)
```

## Error Handling

The protocol includes comprehensive error handling mechanisms to ensure the robustness of the procedure.

Within others, the following checks are performed:

1. **Minimum Variables Check**: Ensures that essential variables such as `numberSourcePlates` and `APINameFinalPlate` are not empty and meet basic requirements.
2. **Pipette Variables Check**: Verifies that necessary pipette-related variables are correctly set, including `replaceTiprack`, `APINamePipR`, and `startingTipPipR`.
3. **Sample and Plate Variables Check**: Ensures the consistency and validity of variables related to samples per plate, such as the existence of the maps, their dimensions, all the parts that are being used in combinations located in the maps,e tc.
4. **Labware Existence Check**: Confirms that specified labware definitions exist within the Opentrons labware context.
5. **Volume and Mixing Checks**: Validates that volumes for samples and different reagents are coherent such as not being individually larger than the final volume.
6. **Consistency Checks**: Verifies that there are no contradictory settings, such as if having the thermocycler as True needing more than 1 final plate would raise an error