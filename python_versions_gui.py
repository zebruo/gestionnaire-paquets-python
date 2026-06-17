import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import re
import sys
import os
import glob
import winreg
import threading
import urllib.request
import urllib.error
import json
import gzip
import io
import webbrowser


def resource_path(relative_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


# -----------------------
# UTILITAIRES DE DÉTECTION
# -----------------------

def detecter_versions_python():
    versions = set()
    try:
        result = subprocess.run(
            ["py", "-0"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
        )
        for ligne in result.stdout.strip().splitlines():
            match = re.search(r"-(\d+\.\d+)", ligne)
            if match:
                version = match.group(1)
                major, _ = version.split(".")
                if int(major) == 3:
                    versions.add(version)
    except Exception:
        pass

    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root, r"SOFTWARE\Python\PythonCore") as key:
                i = 0
                while True:
                    try:
                        version = winreg.EnumKey(key, i)
                        if re.match(r"^3\.\d{1,2}$", version):
                            versions.add(version)
                        i += 1
                    except OSError:
                        break
        except FileNotFoundError:
            continue

    search_paths = [
        r"C:\Program Files\Python*",
        os.path.expandvars(r"%LocalAppData%\Programs\Python\Python*"),
    ]
    for pattern in search_paths:
        for path in glob.glob(pattern):
            m = re.search(r"Python3(\d{1,2})", path)
            if m:
                versions.add(f"3.{m.group(1)}")

    if not versions:
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        versions.add(current)

    return sorted(versions, key=lambda x: [int(n) for n in x.split(".")])


def executer_commande(cmd):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _executer_pip_bool(cmd):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def verifier_pip(version):
    try:
        result = subprocess.run(
            ["py", f"-{version}", "-m", "pip", "--version"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def obtenir_info_paquet(version, paquet):
    output = executer_commande(["py", f"-{version}", "-m", "pip", "show", paquet])
    info = {"nom": paquet, "version": "", "summary": "", "author": "",
            "license": "", "location": "", "requires": "", "required_by": ""}
    for ligne in output.splitlines():
        for key, prefix in [("version", "Version:"), ("summary", "Summary:"),
                             ("author", "Author:"), ("license", "License:"),
                             ("location", "Location:"), ("requires", "Requires:"),
                             ("required_by", "Required-by:")]:
            if ligne.startswith(prefix):
                info[key] = ligne.split(":", 1)[1].strip()
    return info


def lister_paquets(version):
    output = executer_commande(["py", f"-{version}", "-m", "pip", "list", "--format=freeze"])
    paquets = {}
    for ligne in output.splitlines():
        if "==" in ligne:
            nom, ver = ligne.split("==", 1)
            paquets[nom.strip()] = ver.strip()
    return paquets


def paquets_obsoletes(version):
    output = executer_commande(
        ["py", f"-{version}", "-m", "pip", "list", "--outdated", "--format=columns"])
    obsoletes = {}
    lines = output.splitlines()
    if len(lines) > 2:
        for ligne in lines[2:]:
            parts = ligne.split()
            if len(parts) >= 3:
                obsoletes[parts[0]] = (parts[1], parts[2])
    return obsoletes


def installer_paquet(version, paquet):
    return _executer_pip_bool(["py", f"-{version}", "-m", "pip", "install", paquet])


def mettre_a_jour_paquet(version, paquet):
    return _executer_pip_bool(
        ["py", f"-{version}", "-m", "pip", "install", "--upgrade", paquet])


def verifier_paquet_existe(paquet):
    try:
        nom_propre = paquet.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
        url = f"https://pypi.org/pypi/{nom_propre}/json"
        req = urllib.request.Request(url, headers={"User-Agent": "Python Package Manager"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return True, data.get("info", {}).get("summary", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "Paquet introuvable sur PyPI"
    except Exception as e:
        return None, f"Erreur de vérification : {str(e)}"
    return False, "Paquet introuvable"


def desinstaller_paquet_cmd(version, paquet):
    return _executer_pip_bool(
        ["py", f"-{version}", "-m", "pip", "uninstall", "-y", paquet])


# -----------------------
# VÉRIFICATION VERSION PYTHON (thread)
# -----------------------

def _version_complete(version_courte):
    try:
        result = subprocess.run(
            ["py", f"-{version_courte}", "--version"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
        )
        match = re.search(r"Python (\d+\.\d+\.\d+)", result.stdout + result.stderr)
        if match:
            return match.group(1)
    except Exception:
        pass
    return version_courte + ".0"


def afficher_derniere_version_stable():
    def _verifier():
        try:
            req = urllib.request.Request(
                "https://www.python.org/downloads/",
                headers={"Accept-Encoding": "gzip"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.info().get("Content-Encoding") == "gzip":
                    buf = io.BytesIO(response.read())
                    with gzip.GzipFile(fileobj=buf) as f:
                        html = f.read().decode("utf-8")
                else:
                    html = response.read().decode("utf-8")

            versions_stables = re.findall(r'Python ([0-9]+\.[0-9]+\.[0-9]+)</a>', html)

            if not versions_stables:
                fenetre.after(0, lambda: label_version_python.config(
                    text="⚠️ Impossible de déterminer la dernière version stable."))
                return

            derniere_stable = sorted(
                versions_stables,
                key=lambda x: [int(n) for n in x.split(".")], reverse=True,
            )[0]

            locales = detecter_versions_python()
            if not locales:
                fenetre.after(0, lambda: label_version_python.config(
                    text="⚠️ Aucune version Python détectée localement"))
                return

            derniere_locale_courte = sorted(
                locales, key=lambda x: [int(n) for n in x.split(".")], reverse=True
            )[0]
            derniere_locale = _version_complete(derniere_locale_courte)

            def normaliser(v):
                p = v.split(".")
                while len(p) < 3:
                    p.append("0")
                return tuple(map(int, p))

            if normaliser(derniere_stable) > normaliser(derniere_locale):
                msg = f"⚠️ Python {derniere_stable} disponible (installé : {derniere_locale})"
                dl_url = (
                    "https://www.python.org/downloads/release/"
                    f"python-{derniere_stable.replace('.', '')}/"
                )
                def _afficher_update(m=msg, u=dl_url, v=derniere_stable):
                    label_version_python.config(text=m, fg="#f1c40f")
                    btn_telecharger_python.config(
                        text=f"⬇️ Télécharger Python {v}",
                        command=lambda: webbrowser.open(u),
                    )
                    btn_telecharger_python.pack(side="right", anchor="e", padx=(0, 6))
                fenetre.after(0, _afficher_update)
            else:
                msg = f"✅ Dernière version stable installée : Python {derniere_locale}"
                fenetre.after(0, lambda: (
                    label_version_python.config(text=msg, fg="#2ecc71"),
                    btn_telecharger_python.pack_forget(),
                ))

        except Exception:
            fenetre.after(0, lambda: label_version_python.config(
                text="⚠️ Erreur lors de la vérification", fg="#e74c3c"))

    threading.Thread(target=_verifier, daemon=True).start()


# -----------------------
# ÉTAT GLOBAL
# -----------------------
_cache_tableau = {}
_gen = [0]


# -----------------------
# UTILITAIRES IHM
# -----------------------

def _valeurs_ligne(pkg, versions, data):
    values = [pkg]
    for v in versions:
        installee = data[v]["installes"].get(pkg)
        obsolete  = data[v]["obsoletes"].get(pkg)
        if installee:
            if obsolete:
                current, latest = obsolete
                values.append(f"{current} → {latest}")
            else:
                values.append(f"✓ {installee}")
        else:
            values.append("—")
    return values


def _desactiver_boutons():
    btn_maj.config(state="disabled")
    btn_installer.config(state="disabled")


def _make_scroll(canvas):
    return lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


def _appliquer_icone(dialog):
    if hasattr(fenetre, "_icon_path") and fenetre._icon_path and fenetre._icon_path.endswith(".ico"):
        try:
            dialog.iconbitmap(fenetre._icon_path)
        except Exception:
            pass
    elif hasattr(fenetre, "_icon_photo") and fenetre._icon_photo:
        try:
            dialog.iconphoto(True, fenetre._icon_photo)
        except Exception:
            pass


def _lancer_action_pip(msg_confirm, msg_status, cmd_fn, msg_ok, msg_err):
    if msg_confirm and not messagebox.askyesno("Confirmation", msg_confirm):
        return
    label_status.config(text=msg_status)
    _desactiver_boutons()
    def _thread():
        ok = cmd_fn()
        def _fin():
            if ok:
                messagebox.showinfo("Succès", msg_ok)
            else:
                messagebox.showerror("Échec", msg_err)
            construire_tableau()
        fenetre.after(0, _fin)
    threading.Thread(target=_thread, daemon=True).start()


def _ouvrir_info_premier_v(pkg):
    versions = _cache_tableau.get("versions", [])
    data     = _cache_tableau.get("data", {})
    for v in versions:
        if pkg in data.get(v, {}).get("installes", {}):
            afficher_info_paquet(pkg, v)
            return


# -----------------------
# TREEVIEW — REMPLISSAGE
# -----------------------

def _remplir_tree(versions, data, all_paquets, versions_sans_pip=None):
    versions_sans_pip = versions_sans_pip or []
    cols = ["paquet"] + [f"v{v}" for v in versions]
    tree["columns"] = cols
    tree.column("paquet", width=220, minwidth=150, anchor="w")
    tree.heading("paquet", text="📦 Paquet", anchor="w")
    for v in versions:
        tree.column(f"v{v}", width=165, minwidth=120, anchor="center")
        avert = "  ⚠️ pip manquant" if v in versions_sans_pip else ""
        tree.heading(f"v{v}", text=f"🐍 Python {v}{avert}", anchor="center")
    tree.delete(*tree.get_children())
    for iid in _cache_tableau.get("all_paquets", []):
        if tree.exists(iid):
            tree.delete(iid)
    for i, pkg in enumerate(all_paquets):
        parity = "even" if i % 2 == 0 else "odd"
        tree.insert("", "end", iid=pkg, values=_valeurs_ligne(pkg, versions, data), tags=(parity,))


def _actualiser_obsoletes_tree(versions, data):
    for iid in tree.get_children():
        tree.item(iid, values=_valeurs_ligne(iid, versions, data))
    has_any = any(data[v]["obsoletes"] for v in versions)
    btn_maj.config(state="normal" if has_any else "disabled")
    nb = len(_cache_tableau.get("all_paquets", []))
    suffix = "" if has_any else " — tout est à jour"
    label_status.config(text=f"✓ {nb} paquets sur {len(versions)} versions Python{suffix}")


# -----------------------
# CHARGEMENT DU TABLEAU
# -----------------------

def construire_tableau():
    _gen[0] += 1
    gen = _gen[0]
    tree.delete(*tree.get_children())
    _desactiver_boutons()
    label_status.config(text="🔄 Chargement en cours...")

    def _charger():
        versions = detecter_versions_python()
        if _gen[0] != gen:
            return
        if not versions:
            fenetre.after(0, lambda: label_status.config(text="❌ Aucune version Python détectée"))
            return

        versions_sans_pip = [v for v in versions if not verifier_pip(v)]
        data = {}
        all_paquets = set()
        for v in versions:
            if _gen[0] != gen:
                return
            inst = lister_paquets(v)
            data[v] = {"installes": inst, "obsoletes": {}}
            all_paquets.update(inst.keys())

        all_paquets_sorted = sorted(all_paquets, key=lambda x: x.lower())
        _cache_tableau.update({"versions": versions, "data": data,
                               "all_paquets": all_paquets_sorted,
                               "versions_sans_pip": versions_sans_pip})

        def _afficher_phase1():
            if _gen[0] != gen:
                return
            _remplir_tree(versions, data, all_paquets_sorted, versions_sans_pip)
            btn_installer.config(state="normal")
            btn_export.config(state="normal")
            label_status.config(
                text=f"✓ {len(all_paquets_sorted)} paquets — vérification des mises à jour…"
            )
        fenetre.after(0, _afficher_phase1)

        for v in versions:
            if _gen[0] != gen:
                return
            data[v]["obsoletes"] = paquets_obsoletes(v)

        def _afficher_phase2():
            if _gen[0] != gen:
                return
            _actualiser_obsoletes_tree(versions, data)
        fenetre.after(0, _afficher_phase2)

    threading.Thread(target=_charger, daemon=True).start()


# -----------------------
# MISE À JOUR
# -----------------------

def lancer_mise_a_jour():
    versions = _cache_tableau.get("versions", [])
    data     = _cache_tableau.get("data", {})
    selected = tree.selection()
    if not selected:
        messagebox.showwarning(
            "Aucune sélection",
            "Cliquez sur les lignes à mettre à jour.\n"
            "Ctrl+clic pour plusieurs, Ctrl+A pour tout sélectionner.",
        )
        return
    selection = [
        (iid, v)
        for iid in selected
        for v in versions
        if iid in data.get(v, {}).get("obsoletes", {})
    ]
    if not selection:
        messagebox.showwarning("Aucune mise à jour disponible",
                               "Les paquets sélectionnés sont déjà à jour.")
        return

    _desactiver_boutons()
    label_status.config(text=f"🔄 Mise à jour de {len(selection)} paquet(s)...")

    def maj_thread():
        echecs = []
        for i, (pkg, version) in enumerate(selection, 1):
            fenetre.after(0, lambda p=pkg, idx=i: label_status.config(
                text=f"⬆️ [{idx}/{len(selection)}] {p}..."))
            if not mettre_a_jour_paquet(version, pkg):
                echecs.append(pkg)

        def _fin():
            if echecs:
                messagebox.showerror("Échecs", f"Échec sur : {', '.join(echecs)}")
            else:
                messagebox.showinfo("Terminé", f"{len(selection)} paquet(s) mis à jour !")
            construire_tableau()
        fenetre.after(0, _fin)

    threading.Thread(target=maj_thread, daemon=True).start()


def _maj_un_paquet(pkg, version):
    _lancer_action_pip(
        msg_confirm=None,
        msg_status=f"⬆️ Mise à jour de {pkg} sur Python {version}...",
        cmd_fn=lambda: mettre_a_jour_paquet(version, pkg),
        msg_ok=f"'{pkg}' mis à jour sur Python {version}.",
        msg_err=f"Échec de la mise à jour de '{pkg}' sur Python {version}.",
    )


# -----------------------
# FILTRE RECHERCHE
# -----------------------

def filtrer_tableau(texte):
    if not _cache_tableau:
        return
    all_paquets = _cache_tableau["all_paquets"]
    versions    = _cache_tableau["versions"]
    texte = texte.strip().lower()

    nb_visibles = 0
    for pkg in all_paquets:
        if not tree.exists(pkg):
            continue
        if not texte or texte in pkg.lower():
            tree.reattach(pkg, "", "end")
            nb_visibles += 1
        else:
            tree.detach(pkg)

    if texte:
        label_status.config(text=f"🔍 {nb_visibles} / {len(all_paquets)} paquets")
    else:
        has_any = any(_cache_tableau["data"][v]["obsoletes"] for v in versions)
        suffix  = "" if has_any else " — tout est à jour"
        label_status.config(
            text=f"✓ {len(all_paquets)} paquets sur {len(versions)} versions Python{suffix}")


# -----------------------
# ACTIONS SUR LES PAQUETS
# -----------------------

def supprimer_paquet(paquet, version):
    _lancer_action_pip(
        msg_confirm=f"Voulez-vous vraiment supprimer '{paquet}' de Python {version} ?",
        msg_status=f"⏳ Suppression de {paquet}...",
        cmd_fn=lambda: desinstaller_paquet_cmd(version, paquet),
        msg_ok=f"'{paquet}' supprimé de Python {version}",
        msg_err=f"Impossible de supprimer '{paquet}' de Python {version}",
    )


def installer_paquet_sur_autre_version(paquet, version_cible):
    _lancer_action_pip(
        msg_confirm=f"Voulez-vous installer '{paquet}' sur Python {version_cible} ?",
        msg_status=f"⏳ Installation de {paquet} sur Python {version_cible}...",
        cmd_fn=lambda: installer_paquet(version_cible, paquet),
        msg_ok=f"'{paquet}' installé sur Python {version_cible}",
        msg_err=f"Impossible d'installer '{paquet}' sur Python {version_cible}",
    )


# -----------------------
# DIALOGUE INSTALLER UN NOUVEAU PAQUET
# -----------------------

def installer_nouveau_paquet():
    dialog = tk.Toplevel(fenetre)
    dialog.title("Installer un nouveau paquet")
    dialog.geometry("500x280")
    dialog.resizable(False, False)
    dialog.configure(bg="#f5f5f5")
    dialog.transient(fenetre)
    dialog.grab_set()
    _appliquer_icone(dialog)

    tk.Label(dialog, text="📦 Nom du paquet :", font=("Arial", 11), bg="#f5f5f5").pack(pady=(20, 5))

    entry_frame = tk.Frame(dialog, bg="#f5f5f5")
    entry_frame.pack(pady=5)

    entry_paquet = tk.Entry(entry_frame, font=("Arial", 11), width=30)
    entry_paquet.pack(side="left", padx=(0, 5))
    entry_paquet.focus()

    status_label = tk.Label(dialog, text="", font=("Arial", 9), bg="#f5f5f5", fg="#7f8c8d")
    status_label.pack()

    desc_label = tk.Label(dialog, text="", font=("Arial", 9, "italic"), bg="#f5f5f5",
                          fg="#555", wraplength=450, justify="left")
    desc_label.pack(pady=(5, 0), padx=20)

    btn_verifier = tk.Button(entry_frame, text="🔍", font=("Arial", 10),
                             bg="#3498db", fg="white", relief="flat", padx=10, cursor="hand2")
    btn_verifier.pack(side="left")

    tk.Label(dialog, text="🐍 Version Python :", font=("Arial", 11), bg="#f5f5f5").pack(pady=(10, 5))
    versions = _cache_tableau.get("versions") or detecter_versions_python()
    combo_version = ttk.Combobox(dialog, values=versions, state="readonly",
                                  font=("Arial", 11), width=28)
    if versions:
        combo_version.current(0)
    combo_version.pack(pady=5)

    paquet_valide = [None]

    def verifier():
        paquet = entry_paquet.get().strip()
        if not paquet:
            status_label.config(text="", fg="#7f8c8d")
            desc_label.config(text="")
            paquet_valide[0] = None
            return
        status_label.config(text="🔄 Vérification en cours...", fg="#3498db")
        desc_label.config(text="")
        btn_verifier.config(state="disabled")
        paquet_valide[0] = None

        def verif_thread():
            existe, message = verifier_paquet_existe(paquet)
            def _afficher():
                btn_verifier.config(state="normal")
                if existe is True:
                    status_label.config(text="✓ Paquet trouvé sur PyPI", fg="#27ae60")
                    desc_label.config(text=f"📝 {message}" if message else "")
                    paquet_valide[0] = True
                elif existe is False:
                    status_label.config(text="❌ " + message, fg="#e74c3c")
                    desc_label.config(text="")
                    paquet_valide[0] = False
                else:
                    status_label.config(text="⚠️ " + message, fg="#f39c12")
                    desc_label.config(text="L'installation peut quand même être tentée")
                    paquet_valide[0] = None
            dialog.after(0, _afficher)
        threading.Thread(target=verif_thread, daemon=True).start()

    btn_verifier.config(command=verifier)

    verif_timer = [None]
    def on_paquet_change(*args):
        if verif_timer[0]:
            dialog.after_cancel(verif_timer[0])
        verif_timer[0] = dialog.after(1000, verifier)
    entry_paquet.bind("<KeyRelease>", on_paquet_change)

    def valider():
        paquet = entry_paquet.get().strip()
        version = combo_version.get()
        if not paquet:
            messagebox.showwarning("Erreur", "❌ Veuillez entrer un nom de paquet", parent=dialog)
            return
        if not version:
            messagebox.showwarning("Erreur", "❌ Veuillez sélectionner une version Python", parent=dialog)
            return
        if paquet_valide[0] is False:
            if not messagebox.askyesno("Paquet introuvable",
                    f"⚠️ Le paquet '{paquet}' n'a pas été trouvé sur PyPI.\n\n"
                    "Voulez-vous quand même tenter l'installation ?", parent=dialog):
                return
        elif paquet_valide[0] is None and status_label.cget("text") == "":
            messagebox.showinfo("Vérification requise",
                "⏳ Veuillez vérifier l'existence du paquet avant d'installer.\n\n"
                "Cliquez sur 🔍 ou attendez la vérification automatique.", parent=dialog)
            verifier()
            return

        dialog.destroy()
        _lancer_action_pip(
            msg_confirm=None,
            msg_status=f"⏳ Installation de {paquet} sur Python {version}...",
            cmd_fn=lambda: installer_paquet(version, paquet),
            msg_ok=f"'{paquet}' installé sur Python {version}",
            msg_err=f"Impossible d'installer '{paquet}' sur Python {version}",
        )

    def _fermer_installer():
        if verif_timer[0]:
            dialog.after_cancel(verif_timer[0])
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", _fermer_installer)

    btn_frame = tk.Frame(dialog, bg="#f5f5f5")
    btn_frame.pack(pady=20)
    tk.Button(btn_frame, text="✓ Installer", command=valider, font=("Arial", 10),
              bg="#27ae60", fg="white", relief="flat", padx=20, pady=5,
              cursor="hand2").pack(side="left", padx=5)
    tk.Button(btn_frame, text="✗ Annuler", command=_fermer_installer, font=("Arial", 10),
              bg="#95a5a6", fg="white", relief="flat", padx=20, pady=5,
              cursor="hand2").pack(side="left", padx=5)
    entry_paquet.bind("<Return>", lambda e: valider())


# -----------------------
# DIALOGUE INFO PAQUET
# -----------------------

def afficher_info_paquet(paquet, version):
    dialog = tk.Toplevel(fenetre)
    dialog.title(f"Informations : {paquet}")
    dialog.geometry("650x550")
    dialog.configure(bg="#f5f5f5")
    dialog.transient(fenetre)
    _appliquer_icone(dialog)

    header = tk.Frame(dialog, bg="#34495e", height=70)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text=f"📦 {paquet}", font=("Arial", 16, "bold"),
             bg="#34495e", fg="white").pack(side="left", padx=20, pady=20)
    header_right = tk.Label(header, text=f"🐍 Python {version}", font=("Arial", 11),
                             bg="#34495e", fg="#bdc3c7")
    header_right.pack(side="right", padx=20)

    content_frame = tk.Frame(dialog, bg="white")
    content_frame.pack(fill="both", expand=True, padx=15, pady=15)
    canvas_info = tk.Canvas(content_frame, bg="white", highlightthickness=0)
    scrollbar_info = ttk.Scrollbar(content_frame, orient="vertical", command=canvas_info.yview)
    frame_info = tk.Frame(canvas_info, bg="white")
    frame_info.bind("<Configure>", lambda e: canvas_info.configure(
        scrollregion=canvas_info.bbox("all")))
    canvas_info.create_window((0, 0), window=frame_info, anchor="nw")
    canvas_info.configure(yscrollcommand=scrollbar_info.set)
    canvas_info.pack(side="left", fill="both", expand=True)
    scrollbar_info.pack(side="right", fill="y")

    def _fermer_info():
        dialog.destroy()
        fenetre.bind_all("<MouseWheel>", _scroll_vertical)
        fenetre.bind_all("<Shift-MouseWheel>", _scroll_horizontal)

    dialog.bind_all("<MouseWheel>", _make_scroll(canvas_info))
    dialog.protocol("WM_DELETE_WINDOW", _fermer_info)

    loading_label = tk.Label(frame_info, text="🔄 Chargement des informations...",
                              font=("Arial", 11), bg="white", fg="#7f8c8d")
    loading_label.pack(pady=50)

    def charger_info():
        cached_data = _cache_tableau.get("data", {})
        versions_python = _cache_tableau.get("versions") or detecter_versions_python()
        versions_avec_paquet = [
            (v, cached_data[v]["installes"][paquet])
            for v in versions_python
            if v in cached_data and paquet in cached_data[v].get("installes", {})
        ]
        info = obtenir_info_paquet(version, paquet)

        def afficher():
            if not dialog.winfo_exists():
                return
            loading_label.destroy()
            if len(versions_avec_paquet) > 1:
                header_right.config(
                    text=f"🔧 Installé sur {len(versions_avec_paquet)} versions Python")

            def section(bg="white"):
                f = tk.Frame(frame_info, bg=bg)
                f.pack(fill="x", pady=(0, 15), padx=5 if bg != "white" else 0)
                return f

            def titre(parent, texte, bg="white"):
                tk.Label(parent, text=texte, font=("Arial", 11, "bold"),
                         bg=bg, fg="#2c3e50").pack(anchor="w", padx=10 if bg != "white" else 0)

            def valeur(parent, texte, bg="white", mono=False):
                tk.Label(parent, text=texte,
                         font=("Consolas", 9) if mono else ("Arial", 10),
                         bg=bg, fg="#555", wraplength=550, justify="left").pack(
                             anchor="w", padx=20)

            if versions_avec_paquet:
                sf = tk.Frame(frame_info, bg="#e8f5e9", relief="solid", borderwidth=1)
                sf.pack(fill="x", pady=(0, 15), padx=5)
                titre(sf, "🔧 Versions Python :", bg="#e8f5e9")
                for v, ver_p in versions_avec_paquet:
                    rf = tk.Frame(sf, bg="#e8f5e9")
                    rf.pack(fill="x", padx=20, pady=2)
                    tk.Label(rf, text=f"• Python {v}", font=("Arial", 10, "bold"),
                             bg="#e8f5e9", fg="#27ae60").pack(side="left")
                    tk.Label(rf, text=f"→ version {ver_p}", font=("Consolas", 9),
                             bg="#e8f5e9", fg="#555").pack(side="left", padx=10)
                tk.Label(sf, text="", bg="#e8f5e9").pack(pady=5)

            for key, label in [("version", "📌 Version actuelle :"),
                                ("summary", "📄 Description :"),
                                ("author", "👤 Auteur :"),
                                ("license", "⚖️ Licence :"),
                                ("location", "📂 Emplacement :")]:
                if info[key]:
                    sf = section()
                    titre(sf, label)
                    valeur(sf, info[key], mono=(key in ("version", "location")))

            for key, label, vide in [
                ("requires", "🔗 Dépendances requises :", "Aucune dépendance"),
                ("required_by", "🔙 Utilisé par :", "Aucun paquet ne dépend de celui-ci"),
            ]:
                sf = section()
                titre(sf, label)
                if info[key]:
                    for dep in info[key].split(", "):
                        if dep.strip():
                            tk.Label(sf, text=f"  • {dep}", font=("Arial", 10),
                                     bg="white", fg="#555").pack(anchor="w", padx=20)
                else:
                    valeur(sf, vide)

            if not any(info[k] for k in info if k != "nom"):
                tk.Label(frame_info, text="❌ Aucune information disponible pour ce paquet",
                         font=("Arial", 11), bg="white", fg="#e74c3c").pack(pady=50)

        dialog.after(0, afficher)

    threading.Thread(target=charger_info, daemon=True).start()

    btn_frame = tk.Frame(dialog, bg="#f5f5f5")
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="✓ Fermer", command=_fermer_info, font=("Arial", 10),
              bg="#3498db", fg="white", relief="flat", padx=30, pady=8,
              cursor="hand2").pack()


# -----------------------
# EXPORT / IMPORT requirements.txt
# -----------------------

def exporter_requirements():
    if not _cache_tableau:
        messagebox.showwarning("Données manquantes", "Veuillez attendre le chargement des paquets.")
        return

    versions = _cache_tableau["versions"]
    data     = _cache_tableau["data"]

    dialog = tk.Toplevel(fenetre)
    dialog.title("Exporter requirements.txt")
    dialog.geometry("360x160")
    dialog.resizable(False, False)
    dialog.configure(bg="#f5f5f5")
    dialog.transient(fenetre)
    dialog.grab_set()

    tk.Label(dialog, text="🐍 Choisir la version Python à exporter :",
             font=("Arial", 11), bg="#f5f5f5").pack(pady=(20, 8))
    combo = ttk.Combobox(dialog, values=versions, state="readonly", font=("Arial", 11), width=20)
    if versions:
        combo.current(0)
    combo.pack()

    def valider():
        version = combo.get()
        paquets = data[version]["installes"]
        if not paquets:
            messagebox.showinfo("Vide", f"Aucun paquet installé sur Python {version}.", parent=dialog)
            return
        dialog.destroy()
        chemin = filedialog.asksaveasfilename(
            parent=fenetre, title="Enregistrer requirements.txt",
            defaultextension=".txt",
            initialfile=f"requirements_py{version.replace('.', '')}.txt",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")],
        )
        if not chemin:
            return
        contenu = "\n".join(f"{nom}=={ver}" for nom, ver in sorted(paquets.items()))
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(contenu + "\n")
        messagebox.showinfo("Export réussi",
            f"✅ {len(paquets)} paquets exportés pour Python {version}\n\n{chemin}")

    btn_frame = tk.Frame(dialog, bg="#f5f5f5")
    btn_frame.pack(pady=15)
    tk.Button(btn_frame, text="💾 Exporter", command=valider, font=("Arial", 10),
              bg="#27ae60", fg="white", relief="flat", padx=20, pady=5,
              cursor="hand2").pack(side="left", padx=5)
    tk.Button(btn_frame, text="✗ Annuler", command=dialog.destroy, font=("Arial", 10),
              bg="#95a5a6", fg="white", relief="flat", padx=20, pady=5,
              cursor="hand2").pack(side="left", padx=5)


def importer_requirements():
    chemin = filedialog.askopenfilename(
        title="Ouvrir un fichier requirements.txt",
        filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")],
    )
    if not chemin:
        return
    try:
        with open(chemin, encoding="utf-8") as f:
            lignes = f.readlines()
    except Exception as e:
        messagebox.showerror("Erreur", f"Impossible de lire le fichier :\n{e}")
        return

    paquets = [l.strip() for l in lignes if l.strip() and not l.startswith("#")]
    if not paquets:
        messagebox.showwarning("Fichier vide", "Aucun paquet trouvé dans ce fichier.")
        return

    versions = _cache_tableau.get("versions") or detecter_versions_python()
    dialog = tk.Toplevel(fenetre)
    dialog.title("Importer requirements.txt")
    dialog.geometry("420x200")
    dialog.resizable(False, False)
    dialog.configure(bg="#f5f5f5")
    dialog.transient(fenetre)
    dialog.grab_set()

    tk.Label(dialog, text=f"📦 {len(paquets)} paquet(s) trouvé(s) dans le fichier.",
             font=("Arial", 11), bg="#f5f5f5").pack(pady=(20, 8))
    tk.Label(dialog, text="🐍 Choisir la version Python cible :",
             font=("Arial", 11), bg="#f5f5f5").pack(pady=(0, 8))
    combo = ttk.Combobox(dialog, values=versions, state="readonly", font=("Arial", 11), width=20)
    if versions:
        combo.current(0)
    combo.pack()

    def valider():
        version = combo.get()
        if not version:
            return
        dialog.destroy()
        _desactiver_boutons()
        label_status.config(text=f"🔄 Import de {len(paquets)} paquet(s) sur Python {version}...")

        def _thread():
            echecs = []
            for i, pkg in enumerate(paquets, 1):
                fenetre.after(0, lambda p=pkg, idx=i: label_status.config(
                    text=f"📥 [{idx}/{len(paquets)}] {p}..."))
                if not installer_paquet(version, pkg):
                    echecs.append(pkg)
            def _fin():
                if echecs:
                    messagebox.showwarning(
                        "Import partiel",
                        f"{len(paquets) - len(echecs)}/{len(paquets)} paquet(s) installé(s).\n\n"
                        "Échecs :\n" + "\n".join(echecs),
                    )
                else:
                    messagebox.showinfo(
                        "Import terminé",
                        f"{len(paquets)} paquet(s) installé(s) sur Python {version}.")
                construire_tableau()
            fenetre.after(0, _fin)
        threading.Thread(target=_thread, daemon=True).start()

    btn_frame = tk.Frame(dialog, bg="#f5f5f5")
    btn_frame.pack(pady=15)
    tk.Button(btn_frame, text="📥 Importer", command=valider, font=("Arial", 10),
              bg="#2980b9", fg="white", relief="flat", padx=20, pady=5,
              cursor="hand2").pack(side="left", padx=5)
    tk.Button(btn_frame, text="✗ Annuler", command=dialog.destroy, font=("Arial", 10),
              bg="#95a5a6", fg="white", relief="flat", padx=20, pady=5,
              cursor="hand2").pack(side="left", padx=5)


# -----------------------
# AIDE
# -----------------------

def afficher_aide():
    dialog = tk.Toplevel(fenetre)
    dialog.title("Aide — Gestionnaire de paquets Python")
    dialog.geometry("700x580")
    dialog.configure(bg="#f5f5f5")
    dialog.transient(fenetre)
    dialog.grab_set()
    _appliquer_icone(dialog)

    header = tk.Frame(dialog, bg="#34495e", height=55)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text="❓ Aide", font=("Arial", 15, "bold"),
             bg="#34495e", fg="white").pack(side="left", padx=20, pady=12)

    content_frame = tk.Frame(dialog, bg="white")
    content_frame.pack(fill="both", expand=True, padx=0, pady=0)
    canvas_aide = tk.Canvas(content_frame, bg="white", highlightthickness=0)
    scrollbar_aide = ttk.Scrollbar(content_frame, orient="vertical", command=canvas_aide.yview)
    text_frame = tk.Frame(canvas_aide, bg="white")
    text_frame.bind("<Configure>", lambda e: canvas_aide.configure(
        scrollregion=canvas_aide.bbox("all")))
    canvas_aide.create_window((0, 0), window=text_frame, anchor="nw")
    canvas_aide.configure(yscrollcommand=scrollbar_aide.set)
    canvas_aide.pack(side="left", fill="both", expand=True)
    scrollbar_aide.pack(side="right", fill="y")

    def _fermer_aide():
        dialog.destroy()
        fenetre.bind_all("<MouseWheel>", _scroll_vertical)
        fenetre.bind_all("<Shift-MouseWheel>", _scroll_horizontal)

    dialog.bind_all("<MouseWheel>", _make_scroll(canvas_aide))
    dialog.protocol("WM_DELETE_WINDOW", _fermer_aide)

    try:
        with open(resource_path("aide.md"), encoding="utf-8") as f:
            contenu = f.read()
    except Exception:
        contenu = "❌ Fichier aide.md introuvable."

    for ligne in contenu.splitlines():
        if ligne.startswith("# "):
            tk.Label(text_frame, text=ligne[2:], font=("Arial", 14, "bold"),
                     bg="white", fg="#2c3e50", anchor="w").pack(fill="x", padx=20, pady=(15, 4))
        elif ligne.startswith("## "):
            tk.Label(text_frame, text=ligne[3:], font=("Arial", 11, "bold"),
                     bg="#eaf2ff", fg="#2980b9", anchor="w").pack(fill="x", padx=10, pady=(10, 2))
        elif ligne.startswith("---"):
            tk.Frame(text_frame, bg="#dfe6e9", height=1).pack(fill="x", padx=20, pady=4)
        elif ligne.startswith("| "):
            tk.Label(text_frame, text=ligne, font=("Consolas", 9),
                     bg="white", fg="#555", anchor="w").pack(fill="x", padx=30)
        elif ligne.startswith("```"):
            pass
        else:
            tk.Label(text_frame, text=ligne if ligne else " ",
                     font=("Arial", 10), bg="white", fg="#2d3436",
                     anchor="w", wraplength=620, justify="left").pack(fill="x", padx=20)

    btn_frame = tk.Frame(dialog, bg="#f5f5f5")
    btn_frame.pack(pady=8)
    tk.Button(btn_frame, text="✓ Fermer", command=_fermer_aide, font=("Arial", 10),
              bg="#3498db", fg="white", relief="flat", padx=30, pady=7,
              cursor="hand2").pack()


# -----------------------
# INTERFACE GRAPHIQUE
# -----------------------
fenetre = tk.Tk()
fenetre.title("Gestionnaire de paquets Python")
fenetre.geometry("1500x800")
fenetre.configure(bg="#f5f5f5")

fenetre._icon_path = None
fenetre._icon_photo = None
try:
    _ico = resource_path("app_icon.ico")
    fenetre.iconbitmap(_ico)
    fenetre._icon_path = _ico
except Exception:
    try:
        from PIL import Image, ImageTk
        _png = resource_path("app_icon.png")
        icon_image = Image.open(_png)
        fenetre._icon_photo = ImageTk.PhotoImage(icon_image)
        fenetre.iconphoto(True, fenetre._icon_photo)
        fenetre._icon_path = _png
    except Exception:
        pass

# En-tête
header_frame = tk.Frame(fenetre, bg="#2c3e50", height=80)
header_frame.pack(fill="x")
header_frame.pack_propagate(False)

header_inner = tk.Frame(header_frame, bg="#2c3e50")
header_inner.pack(fill="both", expand=True, padx=20, pady=10)

tk.Label(header_inner, text="🐍 Gestionnaire de paquets Python",
         font=("Arial", 18, "bold"), bg="#2c3e50", fg="white").pack(side="left", anchor="w")

label_version_python = tk.Label(
    header_inner,
    text="⏳ Vérification de la dernière version Python...",
    font=("Arial", 10), bg="#2c3e50", fg="#bdc3c7",
    anchor="e", justify="right", wraplength=400,
)
label_version_python.pack(side="right", anchor="e", padx=10)

btn_telecharger_python = tk.Button(
    header_inner, text="⬇️ Télécharger",
    font=("Arial", 9), bg="#e67e22", fg="white",
    relief="flat", padx=10, pady=4, cursor="hand2",
)
btn_telecharger_python.pack_forget()

# Barre d'outils
toolbar = tk.Frame(fenetre, bg="#ecf0f1", height=60)
toolbar.pack(fill="x")
toolbar.pack_propagate(False)

btn_refresh = tk.Button(
    toolbar, text="🔄 Rafraîchir",
    command=construire_tableau,
    font=("Arial", 10), bg="#3498db", fg="white",
    relief="flat", padx=20, pady=8, cursor="hand2",
)
btn_refresh.pack(side="left", padx=10, pady=10)

btn_maj = tk.Button(
    toolbar, text="⬆️ Mettre à jour la sélection",
    command=lancer_mise_a_jour,
    font=("Arial", 10), bg="#27ae60", fg="white",
    relief="flat", padx=20, pady=8, cursor="hand2", state="disabled",
)
btn_maj.pack(side="left", padx=5, pady=10)

btn_installer = tk.Button(
    toolbar, text="➕ Installer un paquet",
    command=installer_nouveau_paquet,
    font=("Arial", 10), bg="#9b59b6", fg="white",
    relief="flat", padx=20, pady=8, cursor="hand2", state="disabled",
)
btn_installer.pack(side="left", padx=5, pady=10)

btn_export = tk.Button(
    toolbar, text="💾 Exporter requirements.txt",
    command=exporter_requirements,
    font=("Arial", 10), bg="#16a085", fg="white",
    relief="flat", padx=20, pady=8, cursor="hand2", state="disabled",
)
btn_export.pack(side="left", padx=5, pady=10)

btn_import = tk.Button(
    toolbar, text="📥 Importer requirements.txt",
    command=importer_requirements,
    font=("Arial", 10), bg="#2980b9", fg="white",
    relief="flat", padx=20, pady=8, cursor="hand2",
)
btn_import.pack(side="left", padx=5, pady=10)

btn_aide = tk.Button(
    toolbar, text="❓ Aide",
    command=afficher_aide,
    font=("Arial", 10), bg="#7f8c8d", fg="white",
    relief="flat", padx=20, pady=8, cursor="hand2",
)
btn_aide.pack(side="left", padx=5, pady=10)

label_status = tk.Label(toolbar, text="", font=("Arial", 10), bg="#ecf0f1", fg="#555")
label_status.pack(side="left", padx=20)

# Barre de recherche
search_bar = tk.Frame(fenetre, bg="#dfe6e9", height=36)
search_bar.pack(fill="x")
search_bar.pack_propagate(False)

tk.Label(search_bar, text="🔍", font=("Arial", 11),
         bg="#dfe6e9").pack(side="left", padx=(10, 2), pady=5)

entry_recherche = tk.Entry(search_bar, font=("Arial", 10), width=30, relief="flat",
                           bg="white", fg="#2d3436")
entry_recherche.pack(side="left", pady=5, ipady=3)


def _effacer_recherche():
    entry_recherche.delete(0, "end")
    filtrer_tableau("")
    entry_recherche.focus()


btn_clear_search = tk.Button(
    search_bar, text="✕", font=("Arial", 9, "bold"),
    bg="#dfe6e9", fg="#b2bec3", relief="flat", cursor="hand2",
    bd=0, padx=4, command=_effacer_recherche,
)
btn_clear_search.pack(side="left", padx=(2, 10))

tk.Label(search_bar, text="Tapez pour filtrer les paquets",
         font=("Arial", 9, "italic"), bg="#dfe6e9", fg="#636e72").pack(side="right", padx=15)

_timer_recherche = [None]


def _on_recherche(event=None):
    if _timer_recherche[0]:
        fenetre.after_cancel(_timer_recherche[0])
    _timer_recherche[0] = fenetre.after(200, lambda: filtrer_tableau(entry_recherche.get()))
    btn_clear_search.config(fg="#636e72" if entry_recherche.get() else "#b2bec3")


entry_recherche.bind("<KeyRelease>", _on_recherche)

# Zone principale
container = tk.Frame(fenetre, bg="white")
container.pack(fill="both", expand=True, padx=10, pady=10)
container.grid_rowconfigure(0, weight=1)
container.grid_columnconfigure(0, weight=1)

# Style Treeview
style = ttk.Style()
style.theme_use("clam")
style.configure("Pkg.Treeview",
                font=("Arial", 10), rowheight=28, foreground="#2d3436")
style.configure("Pkg.Treeview.Heading",
                font=("Arial", 10, "bold"), background="#dfe6e9",
                foreground="#2d3436", relief="flat")
style.map("Pkg.Treeview",
          background=[("selected", "#74b9ff")],
          foreground=[("selected", "white")])

tree = ttk.Treeview(container, style="Pkg.Treeview", show="headings", selectmode="extended")
scrollbar_y = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scrollbar_y.set)

tree.grid(row=0, column=0, sticky="nsew")
scrollbar_y.grid(row=0, column=1, sticky="ns")

tree.tag_configure("odd",  background="white")
tree.tag_configure("even", background="#f0f3f4")


def _scroll_vertical(event):
    if event.widget.winfo_toplevel() is fenetre:
        tree.yview_scroll(int(-1 * (event.delta / 120)), "units")


def _scroll_horizontal(event):
    if event.widget.winfo_toplevel() is fenetre:
        tree.xview_scroll(int(-1 * (event.delta / 120)), "units")


fenetre.bind_all("<MouseWheel>", _scroll_vertical)
fenetre.bind_all("<Shift-MouseWheel>", _scroll_horizontal)


def _on_double_click(event):
    iid = tree.identify_row(event.y)
    col = tree.identify_column(event.x)
    if not iid or col != "#1":
        return
    _ouvrir_info_premier_v(iid)


tree.bind("<Double-Button-1>", _on_double_click)


def _on_ctrl_a(event=None):
    items = tree.get_children()
    if items:
        tree.selection_set(items)
    return "break"


tree.bind("<Control-a>", _on_ctrl_a)
tree.bind("<Control-A>", _on_ctrl_a)


def _on_rightclick(event):
    iid = tree.identify_row(event.y)
    col = tree.identify_column(event.x)
    if not iid:
        return
    tree.selection_set(iid)
    pkg     = iid
    col_idx = int(col.lstrip("#")) - 2
    versions = _cache_tableau.get("versions", [])
    data     = _cache_tableau.get("data", {})
    version  = versions[col_idx] if 0 <= col_idx < len(versions) else None

    menu = tk.Menu(fenetre, tearoff=0)
    if version and pkg in data.get(version, {}).get("installes", {}):
        menu.add_command(label=f"ℹ️  Infos sur {pkg}",
                         command=lambda: afficher_info_paquet(pkg, version))
        menu.add_command(label=f"🗑️  Désinstaller de Python {version}",
                         command=lambda: supprimer_paquet(pkg, version))
        menu.add_separator()

    versions_obsoletes = [v for v in versions if pkg in data.get(v, {}).get("obsoletes", {})]
    if versions_obsoletes:
        for v in versions_obsoletes:
            current, latest = data[v]["obsoletes"][pkg]
            menu.add_command(
                label=f"⬆️  Mettre à jour sur Python {v}  ({current} → {latest})",
                command=lambda ver=v: _maj_un_paquet(pkg, ver),
            )
        menu.add_separator()

    for v in versions:
        if pkg not in data.get(v, {}).get("installes", {}):
            menu.add_command(label=f"➕  Installer sur Python {v}",
                             command=lambda ver=v: installer_paquet_sur_autre_version(pkg, ver))
    try:
        if menu.index("end") >= 0:
            menu.tk_popup(event.x_root, event.y_root)
    except tk.TclError:
        pass


tree.bind("<Button-3>", _on_rightclick)


def _on_enter_tree(event=None):
    selected = tree.selection()
    if not selected:
        return
    _ouvrir_info_premier_v(selected[0])
    return "break"


tree.bind("<Return>", _on_enter_tree)

fenetre.bind("<F5>", lambda e: construire_tableau())
fenetre.bind("<Escape>", lambda e: _effacer_recherche())


# -----------------------
# DÉMARRAGE
# -----------------------
footer = tk.Frame(fenetre, bg="#2c3e50", height=28)
footer.pack(fill="x", side="bottom")
footer.pack_propagate(False)
tk.Label(footer,
         text="💡 Clic droit pour les options et le détail sur un paquet",
         font=("Arial", 9, "italic"), bg="#2c3e50", fg="#95a5a6").pack(side="left", padx=15)

construire_tableau()
fenetre.after(2000, afficher_derniere_version_stable)

fenetre.mainloop()
