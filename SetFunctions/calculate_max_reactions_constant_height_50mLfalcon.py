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