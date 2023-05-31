#!/usr/local/bin/python
# -*- coding: latin-1 -*-
"""
----------------------------------------------------------------------------
TraitEncours: Classe afficher un motif de traitement en cours (sablier en TXT).
----------------------------------------------------------------------------

version 0.03 du 24/05/2008

Auteur:
- Laurent VILLEMIN (LV) - Laurent.villemin(a)laposte.net

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
# 04/04/2008 v0.01 LV : - 1�re version
# 05/04/2008 v0.02 LV : Ajout de l'affichage en mode clignotant
# 24/05/2008 v0.03 LV : Ajout d'une tronquature du message si demand�e
import time,sys

class TraitEnCours:
    """
        Module permettant un affichage d'un motif cyclique
        ou version texte du sablier graphique
        Affichages disponibles
            un seul caract�re d'une chaine affich� en boucle
            une chaine en d�filement Droite Gauche
            une chaine en d�filement Gauche Droite
            une chaine en clignotement
            ...
    """
# Variables internes
# __chaine : chaine contenant le motif affich�
# __mod : longueur de la chaine, utilis� pour la rotation D/G
# __temps : date du dernier affichage (optimise l'affichage au strict n�cessaire)

    def __init__(self):
        """
        Initialisation du motif par d�faut
        """
        self.__chaine='/-\|'
        self.__mod=len(self.__chaine)
        self.__temps=time.time()

    def NewChaine(self, newchaine, LgMax=79, truncate=False):
        """
        Affectation d'un nouveau motif
        Controle du param�tre LgMax
        """

        lg=len(newchaine)
        if truncate==True and lg > LgMax:
            # Chaine trop longue � couper en 2 + insertion de "..." au milieu
            l1 = (LgMax - 3) / 2
            l2 = LgMax - l1 - 3
            self.__chaine = newchaine[0:l1] + "..." + newchaine[lg-l2:lg]
        else:
            self.__chaine=newchaine
        self.__mod=len(self.__chaine)

    def StartIte(self,val=None):
        """
        D�marrage du compteur d'iteration
        """
        if val==None:
            self.__ite=0
        else:
            self.__ite=val

    def __IncrementIte(self):
        """
        Increment du compteur
        """
        self.__ite+=1
        return(self.__ite)

    def __ChDecalDG(self):
        """
        D�calage d'une chaine de droite � gauche
        """
        pos=0
        newchaine=''
        while pos <= self.__mod:
            newchaine+=self.__chaine[(pos-1)%self.__mod]
            pos+=1
        return(newchaine)

    def __ChDecalGD(self):
        """
        D�calage d'une chaine de gauche � droite
        """
        pos=0
        newchaine=''
        while pos <= self.__mod:
            newchaine+=self.__chaine[(pos+1)%self.__mod]
            pos+=1
        return(newchaine)

    def AffCar(self, *args):
        """
        Affichage caractere par caract�re
        """
        CurrentTime=time.time()
        if CurrentTime-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            print("%s\r" %self.__chaine[self.__ite%self.__mod], end=' ')
            sys.stdout.flush()
            self.__temps=CurrentTime

    def AffLigneDG(self, *args):
        """
        Affichage d'une ligne selon un mode "chenillard" de droite � gauche
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            self.__chaine=self.__ChDecalGD()
            print("%s\r" %self.__chaine, end=' ')
            sys.stdout.flush()
            self.__temps=CurrentTime


    def AffLigneGD(self, *args):
        """
        Affichage d'une ligne selon un mode "chenillard" de gauche � droite
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            self.__chaine=self.__ChDecalDG()
            print("%s\r" %self.__chaine, end=' ')
            sys.stdout.flush()
            self.__temps=CurrentTime

    def AffLigneBlink(self, *args):
        """
        Affichage d'une ligne en mode clignotant
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.4:
            self.__ite=self.__IncrementIte()
            if (self.__ite%2):
                print("%s\r" %self.__chaine, end=' ')
            else:
                print(" "*self.__mod + "\r", end=' ')
            sys.stdout.flush()
            self.__temps=CurrentTime
if __name__ == '__main__':
    print("Module d'affichage d'un motif indiquant un 'Traitement en cours'")
    temp=0
    a=TraitEnCours()
    a.StartIte()
    print("Working (caractere)...")
    while temp < 30:
        temp+=1
        a.AffCar()
        time.sleep(0.1)
    a.StartIte()
    a.NewChaine('>12345  ')
    print("Working (Ligne de Gauche a Droite)...")
    while temp < 60:
        temp+=1
        a.AffLigneGD()
        time.sleep(0.2)
    a.StartIte()
    a.NewChaine('12345<  ')
    print("Working (Ligne de Droite a Gauche)...")
    while temp < 90:
        temp+=1
        a.AffLigneDG()
        time.sleep(0.2)
    a.NewChaine('Blinking')
    print("Working (clignotement)...")
    while temp < 120:
        temp+=1
        a.AffLigneBlink()
        time.sleep(0.2)
    a.NewChaine('Blinking a message too long for my small terminal which can only display 60 rows. So I must truncate it in the middle', LgMax=59, truncate=True)
    print("Working (clignotement avec tronquature)")
    while temp < 150:
        temp+=1
        a.AffLigneBlink()
        time.sleep(0.2)

    ToQuit=input("Appuyer sur Entree pour quitter")



