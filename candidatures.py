#!/usr/bin/env python3
"""Envoi automatisé de candidatures (CV + lettre) aux entreprises de offres.csv.

Commandes :
  python3 candidatures.py filtrer              # classe les offres selon ton profil
  python3 candidatures.py apercu               # montre les mails qui seraient envoyés
  python3 candidatures.py envoyer              # envoie (demande confirmation pour chaque mail)
  python3 candidatures.py envoyer --sans-confirmation
"""

import argparse
import csv
import re
import json
import mimetypes
import smtplib
import ssl
import sys
import time
import unicodedata
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
FICHIER_OFFRES = DOSSIER / "offres.csv"
FICHIER_ENVOYES = DOSSIER / "envoyes.csv"
FICHIER_CONFIG = DOSSIER / "config.json"

# Mots qui rapprochent l'offre de ton profil (poids entre parenthèses).
MOTS_METIER = {
    "marketing": 3, "brand": 3, "marque": 2, "chef de produit": 3,
    "chef de produits": 3, "business developer": 3, "business development": 2,
    "developpement produit": 3, "developpement marketing": 3,
    "communication": 1, "trade": 1, "category": 1, "merchandising": 1,
}
MOTS_SECTEUR = {
    "cosmetique": 3, "beaute": 3, "maquillage": 3, "parfum": 3, "luxe": 3,
    "skincare": 3, "bien-etre": 1, "mode": 1, "champagne": 2,
}
MOTS_JUNIOR = {
    "junior": 2, "assistant": 2, "debutant": 2, "premier emploi": 2,
    "jeune diplome": 2, "0 a 3 ans": 2, "1 a 3 ans": 2, "ecole de commerce": 2,
    "bac+5": 1,
}
# Signes que l'offre vise un profil trop expérimenté ou hors cible.
MOTS_EXCLUS = [
    "senior", "directeur", "directrice", "head of", "principal", "confirme",
    "5 ans", "7 ans", "10 ans", "independant", "freelance", "alternance",
]
MOTS_STAGE = ["stage", "stagiaire", "internship"]

ACCROCHES_SECTEUR = {
    "cosmetique": "Passionnée par l'univers de la cosmétique et de la beauté, je suis particulièrement attirée par vos produits et votre positionnement.",
    "luxe": "L'univers du luxe, son exigence et son attention au détail correspondent pleinement à mes aspirations.",
    "business": "Le développement commercial, la prospection et la construction de relations durables avec les clients sont au cœur de ce qui me motive.",
    "defaut": "Votre entreprise et vos produits correspondent pleinement à mes aspirations professionnelles.",
}


def normaliser(texte):
    texte = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def nettoyer_poste(poste):
    """Retire les mentions H/F, F/H, (H/F) du titre pour le mail."""
    poste = re.sub(r"[\s\-–]*\(?\b[HF]\s*/\s*[HF]\b\)?", "", poste)
    return poste.strip(" -–")


def charger_config():
    if not FICHIER_CONFIG.exists():
        sys.exit("config.json introuvable : copie config.example.json en config.json et remplis-le.")
    return json.loads(FICHIER_CONFIG.read_text(encoding="utf-8"))


def charger_offres():
    with FICHIER_OFFRES.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def deja_envoyes():
    if not FICHIER_ENVOYES.exists():
        return set()
    with FICHIER_ENVOYES.open(encoding="utf-8") as f:
        return {(l["entreprise"].lower(), l["poste"].lower()) for l in csv.DictReader(f)}


def envois_du_jour():
    if not FICHIER_ENVOYES.exists():
        return 0
    with FICHIER_ENVOYES.open(encoding="utf-8") as f:
        return sum(1 for l in csv.DictReader(f) if l["date"].startswith(date.today().isoformat()))


def noter(offre, config):
    """Renvoie (score, raison d'exclusion ou None)."""
    texte = normaliser(" ".join([offre["poste"], offre.get("type", ""), offre.get("description", "")]))
    for mot in MOTS_EXCLUS:
        if mot in texte:
            return 0, f"exclue ({mot})"
    if not config.get("inclure_stages") and any(m in texte for m in MOTS_STAGE):
        return 0, "exclue (stage)"
    score = 0
    for table in (MOTS_METIER, MOTS_SECTEUR, MOTS_JUNIOR):
        score += sum(poids for mot, poids in table.items() if mot in texte)
    return score, None


def accroche(offre):
    texte = normaliser(offre["poste"] + " " + offre.get("description", ""))
    if any(m in texte for m in ("cosmetique", "beaute", "maquillage", "parfum", "skincare")):
        return ACCROCHES_SECTEUR["cosmetique"]
    if any(m in texte for m in ("luxe", "champagne")):
        return ACCROCHES_SECTEUR["luxe"]
    if "business" in texte:
        return ACCROCHES_SECTEUR["business"]
    return ACCROCHES_SECTEUR["defaut"]


def selectionner(config):
    envoyes = deja_envoyes()
    retenues = []
    for offre in charger_offres():
        score, raison = noter(offre, config)
        if raison or score < config.get("score_minimum", 3):
            continue
        if (offre["entreprise"].lower(), offre["poste"].lower()) in envoyes:
            continue
        retenues.append((score, offre))
    retenues.sort(key=lambda x: -x[0])
    return retenues


def construire_mail(offre, config):
    champs = {
        "entreprise": offre["entreprise"], "poste": nettoyer_poste(offre["poste"]),
        "nom": config["nom"], "ecole": config["ecole"],
        "telephone": config["telephone"], "accroche_secteur": accroche(offre),
    }
    objet = (DOSSIER / "modeles/objet.txt").read_text(encoding="utf-8").strip().format(**champs)
    corps = (DOSSIER / "modeles/lettre.txt").read_text(encoding="utf-8").format(**champs)

    msg = EmailMessage()
    msg["From"] = f'{config["nom"]} <{config["email"]}>'
    msg["To"] = offre["email_contact"]
    msg["Subject"] = objet
    msg.set_content(corps)

    cv = DOSSIER / config["cv"]
    type_mime, _ = mimetypes.guess_type(cv.name)
    principal, secondaire = (type_mime or "application/pdf").split("/")
    msg.add_attachment(cv.read_bytes(), maintype=principal, subtype=secondaire, filename=cv.name)
    return msg


def cmd_filtrer(config):
    for offre in charger_offres():
        score, raison = noter(offre, config)
        etat = raison or ("retenue" if score >= config.get("score_minimum", 3) else "score trop bas")
        contact = offre["email_contact"] or "(pas d'email)"
        print(f"{score:>3}  {etat:<22} {offre['entreprise']} – {offre['poste']}  {contact}")


def cmd_apercu(config):
    for score, offre in selectionner(config):
        if not offre["email_contact"]:
            print(f"\n[ignorée : pas d'email] {offre['entreprise']} – {offre['poste']}  {offre['lien']}")
            continue
        msg = construire_mail(offre, config)
        print("\n" + "=" * 70)
        print(f"À : {msg['To']}\nObjet : {msg['Subject']}\n")
        print(msg.get_body().get_content())


def cmd_envoyer(config, confirmer):
    cv = DOSSIER / config["cv"]
    if not cv.exists():
        sys.exit(f"CV introuvable : {cv}")
    a_envoyer = [o for _, o in selectionner(config) if o["email_contact"]]
    restant = config.get("max_envois_par_jour", 15) - envois_du_jour()
    if restant <= 0:
        sys.exit("Limite d'envois du jour atteinte.")
    a_envoyer = a_envoyer[:restant]
    if not a_envoyer:
        print("Rien à envoyer (vérifie les emails de contact dans offres.csv).")
        return

    contexte = ssl.create_default_context()
    with smtplib.SMTP_SSL(config["smtp_serveur"], config["smtp_port"], context=contexte) as serveur:
        serveur.login(config["email"], config["smtp_mot_de_passe"])
        nouveau = not FICHIER_ENVOYES.exists()
        with FICHIER_ENVOYES.open("a", newline="", encoding="utf-8") as journal:
            ecrivain = csv.writer(journal)
            if nouveau:
                ecrivain.writerow(["date", "entreprise", "poste", "email_contact"])
            for i, offre in enumerate(a_envoyer):
                msg = construire_mail(offre, config)
                if confirmer:
                    rep = input(f"Envoyer à {offre['entreprise']} ({msg['To']}) ? [o/N/q] ").strip().lower()
                    if rep == "q":
                        break
                    if rep != "o":
                        continue
                serveur.send_message(msg)
                ecrivain.writerow([datetime.now().isoformat(timespec="seconds"),
                                   offre["entreprise"], offre["poste"], offre["email_contact"]])
                journal.flush()
                print(f"Envoyé : {offre['entreprise']} – {offre['poste']}")
                if i < len(a_envoyer) - 1:
                    time.sleep(config.get("pause_secondes", 60))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("commande", choices=["filtrer", "apercu", "envoyer"])
    parser.add_argument("--sans-confirmation", action="store_true")
    args = parser.parse_args()
    config = charger_config()
    if args.commande == "filtrer":
        cmd_filtrer(config)
    elif args.commande == "apercu":
        cmd_apercu(config)
    else:
        cmd_envoyer(config, confirmer=not args.sans_confirmation)


if __name__ == "__main__":
    main()
