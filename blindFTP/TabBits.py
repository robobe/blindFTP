#!/usr/bin/python
# -*- coding: latin-1 -*-
"""
----------------------------------------------------------------------------
TabBits: Classe pour manipuler un tableau de bits de grande taille.
----------------------------------------------------------------------------

version 0.03 du 08/07/2005


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

# HISTORIQUE:
# 03/07/2005 v0.01: - 1�re version
# 06/07/2005 v0.02: - remplacement du buffer chaine par un objet array
# 08/07/2005 v0.03: - ajout du comptage des bits � 1

# A FAIRE:
# + v�rifier si index hors tableau (<0 ou >N-1)
# - import de cha�ne ou fichier ou liste de bool�ens
# - export vers cha�ne ou fichier
# - interface tableau Python
# - taille dynamique

import array

#------------------------------------------------------------------------------
# classe TabBits
#--------------------------

class TabBits:
	"""Classe pour manipuler un tableau de bits de grande taille."""
	
	def __init__ (self, taille, buffer=None, readFile=None):
		"""constructeur de TabBits.
		
		taille: nombre de bits du tableau.
		buffer: chaine utilis�e pour remplir le tableau (optionnel).
		readFile: fichier utilis� pour remplir le tableau (optionnel).
		"""
		self._taille = taille
		self.nb_true = 0    # nombre de bits � 1, 0 par d�faut
		if buffer == None and readFile == None:
			# on calcule le nombre d'octets n�cessaires pour le buffer
			taille_buffer = (taille+7)/8
			# on cr�e alors un buffer de cette taille, initialis� � z�ro:
			# self._buffer = chr(0)*taille_buffer
			# on cr�e un objet array de Bytes
			self._buffer = array.array('B')
			# on ajoute N �l�ments nuls
			# (� optimiser: boucle pour �viter de cr�er une liste ?)
			self._buffer.fromlist([0]*taille_buffer)
		else:
			# pas encore �crit...
			raise NotImplementedError

	def get (self, indexBit):
		"""Pour lire un bit dans le tableau. Retourne un bool�en."""
		# index de l'octet correspondant dans le buffer et d�calage du bit dans l'octet
		indexOctet, decalage =  divmod (indexBit, 8)
		octet = self._buffer[indexOctet]
		masque = 1 << decalage
		bit = octet & masque
		# on retourne un bool�en
		return bool(bit)

	def set (self, indexBit, valeur):
		"""Pour �crire un bit dans le tableau."""
		# on s'assure que valeur est un bool�en
		valeur = bool(valeur)
		# index de l'octet correspondant dans le buffer et d�calage du bit dans l'octet
		indexOctet, decalage =  divmod (indexBit, 8)
		octet = self._buffer[indexOctet]
		masque = 1 << decalage
		ancienne_valeur = bool(octet & masque)
		if valeur == True and ancienne_valeur == False:
			# on doit positionner le bit � 1
			octet = octet | masque
			self._buffer[indexOctet] = octet
			self.nb_true += 1
		elif valeur == False and ancienne_valeur == True:
			# on doit positionner le bit � 0
			masque = 0xFF ^ masque
			octet = octet & masque
			self._buffer[indexOctet] = octet
			self.nb_true -= 1

	def __str__ (self):
		"""pour convertir le TabBits en cha�ne contenant des 0 et des 1."""
		chaine = ""
		for i in range(0, self._taille):
			bit = self.get(i)
			if bit:
				chaine += "1"
			else:
				chaine += "0"
		return chaine
		
if __name__ == "__main__":
	# quelques tests si le module est lanc� directement
	N=100
	tb = TabBits(N)
	print (str(tb))
	tb.set(2, True)
	tb.set(7, True)
	tb.set(N-1, True)
	print (str(tb))
	print ("tb[0] = %d" % tb.get(0))
	print ("tb[2] = %d" % tb.get(2))
	print ("tb[%d] = %d" % (N-1, tb.get(N-1)))
	print ("taille bits = %d" % tb._taille)
	print ("taille buffer = %d" % len(tb._buffer))
			
		
