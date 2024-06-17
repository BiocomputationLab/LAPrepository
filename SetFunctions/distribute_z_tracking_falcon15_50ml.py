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
					number_pos_distr = calculate_max_reactions_constant_height_15mLfalcon (pos_source,
																	                       vol_source,
																						   len(pos_final[start_position:]),
																						   vol_distribute_well)
				else: # In this case the vol of the falcon is 50000 
					number_pos_distr = calculate_max_reactions_constant_height_50mLfalcon (pos_source,
																			               vol_source,
																						   len(pos_final[start_position:]),
																						   vol_distribute_well)
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
						number_pos_distr = calculate_max_reactions_constant_height_15mLfalcon (pos_source,
																			                   vol_source,
																							   pos_max,
																							   vol_distribute_well)
					else:
						number_pos_distr = calculate_max_reactions_constant_height_50mLfalcon (pos_source,
																			                   vol_source,
																							   pos_max,
																							   vol_distribute_well)

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
					pipette_used.distribute(vol_distribute_well,
							                find_safe_15mLfalcon_height(vol_source, pos_source),
											position_distribute,
											new_tip = "never",
											disposal_volume = 0,
											touch_tip = touch_tip)
				else:
					pipette_used.distribute(vol_distribute_well,
							                find_safe_50mLfalcon_height(vol_source, pos_source),
											position_distribute,
											new_tip = "never",
											disposal_volume = 0,
											touch_tip = touch_tip)

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
						number_react_transfer = calculate_max_reactions_constant_height_15mLfalcon (pos_source,
																				                    vol_source,
																									pos_max,
																									pipette_min_volume)
					else:
						number_react_transfer = calculate_max_reactions_constant_height_50mLfalcon (pos_source,
																				                    vol_source,
																									pos_max,
																									pipette_min_volume)
				else: # The new_tip is going to be never so we will not change the tips
					# We are goign to transfer the maximum volume possible
					if vol_max_falcon == 15000:
						number_react_transfer = calculate_max_reactions_constant_height_15mLfalcon (pos_source,
																				                    vol_source, 
																									max_movements_minvol_pipette,
																									pipette_min_volume)
					else:
						number_react_transfer = calculate_max_reactions_constant_height_50mLfalcon (pos_source,
																				                    vol_source,
																									max_movements_minvol_pipette,
																									pipette_min_volume)

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