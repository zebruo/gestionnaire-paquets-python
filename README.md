# 🐍 Gestionnaire de paquets Python

Interface graphique Windows pour gérer les paquets pip sur toutes vos versions Python installées.

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Fonctionnalités

- **Vue unifiée** — un tableau croisant tous les paquets et toutes les versions Python détectées
- **Mises à jour** — détection et installation des paquets obsolètes, un ou plusieurs à la fois
- **Installation** — recherche et vérification sur PyPI avant installation
- **Désinstallation** — via clic droit sur n'importe quelle version
- **Export / Import** — génération et lecture de fichiers `requirements.txt`
- **Informations** — description, auteur, licence, dépendances de chaque paquet
- **Veille Python** — vérification de la dernière version stable sur python.org au démarrage

---

## Captures d'écran

> *Tableau principal avec détection multi-versions, filtre de recherche et barre d'outils.*

---

## Utilisation

### Version compilée (recommandée)

Téléchargez le dernier `.exe` depuis la page [Releases](../../releases) et lancez-le directement.  
Aucune installation Python requise sur la machine cible.

### Depuis les sources

**Prérequis :** Python 3.x avec le Python Launcher (`py`) installé.

```
py python_versions_gui.py
```

---

## Raccourcis clavier

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

## Tableau des paquets

| Affichage | Signification |
|---|---|
| `✓ 1.2.3` | Paquet installé, à jour |
| `1.2.3 → 1.3.0` | Mise à jour disponible |
| `—` | Paquet non installé sur cette version |
| `⚠️ pip manquant` | pip absent sur cette version Python |

---

## Compilation (développeurs)

### En local

```powershell
.\build_release.ps1
```

Génère `release\GestionnairePaquets_v1.0.0.exe` et son archive `.zip`.

### Via GitHub Actions

Pousser un tag déclenche automatiquement le build et la création de la release :

```bash
git tag v1.0.0
git push origin v1.0.0
```

**Prérequis :** PyInstaller installé (`pip install pyinstaller`).

---

## Structure du projet

```
├── python_versions_gui.py      # Application principale
├── aide.md                     # Aide intégrée (affichée dans l'app)
├── GestionnairePaquets.spec    # Configuration PyInstaller
├── build_release.ps1           # Script de build local
└── .github/
    └── workflows/
        └── release.yml         # Pipeline CI/CD
```

---

## Dépannage

**Le tableau reste vide** — vérifiez que Python est installé et accessible via `py` :
```
py -0
```

**⚠️ pip manquant sur Python X.Y** — installez pip sur cette version :
```
py -X.Y -m ensurepip --upgrade
```

**L'application semble lente au démarrage** — normal : la phase 2 interroge PyPI pour chaque paquet installé afin de détecter les mises à jour disponibles.
