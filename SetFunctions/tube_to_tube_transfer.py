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
			optimal_pipette = give_me_optimal_pipette (volume_transfer,
													   program_variables.pipR,
													   program_variables.pipL)

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
				check_tip_and_pick (optimal_pipette,
									tiprack, dict(zip(protocol.deck.keys(), protocol.deck.values())),
									protocol,
									replace_tiprack = user_variables.replaceTiprack,
									initial_tip = first_tip,
									same_tiprack = tipracks_same)

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
						check_tip_and_pick(pipette_use,
										   tiprack, dict(zip(protocol.deck.keys(), protocol.deck.values())),
										   protocol,
										   replace_tiprack = user_variables.replaceTiprack,
										   initial_tip = first_tip,
										   same_tiprack = tipracks_same)
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