#!/usr/local/bin/python
# -*- coding: latin-1 -*-
"""
----------------------------------------------------------------------------
Outstanding line: Class to display a current processing reason (hourglass in TXT).
----------------------------------------------------------------------------

"""

import time, sys


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
        self.__chaine = "/-\|"
        self.__mod = len(self.__chaine)
        self.__temps = time.time()

    def new_channel(self, newchaine, LgMax=79, truncate=False):
        """
        Affectation d'un nouveau motif
        Controle du param�tre LgMax
        """

        lg = len(newchaine)
        if truncate == True and lg > LgMax:
            # Chaine trop longue � couper en 2 + insertion de "..." au milieu
            l1 = (LgMax - 3) / 2
            l2 = LgMax - l1 - 3
            self.__chaine = newchaine[0:l1] + "..." + newchaine[lg - l2 : lg]
        else:
            self.__chaine = newchaine
        self.__mod = len(self.__chaine)

    def StartIte(self, val=None):
        """
        D�marrage du compteur d'iteration
        """
        if val == None:
            self.__ite = 0
        else:
            self.__ite = val

    def __IncrementIte(self):
        """
        Increment du compteur
        """
        self.__ite += 1
        return self.__ite

    def __ChDecalDG(self):
        """
        D�calage d'une chaine de droite � gauche
        """
        pos = 0
        newchaine = ""
        while pos <= self.__mod:
            newchaine += self.__chaine[(pos - 1) % self.__mod]
            pos += 1
        return newchaine

    def __ChDecalGD(self):
        """
        D�calage d'une chaine de gauche � droite
        """
        pos = 0
        newchaine = ""
        while pos <= self.__mod:
            newchaine += self.__chaine[(pos + 1) % self.__mod]
            pos += 1
        return newchaine

    def AffCar(self, *args):
        """
        Display character by character
        """
        CurrentTime = time.time()
        if CurrentTime - self.__temps > 0.2:
            self.__ite = self.__IncrementIte()
            print("%s\r" % self.__chaine[self.__ite % self.__mod], end=" ")
            sys.stdout.flush()
            self.__temps = CurrentTime

    def AffLigneDG(self, *args):
        """
        Affichage d'une ligne selon un mode "chenillard" de droite � gauche
        """
        CurrentTime = time.time()
        if time.time() - self.__temps > 0.2:
            self.__ite = self.__IncrementIte()
            self.__chaine = self.__ChDecalGD()
            print("%s\r" % self.__chaine, end=" ")
            sys.stdout.flush()
            self.__temps = CurrentTime

    def AffLigneGD(self, *args):
        """
        Affichage d'une ligne selon un mode "chenillard" de gauche � droite
        """
        CurrentTime = time.time()
        if time.time() - self.__temps > 0.2:
            self.__ite = self.__IncrementIte()
            self.__chaine = self.__ChDecalDG()
            print("%s\r" % self.__chaine, end=" ")
            sys.stdout.flush()
            self.__temps = CurrentTime

    def AffLigneBlink(self, *args):
        """
        Affichage d'une ligne en mode clignotant
        """
        CurrentTime = time.time()
        if time.time() - self.__temps > 0.4:
            self.__ite = self.__IncrementIte()
            if self.__ite % 2:
                print("%s\r" % self.__chaine, end=" ")
            else:
                print(" " * self.__mod + "\r", end=" ")
            sys.stdout.flush()
            self.__temps = CurrentTime


if __name__ == "__main__":
    print("Module d'affichage d'un motif indiquant un 'Traitement en cours'")
    temp = 0
    a = TraitEnCours()
    a.StartIte()
    print("Working (caractere)...")
    while temp < 30:
        temp += 1
        a.AffCar()
        time.sleep(0.1)
    a.StartIte()
    a.new_channel(">12345  ")
    print("Working (Ligne de Gauche a Droite)...")
    while temp < 60:
        temp += 1
        a.AffLigneGD()
        time.sleep(0.2)
    a.StartIte()
    a.new_channel("12345<  ")
    print("Working (Ligne de Droite a Gauche)...")
    while temp < 90:
        temp += 1
        a.AffLigneDG()
        time.sleep(0.2)
    a.new_channel("Blinking")
    print("Working (clignotement)...")
    while temp < 120:
        temp += 1
        a.AffLigneBlink()
        time.sleep(0.2)
    a.new_channel(
        "Blinking a message too long for my small terminal which can only display 60 rows. So I must truncate it in the middle",
        LgMax=59,
        truncate=True,
    )
    print("Working (clignotement avec tronquature)")
    while temp < 150:
        temp += 1
        a.AffLigneBlink()
        time.sleep(0.2)

    ToQuit = input("Appuyer sur Entree pour quitter")
