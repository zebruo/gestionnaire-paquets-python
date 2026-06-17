# Aide — Gestionnaire de paquets Python

## Présentation

Le Gestionnaire de paquets Python permet de visualiser, installer, mettre à jour et supprimer des paquets pip sur toutes vos versions Python installées.

---

## Tableau des paquets

- Chaque **ligne** représente un paquet.
- Chaque **colonne** représente une version Python détectée.
- `✓ 1.2.3` : paquet installé, à jour.
- `1.2.3 → 1.3.0` : mise à jour disponible.
- `—` : paquet non installé sur cette version.
- `⚠️ pip manquant` dans l'en-tête : pip absent sur cette version.

Le tableau se charge en **deux phases** :
1. Liste des paquets installés (rapide)
2. Vérification des mises à jour disponibles (peut prendre quelques secondes)

---

## Barre de recherche

Tapez dans la barre de recherche pour filtrer les paquets en temps réel.
Cliquez sur **✕** pour effacer le filtre et revenir à la liste complète.

---

## Mettre à jour des paquets

**Plusieurs paquets à la fois :**
1. Cliquez sur les lignes à mettre à jour (Ctrl+clic pour sélectionner plusieurs, Ctrl+A pour tout sélectionner)
2. Cliquez sur **⬆️ Mettre à jour la sélection**

**Un seul paquet sur une version précise :**
Faites un **clic droit** sur la ligne du paquet → *⬆️ Mettre à jour sur Python X.Y*

---

## Installer un paquet

Cliquez sur **➕ Installer un paquet**, saisissez le nom et choisissez la version Python cible.
La vérification d'existence sur PyPI se fait automatiquement.

---

## Désinstaller un paquet

Faites un **clic droit** sur la ligne du paquet → *🗑️ Désinstaller de Python X.Y*

---

## Informations sur un paquet

**Double-cliquez** sur le nom du paquet (colonne de gauche) pour afficher :
- Version installée par version Python
- Description, auteur, licence
- Dépendances requises et paquets dépendants

---

## Export / Import requirements.txt

- **💾 Exporter** : génère un fichier `requirements.txt` pour une version Python choisie
- **📥 Importer** : installe tous les paquets d'un fichier `requirements.txt` sur une version Python cible

---

## Version Python disponible

L'en-tête affiche la dernière version stable de Python (vérifiée sur python.org au démarrage).
Si une version plus récente est disponible, le bouton **⬇️ Télécharger** ouvre directement la page de téléchargement.

---

## Raccourcis

| Action | Geste |
|---|---|
| Sélectionner plusieurs paquets | Ctrl+clic |
| Tout sélectionner | Ctrl+A |
| Infos sur un paquet | Double-clic sur le nom ou Entrée |
| Menu contextuel | Clic droit |
| Effacer la recherche | Bouton ✕ ou Échap |
| Rafraîchir le tableau | F5 |
| Scroll horizontal | Shift + Molette |

---

## Dépannage

**Le tableau reste vide :** Aucune version Python n'a été détectée. Vérifiez que Python est installé et accessible via le Python Launcher (`py`).

**⚠️ pip manquant sur Python X.Y :** pip n'est pas installé sur cette version. Installez-le manuellement avec :
```
py -X.Y -m ensurepip --upgrade
```

**L'application semble lente au démarrage :** Normal — la phase 2 (vérification des mises à jour) interroge PyPI pour chaque paquet installé.
