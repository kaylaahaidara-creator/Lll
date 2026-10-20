# Envoi automatique de candidatures

Petit logiciel (Python 3, aucune installation de paquet nécessaire) qui :

1. **trie les offres** de `offres.csv` selon ton profil : marketing, brand management, business developer, chef de produit / développement produit, avec un bonus pour la cosmétique et le luxe. Il **écarte** les postes seniors, de direction, freelance, alternance (et les stages, sauf si tu les actives) ;
2. **rédige un mail personnalisé** pour chaque entreprise (nom de l'entreprise, poste, phrase adaptée au secteur) à partir de `modeles/lettre.txt` ;
3. **envoie le mail avec ton CV en pièce jointe** depuis ton adresse Gmail, en te demandant de confirmer chaque envoi ;
4. **garde une trace** dans `envoyes.csv` pour ne jamais écrire deux fois à la même entreprise pour le même poste, avec une limite d'envois par jour et une pause entre deux mails (pour ne pas être classée en spam).

## Mise en route

1. Copie `config.example.json` en `config.json` et remplis : ton nom, ton email, ton téléphone, le chemin de ton CV (par ex. `cv/CV.pdf`).
2. Mot de passe Gmail : crée un **mot de passe d'application** (Compte Google → Sécurité → Validation en deux étapes → Mots de passe des applications) et colle-le dans `smtp_mot_de_passe`. Ton vrai mot de passe ne marchera pas.
3. Mets ton CV dans le dossier `cv/`.
4. Dans `offres.csv`, remplis la colonne `email_contact` (email RH / recruteur de l'entreprise). Tu peux ajouter autant de lignes que tu veux.

## Utilisation

```bash
python3 candidatures.py filtrer     # voir quelles offres sont retenues et leur score
python3 candidatures.py apercu      # lire les mails avant envoi
python3 candidatures.py envoyer     # envoyer (o = oui, n = passer, q = arrêter)
```

## À savoir

- Les offres Indeed n'affichent pas l'email du recruteur : pour celles-là, cherche l'email RH sur le site de l'entreprise ou sur LinkedIn, ou postule directement via le lien de la colonne `lien`.
- Relis `modeles/lettre.txt` et adapte-le à ta façon d'écrire : c'est le texte envoyé à toutes les entreprises.
- Pour ajuster le tri, modifie les listes `MOTS_METIER`, `MOTS_SECTEUR`, `MOTS_JUNIOR` et `MOTS_EXCLUS` en haut de `candidatures.py`, ou `score_minimum` dans `config.json`.
