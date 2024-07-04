def conversor_well_position_sorter (wells, position, volumes = None, sort = False, ordering = "ascending"):
	"""
	Function that will take a list of wells or an instance of a well and will return the position provided
	of that or those wells.
	In case the sort argument is set as True, the list of wells will be sorted in function to the volumes list and
	be returned sorted by volume in a descending or ascending way, depending on the value given in ordering

	Only 3 type of positions will be provided, either the top position, the center or the original one if position is set
	as bottom
	"""

	# We do the checks for the arguments
	if position not in ["top", "bottom", "center"]:
		raise Exception("The function 'conversor_well_position_sorter' only accepts 3 values for the position argument: bottom, center or top")
	
	if sort not in [True, False]:
		raise Exception("The function 'conversor_well_position_sorter' only accepts 2 values for the optional sort argument: True or False. By default the value is False")
	
	if ordering not in ["ascending", "descending"]:
		raise Exception("The function 'conversor_well_position_sorter' only accepts 2 values for the optional ordering argument: ascending or descending.\nBy default the value is ascending.")

	if sort and not isinstance(volumes, list):
		raise Exception("If sort set as True in 'conversor_well_position_sorter' the argument volumes need to be provided and needs to be a list with the same dimension as the list provided in wells")
	elif sort == False:
		pass
	else:
		if not isinstance(wells, list):
			raise Exception("If sort set as True in 'conversor_well_position_sorter' the argument wells needs to be a list with the same dimension as the list provided in volumes")
		if len(wells) != len(volumes):
			raise Exception("If sort set as True in 'conversor_well_position_sorter' the list provided in argument wells needs to be the same length as the list provided in volumes")

	# First, lets sort the volumes
	if sort:
		dict_wells_volumes = dict(zip(wells, volumes))
		dict_wells_volumes_sorted = dict(sorted(dict_wells_volumes.items(), key = lambda x:x[1]))
		volumes = list(dict_wells_volumes_sorted.values())
		wells = list(dict_wells_volumes_sorted.keys())

	# Now we just establish the positions
	if isinstance(wells, list):
		positions = []
		for well in wells:
			if position == "top":
				positions.append(well.top())
			elif position == "bottom":
				positions.append(well)
			else:
				positions.append(well.center())
	else:
		if position == "top":
			return wells.top()
		elif position == "bottom":
			return wells
		else:
			return wells.center()

	return (positions, volumes)
