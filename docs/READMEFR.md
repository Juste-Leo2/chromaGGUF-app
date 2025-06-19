# 🎨 Chroma-app-gguf

<div align="left">
  <a href="../README.md" target="_blank">
    <img src="https://img.shields.io/badge/🇬🇧-English%20Version-536af5?style=flat-square&labelColor=333" alt="English Version" />
  </a>
</div>

> Une application simple et autonome pour générer des images avec le modèle Chroma en utilisant des fichiers GGUF.

<p align="center">
  <img src="image.png" alt="Capture d'écran de l'application Chroma" width="700"/>
</p>

## ✅ Prérequis

Pour utiliser cette application, votre configuration doit respecter les points suivants :

- **GPU :** Carte graphique NVIDIA avec au moins **6 Go de VRAM**.
- **RAM :** **16 Go** de mémoire vive.
- **OS :** Windows 10 ou 11.

## 🛠️ Installation (Première utilisation uniquement)

1.  Double-cliquez sur le fichier `setup.bat`.
2.  Une fenêtre de commande s'ouvrira. **L'installation est entièrement automatique** et peut prendre environ 30 minutes. Le script va s'occuper de :
    -   📥 Télécharger et installer une version portable de Miniconda.
    -   📦 Créer un environnement Python isolé pour garantir la propreté de votre système.
    -   ⚙️ Installer toutes les librairies nécessaires (PyTorch, etc.).
    -   🧠 Télécharger les 3 modèles GGUF requis directement dans le dossier `models/`.
3.  Une fois l'installation terminée, la fenêtre vous invitera à appuyer sur une touche pour se fermer.

## 🚀 Lancement de l'application

Pour démarrer l'application, double-cliquez simplement sur `run.bat`.

## ❤️ Remerciements et Crédits

Ce projet n'aurait pas été possible sans le travail formidable des communautés open source suivantes :

-   **ComfyUI Team** ([`github`](https://github.com/comfyanonymous/ComfyUI)) pour le code de base qui a servi d'inspiration.
-   **Développeurs de ComfyUI-GGUF** ([`github`](https://github.com/city96/ComfyUI-GGUF)) pour les nœuds d'inférence GGUF.
-   **Créateurs de Chroma** ([`huggingface`](https://huggingface.co/lodestones/Chroma)) pour ce modèle de génération d'image open source.
-   **silveroxides** ([`huggingface`](https://huggingface.co/silveroxides/Chroma-GGUF)) pour la quantification des modèles au format GGUF.

## 🗺️ Feuille de route (Améliorations prévues)

-   [ ] Ajouter un sélecteur de langue pour l'interface.
-   [ ] Prendre en charge les prompts multilingues.