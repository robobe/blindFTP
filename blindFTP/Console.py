#!/usr/local/bin/python
# -*- coding: latin-1 -*-
"""
----------------------------------------------------------------------------
Console: pour simplifier l'affichage de cha�nes sur la console.
----------------------------------------------------------------------------

v0.02 du 05/04/2008

Copyright Philippe Lagadec 2005-2007
Auteur:
- Philippe Lagadec (PL) - philippe.lagadec(a)laposte.net

Ce logiciel est r�gi par la licence CeCILL soumise au droit fran�ais et
respectant les principes de diffusion des logiciels libres. Vous pouvez
utiliser, modifier et/ou redistribuer ce programme sous les conditions
de la licence CeCILL telle que diffus�e par le CEA, le CNRS et l'INRIA
sur le site "http://www.cecill.info".

En contrepartie de l'accessibilit� au code source et des droits de copie,
de modification et de redistribution accord�s par cette licence, il n'est
offert aux utilisateurs qu'une garantie limit�e.  Pour les m�mes raisons,
seule une responsabilit� restreinte p�se sur l'auteur du programme,  le
titulaire des droits patrimoniaux et les conc�dants successifs.

A cet �gard  l'attention de l'utilisateur est attir�e sur les risques
associ�s au chargement,  � l'utilisation,  � la modification et/ou au
d�veloppement et � la reproduction du logiciel par l'utilisateur �tant
donn� sa sp�cificit� de logiciel libre, qui peut le rendre complexe �
manipuler et qui le r�serve donc � des d�veloppeurs et des professionnels
avertis poss�dant  des  connaissances  informatiques approfondies.  Les
utilisateurs sont donc invit�s � charger  et  tester  l'ad�quation  du
logiciel � leurs besoins dans des conditions permettant d'assurer la
s�curit� de leurs syst�mes et ou de leurs donn�es et, plus g�n�ralement,
� l'utiliser et l'exploiter dans les m�mes conditions de s�curit�.

Le fait que vous puissiez acc�der � cet en-t�te signifie que vous avez
pris connaissance de la licence CeCILL, et que vous en avez accept� les
termes.
"""

#------------------------------------------------------------------------------
# HISTORIQUE:
# 01/08/2005 v0.01 PL: - 1�re version
# 03/08/2005 v0.02 PL: - ajout de print_console pour conversion automatique d'encodage
# 05/04/2008 v0.03 LV: - print_temp avec option Newline

#------------------------------------------------------------------------------

#=== IMPORTS ==================================================================

import sys

#=== CONSTANTES ===============================================================

# Nombre de caract�res temporaires affich�s par Print_temp sur la ligne actuelle:
global _car_temp
_car_temp = 0


#------------------------------------------------------------------------------
# print_console
#-------------------
def print_console (chaine, errors='replace', newline=True):
	"""
	Pour afficher correctement une cha�ne contenant des accents sur un
	terminal cmd de Windows. (conversion en page de code "cp850")
	Affichage simple sans conversion si on n'est pas sous Windows.

	errors: cf. aide du module codecs
	newline: indique s'il faut aller � la ligne
	"""
	if sys.platform == 'win32':
		if type(chaine) == 'str':
			# si c'est une chaine on suppose que c'est du latin_1
			# conversion en unicode:
			chaine = chaine.decode('latin_1', errors)
		chaine = str(chaine.encode('cp850', errors))
	if newline:
		print (chaine)
	else:
		print (chaine,)

#------------------------------------------------------------------------------
# Print
#-------------------
def Print (chaine):
	"""Affiche une cha�ne sur la console, et passe � la ligne suivante,
	comme print. Si Print_temp a �t� utilis� pr�c�demment, les �ventuels
	caract�res qui d�passent sont effac�s pour obtenir un affichage
	correct.
	"""
	global _car_temp
	if _car_temp > len(chaine):
		print (" "*_car_temp + "\r",)
	_car_temp = 0
	print_console(chaine)

#------------------------------------------------------------------------------
# Print_temp
#-------------------
def Print_temp (chaine, taille_max=79, NL=False):
	"""Affiche une cha�ne temporaire sur la console, sans passer � la ligne
	suivante, et en tronquant au milieu pour ne pas d�passer taille_max.
	Si Print_temp a �t� utilis� pr�c�demment, les �ventuels caract�res qui
	d�passent sont effac�s pour obtenir un affichage correct.
	"""
	global _car_temp
	lc = len(chaine)
	if lc > taille_max:
		# si la chaine est trop longue, on la coupe en 2 et on ajoute
		# "..." au milieu
		l1 = (taille_max - 3) / 2
		l2 = taille_max - l1 - 3
		chaine = chaine[0:l1] + "..." + chaine[lc-l2:lc]
		lc = len(chaine)
		if lc != taille_max:
			raise ValueError(msg="erreur dans Print_temp(): lc=%d" % lc)
	if _car_temp > lc:
		print (" "*_car_temp + "\r",)
	_car_temp = lc
	print_console (chaine + "\r", newline=NL)



#------------------------------------------------------------------------------
# MAIN
#-------------------
if __name__ == "__main__":
	pass
	# Print ("test de chaine longue: " + "a"*200)
	# Print_temp("chaine longue temporaire...")
	# Print_temp("chaine moins longue")
	# print ""
	# Print_temp("chaine longue temporaire...")
	# Print("suite")
	# Print_temp("chaine trop longue: "+"a"*100)
	# print ""
	# Print_temp("chaine accentu�e tr�s longue...")
	# Print_temp("chaine r�tr�cie.")
	# print ""


