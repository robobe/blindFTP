#!/usr/local/bin/python
# -*- coding: latin-1 -*-
"""
----------------------------------------------------------------------------
BlindFTP v 0.37 - Unidirectional File Transfer Protocol
----------------------------------------------------------------------------
"""

# === IMPORTS ==================================================================

import sys, socket, struct, time, os, os.path, tempfile, logging, traceback
import binascii
import threading
import configparser

# path.py module import
try:
    from path import path
except:
    raise ImportError()

import xml.etree.ElementTree as ET


# XFL - Python module to create and compare file lists in XML
try:
    import xfl
except:
    raise ImportError(msg="the XFL module is not installed")

# plx - portability layer extension
try:
    from plx import str_lat1, print_console
except:
    raise ImportError(msg="the plx module is not installed:")

# internal modules
from optparse import OptionParser
import TabBits, Console
import TraitEncours


# === CONSTANTES ===============================================================

NOM_SCRIPT = os.path.basename(__file__)  # script filename

ConfigFile = "bftp.ini"
RunningFile = "bftp_run.ini"

# Network Packet Max size
if sys.platform == "darwin":
    # With MacOSX exception 'Message too long' if size is too long
    PACKAGE_SIZE = 1500
else:
    PACKAGE_SIZE = 65500

MODE_DEBUG = True  # check if debug() messages are displayed

RACINE_TEMP = "temp"  # Tempfile root

MAX_FILE_NAME = 1024  # Max length for the filename field

HB_DELAY = 10  # Default time between two Heartbeat

# en synchro stricte dur�e de r�tention
# un fichier disparu/effac� sur le guichet bas est effac� cot� haut apr�s ce d�lai
OFFLINEDELAY = 86400 * 7  # 86400 vaut 1 jour

IgnoreExtensions = (".part", ".tmp", ".ut", ".dlm")  #  Extensions of temp files which are never send (temp files)

# Correction du bug sur taille des fichiers de plus de 4.5 Go
#      Modification de la structure (taille + offset de Int(I) en Long Long (Q))

# Header fields of BFTP data (format v4) :
# check help of module struct for the codes
# - type de paquet: uchar=B
# - longueur du nom de fichier (+chemin): uchar=B
# - longueur des donn�es du fichier dans le paquet: uint16=H
# - offset, position des donn�es dans le fichier: Long Long =Q
# - num�ro de session: uint32=I
# - n� de paquet dans la session: uint32=I
# - n� de paquet du fichier: uint32=I
# - nombre de paquets pour le fichier: uint32=I
# - longueur du fichier (en octets): Long Long=Q
# - date du fichier (en secondes depuis epoch): uint32=I
# - CRC32 du fichier: int32=i (sign�)
# (suivi du nom du fichier, puis des donn�es)
FORMAT_ENTETE = "BBHQIIIIQIi"
# Correction bug 557 : taille du format diff�re selon les OS
SIZE_ENTETE = struct.calcsize(FORMAT_ENTETE)
# size : Win32 (48) ; Linux (44) ; MacOSX PPC (44)

# Types of packages:
PACKAGE_FILE = 0  # File
PACKAGE_DIRECTORY = 1  # Directory (not yet use)
PACKAGE_HEARTBEAT = 10  # HeartBeat
PACKAGE_DELETEFile = 16  # File Delete

# Complement d'attributs � XFL
ATTR_CRC = "crc"  # File CRC
ATTR_NBSEND = "NbSend"  # Number of send
ATTR_LASTVIEW = "LastView"  # Last View Date
ATTR_LASTSEND = "LastSend"  # Last Send Date

# === Valeurs � traiter au sein du fichier .ini in fine ========================
MinFileRedundancy = 5

# === VARIABLES GLOBALES =======================================================

# pour stocker les options (cf. analyse_options)
# options parameters
global options
options = None

# dictionnaire des fichiers en cours de r�ception
# receiving files dictionnary
global files
files = {}

# pour mesurer les stats de reception:

stats = None


# ------------------------------------------------------------------------------
# str_ajuste : Adjust string to a dedicated length adding space or cutting string
# -------------------
def str_ajuste(chain, longueur=79):
    """ajuste la chaine pour qu'elle fasse exactement la longueur indiqu�e,
    en coupant ou en remplissant avec des espaces."""
    l = len(chain)
    if l > longueur:
        return chain[0:longueur]
    else:
        return chain + " " * (longueur - l)


# ------------------------------------------------------------------------------
# DEBUG : Display debug messages if MODE_DEBUG is True
# -------------------


def debug(texte):
    "pour afficher un texte si MODE_DEBUG = True"

    if MODE_DEBUG:
        print_console("DEBUG:" + texte)


# ------------------------------------------------------------------------------
# EXIT_AIDE : Display Help in case of error
# -------------------


def exit_aide():
    "Affiche un texte d'aide en cas d'erreur."

    # on affiche la docstring (en d�but de ce fichier) qui contient l'aide.
    print(__doc__)
    sys.exit(1)


# ------------------------------------------------------------------------------
# MTIME2STR : Convert date as a string
# -------------------


def mtime2str(date_fichier):
    "Convertit une date de fichier en chaine pour l'affichage."
    localtime = time.localtime(date_fichier)
    return time.strftime("%d/%m/%Y %H:%M:%S", localtime)


# ------------------------------------------------------------------------------
# classe STATS
# -------------------


class Stats:
    """classe permettant de calculer des statistiques sur les transferts."""

    def __init__(self):
        """Constructeur d'objet Stats."""
        self.num_session = -1
        self.expected_packet_num = 0
        self.nb_packets_lost = 0

    def add_package(self, pack):
        """pour mettre � jour les stats en fonction du paquet."""
        # on v�rifie si on est toujours dans la m�me session, sinon RAZ
        if pack.num_session != self.num_session:
            self.num_session = pack.num_session
            self.expected_packet_num = 0
            self.nb_packets_lost = 0
        # a-t-on perdu des paquets ?
        if pack.num_paquet_session != self.expected_packet_num:
            self.nb_packets_lost += pack.num_paquet_session - self.expected_packet_num
        self.expected_packet_num = pack.num_paquet_session + 1

    def loss_rate(self):
        """calcule le taux de lost packets, en pourcentage"""
        # num_paquet_attendu correspond au nombre de paquets envoy�s de la session
        if self.expected_packet_num > 0:
            taux = (100 * self.nb_packets_lost) / self.expected_packet_num
        else:
            taux = 0
        return taux

    def print_stats(self):
        """affiche les stats"""
        print(
            "loss rate: %d%%, lost packets: %d/%d" % (self.loss_rate(), self.nb_packets_lost, self.expected_packet_num)
        )


# ------------------------------------------------------------------------------
# CHEMIN_INTERDIT
# -------------------


def chemin_interdit(chemin):
    """V�rifie si le chemin de fichier demand� est interdit, par exemple
    s'il s'agit d'un chemin absolu, s'il contient "..", etc..."""
    # si chemin n'est pas une chaine on le convertit:
    #   if not isinstance(chemin, str):
    #       chemin = str(chemin)
    # est-ce un chemin absolu pour Windows avec une lettre de lecteur ?
    if len(chemin) >= 2 and chemin[0].isalpha() and chemin[1] == ":":
        return True
    # est-ce un chemin absolu qui commence par "/" ou "\" ?
    if chemin.startswith("/") or chemin.startswith("\\"):
        return True
    # est-ce qu'il contient ".." ?
    if ".." in chemin:
        return True
    if "*" in chemin:
        return True
    if "?" in chemin:
        return True
    # A AJOUTER: v�rifier si codage unicode, ou autre ??
    # Sinon c'est OK, le chemin est valide:
    return False


# ------------------------------------------------------------------------------
# classe FICHIER
# -------------------


class Sender:
    """classe repr�sentant un fichier en cours de r�ception."""

    def __init__(self, paquet):
        """Constructeur d'objet Fichier.

        paquet: objet paquet contenant les infos du fichier."""

        self.nom_fichier = paquet.nom_fichier
        self.date_fichier = paquet.date_fichier
        self.taille_fichier = paquet.taille_fichier
        self.nb_paquets = paquet.nb_paquets
        # chemin du fichier destination
        self.fichier_dest = CHEMIN_DEST / self.nom_fichier
        debug('fichier_dest = "%s"' % self.fichier_dest)
        # on cr�e le fichier temporaire (objet file):
        self.fichier_temp = tempfile.NamedTemporaryFile(prefix="BFTP_")
        debug('fichier_temp = "%s"' % self.fichier_temp.name)
        self.paquets_recus = TabBits.TabBits(self.nb_paquets)
        # print 'Reception du fichier "%s"...' % self.nom_fichier
        self.est_termine = False  # flag indiquant une r�ception compl�te
        self.crc32 = paquet.crc32  # CRC32 du fichier
        # on ne doit pas traiter le paquet automatiquement, sinon il peut
        # y avoir des probl�mes d'ordre des actions
        # self.traiter_paquet(paquet)

    def annuler_reception(self):
        "pour annuler la r�ception d'un fichier en cours."
        # on ferme et on supprime le fichier temporaire
        # seulement s'il est effectivement ouvert
        # (sinon � l'initialisation c'est un entier)
        if isinstance(self.fichier_temp, file):
            if not self.fichier_temp.closed:
                self.fichier_temp.close()
        # d'apr�s la doc de tempfile, le fichier est automatiquement supprim�
        # os.remove(self.nom_temp)
        debug("Reception de fichier annulee.")

    def recopier_destination(self):
        "pour recopier le fichier � destination une fois qu'il est termin�."
        print("OK, fichier termine.")
        # cr�er le chemin destination si besoin avec makedirs
        chemin_dest = self.fichier_dest.dirname()
        if not os.path.exists(chemin_dest):
            chemin_dest.makedirs()
        elif not os.path.isdir(chemin_dest):
            chemin_dest.remove()
            chemin_dest.mkdir()
        # recopier le fichier temporaire au bon endroit
        debug("Recopie de %s vers %s..." % (self.fichier_temp.name, self.fichier_dest))
        # move(self.nom_temp, self.fichier_dest)
        # on revient au d�but
        self.fichier_temp.seek(0)
        f_dest = file(self.fichier_dest, "wb")
        buffer = self.fichier_temp.read(16384)
        # on d�marre le calcul de CRC32:
        crc32 = binascii.crc32(buffer)
        while len(buffer) != 0:
            f_dest.write(buffer)
            buffer = self.fichier_temp.read(16384)
            # poursuite du calcul de CRC32:
            crc32 = binascii.crc32(buffer, crc32)
        f_dest.close()
        # v�rifier si la taille obtenue est correcte
        if self.fichier_dest.getsize() != self.taille_fichier:
            debug("taille_fichier = %d, taille obtenue = %d" % (self.taille_fichier, self.fichier_dest.getsize()))
            logging.error('Taille du fichier incorrecte: "%s"' % self.nom_fichier)
            raise IOError("taille du fichier incorrecte.")
        # v�rifier si le checksum CRC32 est correct
        if self.crc32 != crc32:
            debug("CRC32 fichier = %X, CRC32 attendu = %X" % (crc32, self.crc32))
            logging.error('Controle d\'integrite incorrect: "%s"' % self.nom_fichier)
            raise IOError("controle d'integrite incorrect.")
        # mettre � jour la date de modif: tuple (atime,mtime)
        self.fichier_dest.utime((self.date_fichier, self.date_fichier))
        # fermer le fichier temporaire
        self.fichier_temp.close()
        # d'apr�s la doc de tempfile, le fichier est automatiquement supprim�
        self.fichier_en_cours = False
        # Affichage de fin de traitement
        debug("Fichier termine.")
        logging.info('Fichier "%s" recu en entier, recopie a destination.' % self.nom_fichier)
        # dans ce cas on retire le fichier du dictionnaire
        self.est_termine = True
        del files[self.nom_fichier]

    def traiter_paquet(self, paquet):
        "pour traiter un paquet contenant un morceau du fichier."
        # on v�rifie si le paquet n'a pas d�j� �t� re�u
        if not self.paquets_recus.get(paquet.num_paquet):
            # c'est un nouveau paquet: il faut l'�crire dans le fichier temporaire
            # on calcule l'offset dans le fichier, en consid�rant que chaque
            # paquet contient la m�me longueur de donn�es:
            # offset = paquet.num_paquet * paquet.taille_donnees
            # debug("offset = %d" % offset)
            self.fichier_temp.seek(paquet.offset)
            # note: si on d�place le curseur apr�s la fin r�elle du fichier,
            # celui-ci est compl�t� d'octets nuls, ce qui nous arrange bien :-).
            self.fichier_temp.write(paquet.donnees)
            debug("offset apres = %d" % self.fichier_temp.tell())
            self.paquets_recus.set(paquet.num_paquet, True)
            pourcent = 100 * (self.paquets_recus.nb_true) / self.nb_paquets
            # affichage du pourcentage: la virgule �vite un retour chariot
            print("%d%%\r" % pourcent)
            # pour forcer la mise � jour de l'affichage
            sys.stdout.flush()
            # si le fichier est termin�, on le recopie � destination:
            if self.paquets_recus.nb_true == self.nb_paquets:
                # on va � la ligne
                # print ""
                # Mise en thread de la recopie afin de liberer de la ressource pour la r�ception
                recopie = threading.Thread(None, self.recopier_destination, None, ())
                recopie.start()
                # ...et on suppose qu'il n'y a plus d'autres r�f�rences:
                # le garbage collector devrait le supprimer de la m�moire.


# ------------------------------------------------------------------------------
# classe PAQUET
# -------------------


class Pack:
    """classe repr�sentant un paquet BFTP, permettant la construction et le
    d�codage du paquet."""

    def __init__(self):
        "Constructeur d'objet Paquet BFTP."
        # on initialise les infos contenues dans l'ent�te du paquet
        self.type_paquet = PACKAGE_FILE
        self.longueur_nom = 0
        self.taille_donnees = 0
        self.offset = 0
        self.num_paquet = 0
        self.nom_fichier = ""
        self.nb_paquets = 0
        self.taille_fichier = 0
        self.date_fichier = 0
        self.donnees = ""
        self.fichier_en_cours = ""
        self.num_session = -1
        self.num_paquet_session = -1

    def decoder(self, paquet):
        "Pour d�coder un paquet BFTP."
        # on d�code d'abord l'ent�te (cf. d�but de ce fichier):
        entete = paquet[0:SIZE_ENTETE]
        (
            self.type_paquet,
            self.longueur_nom,
            self.taille_donnees,
            self.offset,
            self.num_session,
            self.num_paquet_session,
            self.num_paquet,
            self.nb_paquets,
            self.taille_fichier,
            self.date_fichier,
            self.crc32,
        ) = struct.unpack(FORMAT_ENTETE, entete)
        debug("type_paquet        = %d" % self.type_paquet)
        debug("longueur_nom       = %d" % self.longueur_nom)
        debug("taille_donnees     = %d" % self.taille_donnees)
        debug("offset             = %d" % self.offset)
        debug("num_session        = %d" % self.num_session)
        debug("num_paquet_session = %d" % self.num_paquet_session)
        debug("num_paquet         = %d" % self.num_paquet)
        debug("nb_paquets         = %d" % self.nb_paquets)
        debug("taille_fichier     = %d" % self.taille_fichier)
        debug("date_fichier       = %s" % mtime2str(self.date_fichier))
        debug("CRC32              = %08X" % self.crc32)
        if self.type_paquet not in [PACKAGE_FILE, PACKAGE_HEARTBEAT, PACKAGE_DELETEFile]:
            raise ValueError(msg="type de paquet incorrect")
        if self.type_paquet == PACKAGE_FILE:
            if self.longueur_nom > MAX_FILE_NAME:
                raise ValueError(msg="nom de fichier trop long")
            if self.offset + self.taille_donnees > self.taille_fichier:
                raise ValueError(msg="offset ou taille des donnees incorrects")
            self.nom_fichier = paquet[SIZE_ENTETE : SIZE_ENTETE + self.longueur_nom]
            # conversion en utf-8 pour �viter probl�mes d�s aux accents
            # A VOIR: seulement sous Windows ?? (sous Mac �a pose probl�me...)
            if sys.platform == "win32":
                self.nom_fichier = self.nom_fichier.decode("utf_8", "strict")
            ##debug("nom_fichier    = %s" % self.nom_fichier)
            if chemin_interdit(self.nom_fichier):
                logging.error("nom de fichier ou de chemin incorrect: %s" % self.nom_fichier)
                raise ValueError(msg="nom de fichier ou de chemin incorrect")
            taille_entete_complete = SIZE_ENTETE + self.longueur_nom
            if self.taille_donnees != len(paquet) - taille_entete_complete:
                debug("taille_paquet = %d" % len(paquet))
                debug("taille_entete_complete = %d" % taille_entete_complete)
                raise ValueError(msg="taille de donnees incorrecte")
            self.donnees = paquet[taille_entete_complete : len(paquet)]
            # on mesure les stats, et on les affiche tous les 100 paquets
            stats.add_package(self)
            # if self.num_paquet_session % 100 == 0:
            # stats.print_stats()
            # est-ce que le fichier est en cours de r�ception ?
            if self.nom_fichier in files:
                debug("Fichier en cours de reception")
                f = files[self.nom_fichier]
                # on v�rifie si le fichier n'a pas chang�:
                if (
                    f.date_fichier != self.date_fichier
                    or f.taille_fichier != self.taille_fichier
                    or f.crc32 != self.crc32
                ):
                    # on commence par annuler la r�ception en cours:
                    f.annuler_reception()
                    del files[self.nom_fichier]
                    # puis on recr�e un nouvel objet fichier d'apr�s les infos du paquet:
                    self.nouveau_fichier()
                else:
                    if self.fichier_en_cours != self.nom_fichier:
                        # on change de fichier
                        msg = 'Suite de "%s"...' % self.nom_fichier
                        heure = time.strftime("%d/%m %H:%M ")
                        # V�rifier si un NL est n�cessaire ou non
                        Console.Print_temp(msg, NL=True)
                        logging.info(msg)
                        self.fichier_en_cours = self.nom_fichier
                    f.traiter_paquet(self)
            else:
                # est-ce que le fichier existe d�j� sur le disque ?
                fichier_dest = CHEMIN_DEST / self.nom_fichier
                ##debug('fichier_dest = "%s"' % fichier_dest)
                # si la date et la taille du fichier n'ont pas chang�,
                # inutile de recr�er le fichier, on l'ignore:
                if (
                    fichier_dest.exists()
                    and fichier_dest.getsize() == self.taille_fichier
                    and fichier_dest.getmtime() == self.date_fichier
                ):
                    # debug("Le fichier n'a pas change, on l'ignore.")
                    msg = "Fichier deja recu: %s" % self.nom_fichier
                    # msg = str_ajuste(msg)+'\r'
                    # print_oem(msg),
                    Console.Print_temp(msg)
                    sys.stdout.flush()
                else:
                    # sinon on cr�e un nouvel objet fichier d'apr�s les infos du paquet:
                    self.nouveau_fichier()
        if self.type_paquet == PACKAGE_HEARTBEAT:
            debug("Reception HEARTBEAT")
            HeartBeat.check_heartbeat(hb_reciver, self.num_session, self.num_paquet_session, self.num_paquet)
        if self.type_paquet == PACKAGE_DELETEFile:
            debug("Reception DeleteFile notification")
            self.nom_fichier = paquet[SIZE_ENTETE : SIZE_ENTETE + self.longueur_nom]
            if sys.platform == "win32":
                self.nom_fichier = self.nom_fichier.decode("utf_8", "strict")
            fichier_dest = CHEMIN_DEST / self.nom_fichier
            # Test pour bloquer en pr�sence de caracteres joker ou autres
            if chemin_interdit(self.nom_fichier):
                msg = 'Notification pour effacement suspecte "%s"...' % self.nom_fichier
                Console.Print_temp(msg, NL=True)
                logging.error(msg)
            else:
                msg = 'Effacement de "%s"...' % self.nom_fichier
                if fichier_dest.isfile():
                    try:
                        os.remove(fichier_dest)
                    except OSError:
                        msg = 'Echec effacement de "%s"...' % self.nom_fichier
                        logging.warn(msg)
                    Console.Print_temp(msg, NL=True)
                    # log � supprimer apr�s qualif.
                    logging.info(msg)
                if fichier_dest.isdir():
                    # TODO Supression de dossier vide � coder cot� bas (�mission)
                    logging.info("suppression de dossier")
                    try:
                        os.rmdir(fichier_dest)
                    except OSError:
                        msg = 'Echec de effacement de "%s"...' % self.nom_fichier
                        Console.Print_temp(msg, NL=True)
                        logging.warn(msg)

    def nouveau_fichier(self):
        "pour d�buter la r�ception d'un nouveau fichier."
        msg = 'Reception de "%s"...' % self.nom_fichier
        heure = time.strftime("%d/%m %H:%M ")
        # msg = str_ajuste(msg)+'\r'
        # print_oem(heure + msg)
        Console.Print_temp(msg, NL=True)
        logging.info(msg)
        self.fichier_en_cours = self.nom_fichier
        debug("Nouveau fichier ou fichier mis a jour")
        # on cr�e un nouvel objet fichier d'apr�s les infos du paquet:
        nouveau_fichier = Sender(self)
        files[self.nom_fichier] = nouveau_fichier
        nouveau_fichier.traiter_paquet(self)

    def construire(self):
        "pour construire un paquet BFTP � partir des param�tres. (non impl�ment�)"
        raise NotImplementedError


# ------------------------------------------------------------------------------
# HeartBeat - d�pendant de la classe de paquet
# ---------------
class HeartBeat:
    """Generate and check HeartBeat BFTP packet

    A session is a heartbeat sequence.
    A heartbeat is a simple packet with a timestamp (Session Id + sequence
    number) to identify if the link (physical and logical) is up or down

    The session Id will identify a restart
    The sequence number will identify lost paquet

    Because time synchronisation betwen emission/reception computer isn't garantee,
    timestamp can't be check in absolute.
    """

    # TODO :
    # Add HB from reception to emission in broadcast to detect bi-directional link

    def __init__(self):
        # Variables locales
        self.hb_delay = HB_DELAY
        self.hb_numsession = 0
        self.hb_packetnum = 0
        self.hb_timeout = time.time() + 1.25 * (self.hb_delay)

    def newsession(self):
        """initiate values for a new session"""
        self.hb_numsession = int(time.time())
        self.hb_packetnum = 0
        return (self.hb_numsession, self.hb_packetnum)

    def incsession(self):
        """increment values in a existing session"""
        self.hb_packetnum += 1
        self.hb_timeout = time.time() + (self.hb_delay)
        return (self.hb_packetnum, self.hb_timeout)

    def print_heartbeat(self):
        """Print internal values of heartbeat"""
        print("----- Current HeartBeart -----")
        print("Session ID      : %d " % self.hb_numsession)
        print("Seq             : %d " % self.hb_packetnum)
        print("Delay           : %d " % self.hb_delay)
        print("Current Session : %s " % mtime2str(self.hb_numsession))
        print("Next Timeout    : %s " % mtime2str(self.hb_timeout))
        print("----- ------------------ -----")

    def check_heartbeat(self, num_session, num_paquet, delay):
        """Check and diagnostic last received heartbeat paquet"""
        msg = None
        # self.print_heartbeat()
        # new session identification (session restart)
        if self.hb_numsession != num_session:
            if num_paquet == 0:
                msg = "HeartBeat : emission redemarree"
                logging.info(msg)
            # lost packet in a new session (reception start was too late)
            else:
                # TODO : v�rifier cas du redemarrage de la reception (valeurs locales � 0)
                if self.hb_packetnum == 0 and self.hb_numsession == 0:
                    msg = "HeartBeat : reception redemaree"
                    logging.info(msg)
                else:
                    msg = "HeartBeat : emission redemaree, perte de %d paquet(s)" % num_paquet
                    logging.warn(msg)
            # Set correct num_session
            self.hb_numsession = num_session
        # lost packet identification
        else:
            hb_lost = num_paquet - self.hb_packetnum - 1
            if bool(hb_lost):
                msg = "HeartBeat : perte de %d paquet(s)" % hb_lost
                logging.warn(msg)
        # Set new values
        self.hb_packetnum = num_paquet
        self.hb_timeout = time.time() + 1.5 * (delay)
        if msg != None:
            Console.Print_temp(msg, NL=True)
            sys.stdout.flush()

    def checktimer_heartbeat(self):
        "Timer to send alarm if no heartbeat are received"
        # self.print_heartbeat()
        Nbretard = 0
        while True:
            if self.hb_timeout < time.time():
                Nbretard += 1
                delta = time.time() - self.hb_timeout
                msg = "HeartBeat : Pending receipt ( %d ) " % self.hb_packetnum
                Console.Print_temp(msg, NL=False)
                sys.stdout.flush()
                time.sleep(self.hb_delay - 1)
                if Nbretard % 10 == 0:
                    msg = "HeartBeat : Delay in receipt ( %d ) - %d " % (self.hb_packetnum, Nbretard / 10)
                    logging.warn(msg)
                    Console.Print_temp(msg, NL=True)
            else:
                Nbretard = 0
            time.sleep(1)

    def Th_checktimeout_heartbeatT(self):
        """thead to send heartbeat"""
        Sendheartbeat = threading.Thread(None, self.checktimer_heartbeat, None)
        Sendheartbeat.start()

    def send_heartbeat(self, message=None, num_session=None, num_paquet=None):
        """Send a heartbeat packet"""
        # un HeartBeat est un paquet court donnant un timestamp qui pourra �tre v�rifi� � la r�ception
        # on donne un numero de session afin de tracer cot� haut une relance du guichet bas
        # num paquet permet de tracer les iterations au sein d'une session

        # Affectation statique pour tests et qualification du mod
        if num_session == None:
            num_session = self.hb_numsession
        if num_paquet == None:
            num_paquet = self.hb_packetnum
        if message == None:
            message = "HeartBeat"
        taille_donnees = len(message)
        debug("sending HB...")
        # self.print_heartbeat()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # on commence par packer l'entete:
        entete = struct.pack(
            FORMAT_ENTETE, PACKAGE_HEARTBEAT, 0, taille_donnees, 0, num_session, num_paquet, self.hb_delay, 1, 0, 0, 0
        )
        paquet = bytes(entete) + bytes(message)
        s.sendto(paquet, (HOST, PORT))
        s.close()

    def send_hb_loop(self):
        """A loop to send heartbeat sequence every X seconds"""
        self.newsession()
        while True:
            self.send_heartbeat()
            self.incsession()
            time.sleep(self.hb_delay)

    def start_hb_sender(self):
        """thead to send heartbeat"""
        Sendheartbeat = threading.Thread(None, self.send_hb_loop, None)
        Sendheartbeat.start()


# ------------------------------------------------------------------------------
# LimiteurDebit
# -------------------


class LimiteurDebit:
    "pour controler le d�bit d'envoi de donn�es."

    def __init__(self, debit):
        """contructeur de classe LimiteurDebit.

        debit : d�bit maximum autoris�, en Kbps."""
        # d�bit en Kbps converti en octets/s
        self.debit_max = debit * 1000 / 8
        debug("LimiteurDebit: debit_max = %d octets/s" % self.debit_max)
        # on stocke le temps de d�part
        self.temps_debut = time.time()
        # nombre d'octets d�j� transf�r�
        self.octets_envoyes = 0

    def depart_chrono(self):
        "pour (re)d�marrer la mesure du d�bit."
        self.temps_debut = time.time()
        self.octets_envoyes = 0

    def ajouter_donnees(self, octets):
        "pour ajouter un nombre d'octets envoy�s."
        self.octets_envoyes += octets

    def temps_total(self):
        "donne le temps total de mesure."
        return time.time() - self.temps_debut

    def debit_moyen(self):
        "donne le d�bit moyen mesur�, en octets/s."
        temps_total = self.temps_total()
        if temps_total == 0:
            return 0  # pour �viter division par z�ro
        debit_moyen = self.octets_envoyes / temps_total
        return debit_moyen

    def limiter_debit(self):
        "pour faire une pause afin de respecter le d�bit maximum."
        # on fait des petites pauses (10 ms) tant que le d�bit est trop �lev�:
        while self.debit_moyen() > self.debit_max:
            time.sleep(0.01)
        # m�thode alternative qui ne fonctionne pas tr�s bien
        # (donne souvent des temps de pause n�gatifs !)


#       temps_total = self.temps_total()
#       debit_moyen = self.debit_moyen()
#       # si on d�passe le d�bit max, on calcule la pause:
#       if debit_moyen > self.debit_max:
#           pause = self.octets_envoyes/self.debit_max - temps_total
#           if pause>0:
#               debug ("LimiteurDebit: pause de %.3f s..." % pause)
#               time.sleep(pause)


# ------------------------------------------------------------------------------
# RECEVOIR
# -------------------


def receive(repertoire):
    """Pour recevoir les paquets UDP BFTP contenant les fichiers, et stocker
    les fichiers re�us dans le r�pertoire indiqu� en param�tre."""

    # bidouille: on change le contenu de la variable globale
    CHEMIN_DEST = repertoire
    print('The files will be received in the directory "%s".' % str_lat1(CHEMIN_DEST.abspath(), errors="replace"))
    print("Listening on the port UDP %d..." % PORT)
    print("(type Ctrl+Pause pour quit)")
    p = Pack()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, PORT))
    while 1:
        debug("")
        paquet, emetteur = s.recvfrom(PACKAGE_SIZE)
        debug("emetteur: " + str(emetteur))
        if not paquet:
            break
        # print 'donnees recues:'
        # print paquet
        try:
            p.decoder(paquet)
        except:
            msg = "Erreur lors du decodage d'un paquet: %s" % traceback.format_exc(1)
            print(msg)
            traceback.print_exc()
            logging.error(msg)


# ------------------------------------------------------------------------------
# CalcCRC
# -------------------
def CalcCRC(file):
    """Calcul du CRC32 du fichier."""
    debug('Calcul de CRC32 pour "%s"...' % file)
    MonAff = TraitEncours.TraitEnCours()
    MonAff.StartIte()
    chaine = " Calcul CRC32 " + file
    MonAff.new_channel(chaine, truncate=True)
    try:
        f = open(file, "rb")
        buffer = f.read(16384)
        # on d�marre le calcul de CRC32:
        crc32 = binascii.crc32(buffer)
        while len(buffer) != 0:
            buffer = f.read(16384)
            # poursuite du calcul de CRC32:
            crc32 = binascii.crc32(buffer, crc32)
            MonAff.AffLigneBlink()
        f.close()
        debug("CRC32 = %08X" % crc32)
    except IOError:
        # print "Erreur : CRC32 Ouverture impossible de %s" %fichier
        crc32 = 0
    return crc32


# ------------------------------------------------------------------------------
# SendDeleteFileMessage
# -------------------
def SendDeleteFileMessage(file):
    # TODO: finsh to translate
    """send a file deletion message"""
    debug("Sending DeleteFileMessage...")
    
    file_name = str(file)
    size = len(file_name)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    entete = struct.pack(FORMAT_ENTETE, PACKAGE_DELETEFile, size, size, 0, 0, 0, 0, 1, 0, 0, 0)
    pack = entete + file_name
    s.sendto(pack, (HOST, PORT))
    s.close()


# ------------------------------------------------------------------------------
# ENVOYER
# -------------------


def send(source_file, dest_file, rate_limiter=None, num_session=None, num_paquet_session=None, crc=None):
    """Pour �mettre un fichier en paquets UDP BFTP.

    source_file: source file path on the local disk
    file_dest: relative path of the file in the destination directory
    rate_limiter: to limit the sending rate
    num_session: session number
    num_paquet_session: packet counter
    """

    msg = "Envoi du fichier %s..." % source_file
    Console.Print_temp(msg, NL=True)
    logging.info(msg)
    if num_session == None:
        num_session = int(time.time())
        num_paquet_session = 0
    debug("num_session         = %d" % num_session)
    debug("num_paquet_session  = %d" % num_paquet_session)
    debug("fichier destination = %s" % dest_file)
    if sys.platform == "win32":
        # sous Windows on doit corriger les accents
        nom_fichier_dest = dest_file.encode("utf_8", "strict")
    else:
        # sinon �a a l'air de passer
        nom_fichier_dest = str(dest_file)
    longueur_nom = len(nom_fichier_dest)
    debug("longueur_nom = %d" % longueur_nom)
    if longueur_nom > MAX_FILE_NAME:
        raise ValueError
    if source_file.isfile():
        file_size = source_file.getsize()
        file_date = source_file.getmtime()
        debug("file size = %d" % file_size)
        debug("date_fichier = %s" % mtime2str(file_date))
        # calcul de CRC32
        if crc == None:
            crc32 = CalcCRC(source_file)
        else:
            crc32 = crc
    # taille restant pour les donn�es dans un paquet normal
    taille_donnees_max = PACKAGE_SIZE - SIZE_ENTETE - longueur_nom
    debug("taille_donnees_max = %d" % taille_donnees_max)
    nb_paquets = (file_size + taille_donnees_max - 1) / taille_donnees_max
    if nb_paquets == 0:
        # si le fichier est vide, il faut quand m�me envoyer un paquet
        nb_paquets = 1
    debug("nb_paquets = %d" % nb_paquets)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reste_a_envoyer = file_size
    try:
        f = open(source_file, "rb")
        if rate_limiter == None:
            # si aucun limiteur fourni, on en initialise un:
            rate_limiter = LimiteurDebit(options.debit)
        rate_limiter.depart_chrono()
        for num_paquet in range(0, nb_paquets):
            # on fait une pause si besoin pour limiter le d�bit
            rate_limiter.limiter_debit()
            if reste_a_envoyer > taille_donnees_max:
                data_size = taille_donnees_max
            else:
                data_size = reste_a_envoyer
            reste_a_envoyer -= data_size
            offset = f.tell()
            donnees = f.read(data_size)
            # on commence par packer l'entete:
            entete = struct.pack(
                FORMAT_ENTETE,
                PACKAGE_FILE,
                longueur_nom,
                data_size,
                offset,
                num_session,
                num_paquet_session,
                num_paquet,
                nb_paquets,
                file_size,
                file_date,
                crc32,
            )
            paquet = entete + nom_fichier_dest + donnees
            s.sendto(paquet, (HOST, PORT))
            num_paquet_session += 1
            rate_limiter.ajouter_donnees(len(paquet))
            # debug("debit moyen = %d" % limiteur_debit.debit_moyen())
            # time.sleep(0.3)
            pourcent = 100 * (num_paquet + 1) / nb_paquets
            # affichage du pourcentage: la virgule �vite un retour chariot
            print("%d%%\r" % pourcent)
            # pour forcer la mise � jour de l'affichage
            sys.stdout.flush()
        print(
            "transfert en %.3f secondes - debit moyen %d Kbps"
            % (rate_limiter.temps_total(), rate_limiter.debit_moyen() * 8 / 1000)
        )
    except IOError:
        msg = "Ouverture du fichier %s..." % source_file
        print("Erreur : " + msg)
        logging.error(msg)
        num_paquet_session = -1
    s.close()
    return num_paquet_session


# ------------------------------------------------------------------------------
# SortDictBy
# -----------------
def sortDictBy(nslist, key):
    """
    Sorting a dictionary on a field
    """
    nslist = map(lambda x, key=key: (x[key], x), nslist)
    nslist.sort()
    return map(lambda key, x: x, nslist)


# ------------------------------------------------------------------------------
# SYNCHRO_ARBO
# -------------------


def synchro_arbo(directory):
    """
    # BOOKMARK: robot first translate function
    Synchronize a tree structure by regularly sending all the
      files.
    """

    logging.info('Directory synchronization "%s"' % str_lat1(directory, errors="replace"))

    # on utilise un objet LimiteurDebit global pour tout le transfert:
    limiteur_debit = LimiteurDebit(options.debit)

    # TODO : Distinguer le traitement d'une arborescence locale / distante
    if 0:
        print("arborescence locale")
        # TODO : Traitement Local des donnn�es :
        #            - utiliser wath_directory pour d�tecter le besoin l'�mission
    else:
        # print("arborescence distante")
        # Remote data processing :
        #     Boucle 1 : File analysis and prioritization
        AllFileSendMax = False
        # test for display of a cyclic pattern
        monaff = TraitEncours.TraitEnCours()
        monaff.StartIte()
        while not (AllFileSendMax) or options.boucle:
            print("%s - Tree scan" % mtime2str(time.time()))
            scanning = xfl.DirTree()
            if MODE_DEBUG:
                scanning.read_disk(directory, xfl.callback_dir_print)
                # Dscrutation.read_disk(repertoire, xfl.callback_dir_print, xfl.callback_file_print)
            else:
                scanning.read_disk(directory, None, monaff.AffCar)
                # Dscrutation.read_disk(repertoire)
            debug("%s - Tree analysis" % mtime2str(time.time()))
            same, different, only1, only2 = xfl.compare_DT(scanning, DRef)
            Console.Print_temp("%s - Processing deleted files" % mtime2str(time.time()))
            debug("\n========== Deleted ========== ")
            for f in sorted(only2, reverse=True):
                debug("S  " + f)
                monaff.AffCar()
                DeletionNeeded = False
                parent, myfile = f.splitpath()
                if DRef.dict[f].tag == xfl.TAG_DIR:
                    # V�rifier la pr�sence de fils (dir / file)
                    if not (bool(DRef.dict[f].getchildren())):
                        DeletionNeeded = True
                if DRef.dict[f].tag == xfl.TAG_FILE:
                    LastView = DRef.dict[f].get(ATTR_LASTVIEW)
                    NbSend = DRef.dict[f].get(ATTR_NBSEND)
                    if LastView == None:
                        LastView = 0
                    # Si Disparu depuis X jours ; on notifie la suppression
                    if (time.time() - (float(LastView) + OffLineDelay)) > 0:
                        if NbSend == None:
                            NbSend = -10
                        else:
                            if NbSend >= 0:
                                NbSend = -1
                        for attr in (ATTR_LASTSEND, ATTR_CRC):
                            DRef.dict[f].set(attr, str(0))
                        if options.synchro_arbo_stricte:
                            SendDeleteFileMessage(f)
                        NbSend -= 1
                        if NbSend > -10:
                            DRef.dict[f].set(ATTR_NBSEND, str(NbSend))
                        else:
                            DeletionNeeded = True
                if DeletionNeeded:
                    debug("****** Deletion")
                    if parent == "":
                        DRef.et.remove(DRef.dict[f])
                    else:
                        DRef.dict[parent].remove(DRef.dict[f])
            Console.Print_temp("%s - Processing new files " % mtime2str(time.time()))
            debug("\n========== New  ========== ")
            RefreshDictNeeded = False
            for f in sorted(only1):
                # TODO : Optimiser le traitement
                # en cas de nombreux ajouts ; la reconstruction du dict est trop gourmande
                monaff.AffCar()
                debug("N  " + f)
                parent, myfile = f.splitpath()
                index = 0
                if parent == "":
                    newET = ET.SubElement(DRef.et, scanning.dict[f].tag)
                    index = len(DRef.et) - 1
                    if scanning.dict[f].tag == xfl.TAG_FILE:
                        RefreshDictNeeded = True
                        for attr in (xfl.ATTR_NAME, xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                            DRef.et[index].set(attr, scanning.dict[f].get(attr))
                        for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                            DRef.et[index].set(attr, str(0))
                        DRef.et[index].set(ATTR_LASTVIEW, scanning.et.get(xfl.ATTR_TIME))
                    else:
                        DRef.et[index].set(xfl.ATTR_NAME, scanning.dict[f].get(xfl.ATTR_NAME))
                else:
                    newET = ET.SubElement(DRef.dict[parent], scanning.dict[f].tag)
                    index = len(DRef.dict[parent]) - 1
                    if scanning.dict[f].tag == xfl.TAG_FILE:
                        RefreshDictNeeded = True
                        for attr in (xfl.ATTR_NAME, xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                            DRef.dict[parent][index].set(attr, scanning.dict[f].get(attr))
                        for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                            DRef.dict[parent][index].set(attr, str(0))
                        DRef.dict[parent][index].set(ATTR_LASTVIEW, (scanning.et.get(xfl.ATTR_TIME)))
                    else:
                        DRef.dict[parent][index].set(xfl.ATTR_NAME, scanning.dict[f].get(xfl.ATTR_NAME))
                # Reconstruction du dictionnaire pour faciliter l'insertion des sous �l�ments
                if scanning.dict[f].tag == xfl.TAG_DIR:
                    DRef.pathdict()
                    RefreshDict = False
            # reconstruction du dictionnaire si ajout uniquement de fichiers
            if RefreshDictNeeded:
                DRef.pathdict()
            Console.Print_temp("%s - Processing modified files" % mtime2str(time.time()))
            debug("\n========== Differents  ========== ")
            for f in different:
                monaff.AffCar()
                debug("D  " + f)
                if scanning.dict[f].tag == xfl.TAG_FILE:
                    # Mise � jour des donn�es
                    for attr in (xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                        DRef.dict[f].set(attr, str(scanning.dict[f].get(attr)))
                    for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                        DRef.dict[f].set(attr, str(0))
                    DRef.dict[f].set(ATTR_LASTVIEW, scanning.et.get(xfl.ATTR_TIME))
            Console.Print_temp("%s - Handling identical files" % mtime2str(time.time()))
            debug("\n========== identical  ========== ")
            for f in same:
                monaff.AffCar()
                debug("I  " + f)
                if scanning.dict[f].tag == xfl.TAG_FILE:
                    if DRef.dict[f].get(ATTR_LASTVIEW) == None:
                        for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                            DRef.dict[f].set(attr, str(0))
                    DRef.dict[f].set(ATTR_LASTVIEW, scanning.et.get(xfl.ATTR_TIME))
            Console.Print_temp("%s - Sauvegarde du fichier de reprise" % mtime2str(time.time()))
            DRef.et.set(xfl.ATTR_TIME, str(time.time()))
            if XFLFile == "BFTPsynchro.xml":
                if os.path.isfile(XFLFile):
                    try:
                        os.rename(XFLFile, XFLFileBak)
                    except:
                        os.remove(XFLFileBak)
                        os.rename(XFLFile, XFLFileBak)
            DRef.write_file(XFLFile)
            debug("%s - Selection des fichiers les moins emis " % mtime2str(time.time()))
            FileToSend = []
            Console.Print_temp("%s - Selection des fichiers a emettre" % mtime2str(time.time()))
            for f in only1 + different + same:
                monaff.AffCar()
                (shortname, extension) = os.path.splitext(os.path.basename(f))
                if not (extension in IgnoreExtensions) and (scanning.dict[f].tag == xfl.TAG_FILE):
                    # Ignorer les fichiers trop r�cents (risque de prendre une image iso en cours de t�l�chargement)
                    # et les fichiers trop �mis
                    # if abs(float(DRef.dict[f].get(xfl.ATTR_MTIME))-float(DRef.dict[f].get(ATTR_LASTVIEW)))>60 \
                    # and int(DRef.dict[f].get(ATTR_NBSEND))<MinFileRedundancy:
                    if int(DRef.dict[f].get(ATTR_NBSEND)) < MinFileRedundancy:
                        monfichier = {"iteration": int(DRef.dict[f].get(ATTR_NBSEND)), "file": f}
                        FileToSend.append(monfichier)
                    debug(" +-- " + f)
            Console.Print_temp("%s - Priorisation des fichiers a emettre" % mtime2str(time.time()))
            FileToSend = sortDictBy(FileToSend, "iteration")
            debug("Nombre de fichiers a synchroniser : %d" % len(FileToSend))
            if len(FileToSend) == 0:
                AllFileSendMax = True
            boucleemission = LimiteurDebit(options.debit)
            boucleemission.depart_chrono()
            print("%s - Emission des donnees " % mtime2str(time.time()))
            # Set TransmitDelay from min 300 to max time needed to identify data to send
            TransmitDelay = time.time() - float(scanning.et.get(xfl.ATTR_TIME))
            if TransmitDelay < 300:
                TransmitDelay = 300
            # Boucle 2 d'�mission temporelle
            FileLessRedundancy = 0
            LastFileSendMax = False
            while (boucleemission.temps_total() < TransmitDelay * 4) and (not (LastFileSendMax)):
                if len(FileToSend) != 0:
                    item = FileToSend.pop(0)
                    f = item["file"]
                    i = item["iteration"]
                    debug("Iteration:* %d *" % i)
                    if sys.platform == "win32":
                        separator = "\\"
                    else:
                        separator = "/"
                    fullpathfichier = directory + separator + f
                    # Correction Bug Erreur si le fichier a �t� supprim�.
                    if fullpathfichier.isfile():
                        # Controle de stabilit� du fichier : v�rification des param�tres date et taille par rapport � la r�f�rence
                        #   �jecter le fichier s'il a chang�
                        # bug 4901	Non transmission de fichiers timestamp en mode boucle sur gros volume
                        # modif : pas de v�rif de stabilit� pour les petits fichiers ou le fichier de synchro
                        stable = fullpathfichier.getmtime() == float(
                            DRef.dict[f].get(xfl.ATTR_MTIME)
                        ) and fullpathfichier.getsize() == int(DRef.dict[f].get(xfl.ATTR_SIZE))
                        if not stable:
                            DRef.dict[f].set(ATTR_CRC, "0")
                            DRef.dict[f].set(ATTR_NBSEND, "0")
                        if stable or fullpathfichier.getsize() < 1024 or f == "BFTPsynchro.xml":
                            if DRef.dict[f].get(ATTR_CRC) == "0":
                                current_CRC = str(CalcCRC(fullpathfichier))
                                DRef.dict[f].set(ATTR_CRC, current_CRC)
                            if send(fullpathfichier, f, limiteur_debit, crc=int(DRef.dict[f].get(ATTR_CRC))) != -1:
                                DRef.dict[f].set(ATTR_LASTSEND, str(time.time()))
                                DRef.dict[f].set(ATTR_NBSEND, str(int(DRef.dict[f].get(ATTR_NBSEND)) + 1))
                                if int(DRef.dict[f].get(ATTR_NBSEND)) > MinFileRedundancy:
                                    LastFileSendMax = True
                                    if FileLessRedundancy == 0:
                                        AllFileSendMax = True
                                else:
                                    FileLessRedundancy += 1
                        else:
                            debug("Fichier non stable - out")
                            # doit on r�initialiser les donn�es de r�f�rence ?
                            # fichier non �mis donc � r��mettre ult�rieurement
                            FileLessRedundancy += 1
                        # fin du controle
                # Liste vide : rien � transmettre
                else:
                    # permet de sortir de la boucle 2
                    LastFileSendMax = True
                    # On temporise si on est en mode boucle
                    if options.boucle:
                        attente = options.pause - boucleemission.temps_total()
                        if attente > 0:
                            print("%s - Attente avant nouvelle scrutation" % mtime2str(time.time()))
                            time.sleep(attente)
            Console.Print_temp("%s - Sauvegarde du fichier de reprise" % mtime2str(time.time()))
            DRef.et.set(xfl.ATTR_TIME, str(time.time()))
            if XFLFile == "BFTPsynchro.xml":
                if os.path.isfile(XFLFile):
                    try:
                        os.rename(XFLFile, XFLFileBak)
                    except:
                        os.remove(XFLFileBak)
                        os.rename(XFLFile, XFLFileBak)
            DRef.write_file(XFLFile)
        debug("Tous les fichiers ont ete emis")


# ------------------------------------------------------------------------------
# AUGMENTER_PRIORITE
# ---------------------


def augmenter_priorite():
    """pour augmenter la priorit� du processus, afin de garantir une bonne
    r�ception des paquets UDP."""

    if sys.platform == "win32":
        # sous Windows:
        process = win32process.GetCurrentProcess()
        win32process.SetPriorityClass(process, win32process.REALTIME_PRIORITY_CLASS)
        # win32process.SetPriorityClass (process, win32process.HIGH_PRIORITY_CLASS)
    else:
        # sous Unix:
        try:
            os.nice(-20)
        except:
            print("Impossible d'augmenter la priorite du processus:")
            print("Il est conseille de le lancer en tant que root pour obtenir les meilleures performances.")


# ------------------------------------------------------------------------------
# Analyse Config File
# ---------------------
def analyse_conf():
    """pour analyser/initialiser le parametrage
    (� l'aide du module configparser)"""
    config = configparser.RawConfigParser(allow_no_value=True)
    config.readfp("bftp.ini")
    param = config.items("blindftp")
    for val in param:
        if config.has_option("blindftp", param):
            param = config.get("blindftp", param)


# ------------------------------------------------------------------------------
# Save Config trace File
# ---------------------
def Save_ConfTrace():
    """pour sauvegarder le parametrage courant"""


# ------------------------------------------------------------------------------
# analyse_options
# ---------------------


def analyse_options():
    """
    TODO: Done
    """

    parseur = OptionParser(usage="%prog [options] <file or directory>")
    parseur.doc = __doc__

    # on ajoute les options possibles:
    parseur.add_option("-e", "--pitch", action="store_true", dest="pitch", 
                       default=False, 
                       help="Send file")
    parseur.add_option(
        "-s", "--synchro", action="store_true", dest="synchro_arbo", default=False, 
        help="Synchronize Tree"
    )
    parseur.add_option(
        "-S",
        "--Synchro",
        action="store_true",
        dest="synchro_arbo_stricte",
        default=False,
        help="Synchronize tree with deletion",
    )
    parseur.add_option(
        "-r",
        "--reception",
        action="store_true",
        dest="recevoir",
        default=False,
        help="Receive files in the specified directory",
    )
    parseur.add_option(
        "-a", dest="adresse", default="localhost", help="Adresse destination: Adresse IP ou nom de machine"
    )
    parseur.add_option("-p", dest="port_UDP", help="Port UDP", type="int", default=36016)
    parseur.add_option("-l", dest="debit", help="Rate limit (Kbps)", type="int", default=8000)
    parseur.add_option("-d", "--debug", action="store_true", dest="debug", default=False, help="Mode Debug")
    parseur.add_option(
        "-b", "--boucle", action="store_true", dest="boucle", default=False, help="Looping files"
    )
    parseur.add_option("-P", dest="pause", help="Pause between 2 loops (en secondes)", type="int", default=300)
    parseur.add_option(
        "-c", "--continue", action="store_true", dest="reprise", default=False, help="Warm resume file"
    )

    # on parse les options de ligne de commande:
    (options, args) = parseur.parse_args(sys.argv[1:])
    # v�rif qu'il y a 1 et 1 seule action:
    nb_actions = 0
    if options.pitch:
        nb_actions += 1
    if options.synchro_arbo:
        nb_actions += 1
    if options.synchro_arbo_stricte:
        nb_actions += 1
    if options.recevoir:
        nb_actions += 1
    if nb_actions != 1:
        parseur.error("You must indicate one and only one action. (%s -h pour l'aide complete)" % NOM_SCRIPT)
    if len(args) != 1:
        parseur.error("You must specify one and only one file/directory. (%s -h pour l'aide complete)" % NOM_SCRIPT)
    return (options, args)


# ==============================================================================
# PROGRAMME PRINCIPAL
# =====================
if __name__ == "__main__":

    (options, args) = analyse_options()
    target = path(args[0])
    HOST = options.adresse
    PORT = options.port_UDP
    MODE_DEBUG = options.debug

    stats = Stats()

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        filename="bftp.log",
        filemode="a",
    )
    log = logging.getLogger
    logging.info("Start BlindFTP")

    # Emission de messages heartbeat
    hb_sender = HeartBeat()
    hb_reciver = HeartBeat()
    if not (options.recevoir):
        hb_sender.start_hb_sender()

    if options.pitch:
        send(target, target.name)
    elif options.synchro_arbo or options.synchro_arbo_stricte:
        # D�lais pour consid�rer un fichier "hors ligne" comme d�finitivement effac�
        OffLineDelay = OFFLINEDELAY
        # Fichier r�f�rence de l'arborescence synchronis�e
        # TODO : Nom du fichier transmis en param�tre
        print("Read/build recovery file")
        XFLFile_id = False
        working = TraitEncours.TraitEnCours()
        working.StartIte()
        if options.reprise:
            XFLFile = "BFTPsynchro.xml"
            XFLFileBak = "BFTPsynchro.bak"
        else:
            XFLFile_id, XFLFile = tempfile.mkstemp(prefix="BFTP_", suffix=".xml")
        DRef = xfl.DirTree()
        if XFLFile_id:
            debug("Session resume file : %s" % XFLFile)
            DRef.read_disk(target, working.AffCar)
        else:
            debug("Lecture du fichier de reprise : %s" % XFLFile)
            try:
                DRef.read_file(XFLFile)
            except:
                DRef.read_disk(target, working.AffCar)
        if options.boucle:
            while True:
                try:
                    synchro_arbo(target)
                except:
                    print("Erreur lors de l'envoi d'arborescence.")
                    traceback.print_exc()
                print(
                    "Attente de %d secondes avant prochain envoi... (Ctrl+Pause ou Ctrl+C pour quitter)\n"
                    % options.pause
                )
                time.sleep(options.pause)
        else:
            synchro_arbo(target)
        if XFLFile_id:
            debug("Suppression du fichier de reprise temporaire : %s" % XFLFile)
            os.close(XFLFile_id)
            # os.close(XFLFileBak_id)
            os.remove(XFLFile)
            # os.remove(XFLFileBak)
    elif options.recevoir:
        CHEMIN_DEST = path(args[0])
        # on commence par augmenter la priorit� du processus de r�ception:
        augmenter_priorite()
        # thread de timeout des heartbeat
        hb_reciver.Th_checktimeout_heartbeatT()
        # puis on se met en r�ception:
        receive(CHEMIN_DEST)
    logging.info("Stop BlindFTP")
