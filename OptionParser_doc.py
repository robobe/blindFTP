#!/usr/bin/python
# -*- coding: latin-1 -*-
"""
----------------------------------------------------------------------------
OptionParser_doc: Classe pour g�rer les options de ligne de commande.
----------------------------------------------------------------------------

H�rite de OptionParser pour modifier son affichage.

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

from optparse import OptionParser


#------------------------------------------------------------------------------
# classe OptionParser_doc
#--------------------------

class OptionParser_doc (OptionParser):
	"""classe h�ritant d'optparse.OptionParser, qui ajoute l'affichage de
	la docstring du fichier avant l'aide normale d'OptionParser."""
	
	def print_help(self, file=None):
		"Affiche la docstring du fichier puis l'aide d'OptionParser."
		print (self.doc)
		OptionParser.print_help(self, file)

