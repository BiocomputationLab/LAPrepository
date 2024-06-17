def find_safe_50mLfalcon_height (vol_falcon, theory_position):
	"""
	This function will return the height in which the pipette should aspirate and or dispense the volume to not get wet while doing it
	
	It is manually measured, meaning that if you change the tubes you should test if this work or redo the heights

	This function takes 2 inputs, the tube position and the volume it has and will return the same position with the according height
	"""

	if vol_falcon < 5000 : # The values of comparing are volumes (in uL)
		final_position = theory_position.bottom(z=1) # It will go to the normal position that will go when it aspirates or dispense
	elif vol_falcon >= 5000 and vol_falcon < 12500:
		final_position = theory_position.bottom(z = 12)
	elif vol_falcon >= 12500 and vol_falcon < 22500:
		final_position = theory_position.bottom(z = 28)
	elif vol_falcon >= 22500 and vol_falcon < 32500:
		final_position = theory_position.bottom(z = 45)
	elif vol_falcon >= 32500 and vol_falcon < 42500:
		final_position = theory_position.bottom(z = 62)
	elif vol_falcon >= 42500:
		final_position = theory_position.bottom(z = 81)
	return final_position